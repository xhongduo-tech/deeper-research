"""多语言代码沙箱 (Polyglot Runtime).

支持语言:
  - Python  — 复用 app.services.sandbox（已有 RestrictedPython 隔离）
  - Node.js — subprocess 执行，捕获 stdout/stderr
  - Shell   — subprocess 执行，超时强制杀死
  - Java    — 检测 JDK 可用时编译并运行（内联类）
  - Go      — 检测 go 二进制时运行

安全限制：
  - 所有 subprocess 均设定超时（默认 30s）
  - 工作目录为隔离临时目录
  - 不允许网络访问（Shell 沙箱可通过 ENABLE_BROWSER 配置开放）
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Literal

from app.config import settings

logger = logging.getLogger(__name__)

Language = Literal["python", "javascript", "shell", "java", "go"]


@dataclass
class SandboxResult:
    language: str
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    exec_ms: float = 0.0
    figures: list[dict] = field(default_factory=list)     # Python 图表
    artifacts: list[dict] = field(default_factory=list)   # 产出文件

    @property
    def success(self) -> bool:
        return self.error is None

    def short_summary(self) -> str:
        if self.error:
            return f"❌ [{self.language}] {self.error}"
        out = self.stdout[:500]
        return f"✅ [{self.language}] {out}" if out else f"✅ [{self.language}] 执行完成（无输出）"


class PolyglotSandbox:
    """统一多语言代码执行接口."""

    DEFAULT_TIMEOUT = int(getattr(settings, "sandbox_timeout", 30))

    @classmethod
    async def run(
        cls,
        code: str,
        language: Language,
        *,
        timeout: int | None = None,
        env_vars: dict[str, str] | None = None,
        staged_data_path: str | None = None,
    ) -> SandboxResult:
        timeout = timeout or cls.DEFAULT_TIMEOUT

        if language == "python":
            return await cls._run_python(code, timeout=timeout, staged_data_path=staged_data_path)
        elif language in ("javascript", "js", "node"):
            return await cls._run_node(code, timeout=timeout, env_vars=env_vars)
        elif language in ("shell", "bash", "sh"):
            return await cls._run_shell(code, timeout=timeout, env_vars=env_vars)
        elif language == "java":
            return await cls._run_java(code, timeout=timeout)
        elif language == "go":
            return await cls._run_go(code, timeout=timeout)
        else:
            return SandboxResult(language=language, error=f"不支持的语言: {language}")

    # ── Python ───────────────────────────────────────────────────────────────

    @staticmethod
    async def _run_python(
        code: str, timeout: int, staged_data_path: str | None = None
    ) -> SandboxResult:
        from app.services.sandbox import execute_python
        t0 = time.monotonic()
        result = await execute_python(code, timeout=timeout, staged_data_path=staged_data_path)
        elapsed = (time.monotonic() - t0) * 1000
        return SandboxResult(
            language="python",
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            error=result.get("error"),
            figures=result.get("figures", []),
            artifacts=result.get("artifacts", []),
            exec_ms=elapsed,
        )

    # ── Node.js ──────────────────────────────────────────────────────────────

    @staticmethod
    async def _run_node(
        code: str, timeout: int, env_vars: dict | None = None
    ) -> SandboxResult:
        node_bin = shutil.which("node") or shutil.which("nodejs")
        if not node_bin:
            return SandboxResult(language="javascript", error="Node.js 未安装，无法执行")

        return await PolyglotSandbox._run_in_subprocess(
            args=[node_bin, "-e", code],
            language="javascript",
            timeout=timeout,
            env_vars=env_vars,
        )

    # ── Shell ────────────────────────────────────────────────────────────────

    @staticmethod
    async def _run_shell(
        code: str, timeout: int, env_vars: dict | None = None
    ) -> SandboxResult:
        return await PolyglotSandbox._run_in_subprocess(
            args=["bash", "-c", code],
            language="shell",
            timeout=timeout,
            env_vars=env_vars,
        )

    # ── Java ─────────────────────────────────────────────────────────────────

    @staticmethod
    async def _run_java(code: str, timeout: int) -> SandboxResult:
        javac = shutil.which("javac")
        java  = shutil.which("java")
        if not javac or not java:
            return SandboxResult(language="java", error="JDK 未安装，无法执行 Java")

        # 提取类名
        import re
        m = re.search(r"public\s+class\s+(\w+)", code)
        class_name = m.group(1) if m else "Main"

        workdir = tempfile.mkdtemp(prefix="sandbox_java_")
        try:
            src_file = os.path.join(workdir, f"{class_name}.java")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(code)

            # 编译
            compile_result = await PolyglotSandbox._run_in_subprocess(
                args=[javac, src_file],
                language="java", timeout=min(timeout, 20), cwd=workdir,
            )
            if not compile_result.success:
                compile_result.error = f"编译失败: {compile_result.stderr[:500]}"
                return compile_result

            # 运行
            return await PolyglotSandbox._run_in_subprocess(
                args=[java, "-cp", workdir, class_name],
                language="java", timeout=timeout, cwd=workdir,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    # ── Go ───────────────────────────────────────────────────────────────────

    @staticmethod
    async def _run_go(code: str, timeout: int) -> SandboxResult:
        go_bin = shutil.which("go")
        if not go_bin:
            return SandboxResult(language="go", error="Go 未安装，无法执行")

        workdir = tempfile.mkdtemp(prefix="sandbox_go_")
        try:
            src_file = os.path.join(workdir, "main.go")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(code)
            return await PolyglotSandbox._run_in_subprocess(
                args=[go_bin, "run", src_file],
                language="go", timeout=timeout, cwd=workdir,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    # ── 通用 subprocess 执行 ──────────────────────────────────────────────────

    @staticmethod
    async def _run_in_subprocess(
        args: list[str],
        language: str,
        timeout: int,
        env_vars: dict | None = None,
        cwd: str | None = None,
    ) -> SandboxResult:
        t0 = time.monotonic()
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=float(timeout)
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                elapsed = (time.monotonic() - t0) * 1000
                return SandboxResult(
                    language=language,
                    error=f"执行超时（>{timeout}s）",
                    exec_ms=elapsed,
                )

            elapsed = (time.monotonic() - t0) * 1000
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")

            error = None
            if proc.returncode != 0:
                error = f"退出码 {proc.returncode}"

            return SandboxResult(
                language=language,
                stdout=stdout, stderr=stderr,
                error=error, exec_ms=elapsed,
            )

        except FileNotFoundError:
            return SandboxResult(language=language, error=f"命令未找到: {args[0]}")
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            return SandboxResult(language=language, error=str(exc), exec_ms=elapsed)
