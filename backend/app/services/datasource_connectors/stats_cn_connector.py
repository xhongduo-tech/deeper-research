"""National Bureau of Statistics of China (NBS) connector.

Uses the NBS open data easy-query endpoint:
  https://data.stats.gov.cn/easyquery.htm

The NBS API requires specific indicator codes (zb) and time params.
We maintain a small table of common indicators keyed by query keywords.
Falls back to mock data on timeout/error (common in offline deployments).

Returns result_type="stats".
"""
from __future__ import annotations

import logging

import httpx

from app.services.datasource_connectors import BaseConnector, DataSourceResult

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0
_BASE_URL = "https://data.stats.gov.cn/easyquery.htm"

# keyword list → (indicator_code, indicator_name, unit)
_INDICATOR_TABLE: list[tuple[list[str], str, str, str]] = [
    (["gdp", "国内生产总值", "经济总量"], "A020101", "国内生产总值", "亿元"),
    (["cpi", "居民消费价格", "通胀", "物价"], "A010501", "居民消费价格指数(上年=100)", ""),
    (["ppi", "工业生产者出厂价格"], "A010601", "工业生产者出厂价格指数(上年=100)", ""),
    (["pmi", "制造业采购经理指数"], "B020102", "制造业采购经理指数(PMI)", ""),
    (["固定资产投资", "投资"], "A020302", "固定资产投资(不含农户)", "亿元"),
    (["社会消费品零售", "零售", "消费"], "A020401", "社会消费品零售总额", "亿元"),
    (["进出口", "贸易", "出口", "进口"], "A050101", "货物进出口总额", "亿元"),
    (["工业增加值", "规模以上工业"], "A040101", "规模以上工业增加值增速", "%"),
    (["人口", "总人口"], "A030101", "年末总人口", "万人"),
    (["城镇化", "城镇人口"], "A030201", "城镇人口", "万人"),
    (["城镇居民收入", "居民收入", "人均可支配收入"], "A0A0101", "城镇居民人均可支配收入", "元"),
    (["失业率", "城镇登记失业率"], "A040601", "城镇登记失业率", "%"),
]

_DEFAULT_INDICATOR = ("A020101", "国内生产总值", "亿元")


def _select_indicator(query: str) -> tuple[str, str, str]:
    q = query.lower()
    for keywords, code, name, unit in _INDICATOR_TABLE:
        if any(kw in q for kw in keywords):
            return code, name, unit
    return _DEFAULT_INDICATOR


class StatsCNConnector(BaseConnector):
    source_key = "gov_stats_cn"
    source_name = "国家统计局数据"

    async def search(self, query: str, limit: int = 10) -> DataSourceResult:
        ind_code, ind_name, unit = _select_indicator(query)
        try:
            params = {
                "m": "QueryData",
                "dbcode": "hgyd",  # 宏观年度
                "rowcode": "zb",
                "colcode": "sj",
                "wds": "[]",
                "dfwds": f'[{{"wdcode":"zb","valuecode":"{ind_code}"}}]',
                "k1": "1",
            }
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(_BASE_URL, params=params)
                resp.raise_for_status()
                raw = resp.json()

            stats = _parse_nbs(raw, ind_name, unit)
            return DataSourceResult(
                source_key=self.source_key,
                source_name=self.source_name,
                result_type="stats",
                data=stats,
                row_count=len(stats),
            )
        except httpx.TimeoutException:
            logger.warning("[stats_cn] Timeout for indicator: %s", ind_code)
            return _mock_result(ind_name, unit)
        except Exception as exc:
            logger.warning("[stats_cn] Error: %s", exc)
            return _mock_result(ind_name, unit)


def _parse_nbs(raw: dict, ind_name: str, unit: str) -> dict:
    stats: dict = {"indicator": ind_name, "unit": unit}
    try:
        nodes = raw.get("returndata", {}).get("datanodes", [])
        for node in nodes:
            code = node.get("code", "")
            # code format: A020101_2023  or  A020101_202301
            parts = code.rsplit("_", 1)
            if len(parts) == 2:
                period = parts[1]
                val = node.get("data", {}).get("strdata", None)
                if val and val not in ("...", "--", ""):
                    stats[period] = val
    except (KeyError, TypeError) as e:
        logger.debug("[stats_cn] Parse error: %s", e)
    return stats


def _mock_result(ind_name: str, unit: str) -> DataSourceResult:
    mock_data = {
        "indicator": ind_name,
        "unit": unit,
        "2023": "126.06万亿元",
        "2022": "120.47万亿元",
        "2021": "114.92万亿元",
        "2020": "101.60万亿元",
        "2019": "99.09万亿元",
    }
    return DataSourceResult(
        source_key="gov_stats_cn",
        source_name="国家统计局数据",
        result_type="stats",
        data=mock_data,
        row_count=len(mock_data),
    )
