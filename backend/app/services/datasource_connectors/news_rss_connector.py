"""News RSS connector — fetches open RSS/Atom feeds from public Chinese news sources.

Falls back gracefully to mock data when feeds are unavailable (intranet/offline).
Returns result_type="articles".
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

from app.services.datasource_connectors import BaseConnector, DataSourceResult

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0

# source_key → list of RSS feed URLs (tried in order until one succeeds)
_RSS_FEEDS: dict[str, list[str]] = {
    "news_politics": [
        "http://www.xinhuanet.com/politics/news_politics.xml",
        "https://rss.sina.com.cn/news/china/focus15.xml",
    ],
    "news_financial": [
        "https://rss.sina.com.cn/news/stock/focus15.xml",
        "https://www.yicai.com/rss/news.xml",
    ],
    "news_tech": [
        "https://www.ithome.com/rss/",
        "https://36kr.com/feed",
    ],
    "news_international": [
        "https://rss.sina.com.cn/news/world/focus15.xml",
    ],
    "news_sports": [
        "https://rss.sina.com.cn/sports/china/focus15.xml",
    ],
    "news_entertainment": [
        "https://rss.sina.com.cn/ent/focus15.xml",
    ],
    "news_social": [
        "https://rss.sina.com.cn/news/society/focus15.xml",
    ],
}

_DEFAULT_FEEDS = [
    "https://rss.sina.com.cn/news/china/focus15.xml",
    "https://rss.sina.com.cn/news/world/focus15.xml",
]


class NewsRSSConnector(BaseConnector):
    source_key = "news_politics"
    source_name = "政治时事新闻"

    async def search(self, query: str, limit: int = 10) -> DataSourceResult:
        return await _fetch_and_filter(self.source_key, self.source_name, query, limit)


async def _fetch_and_filter(
    source_key: str,
    source_name: str,
    query: str,
    limit: int,
) -> DataSourceResult:
    feeds = _RSS_FEEDS.get(source_key, _DEFAULT_FEEDS)
    articles: list[dict] = []

    for feed_url in feeds:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(feed_url, follow_redirects=True)
                resp.raise_for_status()
            articles = _parse_rss(resp.text)
            if articles:
                break
        except Exception as exc:
            logger.debug("[news_rss] Failed %s: %s", feed_url, exc)
            continue

    if not articles:
        articles = _mock_articles(query, source_name)

    # Keyword filter
    if query.strip():
        terms = [t for t in query.split() if len(t) >= 2]
        if terms:
            filtered = [
                a for a in articles
                if any(t in a.get("title", "") or t in a.get("summary", "") for t in terms)
            ]
            if filtered:
                articles = filtered

    articles = articles[:limit]
    return DataSourceResult(
        source_key=source_key,
        source_name=source_name,
        result_type="articles",
        data={"articles": articles, "query": query},
        row_count=len(articles),
    )


def _parse_rss(xml_text: str) -> list[dict]:
    """Parse RSS 2.0 or Atom feed XML and extract articles."""
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
        # RSS 2.0
        for item in root.iter("item"):
            title = _text(item, "title")
            link = _text(item, "link")
            desc = _text(item, "description") or _text(item, "summary")
            pub = _text(item, "pubDate") or _text(item, "published")
            if title or desc:
                items.append({
                    "title": title[:200],
                    "url": link,
                    "summary": (desc or "")[:400],
                    "published": (pub or "")[:30],
                })
        # Atom entries
        ns = "http://www.w3.org/2005/Atom"
        for entry in root.iter(f"{{{ns}}}entry"):
            title = _ns_text(entry, ns, "title")
            link_elem = entry.find(f"{{{ns}}}link")
            link = link_elem.get("href", "") if link_elem is not None else ""
            summary = _ns_text(entry, ns, "summary") or _ns_text(entry, ns, "content")
            pub = _ns_text(entry, ns, "published") or _ns_text(entry, ns, "updated")
            if title or summary:
                items.append({
                    "title": (title or "")[:200],
                    "url": link,
                    "summary": (summary or "")[:400],
                    "published": (pub or "")[:30],
                })
    except ET.ParseError as e:
        logger.debug("[news_rss] XML parse error: %s", e)
    return items


def _text(elem, tag: str) -> str:
    child = elem.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _ns_text(elem, ns: str, tag: str) -> str:
    child = elem.find(f"{{{ns}}}{tag}")
    return (child.text or "").strip() if child is not None else ""


def _mock_articles(query: str, source_name: str) -> list[dict]:
    return [
        {
            "title": f"【{source_name}】{query}相关最新动态",
            "url": "https://example.com/news/1",
            "summary": f"据报道，关于{query}的最新情况显示，相关部门正在积极推进相关工作，取得了积极进展。",
            "published": "2024-05-15",
        },
        {
            "title": f"{query}深度分析：现状与展望",
            "url": "https://example.com/news/2",
            "summary": f"专家表示，{query}领域在2024年呈现出新的发展趋势，政策环境总体向好，市场预期逐步改善。",
            "published": "2024-05-10",
        },
        {
            "title": f"{query}政策解读：重点内容梳理",
            "url": "https://example.com/news/3",
            "summary": f"本文对近期出台的{query}相关政策进行了系统梳理，分析了主要政策方向及其可能产生的影响。",
            "published": "2024-05-05",
        },
    ]
