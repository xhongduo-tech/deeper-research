"""Data source configuration for automated knowledge base downloading.

All sources listed here are FREE and do NOT require API keys.
Sources requiring API keys are listed in docs/DATA_SOURCES.md section 四.

Directory layout after download:
  data/kb_sources/
    kb_001_gov_work_reports/
      metadata.json
      doc_001_2020.md
      doc_002_2021.md
    kb_002_stats_yearbook/
      metadata.json
      ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class SourceConfig:
    """Configuration for a single knowledge base data source."""

    kb_id: str
    name: str
    kb_type: str
    description: str
    source_url: str
    download_method: str  # crawl | rss | git | api_free | direct
    output_dir: str
    time_range: tuple[int, int] = (2020, 2026)
    file_pattern: str = "*.md"
    extra: dict = field(default_factory=dict)


# ── Phase 1: No-API sources (immediate start) ───────────────────────────────

PHASE1_SOURCES: list[SourceConfig] = [
    # ── 1. 政府与公共数据 (~200GB) ────────────────────────────────────────
    SourceConfig(
        kb_id="kb_001",
        name="政府工作报告",
        kb_type="policy",
        description="国务院政府工作报告全文（2020-2026）",
        source_url="https://www.gov.cn/guowuyuan/zfgzbg.htm",
        download_method="crawl",
        output_dir="data/kb_sources/kb_001_gov_work_reports",
        time_range=(1954, 2026),
        extra={"base_url": "https://www.gov.cn", "list_url_pattern": "/guowuyuan/zfgzbg_{year}.htm"},
    ),
    SourceConfig(
        kb_id="kb_002",
        name="各省市统计年鉴",
        kb_type="statistics",
        description="重点省份统计年鉴（2020-2025）",
        source_url="https://www.stats.gov.cn/sj/ndsj/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_002_stats_yearbook",
        time_range=(2020, 2025),
        extra={"provinces": ["北京", "上海", "广东", "江苏", "浙江"]},
    ),
    SourceConfig(
        kb_id="kb_003",
        name="国民经济统计公报",
        kb_type="statistics",
        description="国家统计局年度/季度统计公报",
        source_url="https://www.stats.gov.cn/sj/zxfb/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_003_national_stats",
        time_range=(2020, 2026),
    ),
    SourceConfig(
        kb_id="kb_004",
        name="央行货币政策报告",
        kb_type="finance",
        description="中国人民银行货币政策执行报告",
        source_url="https://www.pbc.gov.cn/zhengcehuobisi/11140/index.html",
        download_method="crawl",
        output_dir="data/kb_sources/kb_004_pbc_monetary",
        time_range=(2020, 2026),
        extra={"quarterly": True},
    ),
    SourceConfig(
        kb_id="kb_005",
        name="财政部预算报告",
        kb_type="finance",
        description="中央和地方预算执行情况",
        source_url="https://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_005_mof_budget",
        time_range=(2020, 2026),
    ),
    SourceConfig(
        kb_id="kb_006",
        name="海关总署数据",
        kb_type="trade",
        description="海关总署统计月报/年报",
        source_url="https://www.customs.gov.cn/customs/302249/zfxxgk/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_006_customs_data",
        time_range=(2020, 2026),
    ),
    SourceConfig(
        kb_id="kb_007",
        name="发改委政策",
        kb_type="policy",
        description="国家发改委政策文件",
        source_url="https://www.ndrc.gov.cn/xxgk/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_007_ndrc_policy",
        time_range=(2020, 2026),
    ),

    # ── 2. 法律法规 (~150GB) ──────────────────────────────────────────────
    SourceConfig(
        kb_id="kb_008",
        name="宪法与基本法律",
        kb_type="law",
        description="中华人民共和国宪法及基本法律",
        source_url="https://www.npc.gov.cn/npc/c2/c30834/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_008_constitution",
        time_range=(1949, 2026),
    ),
    SourceConfig(
        kb_id="kb_009",
        name="行政法规",
        kb_type="law",
        description="国务院行政法规",
        source_url="https://www.gov.cn/zhengce/xxgk/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_009_admin_regulations",
        time_range=(2020, 2026),
    ),
    SourceConfig(
        kb_id="kb_010",
        name="司法解释",
        kb_type="law",
        description="最高人民法院/最高检司法解释",
        source_url="https://www.court.gov.cn/zixun-gengduo-104.html",
        download_method="crawl",
        output_dir="data/kb_sources/kb_010_judicial_interp",
        time_range=(2020, 2026),
    ),
    SourceConfig(
        kb_id="kb_011",
        name="金融监管规章",
        kb_type="law",
        description="国家金融监督管理总局规章",
        source_url="https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html",
        download_method="crawl",
        output_dir="data/kb_sources/kb_011_finance_regulations",
        time_range=(2020, 2026),
    ),

    # ── 3. 新闻与舆情 (~200GB) ────────────────────────────────────────────
    SourceConfig(
        kb_id="kb_012",
        name="财经新闻",
        kb_type="news",
        description="财经领域新闻聚合",
        source_url="https://finance.sina.com.cn/",
        download_method="rss",
        output_dir="data/kb_sources/kb_012_finance_news",
        time_range=(2020, 2026),
        extra={"rss_urls": [
            "https://rss.sina.com.cn/finance/financelist.xml",
        ]},
    ),
    SourceConfig(
        kb_id="kb_013",
        name="科技新闻",
        kb_type="news",
        description="科技领域新闻聚合",
        source_url="https://www.ithome.com/",
        download_method="rss",
        output_dir="data/kb_sources/kb_013_tech_news",
        time_range=(2020, 2026),
        extra={"rss_urls": [
            "https://www.ithome.com/rss/",
        ]},
    ),
    SourceConfig(
        kb_id="kb_014",
        name="政治时事",
        kb_type="news",
        description="政治时事新闻",
        source_url="http://www.xinhuanet.com/",
        download_method="rss",
        output_dir="data/kb_sources/kb_014_political_news",
        time_range=(2020, 2026),
        extra={"rss_urls": [
            "http://www.people.com.cn/rss/politics.xml",
            "https://www.chinanews.com/rss/politics.xml",
        ]},
    ),

    # ── 4. 学术论文 — ArXiv / PubMed (免费API) ────────────────────────────
    SourceConfig(
        kb_id="kb_015",
        name="ArXiv CS AI ML",
        kb_type="academic",
        description="ArXiv 计算机科学/AI/机器学习论文",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="data/kb_sources/kb_015_arxiv_cs_ai",
        time_range=(2020, 2026),
        extra={"categories": ["cs.AI", "cs.CL", "cs.LG", "cs.CV"], "max_results": 5000},
    ),
    SourceConfig(
        kb_id="kb_016",
        name="ArXiv 其他子类",
        kb_type="academic",
        description="ArXiv 数学/物理/其他子类",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="data/kb_sources/kb_016_arxiv_others",
        time_range=(2020, 2026),
        extra={"categories": ["math", "physics", "cs.SE", "cs.DB"], "max_results": 5000},
    ),
    SourceConfig(
        kb_id="kb_017",
        name="PubMed生物医学",
        kb_type="academic",
        description="PubMed 高影响力生物医学论文摘要",
        source_url="https://pubmed.ncbi.nlm.nih.gov/",
        download_method="api_free",
        output_dir="data/kb_sources/kb_017_pubmed",
        time_range=(2020, 2026),
        extra={"search_terms": ["machine learning", "artificial intelligence", "drug discovery"], "max_results": 20000},
    ),
    SourceConfig(
        kb_id="kb_018",
        name="经济学与金融学工作论文(ArXiv替代)",
        kb_type="academic",
        description="ArXiv q-fin/econ 类别经济学/金融学论文(替代SSRN)",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="data/kb_sources/kb_018_ssrn",
        time_range=(2020, 2026),
        extra={"categories": ["q-fin.GN", "q-fin.PM", "q-fin.RM"], "max_results": 3000},
    ),

    # ── 5. 代码知识 (~600GB) ──────────────────────────────────────────────
    SourceConfig(
        kb_id="kb_019",
        name="Python官方文档",
        kb_type="code",
        description="Python 官方文档全版本",
        source_url="https://docs.python.org/3/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_019_python_docs",
        extra={"versions": ["3.8", "3.9", "3.10", "3.11", "3.12"]},
    ),
    SourceConfig(
        kb_id="kb_020",
        name="PyTorch文档",
        kb_type="code",
        description="PyTorch 官方文档",
        source_url="https://pytorch.org/docs/stable/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_020_pytorch_docs",
    ),
    SourceConfig(
        kb_id="kb_021",
        name="React文档",
        kb_type="code",
        description="React 官方文档",
        source_url="https://react.dev/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_021_react_docs",
    ),
    SourceConfig(
        kb_id="kb_022",
        name="Vue文档",
        kb_type="code",
        description="Vue.js 官方文档",
        source_url="https://vuejs.org/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_022_vue_docs",
    ),
    SourceConfig(
        kb_id="kb_023",
        name="Go官方文档",
        kb_type="code",
        description="Go 官方文档",
        source_url="https://go.dev/doc/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_023_go_docs",
    ),
    SourceConfig(
        kb_id="kb_024",
        name="Rust官方文档",
        kb_type="code",
        description="Rust 官方文档",
        source_url="https://doc.rust-lang.org/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_024_rust_docs",
    ),
    SourceConfig(
        kb_id="kb_025",
        name="优质GitHub仓库",
        kb_type="code",
        description="精选GitHub开源项目文档和源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="data/kb_sources/kb_025_github_repos",
        extra={"repos": [
            "microsoft/vscode",
            "tensorflow/tensorflow",
            "facebook/react",
            "golang/go",
            "rust-lang/rust",
            "python/cpython",
        ]},
    ),
    SourceConfig(
        kb_id="kb_026",
        name="LeetCode题解",
        kb_type="code",
        description="LeetCode 算法题解",
        source_url="https://leetcode.cn/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_026_leetcode",
    ),
    SourceConfig(
        kb_id="kb_027",
        name="OWASP安全规范",
        kb_type="code",
        description="OWASP 安全标准和指南",
        source_url="https://owasp.org/www-project-top-ten/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_027_owasp",
    ),

    # ── 6. 数学知识 (~300GB) ──────────────────────────────────────────────
    SourceConfig(
        kb_id="kb_028",
        name="数学教材",
        kb_type="math",
        description="公开数学教材和讲义",
        source_url="https://ocw.mit.edu/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_028_math_textbooks",
        extra={"courses": ["18.01", "18.02", "18.03", "18.06"]},
    ),
    SourceConfig(
        kb_id="kb_029",
        name="离散数学",
        kb_type="math",
        description="离散数学课程资料",
        source_url="https://ocw.mit.edu/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_029_discrete_math",
    ),
    SourceConfig(
        kb_id="kb_030",
        name="统计学习",
        kb_type="math",
        description="统计学习方法和教材",
        source_url="https://web.stanford.edu/~hastie/ElemStatLearn/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_030_statistical_learning",
    ),

    # ── 7. 国际机构 (~150GB) ──────────────────────────────────────────────
    SourceConfig(
        kb_id="kb_031",
        name="世界银行数据",
        kb_type="intl",
        description="世界银行开放数据",
        source_url="https://data.worldbank.org/",
        download_method="api_free",
        output_dir="data/kb_sources/kb_031_world_bank",
        time_range=(1960, 2026),
    ),
    SourceConfig(
        kb_id="kb_032",
        name="IMF报告",
        kb_type="intl",
        description="国际货币基金组织报告",
        source_url="https://www.imf.org/en/Publications/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_032_imf_reports",
        time_range=(1980, 2026),
    ),
    SourceConfig(
        kb_id="kb_033",
        name="联合国数据",
        kb_type="intl",
        description="联合国公开数据集",
        source_url="https://data.un.org/",
        download_method="api_free",
        output_dir="data/kb_sources/kb_033_un_data",
        time_range=(2000, 2026),
    ),
    SourceConfig(
        kb_id="kb_034",
        name="WTO贸易数据",
        kb_type="intl",
        description="世界贸易组织数据",
        source_url="https://www.wto.org/english/res_e/statis_e/trade_stats_e.htm",
        download_method="crawl",
        output_dir="data/kb_sources/kb_034_wto_data",
        time_range=(2000, 2026),
    ),

    # ── 8. 金融/银行/数据中台 行业深度数据 ────────────────────────────────
    SourceConfig(
        kb_id="kb_035",
        name="银行业监管政策",
        kb_type="finance",
        description="银行业监管政策和指引（2018-2026）",
        source_url="https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html",
        download_method="crawl",
        output_dir="data/kb_sources/kb_035_banking_regulation",
        time_range=(2018, 2026),
    ),
    SourceConfig(
        kb_id="kb_036",
        name="金融科技发展报告",
        kb_type="finance",
        description="金融科技与数字银行报告",
        source_url="https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html",
        download_method="crawl",
        output_dir="data/kb_sources/kb_036_fintech",
        time_range=(2020, 2026),
    ),
    SourceConfig(
        kb_id="kb_037",
        name="数据中台建设指南",
        kb_type="tech",
        description="数据中台、数据治理相关白皮书和指南",
        source_url="https://www.caict.ac.cn/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_037_data_platform",
        time_range=(2020, 2026),
    ),
    SourceConfig(
        kb_id="kb_038",
        name="数字化转型政策",
        kb_type="policy",
        description="各行业数字化转型政策文件",
        source_url="https://www.gov.cn/zhengce/",
        download_method="crawl",
        output_dir="data/kb_sources/kb_038_digital_transform",
        time_range=(2020, 2026),
    ),

    # ── Phase 2: Tushare Pro 金融数据（需API）───────────────────────────────
    SourceConfig(
        kb_id="kb_039",
        name="A股行情数据",
        kb_type="finance",
        description="A股日线行情、基础信息、指数数据（2020-2026）",
        source_url="https://tushare.pro",
        download_method="api_free",
        output_dir="data/kb_sources/kb_039_a_share",
        time_range=(2020, 2026),
        extra={"provider": "tushare", "data_type": "stock_daily"},
    ),
    SourceConfig(
        kb_id="kb_040",
        name="宏观经济指标",
        kb_type="finance",
        description="GDP、CPI、PPI、货币供应量等宏观数据",
        source_url="https://tushare.pro",
        download_method="api_free",
        output_dir="data/kb_sources/kb_040_macro_econ",
        time_range=(2020, 2026),
        extra={"provider": "tushare", "data_type": "macro"},
    ),
    SourceConfig(
        kb_id="kb_041",
        name="公募基金净值",
        kb_type="finance",
        description="公募基金基础信息和净值数据",
        source_url="https://tushare.pro",
        download_method="api_free",
        output_dir="data/kb_sources/kb_041_fund_nav",
        time_range=(2020, 2026),
        extra={"provider": "tushare", "data_type": "fund"},
    ),
]


def get_source_by_id(kb_id: str) -> SourceConfig | None:
    for s in PHASE1_SOURCES:
        if s.kb_id == kb_id:
            return s
    return None


def list_sources_by_type(kb_type: str) -> list[SourceConfig]:
    return [s for s in PHASE1_SOURCES if s.kb_type == kb_type]
