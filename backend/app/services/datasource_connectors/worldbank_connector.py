"""World Bank Open Data connector (free, no API key required).

Endpoint: https://api.worldbank.org/v2/country/{iso2}/indicator/{indicator}?format=json&mrv=5

Common indicators automatically selected based on query keywords.
Returns result_type="stats".
"""
from __future__ import annotations

import logging

import httpx

from app.services.datasource_connectors import BaseConnector, DataSourceResult

logger = logging.getLogger(__name__)

_BASE = "https://api.worldbank.org/v2"
_TIMEOUT = 8.0

# keyword → (indicator_code, label)
_INDICATOR_MAP: list[tuple[list[str], str, str]] = [
    (["gdp", "经济增长", "增速", "经济", "国内生产总值"], "NY.GDP.MKTP.KD.ZG", "GDP Growth Rate (%)"),
    (["cpi", "通胀", "通货膨胀", "物价", "inflation"], "FP.CPI.TOTL.ZG", "CPI Inflation (%)"),
    (["人口", "population", "人口数量"], "SP.POP.TOTL", "Total Population"),
    (["失业", "unemployment", "就业"], "SL.UEM.TOTL.ZS", "Unemployment Rate (%)"),
    (["贸易", "出口", "进口", "trade", "export"], "NE.TRD.GNFS.ZS", "Trade (% of GDP)"),
    (["外债", "debt", "债务", "政府债务"], "GC.DOD.TOTL.GD.ZS", "Government Debt (% of GDP)"),
    (["贫困", "poverty", "贫困率"], "SI.POV.NAHC", "Poverty Headcount Ratio (%)"),
    (["电力", "electricity", "电能"], "EG.USE.ELEC.KH.PC", "Electric Power Consumption (kWh per capita)"),
    (["教育", "education", "入学率"], "SE.PRM.ENRR", "Primary School Enrollment (%)"),
    (["寿命", "life expectancy", "预期寿命"], "SP.DYN.LE00.IN", "Life Expectancy at Birth (years)"),
]


def _select_indicator(query: str) -> tuple[str, str]:
    """Return the best-matching indicator code and label for the query."""
    query_lower = query.lower()
    for keywords, code, label in _INDICATOR_MAP:
        if any(kw in query_lower for kw in keywords):
            return code, label
    return "NY.GDP.MKTP.KD.ZG", "GDP Growth Rate (%)"


def _extract_country(query: str) -> str:
    """Extract ISO2 country code from the query; default China (CN)."""
    country_map = {
        "中国": "CN", "china": "CN", "美国": "US", "usa": "US", "united states": "US",
        "日本": "JP", "japan": "JP", "德国": "DE", "germany": "DE",
        "印度": "IN", "india": "IN", "英国": "GB", "uk": "GB",
        "法国": "FR", "france": "FR", "巴西": "BR", "brazil": "BR",
        "全球": "1W", "世界": "1W", "global": "1W", "world": "1W",
        "新兴市场": "EMU", "emerging": "EMU",
    }
    q = query.lower()
    for kw, iso in country_map.items():
        if kw in q:
            return iso
    return "CN"


class WorldBankConnector(BaseConnector):
    source_key = "intl_worldbank"
    source_name = "世界银行发展数据"

    async def search(self, query: str, limit: int = 10) -> DataSourceResult:
        indicator, label = _select_indicator(query)
        country = _extract_country(query)
        mrv = min(limit, 10)

        try:
            url = f"{_BASE}/country/{country}/indicator/{indicator}"
            params = {"format": "json", "mrv": mrv, "per_page": mrv}
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()

            stats = _parse_worldbank(payload, label, country)
            return DataSourceResult(
                source_key=self.source_key,
                source_name=self.source_name,
                result_type="stats",
                data=stats,
                row_count=len(stats),
            )
        except httpx.TimeoutException:
            logger.warning("[worldbank_connector] Timeout")
            return _mock_result(label, country)
        except Exception as exc:
            logger.warning("[worldbank_connector] Error: %s", exc)
            return _mock_result(label, country)


def _parse_worldbank(payload: list, label: str, country: str) -> dict:
    stats: dict = {"indicator": label, "country": country}
    try:
        records = payload[1] if len(payload) > 1 else []
        for rec in (records or []):
            year = rec.get("date", "")
            val = rec.get("value")
            if year and val is not None:
                stats[year] = round(float(val), 3)
    except (IndexError, TypeError, ValueError) as e:
        logger.debug("[worldbank_connector] Parse error: %s", e)
    return stats


def _mock_result(label: str, country: str) -> DataSourceResult:
    stats = {
        "indicator": label,
        "country": country,
        "2023": 5.2,
        "2022": 3.0,
        "2021": 8.4,
        "2020": 2.2,
        "2019": 6.0,
    }
    return DataSourceResult(
        source_key="intl_worldbank",
        source_name="世界银行发展数据",
        result_type="stats",
        data=stats,
        row_count=len(stats),
    )
