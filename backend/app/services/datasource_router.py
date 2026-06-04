"""datasource_router.py — domain-aware routing of queries to official data sources.

Route logic:
1. Map domain_hints + query keywords to relevant source keys.
2. Fan out to connectors in parallel (asyncio.gather).
3. Broadcast WebSocket events before/after each call.
4. Return all DataSourceResult objects.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.services.datasource_connectors import DataSourceResult, get_connector

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Routing table: keyword → list of source keys (ordered by priority) ───────

_KEYWORD_ROUTES: list[tuple[list[str], list[str]]] = [
    # 金融 / 股票
    (["股票", "股价", "A股", "上市公司", "市值", "沪深", "涨跌", "K线"],
     ["fin_stock_cn", "fin_annual_report"]),
    (["港股", "恒生", "联交所", "HK"],
     ["fin_stock_hk"]),
    (["美股", "纳斯达克", "纽交所", "标普", "道琼斯"],
     ["fin_stock_us"]),
    (["年报", "财报", "营收", "净利润", "毛利率", "财务"],
     ["fin_annual_report", "fin_stock_cn"]),
    (["期货", "大宗商品", "原油", "黄金", "铜", "大豆", "铁矿"],
     ["fin_futures"]),
    (["债券", "国债", "企业债", "收益率", "信用债"],
     ["fin_bond"]),
    (["基金", "净值", "公募", "私募", "ETF"],
     ["fin_fund"]),
    (["汇率", "外汇", "人民币", "美元", "欧元", "中间价"],
     ["fin_forex"]),
    (["CPI", "PPI", "PMI", "GDP", "宏观经济", "通胀", "通货膨胀"],
     ["fin_macro_cn", "gov_stats_cn"]),

    # 政府 / 政策
    (["政府工作报告", "国务院工作报告"],
     ["gov_report_cn"]),
    (["政策", "规划", "政府文件", "国发", "国办", "中央"],
     ["gov_policy_cn", "gov_report_cn"]),
    (["统计局", "统计数据", "人口统计", "工业产值", "农业统计"],
     ["gov_stats_cn"]),
    (["海关", "进出口", "贸易顺差", "贸易逆差", "贸易额"],
     ["gov_customs_cn"]),
    (["人民银行", "PBOC", "货币供应", "M2", "M1", "LPR", "社融", "外汇储备"],
     ["gov_pboc"]),
    (["发改委", "国家发改委", "五年规划", "产业政策", "价格监管"],
     ["gov_ndrc"]),
    (["财政", "税收", "财政收支", "专项债", "地方债", "预算"],
     ["gov_mof"]),
    (["省级统计", "城市数据", "统计年鉴", "地区GDP", "省市"],
     ["gov_local_stats"]),

    # 学术 / 研究
    (["论文", "研究", "学术", "arxiv", "预印本", "发表", "文献"],
     ["acad_arxiv"]),
    (["医学文献", "pubmed", "生物医学", "临床研究"],
     ["acad_pubmed"]),
    (["中文论文", "CNKI", "知网", "学术期刊"],
     ["acad_cnki_abstract"]),
    (["专利", "发明专利", "知识产权", "CNIPA"],
     ["acad_patent_cn"]),
    (["SSRN", "工作论文", "社会科学"],
     ["acad_ssrn"]),

    # 企业信息
    (["工商", "营业执照", "企业注册", "法定代表人", "股权"],
     ["corp_registration"]),
    (["被执行", "失信", "司法风险", "诉讼", "法院"],
     ["corp_judicial"]),
    (["ESG", "社会责任", "可持续", "碳披露"],
     ["corp_esg"]),
    (["招标", "招投标", "政府采购", "中标"],
     ["corp_tender"]),
    (["公告", "披露", "重大事项", "并购", "定增"],
     ["corp_announcement"]),

    # 新闻 / 舆情
    (["财经新闻", "证券新闻", "股市新闻"],
     ["news_financial"]),
    (["科技新闻", "AI新闻", "芯片新闻", "互联网新闻"],
     ["news_tech"]),
    (["政治新闻", "时政", "新华社", "人民日报", "中央"],
     ["news_politics"]),
    (["国际新闻", "外交", "地缘", "路透", "彭博"],
     ["news_international"]),
    (["体育新闻", "赛事", "足球", "篮球", "奥运"],
     ["news_sports"]),
    (["娱乐新闻", "票房", "影视", "音乐"],
     ["news_entertainment"]),
    (["社会新闻", "民生", "城市", "教育热点", "医疗热点"],
     ["news_social"]),

    # 行业
    (["汽车", "新能源汽车", "车市", "电动车", "销量"],
     ["industry_auto"]),
    (["房地产", "房价", "楼市", "商品房", "土地"],
     ["industry_realestate"]),
    (["能源", "电力", "煤炭", "天然气", "油价"],
     ["industry_energy"]),
    (["农业", "粮食", "农产品", "种植", "化肥"],
     ["industry_agri"]),
    (["医药", "药品", "医疗器械", "集采"],
     ["industry_pharma"]),
    (["零售", "消费", "电商", "GMV", "社零"],
     ["industry_retail"]),
    (["物流", "快递", "航运", "铁路货运", "港口"],
     ["industry_logistics"]),
    (["电信", "通信", "5G", "宽带", "移动用户"],
     ["industry_telecom"]),

    # 气象 / 环境
    (["天气", "气象", "预报", "降雨", "温度", "气候"],
     ["env_weather_cn"]),
    (["气候变化", "全球变暖", "温室气体", "极端天气"],
     ["env_climate"]),
    (["AQI", "空气质量", "PM2.5", "水质", "土壤污染"],
     ["env_pollution"]),
    (["碳排放", "碳市场", "双碳", "碳中和", "碳达峰", "CCER"],
     ["env_carbon"]),
    (["灾害", "地震", "洪涝", "台风", "干旱"],
     ["env_disaster"]),

    # 法律
    (["法律", "法规", "立法", "行政法规"],
     ["law_statute_cn"]),
    (["裁判文书", "判决", "裁定", "诉讼案件"],
     ["law_judicial_cn"]),
    (["部委规章", "地方法规", "地方规章"],
     ["law_regulation_cn"]),
    (["合规", "监管", "反垄断", "数据合规"],
     ["law_compliance"]),

    # 国际
    (["世界银行", "WDI", "世行", "发展数据"],
     ["intl_worldbank"]),
    (["IMF", "国际货币基金", "WEO", "全球经济展望"],
     ["intl_imf"]),
    (["联合国", "SDG", "可持续发展目标"],
     ["intl_un_stats"]),
    (["全球贸易", "WTO", "Comtrade", "双边贸易"],
     ["intl_trade"]),
    (["地缘政治", "国际关系", "军费", "冲突", "SIPRI"],
     ["intl_geopolitics"]),

    # 医疗健康
    (["疾病数据", "流行病", "传染病", "慢性病"],
     ["health_disease"]),
    (["药品说明", "临床试验", "不良反应"],
     ["health_drug"]),
    (["医改", "医疗政策", "医保", "DRG"],
     ["health_policy"]),

    # 教育
    (["教育统计", "高校招生", "毕业生就业", "院校数量"],
     ["edu_stats_cn"]),
    (["高考", "分数线", "双减", "教育改革"],
     ["edu_policy"]),
]

# domain_hint → direct source keys (fast path)
_DOMAIN_HINT_MAP: dict[str, list[str]] = {
    "finance": ["fin_stock_cn", "fin_macro_cn"],
    "financial": ["fin_stock_cn", "fin_macro_cn"],
    "金融": ["fin_stock_cn", "fin_macro_cn"],
    "academic": ["acad_arxiv"],
    "research": ["acad_arxiv"],
    "学术": ["acad_arxiv"],
    "government": ["gov_stats_cn", "gov_policy_cn"],
    "政府": ["gov_stats_cn", "gov_policy_cn"],
    "news": ["news_financial", "news_politics"],
    "新闻": ["news_financial", "news_politics"],
    "weather": ["env_weather_cn"],
    "天气": ["env_weather_cn"],
    "international": ["intl_worldbank", "intl_imf"],
    "国际": ["intl_worldbank", "intl_imf"],
    "legal": ["law_statute_cn"],
    "法律": ["law_statute_cn"],
    "health": ["health_disease"],
    "医疗": ["health_disease"],
    "education": ["edu_stats_cn"],
    "教育": ["edu_stats_cn"],
    "industry": ["industry_auto"],
    "行业": ["industry_auto"],
    "environment": ["env_weather_cn", "env_pollution"],
    "环境": ["env_weather_cn", "env_pollution"],
}

_MAX_SOURCES_PER_QUERY = 5


def _select_sources(query: str, domain_hints: list[str]) -> list[str]:
    """Return an ordered, deduplicated list of source keys to query."""
    selected: list[str] = []
    seen: set[str] = set()

    def _add(keys: list[str]):
        for k in keys:
            if k not in seen:
                seen.add(k)
                selected.append(k)

    # 1. Domain hints (fast path)
    for hint in (domain_hints or []):
        mapped = _DOMAIN_HINT_MAP.get(hint.lower(), [])
        _add(mapped)

    # 2. Keyword matching against query
    q_lower = query.lower()
    for keywords, sources in _KEYWORD_ROUTES:
        if any(kw in q_lower for kw in keywords):
            _add(sources)
        if len(selected) >= _MAX_SOURCES_PER_QUERY:
            break

    # 3. Default: if nothing matched, use general Chinese stats
    if not selected:
        _add(["gov_stats_cn", "fin_macro_cn", "acad_arxiv"])

    return selected[:_MAX_SOURCES_PER_QUERY]


async def _search_offline_kb_for_source(source_key: str, query: str) -> DataSourceResult | None:
    """Fallback: text-substring search over offline KB chunks for the given source.

    Used when the connector fails or returns empty results in intranet/offline mode.
    Offline KBs are identified by 【离线】 name prefix; no embedding required.
    """
    import re
    from app.database import async_session
    from app.models.knowledge_base import KnowledgeBase, KBChunk
    from sqlalchemy import select as sa_select

    try:
        async with async_session() as db:
            offline_kbs = (await db.execute(
                sa_select(KnowledgeBase.id).where(KnowledgeBase.name.like("【离线】%"))
            )).scalars().all()

            if not offline_kbs:
                return None

            keywords = [kw.strip() for kw in re.split(r"[\s，。？！、]+", query) if len(kw.strip()) >= 2]
            if not keywords:
                keywords = [query[:10]] if query else []

            scored: list[tuple[int, str]] = []
            for kb_id in offline_kbs:
                chunks = (await db.execute(
                    sa_select(KBChunk).where(KBChunk.kb_id == kb_id).limit(300)
                )).scalars().all()
                for chunk in chunks:
                    content = chunk.content or ""
                    score = sum(1 for kw in keywords if kw in content)
                    if score > 0:
                        scored.append((score, content))

            if not scored:
                return None

            scored.sort(key=lambda x: x[0], reverse=True)
            articles = [
                {"title": f"【离线】{source_key}", "summary": c, "published": "离线预加载", "url": ""}
                for _, c in scored[:8]
            ]

            connector = get_connector(source_key)
            return DataSourceResult(
                source_key=source_key,
                source_name=connector.source_name + "（离线）",
                result_type="articles",
                data={"articles": articles},
                row_count=len(articles),
                error=None,
            )
    except Exception as exc:
        logger.debug("[datasource_router] Offline KB fallback error for %s: %s", source_key, exc)
        return None


async def _query_one(
    report_id: int,
    source_key: str,
    query: str,
) -> DataSourceResult:
    """Query a single connector with WS event broadcasting.

    If the connector fails or returns empty results, falls back to offline KB
    text search (intranet/air-gapped mode).
    """
    from app.api.ws import broadcast_db_query_start, broadcast_db_query_result, broadcast_db_query_error

    connector = get_connector(source_key)
    name = connector.source_name

    await broadcast_db_query_start(report_id, source_key, name, query)
    try:
        result = await connector.search(query, limit=8)

        # Offline fallback: if connector returned no data, try offline KB
        if (result.error or result.row_count == 0) and not result.data:
            offline_result = await _search_offline_kb_for_source(source_key, query)
            if offline_result:
                logger.info("[datasource_router] Using offline KB fallback for %s", source_key)
                await broadcast_db_query_result(
                    report_id, source_key, offline_result.source_name,
                    offline_result.result_type, offline_result.data, offline_result.row_count,
                )
                return offline_result

        if result.error:
            await broadcast_db_query_error(report_id, source_key, name, result.error)
        else:
            await broadcast_db_query_result(
                report_id, source_key, name,
                result.result_type, result.data, result.row_count,
            )
        return result
    except Exception as exc:
        logger.warning("[datasource_router] Connector %s raised: %s", source_key, exc)
        err = str(exc)

        # Offline fallback on exception
        offline_result = await _search_offline_kb_for_source(source_key, query)
        if offline_result:
            logger.info("[datasource_router] Using offline KB fallback for %s after error", source_key)
            await broadcast_db_query_result(
                report_id, source_key, offline_result.source_name,
                offline_result.result_type, offline_result.data, offline_result.row_count,
            )
            return offline_result

        await broadcast_db_query_error(report_id, source_key, name, err)
        return DataSourceResult(
            source_key=source_key,
            source_name=name,
            result_type="stats",
            data={},
            row_count=0,
            error=err,
        )


async def route_query(
    report_id: int,
    query: str,
    domain_hints: list[str] | None = None,
) -> list[DataSourceResult]:
    """Route a research query to relevant data sources.

    Args:
        report_id:    Used for WS broadcasting.
        query:        The research query string.
        domain_hints: Optional domain keywords from section content_type / title.

    Returns:
        List of DataSourceResult objects (one per queried source).
    """
    source_keys = _select_sources(query, domain_hints or [])
    logger.debug("[datasource_router] query=%r → sources=%s", query[:60], source_keys)

    tasks = [_query_one(report_id, key, query) for key in source_keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final: list[DataSourceResult] = []
    for r in results:
        if isinstance(r, DataSourceResult):
            final.append(r)
        elif isinstance(r, Exception):
            logger.warning("[datasource_router] gather exception: %s", r)
    return final


def format_result_as_text(result: DataSourceResult) -> str:
    """Format a DataSourceResult into a plain-text evidence block."""
    header = f"【{result.source_name}数据】"
    lines = [header]

    if result.error:
        lines.append(f"（数据获取失败：{result.error}）")
        return "\n".join(lines)

    rtype = result.result_type
    data = result.data or {}

    if rtype in ("table", "financial"):
        cols = data.get("columns", [])
        rows = data.get("rows", [])
        if cols:
            lines.append("  " + " | ".join(str(c) for c in cols))
            lines.append("  " + "-" * (len(cols) * 12))
        for row in rows[:8]:
            lines.append("  " + " | ".join(str(v) for v in row))
        if data.get("as_of"):
            lines.append(f"  数据日期：{data['as_of']}")

    elif rtype == "stats":
        for k, v in data.items():
            if k not in ("columns", "rows"):
                lines.append(f"  {k}: {v}")

    elif rtype == "articles":
        articles = data.get("articles", [])
        for art in articles[:5]:
            title = art.get("title", "")
            summary = art.get("summary", "")
            pub = art.get("published", "")
            url = art.get("url", "")
            line = f"  • {title}"
            if pub:
                line += f"（{pub}）"
            lines.append(line)
            if summary:
                lines.append(f"    {summary[:200]}")
            if url:
                lines.append(f"    {url}")

    elif rtype == "text":
        title = data.get("title", "")
        summary = data.get("summary", "")
        url = data.get("url", "")
        if title:
            lines.append(f"  标题：{title}")
        if summary:
            lines.append(f"  摘要：{summary[:600]}")
        if url:
            lines.append(f"  来源：{url}")

    return "\n".join(lines)
