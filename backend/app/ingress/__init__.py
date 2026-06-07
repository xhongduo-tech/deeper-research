"""Universal Ingress Gateway —吃进一切异构输入，吐出标准化上下文资产。"""
from .vfs import VirtualFileSystem, VFSNode
from .dispatcher import IngressDispatcher, ParsedAsset

__all__ = ["VirtualFileSystem", "VFSNode", "IngressDispatcher", "ParsedAsset"]
