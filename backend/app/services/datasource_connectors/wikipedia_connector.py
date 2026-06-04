"""Wikipedia connector using the REST API (free, no key required).

Endpoint: https://zh.wikipedia.org/api/rest_v1/page/summary/{title}

Returns result_type="text".
"""
from __future__ import annotations

import logging
import re
import urllib.parse

import httpx

from app.services.datasource_connectors import BaseConnector, DataSourceResult

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0
_ZH_API = "https://zh.wikipedia.org/api/rest_v1/page/summary/{title}"
_EN_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


class WikipediaConnector(BaseConnector):
    source_key = "acad_cnki_abstract"
    source_name = "Wikipedia百科摘要"

    async def search(self, query: str, limit: int = 10) -> DataSourceResult:
        title = _extract_title(query)
        encoded = urllib.parse.quote(title, safe="")

        for api_template in [_ZH_API, _EN_API]:
            try:
                url = api_template.format(title=encoded)
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(url, headers={"Accept": "application/json"})
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                summary = data.get("extract", "")
                page_title = data.get("title", title)
                wiki_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

                return DataSourceResult(
                    source_key=self.source_key,
                    source_name=self.source_name,
                    result_type="text",
                    data={
                        "title": page_title,
                        "summary": summary,
                        "url": wiki_url,
                        "language": "zh" if "zh.wikipedia" in api_template else "en",
                    },
                    row_count=1 if summary else 0,
                )
            except httpx.TimeoutException:
                logger.warning("[wikipedia_connector] Timeout for: %s", title)
                continue
            except Exception as exc:
                logger.debug("[wikipedia_connector] Error for '%s': %s", title, exc)
                continue

        return DataSourceResult(
            source_key=self.source_key,
            source_name=self.source_name,
            result_type="text",
            data={"title": title, "summary": f"未找到关于「{title}」的百科词条。", "url": "", "language": "zh"},
            row_count=0,
        )


def _extract_title(query: str) -> str:
    """Extract the most relevant title from a query string."""
    # Remove common question prefixes
    query = re.sub(r"^(请问|查询|搜索|介绍|什么是|关于|解释)\s*", "", query.strip())
    # Take first significant phrase (up to 20 chars)
    m = re.match(r"^([一-龥a-zA-Z0-9\s\-\_]{2,30})", query)
    if m:
        return m.group(1).strip()
    return query[:20].strip() or "China"
