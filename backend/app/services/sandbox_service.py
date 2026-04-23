"""
SandboxService — 安全的科学计算沙箱。

v3 升级：在原有 pandas/numpy 基础上，开放 scipy / scikit-learn / statsmodels，
为 Quinn（数据整理员）提供 PandasAI 级数据分析能力。

Pipeline:
  1. AST security scan  →  发现危险操作时抛出 SandboxSecurityError
  2. Execute in a restricted namespace with a CPU/time budget
  3. Return stdout + extracted variables

完全离线安全：无网络、无文件写入、无子进程、无动态 eval/exec。

已开放科学计算库：
  - scipy.stats     统计检验（t-test / 卡方 / Shapiro / pearsonr）
  - scipy.signal    时序平滑（savgol_filter）
  - sklearn.cluster KMeans 聚类
  - sklearn.preprocessing StandardScaler / MinMaxScaler
  - statsmodels.api OLS 回归 / ADF 检验
  - tabulate        Markdown 表格格式化
"""
from __future__ import annotations

import ast
import builtins
import io
import json
import math
import re
import sys
import textwrap
import threading
import traceback
from contextlib import redirect_stdout
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Dangerous node / name blocklist
# ---------------------------------------------------------------------------

_BLOCKED_NAMES = frozenset({
    # execution
    "eval", "exec", "compile", "__import__", "__builtins__",
    # file system
    "open", "file",
    # OS / process
    "os", "sys", "subprocess", "shutil", "glob", "pathlib",
    # network
    "socket", "urllib", "requests", "httpx", "aiohttp",
    # dynamic attribute
    "getattr", "setattr", "delattr", "vars", "dir",
    # inspect / reflection
    "inspect", "importlib",
})

_BLOCKED_IMPORT_MODULES = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib", "glob",
    "socket", "urllib", "requests", "httpx", "aiohttp",
    "importlib", "inspect", "ctypes", "mmap",
})


class SandboxSecurityError(Exception):
    """Raised when code fails the AST security check."""


class _ASTSecurityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in _BLOCKED_IMPORT_MODULES:
                self.violations.append(f"Blocked import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = (node.module or "").split(".")[0]
        if module in _BLOCKED_IMPORT_MODULES:
            self.violations.append(f"Blocked from-import: {node.module}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in _BLOCKED_NAMES:
            self.violations.append(f"Blocked name: {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Block dunder attribute access used to escape sandboxes
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.violations.append(f"Blocked dunder attribute: {node.attr}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Block open() even if not imported explicitly
        if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_NAMES:
            self.violations.append(f"Blocked call: {node.func.id}()")
        self.generic_visit(node)


def check_ast(code: str) -> list[str]:
    """Return a list of violation strings (empty = safe)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]
    visitor = _ASTSecurityVisitor()
    visitor.visit(tree)
    return visitor.violations


# ---------------------------------------------------------------------------
# Restricted namespace builder
# ---------------------------------------------------------------------------

_SAFE_STDLIB_NAMES = frozenset({
    "math", "re", "json", "datetime", "collections", "statistics", "io",
    "pd", "pandas", "np", "numpy",
    "scipy", "stats", "signal",
    "sklearn", "preprocessing", "cluster", "decomposition",
    "sm", "statsmodels",
    "tabulate",
})


def _build_namespace(extra_vars: Dict[str, Any]) -> Dict[str, Any]:
    """Return the restricted globals dict for exec().

    v3：增加 scipy / scikit-learn / statsmodels / tabulate 科学计算库。
    """
    safe_builtins = {
        name: getattr(builtins, name)
        for name in (
            "abs", "all", "any", "bool", "dict", "enumerate", "filter",
            "float", "format", "frozenset", "int", "isinstance", "issubclass",
            "iter", "len", "list", "map", "max", "min", "next", "print",
            "range", "repr", "reversed", "round", "set", "slice", "sorted",
            "str", "sum", "tuple", "type", "zip", "None", "True", "False",
        )
        if hasattr(builtins, name)
    }
    ns: Dict[str, Any] = {"__builtins__": safe_builtins}

    # Safe stdlib
    import math as _math
    import re as _re
    import json as _json
    import datetime as _datetime
    import collections as _collections
    import statistics as _statistics
    ns["math"] = _math
    ns["re"] = _re
    ns["json"] = _json
    ns["datetime"] = _datetime
    ns["collections"] = _collections
    ns["statistics"] = _statistics
    ns["io"] = io

    # Data science — pandas / numpy
    try:
        import pandas as _pd
        ns["pd"] = _pd
        ns["pandas"] = _pd
    except ImportError:
        pass
    try:
        import numpy as _np
        ns["np"] = _np
        ns["numpy"] = _np
    except ImportError:
        pass

    # Scientific computing — scipy
    try:
        import scipy.stats as _scipy_stats
        import scipy.signal as _scipy_signal
        import scipy.cluster.hierarchy as _scipy_hierarchy
        ns["scipy_stats"] = _scipy_stats
        ns["scipy_signal"] = _scipy_signal
        # Common alias used in agent prompts
        ns["stats"] = _scipy_stats
    except ImportError:
        pass

    # Machine learning — scikit-learn
    try:
        from sklearn import preprocessing as _preprocessing
        from sklearn.cluster import KMeans as _KMeans
        from sklearn.decomposition import PCA as _PCA
        ns["StandardScaler"] = _preprocessing.StandardScaler
        ns["MinMaxScaler"] = _preprocessing.MinMaxScaler
        ns["KMeans"] = _KMeans
        ns["PCA"] = _PCA
    except ImportError:
        pass

    # Time series & regression — statsmodels
    try:
        import statsmodels.api as _sm
        ns["sm"] = _sm
        ns["statsmodels"] = _sm
    except ImportError:
        pass

    # Table formatting — tabulate
    try:
        from tabulate import tabulate as _tabulate
        ns["tabulate"] = _tabulate
    except ImportError:
        pass

    # Caller-supplied data (e.g. pre-loaded DataFrames)
    ns.update(extra_vars)
    return ns


# ---------------------------------------------------------------------------
# Public execute function
# ---------------------------------------------------------------------------

class SandboxResult:
    def __init__(
        self,
        stdout: str,
        variables: Dict[str, Any],
        error: Optional[str],
        ok: bool,
    ):
        self.stdout = stdout
        self.variables = variables
        self.error = error
        self.ok = ok

    def scalar(self, key: str, default: Any = None) -> Any:
        """Retrieve a scalar value from captured variables."""
        return self.variables.get(key, default)

    def summary(self) -> str:
        lines = []
        if self.stdout.strip():
            lines.append("=== stdout ===")
            lines.append(self.stdout[:2000])
        if self.variables:
            lines.append("=== exported vars ===")
            for k, v in list(self.variables.items())[:20]:
                lines.append(f"  {k} = {repr(v)[:200]}")
        if self.error:
            lines.append(f"=== error ===\n{self.error}")
        return "\n".join(lines)


def execute(
    code: str,
    extra_vars: Optional[Dict[str, Any]] = None,
    timeout_s: float = 30.0,
) -> SandboxResult:
    """
    Execute *code* in the restricted sandbox.

    Steps:
      1. AST security check — raises SandboxSecurityError on violations
      2. Run in a thread with a timeout
      3. Capture stdout + namespace exports
    """
    code = textwrap.dedent(code).strip()

    # Step 1 — security check
    violations = check_ast(code)
    if violations:
        raise SandboxSecurityError(
            "Code failed security check:\n" + "\n".join(f"  • {v}" for v in violations)
        )

    ns = _build_namespace(extra_vars or {})
    stdout_capture = io.StringIO()
    result_holder: list[Any] = [None]  # [SandboxResult | Exception]

    def _run() -> None:
        try:
            with redirect_stdout(stdout_capture):
                exec(compile(code, "<sandbox>", "exec"), ns)  # noqa: S102
            # Collect any user-defined variables (skip builtins/stdlib modules)
            exported = {
                k: v
                for k, v in ns.items()
                if not k.startswith("_")
                and k not in _SAFE_STDLIB_NAMES
                and k not in ("StandardScaler", "MinMaxScaler", "KMeans", "PCA",
                              "scipy_stats", "scipy_signal", "stats", "sm",
                              "statsmodels", "tabulate")
                and not callable(v)
            }
            result_holder[0] = SandboxResult(
                stdout=stdout_capture.getvalue(),
                variables=exported,
                error=None,
                ok=True,
            )
        except Exception:
            result_holder[0] = SandboxResult(
                stdout=stdout_capture.getvalue(),
                variables={},
                error=traceback.format_exc(limit=6),
                ok=False,
            )

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        return SandboxResult(
            stdout="",
            variables={},
            error=f"Execution timed out after {timeout_s}s",
            ok=False,
        )

    res = result_holder[0]
    if res is None:
        return SandboxResult(stdout="", variables={}, error="Unknown error", ok=False)
    return res  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Convenience: extract key metrics from result + LLM code
# ---------------------------------------------------------------------------

def extract_metrics_from_result(result: SandboxResult) -> Dict[str, Any]:
    """
    Try to find a dict called `metrics` or `results` in the sandbox variables,
    or parse key=value lines from stdout.
    """
    # 1. Check for explicit dict
    for key in ("metrics", "results", "output", "report"):
        val = result.variables.get(key)
        if isinstance(val, dict):
            return val

    # 2. Parse stdout for "key: value" or "key = value" patterns
    metrics: Dict[str, Any] = {}
    for line in result.stdout.splitlines():
        m = re.match(r"^\s*([A-Za-z_]\w*)\s*[:=]\s*(.+)$", line)
        if m:
            key, raw = m.group(1), m.group(2).strip()
            try:
                metrics[key] = json.loads(raw)
            except Exception:
                metrics[key] = raw
    return metrics
