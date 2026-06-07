"""Code AST/静态分析解析器.

对 Python 使用内置 ast 模块精确提取；
对 Java/JS/TS/Go/Shell/C 使用正则提取函数签名与注释。
输出标准化 CodeAsset，供 LLM 按需下钻读取。
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    name: str
    signature: str
    docstring: str
    start_line: int
    end_line: int


@dataclass
class ClassInfo:
    name: str
    bases: list[str]
    methods: list[FunctionInfo]
    docstring: str
    start_line: int


@dataclass
class CodeAsset:
    """标准化代码静态分析结果."""
    language: str
    path: str
    size_bytes: int
    imports: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    top_level_comments: str = ""
    raw_snippet: str = ""  # 前 100 行原始代码（LLM 快速理解）

    def to_context_text(self) -> str:
        """序列化为 LLM 可读的结构化文本."""
        lines = [f"## [{self.language}] {self.path}"]
        if self.top_level_comments:
            lines.append(f"注释/文档: {self.top_level_comments[:300]}")
        if self.imports:
            lines.append(f"依赖: {', '.join(self.imports[:20])}")
        for cls in self.classes:
            method_names = [m.name for m in cls.methods]
            lines.append(f"类 {cls.name}({', '.join(cls.bases)}): 方法=[{', '.join(method_names)}]")
        for fn in self.functions[:30]:
            lines.append(f"函数 {fn.signature} (line {fn.start_line})")
        if self.raw_snippet:
            lines.append(f"\n```{self.language}\n{self.raw_snippet}\n```")
        return "\n".join(lines)


# ── Language dispatch ──────────────────────────────────────────────────────

_EXT_LANG = {
    ".py": "python", ".pyw": "python",
    ".java": "java",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".rs": "rust",
    ".kt": "kotlin",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".scala": "scala",
    ".r": "r", ".R": "r",
    ".sql": "sql",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".less": "css",
    ".xml": "xml",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
}


class CodeParser:
    """多语言静态代码解析器."""

    @classmethod
    def parse(cls, path: str, content: bytes) -> CodeAsset | None:
        from pathlib import PurePosixPath
        suffix = PurePosixPath(path).suffix.lower()
        lang = _EXT_LANG.get(suffix)
        if not lang:
            return None

        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = ""

        raw_snippet = "\n".join(text.splitlines()[:100])
        asset = CodeAsset(language=lang, path=path, size_bytes=len(content), raw_snippet=raw_snippet)

        if lang == "python":
            cls._parse_python(text, asset)
        else:
            cls._parse_generic(text, lang, asset)

        return asset

    # ── Python (精确 AST) ───────────────────────────────────────────────

    @classmethod
    def _parse_python(cls, text: str, asset: CodeAsset) -> None:
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            logger.debug("Python AST parse error in %s: %s", asset.path, e)
            cls._parse_generic(text, "python", asset)
            return

        # Top-level docstring
        if (tree.body and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)):
            asset.top_level_comments = str(tree.body[0].value.value)[:500]

        # Imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                asset.imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                asset.imports.extend(f"{mod}.{a.name}" for a in node.names)

        # Classes and functions at module level
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_info = cls._extract_python_class(node)
                asset.classes.append(cls_info)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_info = cls._extract_python_function(node)
                asset.functions.append(fn_info)

    @staticmethod
    def _extract_python_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
        # Build signature
        args = []
        for arg in node.args.args:
            ann = ""
            if arg.annotation:
                try:
                    ann = f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            args.append(f"{arg.arg}{ann}")
        ret = ""
        if node.returns:
            try:
                ret = f" -> {ast.unparse(node.returns)}"
            except Exception:
                pass
        sig = f"{'async ' if isinstance(node, ast.AsyncFunctionDef) else ''}def {node.name}({', '.join(args)}){ret}"

        docstring = ""
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)):
            docstring = str(node.body[0].value.value)[:200]

        end_line = getattr(node, "end_lineno", node.lineno)
        return FunctionInfo(
            name=node.name, signature=sig, docstring=docstring,
            start_line=node.lineno, end_line=end_line,
        )

    @classmethod
    def _extract_python_class(cls, node: ast.ClassDef) -> ClassInfo:
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                pass

        docstring = ""
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)):
            docstring = str(node.body[0].value.value)[:200]

        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(cls._extract_python_function(item))

        return ClassInfo(
            name=node.name, bases=bases, methods=methods,
            docstring=docstring, start_line=node.lineno,
        )

    # ── Generic (正则) ────────────────────────────────────────────────────

    _IMPORT_PATTERNS = {
        "java": re.compile(r"^import\s+([\w.]+);", re.MULTILINE),
        "javascript": re.compile(r"""(?:^import\s+.+?\s+from\s+['"](.+?)['"]|^const\s+\w+\s*=\s*require\(['"](.+?)['"]\))""", re.MULTILINE),
        "typescript": re.compile(r"""^import\s+.+?\s+from\s+['"](.+?)['"]""", re.MULTILINE),
        "go": re.compile(r'"([\w./]+)"', re.MULTILINE),
    }

    _FUNC_PATTERNS = {
        "java": re.compile(r"(?:public|private|protected|static|final|abstract|\s)+[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{", re.MULTILINE),
        "javascript": re.compile(r"(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?([^)]*)\)?\s*=>", re.MULTILINE),
        "typescript": re.compile(r"(?:async\s+)?(?:function\s+)?(\w+)\s*\(([^)]*)\)(?:\s*:\s*[\w<>\[\]|&]+)?\s*\{", re.MULTILINE),
        "go": re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(([^)]*)\)", re.MULTILINE),
        "shell": re.compile(r"^(\w+)\s*\(\s*\)\s*\{", re.MULTILINE),
        "c": re.compile(r"^[\w\s\*]+\s+(\w+)\s*\([^)]*\)\s*\{", re.MULTILINE),
        "cpp": re.compile(r"^[\w\s\*:<>]+\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?\{", re.MULTILINE),
        "rust": re.compile(r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)", re.MULTILINE),
    }

    _CLASS_PATTERNS = {
        "java": re.compile(r"(?:public|private|abstract|final|\s)*class\s+(\w+)(?:\s+extends\s+([\w.]+))?", re.MULTILINE),
        "javascript": re.compile(r"class\s+(\w+)(?:\s+extends\s+(\w+))?", re.MULTILINE),
        "typescript": re.compile(r"class\s+(\w+)(?:\s+extends\s+(\w+))?", re.MULTILINE),
    }

    @classmethod
    def _parse_generic(cls, text: str, lang: str, asset: CodeAsset) -> None:
        # Comments / docstrings
        comment_match = re.match(r"(/\*\*?[\s\S]*?\*/|#!.*?\n|(?:#[^\n]*\n)+)", text)
        if comment_match:
            asset.top_level_comments = comment_match.group(0)[:400]

        # Imports
        pattern = cls._IMPORT_PATTERNS.get(lang)
        if pattern:
            asset.imports = [m.group(1) or m.group(2) or "" for m in pattern.finditer(text) if m][:30]

        # Functions
        fn_pattern = cls._FUNC_PATTERNS.get(lang)
        if fn_pattern:
            for m in fn_pattern.finditer(text):
                name = m.group(1) or m.group(3) or ""
                if not name:
                    continue
                line_no = text[:m.start()].count("\n") + 1
                asset.functions.append(FunctionInfo(
                    name=name, signature=m.group(0)[:120],
                    docstring="", start_line=line_no, end_line=line_no,
                ))

        # Classes
        cls_pattern = cls._CLASS_PATTERNS.get(lang)
        if cls_pattern:
            for m in cls_pattern.finditer(text):
                name = m.group(1)
                base = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
                line_no = text[:m.start()].count("\n") + 1
                asset.classes.append(ClassInfo(
                    name=name, bases=[base] if base else [],
                    methods=[], docstring="", start_line=line_no,
                ))
