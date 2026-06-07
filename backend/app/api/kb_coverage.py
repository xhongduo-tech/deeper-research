"""Knowledge base coverage analysis and network graph data API.

Provides endpoints for:
- Gap analysis between planned and actual KBs
- Network graph visualization data
- Domain coverage metrics
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── Planned KB taxonomy (from the 315 KB plan) ───────────────────────────────

@dataclass
class PlannedDomain:
    name: str
    en_name: str
    color: str
    planned_kbs: int
    planned_docs: int
    planned_size_gb: float
    subdomains: list[dict] = field(default_factory=list)


# Domain taxonomy matching the plan document
PLANNED_DOMAINS: list[PlannedDomain] = [
    PlannedDomain(
        name="政府与公共数据", en_name="Government & Public Data",
        color="#2563eb", planned_kbs=35, planned_docs=5000, planned_size_gb=200,
        subdomains=[
            {"name": "政府工作报告", "planned_kbs": 5, "sources": ["国务院官网"], "key_apis": ["gov.cn crawling"]},
            {"name": "省市统计年鉴", "planned_kbs": 5, "sources": ["各省市统计局"], "key_apis": ["stats.gov.cn crawling"]},
            {"name": "国民经济统计公报", "planned_kbs": 5, "sources": ["国家统计局"], "key_apis": ["stats.gov.cn crawling"]},
            {"name": "央行货币政策", "planned_kbs": 5, "sources": ["中国人民银行"], "key_apis": ["pbc.gov.cn crawling"]},
            {"name": "财政部预算报告", "planned_kbs": 5, "sources": ["财政部"], "key_apis": ["mof.gov.cn crawling"]},
            {"name": "海关总署数据", "planned_kbs": 5, "sources": ["海关总署"], "key_apis": ["customs.gov.cn crawling"]},
            {"name": "发改委政策", "planned_kbs": 5, "sources": ["国家发改委"], "key_apis": ["ndrc.gov.cn crawling"]},
        ],
    ),
    PlannedDomain(
        name="法律法规", en_name="Laws & Regulations",
        color="#7c3aed", planned_kbs=25, planned_docs=10000, planned_size_gb=150,
        subdomains=[
            {"name": "宪法与基本法律", "planned_kbs": 5, "sources": ["全国人大"], "key_apis": ["npc.gov.cn crawling"]},
            {"name": "行政法规", "planned_kbs": 5, "sources": ["国务院"], "key_apis": ["gov.cn policy crawling"]},
            {"name": "司法解释", "planned_kbs": 5, "sources": ["最高法/最高检"], "key_apis": ["court.gov.cn crawling"]},
            {"name": "金融监管规章", "planned_kbs": 5, "sources": ["金融监管总局"], "key_apis": ["nfra.gov.cn crawling"]},
            {"name": "地方法规", "planned_kbs": 5, "sources": ["各省市人大"], "key_apis": ["local gov crawling"]},
        ],
    ),
    PlannedDomain(
        name="新闻与舆情", en_name="News & Sentiment",
        color="#059669", planned_kbs=15, planned_docs=50000, planned_size_gb=200,
        subdomains=[
            {"name": "财经新闻", "planned_kbs": 5, "sources": ["新浪财经 RSS"], "key_apis": ["RSS feeds"]},
            {"name": "科技新闻", "planned_kbs": 5, "sources": ["IT之家 RSS"], "key_apis": ["RSS feeds"]},
            {"name": "政治时事", "planned_kbs": 5, "sources": ["新华网 RSS"], "key_apis": ["RSS feeds"]},
        ],
    ),
    PlannedDomain(
        name="学术论文", en_name="Academic Papers",
        color="#d97706", planned_kbs=50, planned_docs=50000, planned_size_gb=500,
        subdomains=[
            {"name": "计算机科学", "planned_kbs": 12, "sources": ["ArXiv CS"], "key_apis": ["ArXiv API (free)"]},
            {"name": "生物医学", "planned_kbs": 10, "sources": ["PubMed"], "key_apis": ["PubMed E-utilities (free)"]},
            {"name": "材料科学", "planned_kbs": 5, "sources": ["ArXiv cond-mat"], "key_apis": ["ArXiv API (free)"]},
            {"name": "经济学", "planned_kbs": 10, "sources": ["ArXiv q-fin"], "key_apis": ["ArXiv API (free)"]},
            {"name": "环境科学", "planned_kbs": 5, "sources": ["ArXiv physics"], "key_apis": ["ArXiv API (free)"]},
            {"name": "数学论文", "planned_kbs": 8, "sources": ["ArXiv math"], "key_apis": ["ArXiv API (free)"]},
        ],
    ),
    PlannedDomain(
        name="代码知识", en_name="Code Knowledge",
        color="#0891b2", planned_kbs=40, planned_docs=100000, planned_size_gb=600,
        subdomains=[
            {"name": "编程语言文档", "planned_kbs": 8, "sources": ["Python/Go/Rust官方"], "key_apis": ["wget mirror crawling"]},
            {"name": "框架与库文档", "planned_kbs": 8, "sources": ["PyTorch/React/Vue"], "key_apis": ["wget mirror crawling"]},
            {"name": "算法与数据结构", "planned_kbs": 6, "sources": ["LeetCode"], "key_apis": ["leetcode.cn crawling"]},
            {"name": "系统与架构", "planned_kbs": 6, "sources": ["微服务/云原生"], "key_apis": ["GitHub + docs"]},
            {"name": "数据库文档", "planned_kbs": 6, "sources": ["MySQL/PostgreSQL/MongoDB"], "key_apis": ["wget mirror crawling"]},
            {"name": "安全规范", "planned_kbs": 6, "sources": ["OWASP"], "key_apis": ["owasp.org crawling"]},
        ],
    ),
    PlannedDomain(
        name="数学知识", en_name="Mathematics",
        color="#dc2626", planned_kbs=25, planned_docs=20000, planned_size_gb=300,
        subdomains=[
            {"name": "基础数学", "planned_kbs": 5, "sources": ["MIT OCW"], "key_apis": ["ocw.mit.edu crawling"]},
            {"name": "离散数学", "planned_kbs": 4, "sources": ["MIT OCW"], "key_apis": ["ocw.mit.edu crawling"]},
            {"name": "应用数学", "planned_kbs": 5, "sources": ["Stanford ESL"], "key_apis": ["stanford.edu crawling"]},
            {"name": "统计与机器学习", "planned_kbs": 5, "sources": ["教材与讲义"], "key_apis": ["open courseware"]},
            {"name": "数学史与科普", "planned_kbs": 3, "sources": ["公开出版物"], "key_apis": ["Project Gutenberg"]},
            {"name": "数学工具", "planned_kbs": 3, "sources": ["MATLAB/SageMath"], "key_apis": ["official docs"]},
        ],
    ),
    PlannedDomain(
        name="书籍与教材", en_name="Books & Textbooks",
        color="#9333ea", planned_kbs=35, planned_docs=15000, planned_size_gb=500,
        subdomains=[
            {"name": "计算机技术书籍", "planned_kbs": 8, "sources": ["经典教材"], "key_apis": ["Project Gutenberg", "Open Library"]},
            {"name": "经济与金融书籍", "planned_kbs": 6, "sources": ["经济学教材"], "key_apis": ["Project Gutenberg"]},
            {"name": "科学与工程书籍", "planned_kbs": 6, "sources": ["科学教材"], "key_apis": ["Open Textbook Library"]},
            {"name": "管理与商业书籍", "planned_kbs": 5, "sources": ["MBA教材"], "key_apis": ["Open Library"]},
            {"name": "人文社科书籍", "planned_kbs": 5, "sources": ["人文经典"], "key_apis": ["Project Gutenberg"]},
            {"name": "法律教材", "planned_kbs": 3, "sources": ["法律教材"], "key_apis": ["open access books"]},
            {"name": "语言学习", "planned_kbs": 2, "sources": ["语言教材"], "key_apis": ["open access"]},
        ],
    ),
    PlannedDomain(
        name="国际与全球", en_name="International & Global",
        color="#ea580c", planned_kbs=30, planned_docs=5000, planned_size_gb=150,
        subdomains=[
            {"name": "世界银行数据", "planned_kbs": 5, "sources": ["World Bank"], "key_apis": ["World Bank API (free)"]},
            {"name": "IMF报告", "planned_kbs": 5, "sources": ["IMF"], "key_apis": ["imf.org crawling"]},
            {"name": "联合国数据", "planned_kbs": 5, "sources": ["UN Data"], "key_apis": ["data.un.org API"]},
            {"name": "国际贸易", "planned_kbs": 5, "sources": ["WTO"], "key_apis": ["wto.org crawling"]},
            {"name": "地缘政治", "planned_kbs": 10, "sources": ["智库报告"], "key_apis": ["think tank reports"]},
        ],
    ),
    PlannedDomain(
        name="行业深度数据", en_name="Industry Deep Data",
        color="#0d9488", planned_kbs=80, planned_docs=15000, planned_size_gb=600,
        subdomains=[
            {"name": "汽车行业", "planned_kbs": 8, "sources": ["中汽协/工信部"], "key_apis": ["caam.org.cn"]},
            {"name": "房地产", "planned_kbs": 8, "sources": ["住建部/统计局"], "key_apis": ["gov.cn crawling"]},
            {"name": "能源行业", "planned_kbs": 8, "sources": ["能源局"], "key_apis": ["nea.gov.cn"]},
            {"name": "医药行业", "planned_kbs": 8, "sources": ["药监局/NMPA"], "key_apis": ["nmpa.gov.cn"]},
            {"name": "金融行业", "planned_kbs": 10, "sources": ["证监会/交易所"], "key_apis": ["csrc.gov.cn", "AkShare"]},
            {"name": "科技行业", "planned_kbs": 10, "sources": ["工信部/科技部"], "key_apis": ["gov.cn crawling"]},
            {"name": "消费零售", "planned_kbs": 8, "sources": ["商务部"], "key_apis": ["mofcom.gov.cn"]},
            {"name": "制造业", "planned_kbs": 10, "sources": ["工信部"], "key_apis": ["gov.cn crawling"]},
            {"name": "物流交通", "planned_kbs": 10, "sources": ["交通运输部"], "key_apis": ["mot.gov.cn"]},
        ],
    ),
]


# ── Actual downloaded KB mapping ─────────────────────────────────────────────

# Maps kb_id -> (domain_name, subdomain_name, actual_info)
ACTUAL_KB_MAP: dict[str, tuple[str, str, dict]] = {
    "kb_001": ("政府与公共数据", "政府工作报告", {"files": 1, "size_mb": 0.004}),
    "kb_002": ("政府与公共数据", "省市统计年鉴", {"files": 12, "size_mb": 0.332}),
    "kb_003": ("政府与公共数据", "国民经济统计公报", {"files": 1, "size_mb": 0.004}),
    "kb_004": ("政府与公共数据", "央行货币政策", {"files": 13, "size_mb": 1.9}),
    "kb_005": ("政府与公共数据", "财政部预算报告", {"files": 13, "size_mb": 1.9}),
    "kb_006": ("政府与公共数据", "海关总署数据", {"files": 1, "size_mb": 0.004}),
    "kb_007": ("政府与公共数据", "发改委政策", {"files": 10, "size_mb": 0.128}),
    "kb_008": ("法律法规", "宪法与基本法律", {"files": 1, "size_mb": 0.004}),
    "kb_009": ("法律法规", "行政法规", {"files": 23, "size_mb": 1.5}),
    "kb_010": ("法律法规", "司法解释", {"files": 6, "size_mb": 0.08}),
    "kb_011": ("法律法规", "金融监管规章", {"files": 4, "size_mb": 0.02}),
    "kb_012": ("新闻与舆情", "财经新闻", {"files": 1, "size_mb": 0.004}),
    "kb_013": ("新闻与舆情", "科技新闻", {"files": 61, "size_mb": 0.76}),
    "kb_014": ("新闻与舆情", "政治时事", {"files": 1, "size_mb": 0.004}),
    "kb_015": ("学术论文", "计算机科学", {"files": 1001, "size_mb": 3.9}),
    "kb_016": ("学术论文", "计算机科学", {"files": 4890, "size_mb": 19}),
    "kb_017": ("学术论文", "生物医学", {"files": 17499, "size_mb": 69}),
    "kb_018": ("学术论文", "经济学", {"files": 2973, "size_mb": 12}),
    "kb_019": ("代码知识", "编程语言文档", {"files": 1109, "size_mb": 153}),
    "kb_020": ("代码知识", "框架与库文档", {"files": 4, "size_mb": 0.016}),
    "kb_021": ("代码知识", "框架与库文档", {"files": 949, "size_mb": 93}),
    "kb_022": ("代码知识", "框架与库文档", {"files": 348, "size_mb": 18}),
    "kb_023": ("代码知识", "编程语言文档", {"files": 380, "size_mb": 13}),
    "kb_024": ("代码知识", "编程语言文档", {"files": 155, "size_mb": 27}),
    "kb_025": ("代码知识", "系统与架构", {"files": 28217, "size_mb": 584}),
    "kb_026": ("代码知识", "算法与数据结构", {"files": 224, "size_mb": 13}),
    "kb_027": ("代码知识", "安全规范", {"files": 139, "size_mb": 4.8}),
    "kb_028": ("数学知识", "基础数学", {"files": 29, "size_mb": 0.76}),
    "kb_029": ("数学知识", "离散数学", {"files": 29, "size_mb": 0.76}),
    "kb_030": ("数学知识", "统计与机器学习", {"files": 1, "size_mb": 0.004}),
    "kb_031": ("国际与全球", "世界银行数据", {"files": 26, "size_mb": 4.2}),
    "kb_032": ("国际与全球", "IMF报告", {"files": 1, "size_mb": 0.004}),
    "kb_033": ("国际与全球", "联合国数据", {"files": 4, "size_mb": 0.04}),
    "kb_034": ("国际与全球", "国际贸易", {"files": 26, "size_mb": 0.4}),
    "kb_035": ("行业深度数据", "金融行业", {"files": 13, "size_mb": 1.9}),
    "kb_036": ("行业深度数据", "金融行业", {"files": 13, "size_mb": 1.9}),
    "kb_037": ("行业深度数据", "科技行业", {"files": 1, "size_mb": 0.004}),
    "kb_038": ("行业深度数据", "消费零售", {"files": 20, "size_mb": 0.584}),
    "kb_039": ("行业深度数据", "金融行业", {"files": 13, "size_mb": 1.9}),
    "kb_040": ("行业深度数据", "金融行业", {"files": 15, "size_mb": 0.26}),
    "kb_041": ("行业深度数据", "金融行业", {"files": 5, "size_mb": 5.1}),
}


# ── Missing APIs / Data sources with alternatives ────────────────────────────

MISSING_SOURCES: list[dict] = [
    {
        "category": "政府与公共数据",
        "missing": [
            {"source": "国家统计局PDF年报", "issue": "仅爬取到HTML列表页，未下载PDF全文", "alternative": "使用 wget --accept=pdf 批量下载统计局PDF", "effort": "低"},
            {"source": "海关总署统计月报", "issue": "仅爬取到目录页", "alternative": "使用 AkShare 获取海关贸易数据", "effort": "中"},
        ],
    },
    {
        "category": "法律法规",
        "missing": [
            {"source": "国家法律法规数据库", "issue": "需要登录才能下载全文", "alternative": "使用北大法宝/无讼网公开接口", "effort": "高"},
            {"source": "地方法规", "issue": "未配置任何省市法规源", "alternative": "使用国家法律法规数据库地方法规频道", "effort": "中"},
        ],
    },
    {
        "category": "学术论文",
        "missing": [
            {"source": "SSRN经济学论文", "issue": "无免费批量API", "alternative": "已替换为 ArXiv q-fin", "effort": "已完成"},
            {"source": "NBER工作论文", "issue": "需要订阅", "alternative": "使用 RePEc/IDEAS 开放论文库", "effort": "中"},
            {"source": "IEEE/Xplore论文", "issue": "需要机构订阅", "alternative": "使用 Semantic Scholar API（免费）", "effort": "中"},
            {"source": "CNKI中文论文", "issue": "需要付费订阅", "alternative": "使用 万方/维普开放接口或学位论文库", "effort": "高"},
        ],
    },
    {
        "category": "代码知识",
        "missing": [
            {"source": "Java/Spring官方文档", "issue": "未配置", "alternative": "wget mirror spring.io/docs", "effort": "低"},
            {"source": "C++官方文档", "issue": "未配置", "alternative": "wget mirror cppreference.com", "effort": "低"},
            {"source": "Node.js官方文档", "issue": "未配置", "alternative": "wget mirror nodejs.org/docs", "effort": "低"},
            {"source": "Docker/K8s文档", "issue": "未配置", "alternative": "wget mirror kubernetes.io/docs", "effort": "低"},
            {"source": "TensorFlow官方文档", "issue": "未配置", "alternative": "wget mirror tensorflow.org", "effort": "低"},
            {"source": "全量GitHub源码", "issue": "仅下载了README", "alternative": "使用 ghrepo 批量克隆 + 源码解析", "effort": "高"},
        ],
    },
    {
        "category": "数学知识",
        "missing": [
            {"source": "MIT OCW数学课程", "issue": "wget被反爬，仅下载了少量文件", "alternative": "使用 OCW 官方批量下载包", "effort": "中"},
            {"source": "数学教材全文", "issue": "版权限制", "alternative": "使用 OpenStax 免费教材（开放授权）", "effort": "低"},
            {"source": "arXiv math论文", "issue": "未配置", "alternative": "扩展 ArXiv 下载器到 math 类别", "effort": "低"},
        ],
    },
    {
        "category": "书籍与教材",
        "missing": [
            {"source": "技术书籍全文", "issue": "版权限制，无法批量获取", "alternative": "1) Project Gutenberg 公版书\n2) Open Library API\n3) Internet Archive 开放借阅", "effort": "中"},
            {"source": "计算机经典教材", "issue": "版权限制", "alternative": "使用作者公开的 draft 版本或 lecture notes", "effort": "中"},
        ],
    },
    {
        "category": "行业深度数据",
        "missing": [
            {"source": "行业协会报告", "issue": "仅覆盖金融/科技，其他7个行业未配置", "alternative": "使用各行业协会官网公开报告", "effort": "高"},
            {"source": "上市公司年报", "issue": "未配置", "alternative": "使用巨潮资讯网/AkShare批量下载", "effort": "中"},
            {"source": "专利数据", "issue": "未配置", "alternative": "使用 Google Patents 批量下载或 CNIPA 开放数据", "effort": "高"},
            {"source": "招投标数据", "issue": "未配置", "alternative": "使用中国政府采购网/各省市公共资源交易中心", "effort": "中"},
            {"source": "ESG报告", "issue": "未配置", "alternative": "使用交易所强制披露页面", "effort": "中"},
        ],
    },
    {
        "category": "国际与全球",
        "missing": [
            {"source": "IMF WEO报告PDF", "issue": "仅爬取到目录页", "alternative": "wget 直接下载 IMF 报告PDF", "effort": "低"},
            {"source": "联合国SDG数据", "issue": "未配置", "alternative": "使用 UN Data API", "effort": "低"},
            {"source": "地缘政治报告", "issue": "未配置", "alternative": "使用 CRS Report（美国国会研究处开放报告）", "effort": "中"},
        ],
    },
]


# ── Scan actual filesystem ───────────────────────────────────────────────────

def scan_kb_filesystem() -> dict[str, dict]:
    """Scan data/kb_sources for actual file counts and sizes."""
    # Try current dir first, then parent (for when running from backend/)
    for rel in ["data/kb_sources", "../data/kb_sources"]:
        base = Path(rel)
        if base.exists():
            break
    else:
        return {}

    result: dict[str, dict] = {}
    for kb_dir in base.iterdir():
        if not kb_dir.is_dir():
            continue
        kb_id = kb_dir.name.split("_")[0] + "_" + kb_dir.name.split("_")[1] if "_" in kb_dir.name else kb_dir.name
        files = list(kb_dir.rglob("*"))
        file_count = len([f for f in files if f.is_file()])
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        md_count = len([f for f in files if f.is_file() and f.suffix == ".md"])
        result[kb_id] = {
            "file_count": file_count,
            "md_count": md_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
        }
    return result


def compute_coverage() -> dict[str, Any]:
    """Compute coverage metrics for all domains."""
    actual = scan_kb_filesystem()

    # Aggregate by domain
    domain_actuals: dict[str, dict] = {}
    for kb_id, info in actual.items():
        mapped = ACTUAL_KB_MAP.get(kb_id)
        if not mapped:
            continue
        domain_name, subdomain_name, extra = mapped
        if domain_name not in domain_actuals:
            domain_actuals[domain_name] = {
                "kbs": 0, "files": 0, "size_mb": 0, "subdomains": {},
            }
        d = domain_actuals[domain_name]
        d["kbs"] += 1
        d["files"] += info["file_count"]
        d["size_mb"] += info["total_size_mb"]
        if subdomain_name not in d["subdomains"]:
            d["subdomains"][subdomain_name] = {"kbs": 0, "files": 0, "size_mb": 0}
        d["subdomains"][subdomain_name]["kbs"] += 1
        d["subdomains"][subdomain_name]["files"] += info["file_count"]
        d["subdomains"][subdomain_name]["size_mb"] += info["total_size_mb"]

    # Build domain coverage list
    total_planned_kbs = sum(d.planned_kbs for d in PLANNED_DOMAINS)
    total_planned_docs = sum(d.planned_docs for d in PLANNED_DOMAINS)
    total_planned_gb = sum(d.planned_size_gb for d in PLANNED_DOMAINS)
    total_actual_kbs = sum(d["kbs"] for d in domain_actuals.values())
    total_actual_files = sum(d["files"] for d in domain_actuals.values())
    total_actual_mb = sum(d["size_mb"] for d in domain_actuals.values())

    domains = []
    for pd in PLANNED_DOMAINS:
        actual_d = domain_actuals.get(pd.name, {"kbs": 0, "files": 0, "size_mb": 0, "subdomains": {}})
        kb_coverage = round(actual_d["kbs"] / pd.planned_kbs * 100, 1) if pd.planned_kbs else 0
        doc_coverage = round(actual_d["files"] / pd.planned_docs * 100, 1) if pd.planned_docs else 0
        size_coverage = round(actual_d["size_mb"] / (pd.planned_size_gb * 1024) * 100, 1) if pd.planned_size_gb else 0

        # Coverage score is weighted average
        coverage_score = round((kb_coverage * 0.3 + doc_coverage * 0.3 + size_coverage * 0.4), 1)

        subdomains = []
        for sd in pd.subdomains:
            sd_actual = actual_d["subdomains"].get(sd["name"], {"kbs": 0, "files": 0, "size_mb": 0})
            sd_kb_coverage = round(sd_actual["kbs"] / sd["planned_kbs"] * 100, 1) if sd["planned_kbs"] else 0
            subdomains.append({
                "name": sd["name"],
                "planned_kbs": sd["planned_kbs"],
                "actual_kbs": sd_actual["kbs"],
                "actual_files": sd_actual["files"],
                "actual_size_mb": round(sd_actual["size_mb"], 2),
                "coverage_pct": sd_kb_coverage,
                "sources": sd["sources"],
                "key_apis": sd["key_apis"],
            })

        domains.append({
            "name": pd.name,
            "en_name": pd.en_name,
            "color": pd.color,
            "planned_kbs": pd.planned_kbs,
            "planned_docs": pd.planned_docs,
            "planned_size_gb": pd.planned_size_gb,
            "actual_kbs": actual_d["kbs"],
            "actual_files": actual_d["files"],
            "actual_size_mb": round(actual_d["size_mb"], 2),
            "kb_coverage_pct": kb_coverage,
            "doc_coverage_pct": doc_coverage,
            "size_coverage_pct": size_coverage,
            "coverage_score": coverage_score,
            "subdomains": subdomains,
        })

    return {
        "summary": {
            "total_planned_kbs": total_planned_kbs,
            "total_actual_kbs": total_actual_kbs,
            "total_kb_coverage_pct": round(total_actual_kbs / total_planned_kbs * 100, 1) if total_planned_kbs else 0,
            "total_planned_docs": total_planned_docs,
            "total_actual_files": total_actual_files,
            "total_doc_coverage_pct": round(total_actual_files / total_planned_docs * 100, 1) if total_planned_docs else 0,
            "total_planned_size_gb": total_planned_gb,
            "total_actual_size_gb": round(total_actual_mb / 1024, 2),
            "total_size_coverage_pct": round(total_actual_mb / (total_planned_gb * 1024) * 100, 1) if total_planned_gb else 0,
        },
        "domains": domains,
        "missing_sources": MISSING_SOURCES,
    }


# ── Network graph data generator ─────────────────────────────────────────────

def build_network_graph_data() -> dict[str, Any]:
    """Build nodes and edges for the force-directed network graph."""
    coverage = compute_coverage()
    nodes: list[dict] = []
    edges: list[dict] = []

    # Center node
    nodes.append({
        "id": "root",
        "label": "DataAgent 知识体系",
        "type": "root",
        "coverage_score": coverage["summary"]["total_kb_coverage_pct"],
        "size": 40,
        "color": "#1e293b",
    })

    for domain in coverage["domains"]:
        domain_id = f"domain_{domain['name']}"
        coverage_score = domain["coverage_score"]

        # Color based on coverage
        if coverage_score >= 70:
            status = "good"
            node_color = "#10b981"  # green
        elif coverage_score >= 30:
            status = "partial"
            node_color = "#f59e0b"  # yellow
        else:
            status = "poor"
            node_color = "#ef4444"  # red

        nodes.append({
            "id": domain_id,
            "label": domain["name"],
            "type": "domain",
            "coverage_score": coverage_score,
            "planned_kbs": domain["planned_kbs"],
            "actual_kbs": domain["actual_kbs"],
            "planned_size_gb": domain["planned_size_gb"],
            "actual_size_mb": domain["actual_size_mb"],
            "size": 20 + min(coverage_score / 100 * 15, 15),
            "color": node_color,
            "status": status,
        })

        edges.append({
            "source": "root",
            "target": domain_id,
            "strength": 0.5,
        })

        for sd in domain["subdomains"]:
            sd_id = f"sd_{domain['name']}_{sd['name']}"
            sd_coverage = sd["coverage_pct"]

            if sd_coverage >= 70:
                sd_status = "good"
                sd_color = "#10b981"
            elif sd_coverage >= 30:
                sd_status = "partial"
                sd_color = "#f59e0b"
            else:
                sd_status = "poor"
                sd_color = "#ef4444"

            # Special case: if actual_kbs > 0 but coverage is 0, mark as started
            if sd["actual_kbs"] > 0 and sd_coverage == 0:
                sd_status = "started"
                sd_color = "#3b82f6"

            # Find actual KB IDs for this subdomain
            kb_ids_for_sd = [
                kb_id for kb_id, mapped in ACTUAL_KB_MAP.items()
                if mapped[0] == domain["name"] and mapped[1] == sd["name"]
            ]

            nodes.append({
                "id": sd_id,
                "label": sd["name"],
                "type": "subdomain",
                "coverage_score": sd_coverage,
                "planned_kbs": sd["planned_kbs"],
                "actual_kbs": sd["actual_kbs"],
                "actual_files": sd["actual_files"],
                "actual_size_mb": sd["actual_size_mb"],
                "size": 8 + min(sd_coverage / 100 * 7, 7),
                "color": sd_color,
                "status": sd_status,
                "parent": domain_id,
                "kb_ids": kb_ids_for_sd,
            })

            edges.append({
                "source": domain_id,
                "target": sd_id,
                "strength": 0.3,
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "summary": coverage["summary"],
        "domains": coverage["domains"],
        "missing_sources": coverage["missing_sources"],
    }


# ── API Endpoints ────────────────────────────────────────────────────────────

@router.get("/kb-coverage")
async def get_kb_coverage():
    """Get comprehensive KB coverage analysis."""
    return compute_coverage()


@router.get("/kb-coverage/network")
async def get_kb_network_graph():
    """Get network graph data for visualization."""
    return build_network_graph_data()
