"""Ingress Dispatcher — 按文件类型路由到正确解析器，输出标准化 ParsedAsset."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from .vfs import VFSNode

if TYPE_CHECKING:
    from .vfs import VirtualFileSystem

logger = logging.getLogger(__name__)

# 代码文件扩展名集合
_CODE_EXTS = {
    ".py", ".pyw", ".java", ".js", ".mjs", ".ts", ".tsx",
    ".go", ".sh", ".bash", ".zsh", ".c", ".h", ".cpp", ".cc",
    ".hpp", ".rs", ".kt", ".swift", ".rb", ".php", ".cs", ".scala",
    ".r", ".sql",
}

# 配置文件扩展名集合
_CONFIG_EXTS = {
    ".json", ".yaml", ".yml", ".toml",
    ".env", ".ini", ".cfg", ".conf",
}

# 模板文件扩展名集合
_TEMPLATE_EXTS = {".docx", ".dotx", ".pptx", ".potx"}

# 文档/富媒体 — 转交给现有 file_parser
_DOC_EXTS = {".pdf", ".doc", ".xls", ".xlsx", ".xlsb", ".ods", ".txt", ".md", ".csv"}

# 图片
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".svg"}


@dataclass
class ParsedAsset:
    """统一的解析输出结构体."""
    path: str
    asset_type: str          # "code" | "config" | "template" | "document" | "image" | "unknown"
    language: str = ""       # 代码语言，或文档格式
    size_bytes: int = 0

    # 结构化内容
    code_asset: object = None           # CodeAsset
    config_data: dict = field(default_factory=dict)       # ConfigParser 输出
    template_meta: object = None        # TemplateMeta
    document_text: str = ""             # 普通文档提取的文本
    image_base64: str = ""              # 图片 base64

    # 通用摘要（LLM 可直接消费）
    summary: str = ""
    context_text: str = ""             # 用于注入 LLM prompt 的上下文块


class IngressDispatcher:
    """将 VFS 中的每个文件节点分发给对应解析器，返回 ParsedAsset 列表."""

    @classmethod
    async def dispatch_vfs(cls, vfs: "VirtualFileSystem") -> list[ParsedAsset]:
        """解析整个 VFS，返回所有文件的 ParsedAsset."""
        assets: list[ParsedAsset] = []
        for node in vfs.all_files():
            asset = await cls.dispatch_node(node)
            if asset:
                assets.append(asset)
        return assets

    @classmethod
    async def dispatch_node(cls, node: VFSNode) -> ParsedAsset | None:
        """解析单个 VFSNode."""
        if not node.content:
            return None
        suffix = PurePosixPath(node.name).suffix.lower()
        try:
            if suffix in _CODE_EXTS:
                return cls._parse_code(node)
            elif suffix in _CONFIG_EXTS:
                return cls._parse_config(node)
            elif suffix in _TEMPLATE_EXTS:
                return cls._parse_template(node)
            elif suffix in _DOC_EXTS:
                return await cls._parse_document(node)
            elif suffix in _IMAGE_EXTS:
                return cls._parse_image(node)
            else:
                return cls._parse_unknown(node)
        except Exception as exc:
            logger.warning("IngressDispatcher error for %s: %s", node.path, exc)
            return None

    @classmethod
    async def dispatch_bytes(cls, filename: str, data: bytes) -> list[ParsedAsset]:
        """直接从文件名 + 字节数据分发（不经过 VFS）."""
        from .vfs import VFSNode
        node = VFSNode(name=filename, path=filename, is_dir=False, content=data)
        asset = await cls.dispatch_node(node)
        return [asset] if asset else []

    # ── 具体解析器 ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_code(node: VFSNode) -> ParsedAsset:
        from .parsers.code_parser import CodeParser
        ca = CodeParser.parse(node.path, node.content or b"")
        if not ca:
            return ParsedAsset(path=node.path, asset_type="unknown", size_bytes=node.size)
        ctx = ca.to_context_text()
        return ParsedAsset(
            path=node.path, asset_type="code",
            language=ca.language, size_bytes=node.size,
            code_asset=ca, summary=ctx[:500], context_text=ctx,
        )

    @staticmethod
    def _parse_config(node: VFSNode) -> ParsedAsset:
        from .parsers.config_parser import ConfigParser
        data = ConfigParser.parse(node.name, node.content or b"")
        return ParsedAsset(
            path=node.path, asset_type="config",
            language=data["format"], size_bytes=node.size,
            config_data=data, summary=data["summary"], context_text=data["summary"],
        )

    @staticmethod
    def _parse_template(node: VFSNode) -> ParsedAsset:
        from .parsers.template_parser import TemplatePlaceholderParser
        meta = TemplatePlaceholderParser.parse(node.name, node.content or b"")
        if not meta:
            return ParsedAsset(path=node.path, asset_type="unknown", size_bytes=node.size)
        summ = meta.summary()
        return ParsedAsset(
            path=node.path, asset_type="template",
            language=meta.file_type, size_bytes=node.size,
            template_meta=meta, summary=summ, context_text=summ,
        )

    @staticmethod
    async def _parse_document(node: VFSNode) -> ParsedAsset:
        """委托给现有 file_parser 提取文本."""
        import asyncio, tempfile, os
        from pathlib import Path as SysPath
        from app.services.file_parser import parse_file

        # 写入临时文件，复用现有解析器
        suffix = PurePosixPath(node.name).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
            tf.write(node.content or b"")
            tmp_path = tf.name

        try:
            text = await asyncio.to_thread(parse_file, tmp_path)
        except Exception as exc:
            logger.warning("Document parse failed for %s: %s", node.path, exc)
            text = ""
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        snippet = text[:1000]
        return ParsedAsset(
            path=node.path, asset_type="document",
            language=suffix.lstrip("."), size_bytes=node.size,
            document_text=text, summary=snippet, context_text=text[:3000],
        )

    @staticmethod
    def _parse_image(node: VFSNode) -> ParsedAsset:
        import base64
        b64 = base64.b64encode(node.content or b"").decode()
        suffix = PurePosixPath(node.name).suffix.lstrip(".")
        return ParsedAsset(
            path=node.path, asset_type="image",
            language=suffix, size_bytes=node.size,
            image_base64=b64,
            summary=f"图片: {node.name} ({node.size // 1024} KB)",
            context_text=f"[IMAGE:{node.name}]",
        )

    @staticmethod
    def _parse_unknown(node: VFSNode) -> ParsedAsset:
        try:
            text = (node.content or b"").decode("utf-8", errors="replace")[:2000]
        except Exception:
            text = ""
        return ParsedAsset(
            path=node.path, asset_type="unknown", size_bytes=node.size,
            document_text=text, summary=text[:200], context_text=text,
        )
