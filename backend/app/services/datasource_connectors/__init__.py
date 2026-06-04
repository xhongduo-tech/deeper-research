"""datasource_connectors — pluggable connector framework for official data sources.

Each connector implements BaseConnector.search() and returns a DataSourceResult.
Connectors are registered in CONNECTOR_MAP and instantiated on demand by the
datasource router.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class DataSourceResult:
    source_key: str
    source_name: str
    result_type: str          # "table" | "financial" | "articles" | "stats" | "text"
    data: dict
    row_count: int = 0
    error: str | None = None


class BaseConnector(ABC):
    """Abstract base for all data-source connectors."""

    source_key: str = ""
    source_name: str = ""

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> DataSourceResult:
        """Execute a search/query against the data source.

        Must never raise — return a DataSourceResult with error set on failure.
        """
        ...


# ── Connector registry (populated below) ────────────────────────────────────

CONNECTOR_MAP: dict[str, type[BaseConnector]] = {}


def _register():
    """Lazy-load all concrete connectors into CONNECTOR_MAP."""
    from app.services.datasource_connectors.arxiv_connector import ArxivConnector
    from app.services.datasource_connectors.weather_connector import WeatherConnector
    from app.services.datasource_connectors.worldbank_connector import WorldBankConnector
    from app.services.datasource_connectors.news_rss_connector import NewsRSSConnector
    from app.services.datasource_connectors.wikipedia_connector import WikipediaConnector
    from app.services.datasource_connectors.mock_connector import MockConnector
    from app.services.datasource_connectors.stats_cn_connector import StatsCNConnector

    for cls in [
        ArxivConnector,
        WeatherConnector,
        WorldBankConnector,
        NewsRSSConnector,
        WikipediaConnector,
        StatsCNConnector,
    ]:
        CONNECTOR_MAP[cls.source_key] = cls

    # Mock connector covers all remaining sources
    CONNECTOR_MAP["__mock__"] = MockConnector


_register()


def get_connector(source_key: str) -> BaseConnector:
    """Return an instantiated connector for the given source key.

    Falls back to MockConnector for sources without a dedicated implementation.
    """
    from app.services.datasource_connectors.mock_connector import MockConnector as _MockConnector
    cls = CONNECTOR_MAP.get(source_key) or CONNECTOR_MAP.get("__mock__")
    if cls is _MockConnector:
        return cls(source_key=source_key)
    return cls()


# Re-export for convenience
__all__ = ["BaseConnector", "DataSourceResult", "get_connector", "CONNECTOR_MAP"]
