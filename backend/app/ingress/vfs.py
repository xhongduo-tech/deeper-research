"""Virtual File System — 将 zip/tar/目录上传构建成内存目录树.

支持：
  - .zip / .tar.gz / .tar.bz2 压缩包
  - 单个文件直接包装
  - 限制：单文件最大 50MB，总解压大小最大 500MB
"""
from __future__ import annotations

import io
import logging
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterator

logger = logging.getLogger(__name__)

_MAX_SINGLE_FILE = 50 * 1024 * 1024   # 50 MB
_MAX_TOTAL_SIZE  = 500 * 1024 * 1024  # 500 MB


@dataclass
class VFSNode:
    """一个虚拟文件系统节点（文件或目录）."""
    name: str
    path: str                   # 相对于根节点的 POSIX 路径
    is_dir: bool
    content: bytes | None = None
    children: list["VFSNode"] = field(default_factory=list)

    @property
    def suffix(self) -> str:
        return PurePosixPath(self.name).suffix.lower()

    @property
    def size(self) -> int:
        return len(self.content) if self.content else 0

    def walk(self) -> Iterator["VFSNode"]:
        """深度优先遍历所有文件节点."""
        if not self.is_dir:
            yield self
        for child in self.children:
            yield from child.walk()

    def to_tree_text(self, indent: int = 0) -> str:
        prefix = "  " * indent
        if self.is_dir:
            lines = [f"{prefix}[DIR] {self.name}/"]
            for c in self.children:
                lines.append(c.to_tree_text(indent + 1))
            return "\n".join(lines)
        size_kb = self.size / 1024
        return f"{prefix}{self.name}  ({size_kb:.1f} KB)"


class VirtualFileSystem:
    """从字节流构建虚拟文件系统树."""

    @classmethod
    def from_bytes(cls, filename: str, data: bytes) -> "VirtualFileSystem":
        vfs = cls()
        lower = filename.lower()
        if lower.endswith(".zip"):
            vfs._root = cls._from_zip(data)
        elif lower.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar")):
            vfs._root = cls._from_tar(data)
        else:
            # 单文件，包装为单节点树
            node = VFSNode(name=filename, path=filename, is_dir=False, content=data)
            root = VFSNode(name="__root__", path="", is_dir=True)
            root.children.append(node)
            vfs._root = root
        return vfs

    def __init__(self):
        self._root: VFSNode = VFSNode(name="__root__", path="", is_dir=True)

    @property
    def root(self) -> VFSNode:
        return self._root

    def all_files(self) -> list[VFSNode]:
        return list(self._root.walk())

    def get_file(self, path: str) -> VFSNode | None:
        for node in self._root.walk():
            if node.path == path or node.name == path:
                return node
        return None

    def directory_tree(self) -> str:
        return self._root.to_tree_text()

    def summary(self) -> dict:
        files = self.all_files()
        by_type: dict[str, int] = {}
        for f in files:
            ext = f.suffix or "(no ext)"
            by_type[ext] = by_type.get(ext, 0) + 1
        return {
            "total_files": len(files),
            "by_type": by_type,
            "total_size_kb": sum(f.size for f in files) / 1024,
        }

    # ── 内部构建 ──────────────────────────────────────────────────────────

    @staticmethod
    def _from_zip(data: bytes) -> VFSNode:
        root = VFSNode(name="__root__", path="", is_dir=True)
        node_map: dict[str, VFSNode] = {"": root}
        total = 0

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.file_size > _MAX_SINGLE_FILE:
                    logger.warning("VFS skip oversized entry: %s (%d bytes)", info.filename, info.file_size)
                    continue
                total += info.file_size
                if total > _MAX_TOTAL_SIZE:
                    logger.warning("VFS total size limit reached, stopping extraction")
                    break

                parts = PurePosixPath(info.filename).parts
                if not parts:
                    continue

                # 构建目录节点
                VirtualFileSystem._ensure_dir_nodes(node_map, parts[:-1], root)

                if info.is_dir():
                    VirtualFileSystem._ensure_dir_nodes(node_map, parts, root)
                    continue

                parent_path = "/".join(parts[:-1])
                parent = node_map.get(parent_path, root)
                content = zf.read(info.filename)
                node = VFSNode(
                    name=parts[-1],
                    path=info.filename.rstrip("/"),
                    is_dir=False,
                    content=content,
                )
                parent.children.append(node)

        return root

    @staticmethod
    def _from_tar(data: bytes) -> VFSNode:
        root = VFSNode(name="__root__", path="", is_dir=True)
        node_map: dict[str, VFSNode] = {"": root}
        total = 0

        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            for member in tf.getmembers():
                if member.size > _MAX_SINGLE_FILE:
                    logger.warning("VFS skip oversized entry: %s", member.name)
                    continue
                total += member.size
                if total > _MAX_TOTAL_SIZE:
                    break

                parts = PurePosixPath(member.name).parts
                if not parts:
                    continue

                VirtualFileSystem._ensure_dir_nodes(node_map, parts[:-1], root)

                if member.isdir():
                    VirtualFileSystem._ensure_dir_nodes(node_map, parts, root)
                    continue

                parent_path = "/".join(parts[:-1])
                parent = node_map.get(parent_path, root)

                f = tf.extractfile(member)
                content = f.read() if f else b""
                node = VFSNode(
                    name=parts[-1],
                    path=member.name,
                    is_dir=False,
                    content=content,
                )
                parent.children.append(node)

        return root

    @staticmethod
    def _ensure_dir_nodes(node_map: dict, parts: tuple, root: VFSNode) -> None:
        for i in range(len(parts)):
            path = "/".join(parts[: i + 1])
            if path not in node_map:
                parent_path = "/".join(parts[:i])
                parent = node_map.get(parent_path, root)
                dir_node = VFSNode(name=parts[i], path=path, is_dir=True)
                parent.children.append(dir_node)
                node_map[path] = dir_node
