"""MockConnector — returns realistic mock data for sources that require API keys
or are unavailable in an intranet/offline deployment.

Covers: fin_stock_cn, fin_stock_hk, fin_stock_us, fin_futures, fin_bond, fin_fund,
fin_forex, fin_annual_report, fin_macro_cn, corp_registration, corp_judicial,
corp_esg, corp_tender, corp_announcement, and any other unmapped source.
"""
from __future__ import annotations

import hashlib
import logging
import random
from datetime import date, timedelta

from app.services.datasource_connectors import BaseConnector, DataSourceResult

logger = logging.getLogger(__name__)

# ── Category-level mock generators ──────────────────────────────────────────

_STOCK_COLS = ["代码", "名称", "最新价", "涨跌幅(%)", "成交额(万元)", "市值(亿元)", "PE"]
_FUTURES_COLS = ["合约", "最新价", "涨跌幅(%)", "成交量(手)", "持仓量(手)", "结算价"]
_BOND_COLS = ["债券代码", "债券名称", "最新收益率(%)", "涨跌(bp)", "剩余期限(年)", "评级"]
_FUND_COLS = ["基金代码", "基金名称", "最新净值", "日涨跌(%)", "规模(亿元)", "基金类型"]
_FOREX_COLS = ["货币对", "中间价", "买入价", "卖出价", "日变动", "来源"]
_CORP_COLS = ["企业名称", "统一社会信用代码", "注册资本(万元)", "成立日期", "法定代表人", "经营状态"]

# Seed tables for plausible mock data
_STOCKS_CN = [
    ["600519", "贵州茅台", "1689.00", "+0.82", "156234", "21217", "28.5"],
    ["000858", "五粮液", "148.32", "-0.35", "45123", "5742", "22.1"],
    ["300750", "宁德时代", "189.45", "+1.23", "234567", "8293", "35.6"],
    ["601318", "中国平安", "42.10", "+0.12", "89234", "7683", "9.8"],
    ["000001", "平安银行", "10.35", "-0.48", "62341", "2015", "6.2"],
]
_FUTURES = [
    ["SC2406", "原油(上海)", "611.5", "+1.2", "45234", "123456", "608.0"],
    ["AU2406", "黄金(沪金)", "537.2", "+0.4", "34521", "89012", "535.8"],
    ["CU2406", "铜(沪铜)", "78560", "-0.8", "23456", "56789", "79000"],
    ["A2407", "大豆(大商所)", "4380", "+0.3", "12345", "34567", "4365"],
    ["RB2406", "螺纹钢", "3745", "-0.5", "89012", "345678", "3760"],
]
_BONDS = [
    ["019666", "24附息国债06", "2.285", "-0.5", "9.87", "AAA"],
    ["019661", "24附息国债01", "2.335", "+0.2", "4.92", "AAA"],
    ["019556", "23附息国债06", "2.415", "-0.8", "7.65", "AAA"],
    ["112065", "22央行票据", "2.050", "+0.1", "1.23", "AAA"],
    ["148038", "24农发债01", "2.180", "-0.3", "3.45", "AAA"],
]


def _stable_random(seed_str: str, lo: float, hi: float) -> float:
    """Return a deterministic pseudo-random float in [lo, hi] based on seed."""
    h = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    return round(lo + (h / 0xFFFFFFFF) * (hi - lo), 2)


class MockConnector(BaseConnector):
    """Generic mock connector; handles any source_key."""

    source_name = "模拟数据"

    def __init__(self, source_key: str = "__mock__"):
        self.source_key = source_key
        self.source_name = _SOURCE_NAMES.get(source_key, "官方数据源(模拟)")

    async def search(self, query: str, limit: int = 10) -> DataSourceResult:
        gen = _GENERATORS.get(self.source_key, _gen_generic)
        return gen(self.source_key, self.source_name, query, limit)


# ── Individual generators ────────────────────────────────────────────────────

def _gen_stock_cn(key, name, query, limit) -> DataSourceResult:
    # Try to match a specific stock from query for single-quote financial display
    q = query.upper()
    matched = next((r for r in _STOCKS_CN if r[0] in q or r[1] in query), None)
    today = str(date.today())
    if matched:
        code, sname, price_s, chg_pct, _, _, _ = matched
        price = float(price_s)
        chg_val = _stable_random(f"{code}_chg", -15, 20)
        return DataSourceResult(
            source_key=key, source_name=name, result_type="financial",
            data={
                "symbol": code, "name": sname, "price": price,
                "change": round(chg_val, 2), "change_pct": chg_pct,
                "open": round(price - _stable_random(f"{code}_open", 2, 8), 2),
                "close": price,
                "high": round(price + _stable_random(f"{code}_high", 1, 6), 2),
                "low": round(price - _stable_random(f"{code}_low", 3, 10), 2),
                "volume": f"{round(_stable_random(code, 100, 500), 1)}万",
                "date": today,
            },
            row_count=1,
        )
    # General market list — use table format
    rows = _STOCKS_CN[:min(limit, len(_STOCKS_CN))]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={"columns": _STOCK_COLS, "rows": rows, "market": "A股", "as_of": today},
        row_count=len(rows),
    )


def _gen_futures(key, name, query, limit) -> DataSourceResult:
    rows = _FUTURES[:min(limit, len(_FUTURES))]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={"columns": _FUTURES_COLS, "rows": rows, "as_of": str(date.today())},
        row_count=len(rows),
    )


def _gen_bond(key, name, query, limit) -> DataSourceResult:
    rows = _BONDS[:min(limit, len(_BONDS))]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={"columns": _BOND_COLS, "rows": rows, "as_of": str(date.today())},
        row_count=len(rows),
    )


def _gen_forex(key, name, query, limit) -> DataSourceResult:
    today = str(date.today())
    rows = [
        ["USD/CNY", "7.2350", "7.2301", "7.2398", "-0.0012", "PBOC"],
        ["EUR/CNY", "7.8120", "7.8052", "7.8188", "+0.0045", "PBOC"],
        ["JPY/CNY", "0.04681", "0.04675", "0.04687", "-0.00003", "PBOC"],
        ["GBP/CNY", "9.1200", "9.1120", "9.1280", "+0.0023", "PBOC"],
        ["HKD/CNY", "0.9265", "0.9261", "0.9269", "-0.0002", "PBOC"],
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="financial",
        data={"columns": _FOREX_COLS, "rows": rows[:limit], "as_of": today},
        row_count=min(limit, len(rows)),
    )


def _gen_fund(key, name, query, limit) -> DataSourceResult:
    today = str(date.today())
    rows = [
        ["110020", "易方达消费行业", "3.2450", "+0.34", "856.32", "股票型"],
        ["001156", "申万菱信新能源", "2.1230", "-0.21", "234.56", "股票型"],
        ["000270", "广发稳增", "1.4560", "+0.05", "123.45", "债券型"],
        ["163406", "兴全合润混合", "2.8900", "+0.12", "345.67", "混合型"],
        ["100038", "富国天鼎中短债", "1.1230", "+0.02", "567.89", "债券型"],
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="financial",
        data={"columns": _FUND_COLS, "rows": rows[:limit], "as_of": today},
        row_count=min(limit, len(rows)),
    )


def _gen_corp_registration(key, name, query, limit) -> DataSourceResult:
    rows = [
        ["字节跳动有限公司", "91110108MA01FXXX00", "100000", "2012-03-09", "张一鸣", "存续"],
        ["北京百度网讯科技有限公司", "91110000800088421P", "168000", "2001-06-05", "李彦宏", "存续"],
        ["腾讯科技(深圳)有限公司", "914403001922038216", "350000", "1998-11-11", "马化腾", "存续"],
        ["阿里云计算有限公司", "9133010057462616XH", "500000", "2009-09-17", "张勇", "存续"],
        ["华为技术有限公司", "914403001870826678", "2000000", "1987-09-15", "任正非", "存续"],
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={"columns": _CORP_COLS, "rows": rows[:limit]},
        row_count=min(limit, len(rows)),
    )


def _gen_annual_report(key, name, query, limit) -> DataSourceResult:
    years = ["2023", "2022", "2021", "2020", "2019"]
    rows = [
        [y, "贵州茅台", "149.08亿元", "735.97亿元", "83.04%", "74.73亿元", "https://example.com/report"]
        for y in years[:limit]
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={
            "columns": ["年份", "公司名称", "净利润", "营业收入", "毛利率", "EPS", "报告链接"],
            "rows": rows,
        },
        row_count=len(rows),
    )


def _gen_macro_cn(key, name, query, limit) -> DataSourceResult:
    stats = {
        "indicator": "中国宏观经济指标",
        "GDP增速(2023)": "5.2%",
        "CPI同比(2024-04)": "0.3%",
        "PPI同比(2024-04)": "-2.5%",
        "PMI制造业(2024-04)": "50.4",
        "社零增速(2024-04)": "2.3%",
        "固定资产投资增速(2024-04)": "4.2%",
        "出口增速(2024-04)": "1.5%",
        "M2同比(2024-04)": "7.2%",
        "社融增速(2024-04)": "8.3%",
    }
    return DataSourceResult(
        source_key=key, source_name=name, result_type="stats",
        data=stats, row_count=len(stats),
    )


def _gen_esg(key, name, query, limit) -> DataSourceResult:
    rows = [
        ["贵州茅台", "AA", "85.2", "3.2万吨", "28人", "优秀"],
        ["宁德时代", "A", "78.5", "45.6万吨", "15人", "良好"],
        ["中国石油", "BBB", "62.1", "1234万吨", "5人", "待改进"],
        ["比亚迪", "A", "76.3", "28.4万吨", "8人", "良好"],
        ["招商银行", "AA", "82.7", "12.3万吨", "22人", "优秀"],
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={
            "columns": ["公司名称", "ESG评级", "ESG得分", "碳排放", "独立董事(人)", "评估"],
            "rows": rows[:limit],
        },
        row_count=min(limit, len(rows)),
    )


def _gen_tender(key, name, query, limit) -> DataSourceResult:
    today = str(date.today())
    rows = [
        [f"2024-BJ-{1000 + i}", f"{query}相关采购项目{i + 1}", f"北京市{['海淀区', '朝阳区', '丰台区'][i % 3]}政府", f"{_stable_random(str(i), 50, 5000):.0f}万元", today, "公开招标"]
        for i in range(min(limit, 5))
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={"columns": ["招标编号", "项目名称", "采购单位", "预算金额", "发布日期", "采购方式"], "rows": rows},
        row_count=len(rows),
    )


def _gen_announcement(key, name, query, limit) -> DataSourceResult:
    today = str(date.today())
    rows = [
        ["600519", "贵州茅台", "2024-05-15", "重大合同公告", f"公司签署重要合作协议，涉及金额约5.2亿元"],
        ["000858", "五粮液", "2024-05-14", "股权激励计划", "拟向核心管理层授予限制性股票1500万股"],
        ["300750", "宁德时代", "2024-05-13", "定向增发公告", "拟非公开发行股票不超过5000万股"],
        ["601318", "中国平安", "2024-05-12", "年度分红公告", "每股派息0.98元，分红总额178亿元"],
        ["000001", "平安银行", "2024-05-10", "业绩预告", "预计一季度净利润同比增长约8%"],
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={"columns": ["股票代码", "公司名称", "公告日期", "公告类型", "摘要"], "rows": rows[:limit]},
        row_count=min(limit, len(rows)),
    )


def _gen_stock_hk(key, name, query, limit) -> DataSourceResult:
    rows = [
        ["0700", "腾讯控股", "358.20", "+1.45", "88234", "34521"],
        ["0941", "中国移动", "72.35", "-0.28", "23456", "14532"],
        ["1299", "友邦保险", "68.90", "+0.52", "12345", "9823"],
        ["0005", "汇丰控股", "58.45", "-0.67", "45678", "12345"],
        ["9988", "阿里巴巴", "73.60", "+2.13", "123456", "16789"],
    ]
    cols = ["代码", "名称", "最新价", "涨跌幅(%)", "成交额(万港元)", "市值(亿港元)"]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="financial",
        data={"columns": cols, "rows": rows[:limit], "market": "港股", "as_of": str(date.today())},
        row_count=min(limit, len(rows)),
    )


def _gen_stock_us(key, name, query, limit) -> DataSourceResult:
    rows = [
        ["AAPL", "苹果", "189.30", "+0.85", "4523456", "293450"],
        ["MSFT", "微软", "415.60", "+1.23", "2345678", "308920"],
        ["NVDA", "英伟达", "878.45", "+3.21", "5678901", "216780"],
        ["GOOGL", "谷歌", "175.20", "-0.43", "1234567", "218950"],
        ["TSLA", "特斯拉", "178.90", "-1.23", "3456789", "56920"],
    ]
    cols = ["代码", "名称", "最新价(USD)", "涨跌幅(%)", "成交量(股)", "市值(亿USD)"]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="financial",
        data={"columns": cols, "rows": rows[:limit], "market": "美股", "as_of": str(date.today())},
        row_count=min(limit, len(rows)),
    )


def _gen_pboc(key, name, query, limit) -> DataSourceResult:
    stats = {
        "indicator": "人民银行货币金融数据",
        "M2同比增速(2024-04)": "7.2%",
        "M1同比增速(2024-04)": "1.2%",
        "社会融资规模存量同比(2024-04)": "8.3%",
        "1年期LPR": "3.45%",
        "5年期以上LPR": "3.95%",
        "存款准备金率(大型银行)": "10.0%",
        "外汇储备(2024-04)": "32,005亿美元",
        "新增人民币贷款(2024-04)": "7300亿元",
        "社融月增量(2024-04)": "1.22万亿元",
    }
    return DataSourceResult(
        source_key=key, source_name=name, result_type="stats",
        data=stats, row_count=len(stats),
    )


def _gen_law(key, name, query, limit) -> DataSourceResult:
    rows = [
        [f"《{query}相关法律》", "全国人民代表大会", "2024-01-01", "现行有效", "https://example.com/law/1"],
        [f"《{query}实施条例》", "国务院", "2023-06-01", "现行有效", "https://example.com/law/2"],
        [f"《{query}管理办法》", "主管部门", "2022-09-01", "现行有效", "https://example.com/law/3"],
    ]
    return DataSourceResult(
        source_key=key, source_name=name, result_type="table",
        data={"columns": ["法规名称", "颁布机构", "施行日期", "效力状态", "全文链接"], "rows": rows[:limit]},
        row_count=min(limit, len(rows)),
    )


def _gen_industry(key, name, query, limit) -> DataSourceResult:
    stats = {
        "数据类型": name,
        "查询关键词": query,
        "数据周期": "2024年1-4月",
        "同比增速": f"{_stable_random(query + 'growth', -5.0, 15.0):.1f}%",
        "环比变化": f"{_stable_random(query + 'mom', -3.0, 5.0):.1f}%",
        "市场规模": f"{_stable_random(query + 'size', 100, 50000):.0f}亿元",
        "数据来源": f"{name}官方统计",
        "统计口径": "规模以上企业",
    }
    return DataSourceResult(
        source_key=key, source_name=name, result_type="stats",
        data=stats, row_count=len(stats),
    )


def _gen_health(key, name, query, limit) -> DataSourceResult:
    stats = {
        "数据类型": name,
        "查询关键词": query,
        "数据来源": "国家卫生健康委员会/WHO",
        "统计周期": "2023年度",
        "关键指标1": f"发病率：{_stable_random(query + 'rate', 10, 500):.1f}/10万",
        "关键指标2": f"治愈率：{_stable_random(query + 'cure', 60, 98):.1f}%",
        "覆盖地区": "全国31省市",
    }
    return DataSourceResult(
        source_key=key, source_name=name, result_type="stats",
        data=stats, row_count=len(stats),
    )


def _gen_edu(key, name, query, limit) -> DataSourceResult:
    stats = {
        "数据类型": name,
        "查询关键词": query,
        "数据来源": "教育部官方统计",
        "统计周期": "2023学年",
        "高校数量": "3013所",
        "在校生人数": "4763万人",
        "本科招生数": "472万人",
        "高职招生数": "543万人",
        "毕业生就业率": "91.6%",
        "生均教育经费": "3.28万元",
    }
    return DataSourceResult(
        source_key=key, source_name=name, result_type="stats",
        data=stats, row_count=len(stats),
    )


def _gen_generic(key, name, query, limit) -> DataSourceResult:
    stats = {
        "数据源": name,
        "查询关键词": query,
        "状态": "数据获取中（需配置API密钥）",
        "备注": "此数据源需要专用API接入，当前返回示意性数据。",
        "数据示例_2024": f"{_stable_random(query + '2024', 100, 10000):.1f}",
        "数据示例_2023": f"{_stable_random(query + '2023', 100, 10000):.1f}",
        "数据示例_2022": f"{_stable_random(query + '2022', 100, 10000):.1f}",
    }
    return DataSourceResult(
        source_key=key, source_name=name, result_type="stats",
        data=stats, row_count=len(stats),
    )


# ── Source name lookup ────────────────────────────────────────────────────────

_SOURCE_NAMES: dict[str, str] = {
    "fin_stock_cn": "中国A股行情数据",
    "fin_stock_hk": "港股行情数据",
    "fin_stock_us": "美股行情数据",
    "fin_futures": "期货与大宗商品数据",
    "fin_bond": "债券市场数据",
    "fin_fund": "公募基金净值数据",
    "fin_forex": "外汇汇率数据",
    "fin_annual_report": "上市公司年度报告",
    "fin_macro_cn": "中国宏观经济指标",
    "corp_registration": "工商注册与企业基本信息",
    "corp_judicial": "司法风险数据",
    "corp_esg": "企业ESG与社会责任报告",
    "corp_tender": "政府采购与招投标公告",
    "corp_announcement": "上市公司公告与披露",
    "gov_pboc": "人民银行货币金融数据",
    "gov_report_cn": "政府工作报告",
    "gov_policy_cn": "中央政策文件",
    "gov_ndrc": "国家发改委政策与规划",
    "gov_mof": "财政部财政数据",
    "gov_local_stats": "省市统计年鉴",
    "gov_customs_cn": "中国海关进出口数据",
    "law_statute_cn": "中国现行法律法规全文",
    "law_judicial_cn": "司法裁判文书",
    "law_regulation_cn": "部委规章与地方性法规",
    "law_compliance": "合规与监管政策",
    "industry_auto": "汽车行业数据",
    "industry_realestate": "房地产数据",
    "industry_energy": "能源数据",
    "industry_agri": "农业与粮食数据",
    "industry_pharma": "医药与医疗数据",
    "industry_retail": "零售与消费数据",
    "industry_logistics": "物流与运输数据",
    "industry_telecom": "通信与互联网数据",
    "health_disease": "疾病数据与流行病学",
    "health_drug": "药品说明与临床数据",
    "health_policy": "医疗卫生政策",
    "edu_stats_cn": "教育统计数据",
    "edu_policy": "教育政策与高考数据",
    "env_climate": "气候变化数据",
    "env_pollution": "环境质量数据",
    "env_carbon": "碳排放与双碳政策数据",
    "env_disaster": "自然灾害预警与历史数据",
    "intl_imf": "IMF世界经济展望数据",
    "intl_un_stats": "联合国统计数据库",
    "intl_trade": "全球贸易数据",
    "intl_geopolitics": "地缘政治与国际关系报告",
    "acad_pubmed": "PubMed生物医学文献",
    "acad_patent_cn": "中国专利数据库",
    "acad_ssrn": "社会科学研究网络",
    "news_financial": "财经新闻",
    "news_tech": "科技新闻",
    "news_international": "国际新闻",
    "news_sports": "体育新闻",
    "news_entertainment": "文娱新闻",
    "news_social": "社会民生新闻",
}

# ── Generator dispatch ────────────────────────────────────────────────────────

_GENERATORS: dict = {
    "fin_stock_cn": _gen_stock_cn,
    "fin_stock_hk": _gen_stock_hk,
    "fin_stock_us": _gen_stock_us,
    "fin_futures": _gen_futures,
    "fin_bond": _gen_bond,
    "fin_fund": _gen_fund,
    "fin_forex": _gen_forex,
    "fin_annual_report": _gen_annual_report,
    "fin_macro_cn": _gen_macro_cn,
    "corp_registration": _gen_corp_registration,
    "corp_judicial": _gen_corp_registration,   # same structure
    "corp_esg": _gen_esg,
    "corp_tender": _gen_tender,
    "corp_announcement": _gen_announcement,
    "gov_pboc": _gen_pboc,
    "gov_report_cn": _gen_generic,
    "gov_policy_cn": _gen_generic,
    "gov_ndrc": _gen_generic,
    "gov_mof": _gen_macro_cn,
    "gov_local_stats": _gen_macro_cn,
    "gov_customs_cn": _gen_macro_cn,
    "law_statute_cn": _gen_law,
    "law_judicial_cn": _gen_law,
    "law_regulation_cn": _gen_law,
    "law_compliance": _gen_law,
    "industry_auto": _gen_industry,
    "industry_realestate": _gen_industry,
    "industry_energy": _gen_industry,
    "industry_agri": _gen_industry,
    "industry_pharma": _gen_industry,
    "industry_retail": _gen_industry,
    "industry_logistics": _gen_industry,
    "industry_telecom": _gen_industry,
    "health_disease": _gen_health,
    "health_drug": _gen_health,
    "health_policy": _gen_health,
    "edu_stats_cn": _gen_edu,
    "edu_policy": _gen_edu,
    "env_climate": _gen_industry,
    "env_pollution": _gen_industry,
    "env_carbon": _gen_industry,
    "env_disaster": _gen_industry,
    "intl_imf": _gen_macro_cn,
    "intl_un_stats": _gen_macro_cn,
    "intl_trade": _gen_macro_cn,
    "intl_geopolitics": _gen_generic,
    "acad_pubmed": _gen_generic,
    "acad_patent_cn": _gen_generic,
    "acad_ssrn": _gen_generic,
    "news_financial": _gen_generic,
    "news_tech": _gen_generic,
    "news_international": _gen_generic,
    "news_sports": _gen_generic,
    "news_entertainment": _gen_generic,
    "news_social": _gen_generic,
}
