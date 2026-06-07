"""Offline stub for public web search.

DataAgent Studio is designed for **intranet / air-gapped** deployments.
All external network access is permanently disabled at the architecture level.
This module exists only so that existing call-sites can import without error;
every code-path unconditionally returns the "disabled" envelope — no HTTP
client is instantiated, no DNS resolution is attempted.

To replace with a real intranet full-text search (e.g. Elasticsearch, Solr,
internal knowledge portal), subclass or monkey-patch `search_web` and point
it at your on-premise search endpoint.  The caller contract is identical.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_OFFLINE_NOTE = (
    "外网搜索已在内网部署策略中永久关闭。"
    "当前内容生成仅使用：上传文件、知识库 RAG 检索、离线 LLM 知识激活。"
)


def format_search_results(results: list[dict]) -> str:  # noqa: ARG001
    """Kept for import-compatibility; always returns the offline notice."""
    return _OFFLINE_NOTE


async def search_web(query: str, max_results: int | None = None) -> dict:  # noqa: ARG001
    """Always returns a disabled-envelope — no network call is made."""
    return {
        "enabled": False,
        "query": query,
        "results": [],
        "sources": [],
        "note": _OFFLINE_NOTE,
    }
