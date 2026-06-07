"""Data source configuration V2 — ZERO API keys required.

Comprehensive knowledge base expansion using only freely accessible sources:
- Web crawling (landing pages, PDFs, document listings)
- RSS feeds (open aggregation)
- Git cloning (open source)
- wget mirroring (documentation sites)
- Open data portals (no-key APIs)
- Public domain books (Project Gutenberg, OpenStax)
- Wikipedia dumps (free full-text corpus)

Target: 100+ KBs covering all 9 domains with actual depth.
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
    download_method: str  # crawl | rss | git | api_free | direct | wget
    output_dir: str
    time_range: tuple[int, int] = (2020, 2026)
    file_pattern: str = "*.md"
    extra: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: Core Public Data — Government, Statistics, Policy (20 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_GOVERNMENT: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_001",
        name="国务院政府工作报告",
        kb_type="policy",
        description="国务院政府工作报告全文（2014-2025）",
        source_url="https://www.gov.cn/premier/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_001_gov_work_reports",
        time_range=(2014, 2025),
        extra={"deep_crawl": True, "pdf_pattern": r"\.pdf$", "content_selector": ".pages_content"},
    ),
    SourceConfig(
        kb_id="kb_002",
        name="国家统计局统计公报",
        kb_type="statistics",
        description="国民经济和社会发展统计公报",
        source_url="https://www.stats.gov.cn/sj/zxfb/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_002_national_stats",
        time_range=(2015, 2025),
        extra={"deep_crawl": True, "yearly_index": True},
    ),
    SourceConfig(
        kb_id="kb_003",
        name="各省市统计年鉴",
        kb_type="statistics",
        description="重点省份统计年鉴",
        source_url="https://www.stats.gov.cn/sj/ndsj/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_003_stats_yearbook",
        time_range=(2015, 2025),
        extra={"provinces": ["北京", "上海", "广东", "江苏", "浙江", "山东", "四川"], "deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_004",
        name="中国人民银行货币政策",
        kb_type="finance",
        description="货币政策执行报告",
        source_url="http://www.pbc.gov.cn/zhengcehuobisi/11140/index.html",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_004_pbc_monetary",
        time_range=(2015, 2025),
        extra={"quarterly": True, "deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_005",
        name="财政部预算决算",
        kb_type="finance",
        description="中央和地方预算执行及决算报告",
        source_url="http://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_005_mof_budget",
        time_range=(2015, 2025),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_006",
        name="海关总署统计数据",
        kb_type="trade",
        description="进出口统计数据",
        source_url="http://www.customs.gov.cn/customs/302249/zfxxgk/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_006_customs_data",
        time_range=(2015, 2025),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_007",
        name="国家发改委政策",
        kb_type="policy",
        description="宏观政策与产业规划文件",
        source_url="https://www.ndrc.gov.cn/xxgk/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_007_ndrc_policy",
        time_range=(2015, 2025),
        extra={"deep_crawl": True, "policy_focus": ["十四五", "双碳", "新能源", "数字经济"]},
    ),
    SourceConfig(
        kb_id="kb_008",
        name="全国人大法律法规",
        kb_type="law",
        description="宪法与基本法律全文",
        source_url="https://www.npc.gov.cn/npc/c2/c30834/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_008_constitution",
        time_range=(1949, 2025),
        extra={"deep_crawl": True, "full_text": True},
    ),
    SourceConfig(
        kb_id="kb_009",
        name="国务院行政法规",
        kb_type="law",
        description="国务院行政法规库",
        source_url="https://www.gov.cn/zhengce/xxgk/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_009_admin_regulations",
        time_range=(2015, 2025),
        extra={"deep_crawl": True, "full_text": True},
    ),
    SourceConfig(
        kb_id="kb_010",
        name="最高法司法解释",
        kb_type="law",
        description="最高人民法院司法解释",
        source_url="https://www.court.gov.cn/zixun-gengduo-104.html",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_010_judicial_interp",
        time_range=(2015, 2025),
        extra={"deep_crawl": True, "full_text": True},
    ),
    SourceConfig(
        kb_id="kb_011",
        name="金融监管总局规章",
        kb_type="law",
        description="金融监管总局发布的规章",
        source_url="https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_011_finance_regulations",
        time_range=(2018, 2025),
        extra={"deep_crawl": True},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: News & Current Affairs (8 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_NEWS: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_012",
        name="新浪财经",
        kb_type="news",
        description="财经新闻 RSS 聚合",
        source_url="https://finance.sina.com.cn/",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_012_finance_news",
        extra={"rss_urls": [
            "https://rss.sina.com.cn/finance/financelist.xml",
            "https://rss.sina.com.cn/roll/finance/hot_roll.xml",
        ]},
    ),
    SourceConfig(
        kb_id="kb_013",
        name="IT之家科技新闻",
        kb_type="news",
        description="科技领域新闻聚合",
        source_url="https://www.ithome.com/",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_013_tech_news",
        extra={"rss_urls": ["https://www.ithome.com/rss/"]},
    ),
    SourceConfig(
        kb_id="kb_014",
        name="政治时事新闻",
        kb_type="news",
        description="政治时事新闻聚合",
        source_url="http://www.people.com.cn/",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_014_political_news",
        extra={"rss_urls": [
            "http://www.people.com.cn/rss/politics.xml",
            "https://www.chinanews.com/rss/politics.xml",
        ]},
    ),
    SourceConfig(
        kb_id="kb_042",
        name="环球时报国际新闻",
        kb_type="news",
        description="国际新闻与评论",
        source_url="https://www.globaltimes.cn/",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_042_global_times",
        extra={"rss_urls": ["https://www.globaltimes.cn/rss/index.xml"]},
    ),
    SourceConfig(
        kb_id="kb_043",
        name="BBC中文新闻",
        kb_type="news",
        description="BBC中文国际新闻",
        source_url="https://www.bbc.com/zhongwen",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_043_bbc_chinese",
        extra={"rss_urls": ["https://feeds.bbci.co.uk/zhongwen/simp/rss.xml"]},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: Academic Papers — All free APIs (12 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_ACADEMIC: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_015",
        name="ArXiv CS/AI/ML",
        kb_type="academic",
        description="ArXiv 计算机科学/人工智能/机器学习",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_015_arxiv_cs_ai",
        time_range=(2020, 2026),
        extra={"categories": ["cs.AI", "cs.CL", "cs.LG", "cs.CV"], "max_results": 50000},
    ),
    SourceConfig(
        kb_id="kb_016",
        name="ArXiv 数学与物理",
        kb_type="academic",
        description="ArXiv 数学/物理/其他子类",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_016_arxiv_math_physics",
        time_range=(2020, 2026),
        extra={"categories": ["math", "physics", "cs.SE", "cs.DB", "cs.IR"], "max_results": 30000},
    ),
    SourceConfig(
        kb_id="kb_017",
        name="PubMed生物医学",
        kb_type="academic",
        description="PubMed 高影响力生物医学论文",
        source_url="https://pubmed.ncbi.nlm.nih.gov/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_017_pubmed",
        time_range=(2020, 2026),
        extra={"search_terms": ["machine learning", "artificial intelligence", "drug discovery", "genomics"], "max_results": 50000},
    ),
    SourceConfig(
        kb_id="kb_018",
        name="ArXiv 经济学与金融",
        kb_type="academic",
        description="ArXiv q-fin/econ 经济学论文",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_018_arxiv_econ",
        time_range=(2020, 2026),
        extra={"categories": ["q-fin.GN", "q-fin.PM", "q-fin.RM", "q-fin.ST", "q-fin.TR"], "max_results": 15000},
    ),
    SourceConfig(
        kb_id="kb_044",
        name="ArXiv 量子计算",
        kb_type="academic",
        description="ArXiv 量子物理与量子计算",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_044_arxiv_quantum",
        time_range=(2020, 2026),
        extra={"categories": ["quant-ph", "cs.CC", "cs.ET"], "max_results": 15000},
    ),
    SourceConfig(
        kb_id="kb_045",
        name="ArXiv 网络安全",
        kb_type="academic",
        description="ArXiv 密码学与网络安全",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_045_arxiv_security",
        time_range=(2020, 2026),
        extra={"categories": ["cs.CR", "cs.CY"], "max_results": 15000},
    ),
    SourceConfig(
        kb_id="kb_046",
        name="ArXiv 机器人",
        kb_type="academic",
        description="ArXiv 机器人与自动化",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_046_arxiv_robotics",
        time_range=(2020, 2026),
        extra={"categories": ["cs.RO", "eess.SY"], "max_results": 15000},
    ),
    SourceConfig(
        kb_id="kb_047",
        name="ArXiv 数据科学",
        kb_type="academic",
        description="ArXiv 数据挖掘与信息检索",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_047_arxiv_data_science",
        time_range=(2020, 2026),
        extra={"categories": ["cs.IR", "cs.DB", "cs.DS", "cs.CE"], "max_results": 15000},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: Code Knowledge — Documentation + Source (18 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_CODE: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_019",
        name="Python官方文档",
        kb_type="code",
        description="Python官方文档全版本",
        source_url="https://docs.python.org/3/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_019_python_docs",
        extra={"versions": ["3.9", "3.10", "3.11", "3.12", "3.13"]},
    ),
    SourceConfig(
        kb_id="kb_020",
        name="PyTorch文档",
        kb_type="code",
        description="PyTorch官方文档",
        source_url="https://pytorch.org/docs/stable/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_020_pytorch_docs",
    ),
    SourceConfig(
        kb_id="kb_021",
        name="React文档",
        kb_type="code",
        description="React官方文档",
        source_url="https://react.dev/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_021_react_docs",
    ),
    SourceConfig(
        kb_id="kb_022",
        name="Vue文档",
        kb_type="code",
        description="Vue.js官方文档",
        source_url="https://vuejs.org/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_022_vue_docs",
    ),
    SourceConfig(
        kb_id="kb_023",
        name="Go官方文档",
        kb_type="code",
        description="Go官方文档与标准库",
        source_url="https://go.dev/doc/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_023_go_docs",
    ),
    SourceConfig(
        kb_id="kb_024",
        name="Rust官方文档",
        kb_type="code",
        description="Rust官方文档与The Book",
        source_url="https://doc.rust-lang.org/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_024_rust_docs",
    ),
    SourceConfig(
        kb_id="kb_048",
        name="Java/Spring文档",
        kb_type="code",
        description="Java官方文档与Spring框架",
        source_url="https://docs.spring.io/spring-framework/docs/current/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_048_java_spring_docs",
    ),
    SourceConfig(
        kb_id="kb_049",
        name="Node.js文档",
        kb_type="code",
        description="Node.js官方API文档",
        source_url="https://nodejs.org/docs/latest/api/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_049_nodejs_docs",
    ),
    SourceConfig(
        kb_id="kb_050",
        name="Docker文档",
        kb_type="code",
        description="Docker官方文档",
        source_url="https://docs.docker.com/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_050_docker_docs",
    ),
    SourceConfig(
        kb_id="kb_051",
        name="Kubernetes文档",
        kb_type="code",
        description="K8s官方文档",
        source_url="https://kubernetes.io/docs/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_051_kubernetes_docs",
    ),
    SourceConfig(
        kb_id="kb_052",
        name="TensorFlow文档",
        kb_type="code",
        description="TensorFlow官方文档",
        source_url="https://www.tensorflow.org/api_docs",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_052_tensorflow_docs",
    ),
    SourceConfig(
        kb_id="kb_053",
        name="PostgreSQL文档",
        kb_type="code",
        description="PostgreSQL官方文档",
        source_url="https://www.postgresql.org/docs/current/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_053_postgresql_docs",
    ),
    SourceConfig(
        kb_id="kb_054",
        name="MongoDB文档",
        kb_type="code",
        description="MongoDB官方文档",
        source_url="https://www.mongodb.com/docs/manual/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_054_mongodb_docs",
    ),
    SourceConfig(
        kb_id="kb_055",
        name="Redis文档",
        kb_type="code",
        description="Redis官方文档",
        source_url="https://redis.io/docs/latest/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_055_redis_docs",
    ),
    SourceConfig(
        kb_id="kb_025",
        name="GitHub开源项目",
        kb_type="code",
        description="精选GitHub开源项目源码与文档",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_025_github_repos",
        extra={"repos": [
            # ── 超大型仓库 (1GB+) ──
            "torvalds/linux",           # ~4GB  Linux内核源码
            "chromium/chromium",        # ~20GB 浏览器引擎
            "llvm/llvm-project",        # ~2GB  编译器基础设施
            "mongodb/mongo",            # ~2GB  数据库
            "postgresql/postgresql",    # ~1GB  数据库
            "elasticsearch/elasticsearch", # ~1GB 搜索引擎
            "pytorch/pytorch",          # ~1GB  深度学习框架
            "kubernetes/kubernetes",    # ~1GB  容器编排
            "microsoft/vscode",         # ~1GB  编辑器
            "rust-lang/rust",           # ~1GB  编程语言
            "golang/go",                # ~500MB 编程语言
            "python/cpython",           # ~500MB 编程语言
            "nodejs/node",              # ~500MB 运行时
            "apache/spark",             # ~500MB 大数据
            "apache/hadoop",            # ~500MB 大数据
            "apache/flink",             # ~500MB 流处理
            "qemu/qemu",                # ~500MB 虚拟化
            "ffmpeg/ffmpeg",            # ~500MB 多媒体
            "openssl/openssl",          # ~200MB 加密库
            "redis/redis",              # ~200MB 缓存数据库
            # ── 大型框架 (~200-500MB) ──
            "tensorflow/tensorflow",    # ~500MB ML框架
            "facebook/react",           # ~200MB 前端框架
            "vuejs/vue",                # ~200MB 前端框架
            "angular/angular",          # ~300MB 前端框架
            "django/django",            # ~200MB Web框架
            "rails/rails",              # ~200MB Web框架
            "laravel/laravel",          # ~100MB Web框架
            "spring-projects/spring-boot", # ~200MB Java框架
            "docker/docker-ce",         # ~500MB 容器
            "apache/kafka",             # ~200MB 消息队列
            "apache/airflow",           # ~200MB 工作流
            "ansible/ansible",          # ~200MB 自动化
            "prometheus/prometheus",    # ~200MB 监控
            "grafana/grafana",          # ~200MB 可视化
            "istio/istio",              # ~200MB 服务网格
            "helm/helm",                # ~100MB K8s包管理
            "terraform/terraform",      # ~200MB 基础设施
            "hashicorp/vault",          # ~200MB 密钥管理
            "etcd-io/etcd",             # ~200MB 分布式KV
            "cockroachdb/cockroach",    # ~500MB 分布式DB
            "tidb/tidb",                # ~500MB 分布式DB
            "clickhouse/clickhouse",    # ~2GB 列式DB
            "apache/arrow",             # ~500MB 列式数据
            "apache/parquet-format",    # ~100MB 数据格式
            # ── 语言生态 ──
            "JetBrains/kotlin",         # ~200MB 编程语言
            "apple/swift",              # ~1GB 编程语言
            "dotnet/runtime",           # ~1GB .NET运行时
            "php/php-src",              # ~200MB 编程语言
            "perl/perl5",               # ~200MB 编程语言
            "ruby/ruby",                # ~200MB 编程语言
            "erlang/otp",               # ~500MB 运行时
            "dart-lang/sdk",            # ~1GB SDK
            "flutter/flutter",          # ~2GB UI框架
        ]},
    ),
    SourceConfig(
        kb_id="kb_026",
        name="LeetCode题解",
        kb_type="code",
        description="LeetCode算法题解与思路",
        source_url="https://leetcode.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_026_leetcode",
    ),
    SourceConfig(
        kb_id="kb_027",
        name="OWASP安全规范",
        kb_type="code",
        description="OWASP安全标准与指南",
        source_url="https://owasp.org/www-project-top-ten/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_027_owasp",
    ),
    SourceConfig(
        kb_id="kb_056",
        name="Linux内核文档",
        kb_type="code",
        description="Linux内核源码Documentation",
        source_url="https://www.kernel.org/doc/html/latest/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_056_linux_kernel_docs",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: Mathematics (12 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_MATH: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_028",
        name="MIT OCW数学",
        kb_type="math",
        description="MIT开放课程数学教材",
        source_url="https://ocw.mit.edu/search/?d=Mathematics",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_028_mit_ocw_math",
        extra={"courses": ["18.01", "18.02", "18.03", "18.06", "18.6501"], "deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_029",
        name="MIT OCW离散数学",
        kb_type="math",
        description="离散数学与计算机科学数学",
        source_url="https://ocw.mit.edu/search/?d=Mathematics",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_029_discrete_math",
        extra={"courses": ["6.042J", "6.006"], "deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_030",
        name="统计学习方法",
        kb_type="math",
        description="统计学习经典教材与讲义",
        source_url="https://web.stanford.edu/~hastie/ElemStatLearn/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_030_statistical_learning",
    ),
    SourceConfig(
        kb_id="kb_057",
        name="ArXiv纯数学",
        kb_type="math",
        description="ArXiv纯数学论文",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_057_arxiv_pure_math",
        time_range=(2020, 2026),
        extra={"categories": ["math.AG", "math.AT", "math.GT", "math.NT", "math.RT"], "max_results": 20000},
    ),
    SourceConfig(
        kb_id="kb_058",
        name="ArXiv应用数学",
        kb_type="math",
        description="ArXiv应用数学与数值分析",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_058_arxiv_applied_math",
        time_range=(2020, 2026),
        extra={"categories": ["math.AP", "math.NA", "math.OC", "math.ST", "math.PR"], "max_results": 20000},
    ),
    SourceConfig(
        kb_id="kb_059",
        name="3Blue1Brown数学视频文稿",
        kb_type="math",
        description="3Blue1Brown数学可视化讲义",
        source_url="https://www.3blue1brown.com/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_059_3b1b_math",
    ),
    SourceConfig(
        kb_id="kb_060",
        name="Wolfram MathWorld",
        kb_type="math",
        description="Wolfram数学百科全书",
        source_url="https://mathworld.wolfram.com/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_060_mathworld",
        extra={"max_pages": 2000},
    ),
    SourceConfig(
        kb_id="kb_061",
        name="NIST数学函数手册",
        kb_type="math",
        description="NIST Handbook of Mathematical Functions",
        source_url="https://dlmf.nist.gov/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_061_nist_dlmf",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: Books & Textbooks — Free/Open Access (15 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_BOOKS: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_062",
        name="Project Gutenberg英文经典",
        kb_type="book",
        description="公版英文文学经典",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_062_gutenberg_english",
        extra={"language": "en", "max_books": 100000, "catalog_url": "https://www.gutenberg.org/ebooks/search/?sort_order=downloads"},
    ),
    SourceConfig(
        kb_id="kb_063",
        name="Project Gutenberg中文经典",
        kb_type="book",
        description="公版中文文学经典",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_063_gutenberg_chinese",
        extra={"language": "zh", "max_books": 5000},
    ),
    SourceConfig(
        kb_id="kb_064",
        name="OpenStax教科书",
        kb_type="book",
        description="OpenStax免费大学教科书",
        source_url="https://openstax.org/subjects",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_064_openstax_textbooks",
        extra={"deep_crawl": True, "subjects": ["math", "science", "social-sciences", "business", "humanities"]},
    ),
    SourceConfig(
        kb_id="kb_065",
        name="计算机技术书籍",
        kb_type="book",
        description="开源技术书籍与讲义",
        source_url="https://github.com/EbookFoundation/free-programming-books",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_065_tech_books",
        extra={"repo": "EbookFoundation/free-programming-books", "focus": "zh"},
    ),
    SourceConfig(
        kb_id="kb_066",
        name="经济学原理教材",
        kb_type="book",
        description="经济学开放教材",
        source_url="https://openstax.org/details/books/principles-economics-3e",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_066_economics_books",
    ),
    SourceConfig(
        kb_id="kb_067",
        name="ManyBooks免费电子书",
        kb_type="book",
        description="ManyBooks.net免费电子书",
        source_url="https://manybooks.net/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_067_manybooks",
        extra={"max_books": 10000},
    ),
    SourceConfig(
        kb_id="kb_068",
        name="LibriVox有声书文本",
        kb_type="book",
        description="LibriVox公版书文本",
        source_url="https://librivox.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_068_librivox",
        extra={"max_books": 5000},
    ),
    SourceConfig(
        kb_id="kb_069",
        name="标准电子书",
        kb_type="book",
        description="Standard Ebooks高质量公版书",
        source_url="https://standardebooks.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_069_standard_ebooks",
        extra={"max_books": 5000},
    ),
    SourceConfig(
        kb_id="kb_070",
        name="Wikibooks开放教材",
        kb_type="book",
        description="Wikibooks协作教科书",
        source_url="https://en.wikibooks.org/wiki/Subject:Computing",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_070_wikibooks",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7: International & Global Data (10 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_INTL: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_031",
        name="世界银行开放数据",
        kb_type="intl",
        description="World Bank Open Data",
        source_url="https://data.worldbank.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_031_world_bank",
        time_range=(1960, 2026),
    ),
    SourceConfig(
        kb_id="kb_032",
        name="IMF世界经济展望",
        kb_type="intl",
        description="IMF WEO Reports",
        source_url="https://www.imf.org/en/Publications/WEO",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_032_imf_weo",
        time_range=(2000, 2026),
        extra={"deep_crawl": True, "pdf_download": True},
    ),
    SourceConfig(
        kb_id="kb_033",
        name="联合国数据",
        kb_type="intl",
        description="UN Data Portal",
        source_url="https://data.un.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_033_un_data",
        time_range=(2000, 2026),
    ),
    SourceConfig(
        kb_id="kb_034",
        name="WTO贸易统计",
        kb_type="intl",
        description="WTO Trade Statistics",
        source_url="https://www.wto.org/english/res_e/statis_e/trade_stats_e.htm",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_034_wto_data",
        time_range=(2000, 2026),
    ),
    SourceConfig(
        kb_id="kb_071",
        name="OECD经济报告",
        kb_type="intl",
        description="OECD Economic Outlook",
        source_url="https://www.oecd.org/economic-outlook/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_071_oecd_reports",
        time_range=(2010, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_072",
        name="联合国可持续发展目标",
        kb_type="intl",
        description="UN SDG Reports and Data",
        source_url="https://unstats.un.org/sdgs/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_072_un_sdg",
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_073",
        name="美国国会研究处报告",
        kb_type="intl",
        description="CRS Reports (public domain)",
        source_url="https://crsreports.congress.gov/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_073_crs_reports",
        time_range=(2015, 2026),
        extra={"deep_crawl": True, "pdf_download": True},
    ),
    SourceConfig(
        kb_id="kb_074",
        name="欧盟统计局",
        kb_type="intl",
        description="Eurostat Open Data",
        source_url="https://ec.europa.eu/eurostat/databrowser/view/NAMQ_10_GDP",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_074_eurostat",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8: Industry Deep Data — Government Portals (15 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_INDUSTRY: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_035",
        name="银行业监管政策",
        kb_type="finance",
        description="银行业监管政策与指引",
        source_url="https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_035_banking_regulation",
        time_range=(2018, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_036",
        name="金融科技发展报告",
        kb_type="finance",
        description="金融科技与数字银行报告",
        source_url="https://www.nfra.gov.cn/cn/view/pages/governmentDetail.html",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_036_fintech",
        time_range=(2020, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_037",
        name="中国信通院白皮书",
        kb_type="tech",
        description="CAICT产业白皮书与研究报告",
        source_url="https://www.caict.ac.cn/kxyj/qwfb/bps/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_037_caict_whitepapers",
        time_range=(2018, 2026),
        extra={"deep_crawl": True, "pdf_download": True},
    ),
    SourceConfig(
        kb_id="kb_038",
        name="数字化转型政策",
        kb_type="policy",
        description="各行业数字化转型政策文件",
        source_url="https://www.gov.cn/zhengce/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_038_digital_transform",
        time_range=(2020, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_075",
        name="工信部产业政策",
        kb_type="policy",
        description="工信部行业政策与规划",
        source_url="https://www.miit.gov.cn/jgsj/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_075_miit_policy",
        time_range=(2018, 2026),
        extra={"deep_crawl": True, "industries": ["汽车", "电子", "软件", "通信", "装备"]},
    ),
    SourceConfig(
        kb_id="kb_076",
        name="证监会监管规则",
        kb_type="finance",
        description="证监会监管规则与指引",
        source_url="http://www.csrc.gov.cn/csrc/c101954/common_list.shtml",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_076_csrc_regulations",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_077",
        name="商务部贸易政策",
        kb_type="trade",
        description="商务部外贸与内贸政策",
        source_url="http://www.mofcom.gov.cn/article/b/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_077_mofcom_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_078",
        name="环保部环境政策",
        kb_type="policy",
        description="生态环境部政策文件",
        source_url="https://www.mee.gov.cn/zcwj/zcjd/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_078_mee_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_079",
        name="住建部房地产政策",
        kb_type="policy",
        description="住房和城乡建设部政策",
        source_url="https://www.mohurd.gov.cn/gongkai/zhengce/zcwj/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_079_mohurd_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_080",
        name="交通运输部政策",
        kb_type="policy",
        description="交通运输行业政策文件",
        source_url="https://www.mot.gov.cn/zhengcejiedu/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_080_mot_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_081",
        name="教育部政策文件",
        kb_type="policy",
        description="教育部政策与规划",
        source_url="http://www.moe.gov.cn/srcsite/A01/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_081_moe_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_082",
        name="卫健委医疗政策",
        kb_type="policy",
        description="国家卫健委政策文件",
        source_url="http://www.nhc.gov.cn/zwgkzt/wsbysj/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_082_nhc_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_083",
        name="科技部科技政策",
        kb_type="policy",
        description="科技部科技创新政策",
        source_url="https://www.most.gov.cn/kjbgz/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_083_most_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_084",
        name="农业农村部政策",
        kb_type="policy",
        description="农业与农村政策文件",
        source_url="http://www.moa.gov.cn/gk/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_084_moa_policy",
        time_range=(2015, 2026),
        extra={"deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_085",
        name="市场监管总局",
        kb_type="policy",
        description="市场监管政策与标准",
        source_url="https://www.samr.gov.cn/zw/zfxxgk/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_085_samr_policy",
        time_range=(2018, 2026),
        extra={"deep_crawl": True},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9: Wikipedia — Massive Free Text Corpus (5 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_WIKIPEDIA: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_086",
        name="Wikipedia中文dump",
        kb_type="general",
        description="Wikipedia中文全站文本dump（约3GB纯文本）",
        source_url="https://dumps.wikimedia.org/zhwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_086_wikipedia_zh",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_087",
        name="Wikipedia英文dump",
        kb_type="general",
        description="Wikipedia英文全站文本dump（约20GB纯文本）",
        source_url="https://dumps.wikimedia.org/enwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_087_wikipedia_en",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_088",
        name="Wikidata实体数据",
        kb_type="general",
        description="Wikidata结构化知识库",
        source_url="https://www.wikidata.org/wiki/Wikidata:Database_download",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_088_wikidata",
        extra={"dump_url": "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 10: Additional Open Knowledge (10 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_ADDITIONAL: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_089",
        name="StackOverflow技术问答",
        kb_type="code",
        description="StackOverflow热门技术问答",
        source_url="https://archive.org/details/stackexchange",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_089_stackoverflow",
        extra={"dump_url": "https://archive.org/download/stackexchange/stackoverflow.com-Posts.7z"},
    ),
    SourceConfig(
        kb_id="kb_090",
        name="CIA世界概况",
        kb_type="intl",
        description="CIA World Factbook",
        source_url="https://www.cia.gov/the-world-factbook/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_090_cia_factbook",
    ),
    SourceConfig(
        kb_id="kb_091",
        name="中国哲学书电子化计划",
        kb_type="book",
        description="中国古籍全文数据库",
        source_url="https://ctext.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_091_chinese_classics",
        extra={"max_texts": 2000, "deep_crawl": True},
    ),
    SourceConfig(
        kb_id="kb_092",
        name="Python PEP规范",
        kb_type="code",
        description="Python Enhancement Proposals",
        source_url="https://peps.python.org/",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_092_python_peps",
    ),
    SourceConfig(
        kb_id="kb_093",
        name="MDN Web文档",
        kb_type="code",
        description="MDN Web技术文档",
        source_url="https://developer.mozilla.org/zh-CN/docs/Web",
        download_method="wget",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_093_mdn_web",
    ),
    SourceConfig(
        kb_id="kb_094",
        name="NLP论文解读",
        kb_type="academic",
        description="PapersWithCode NLP领域",
        source_url="https://paperswithcode.com/area/natural-language-processing",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_094_paperswithcode_nlp",
        extra={"max_papers": 5000},
    ),
    SourceConfig(
        kb_id="kb_095",
        name="CV论文解读",
        kb_type="academic",
        description="PapersWithCode计算机视觉",
        source_url="https://paperswithcode.com/area/computer-vision",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_095_paperswithcode_cv",
        extra={"max_papers": 5000},
    ),
    SourceConfig(
        kb_id="kb_096",
        name="机器学习论文解读",
        kb_type="academic",
        description="PapersWithCode机器学习",
        source_url="https://paperswithcode.com/area/machine-learning",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_096_paperswithcode_ml",
        extra={"max_papers": 5000},
    ),
    SourceConfig(
        kb_id="kb_097",
        name="中国知网开放获取",
        kb_type="academic",
        description="CNKI开放获取论文",
        source_url="https://oa.cnki.net/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_097_cnki_oa",
        extra={"deep_crawl": True, "max_papers": 5000},
    ),
    SourceConfig(
        kb_id="kb_098",
        name="PubMed Central开放全文",
        kb_type="academic",
        description="PMC开放获取全文",
        source_url="https://www.ncbi.nlm.nih.gov/pmc/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_098_pmc_fulltext",
        extra={"deep_crawl": True, "max_articles": 20000},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 11: Additional Wikipedia Language Dumps — Massive Text Corpus (15 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE2_WIKIPEDIA_LANGS: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_099",
        name="Wikipedia德文dump",
        kb_type="general",
        description="Wikipedia德文全站文本dump",
        source_url="https://dumps.wikimedia.org/dewiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_099_wikipedia_de",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/dewiki/latest/dewiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_100",
        name="Wikipedia法文dump",
        kb_type="general",
        description="Wikipedia法文全站文本dump",
        source_url="https://dumps.wikimedia.org/frwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_100_wikipedia_fr",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/frwiki/latest/frwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_101",
        name="Wikipedia西班牙文dump",
        kb_type="general",
        description="Wikipedia西班牙文全站文本dump",
        source_url="https://dumps.wikimedia.org/eswiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_101_wikipedia_es",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/eswiki/latest/eswiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_102",
        name="Wikipedia日文dump",
        kb_type="general",
        description="Wikipedia日文全站文本dump",
        source_url="https://dumps.wikimedia.org/jawiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_102_wikipedia_ja",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/jawiki/latest/jawiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_103",
        name="Wikipedia俄文dump",
        kb_type="general",
        description="Wikipedia俄文全站文本dump",
        source_url="https://dumps.wikimedia.org/ruwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_103_wikipedia_ru",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/ruwiki/latest/ruwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_104",
        name="Wikipedia葡萄牙文dump",
        kb_type="general",
        description="Wikipedia葡萄牙文全站文本dump",
        source_url="https://dumps.wikimedia.org/ptwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_104_wikipedia_pt",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/ptwiki/latest/ptwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_105",
        name="Wikipedia意大利文dump",
        kb_type="general",
        description="Wikipedia意大利文全站文本dump",
        source_url="https://dumps.wikimedia.org/itwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_105_wikipedia_it",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/itwiki/latest/itwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_106",
        name="Wikipedia韩文dump",
        kb_type="general",
        description="Wikipedia韩文全站文本dump",
        source_url="https://dumps.wikimedia.org/kowiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_106_wikipedia_ko",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/kowiki/latest/kowiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_107",
        name="Wikipedia阿拉伯文dump",
        kb_type="general",
        description="Wikipedia阿拉伯文全站文本dump",
        source_url="https://dumps.wikimedia.org/arwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_107_wikipedia_ar",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/arwiki/latest/arwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_108",
        name="Wikipedia荷兰文dump",
        kb_type="general",
        description="Wikipedia荷兰文全站文本dump",
        source_url="https://dumps.wikimedia.org/nlwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_108_wikipedia_nl",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/nlwiki/latest/nlwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_109",
        name="Wikipedia波兰文dump",
        kb_type="general",
        description="Wikipedia波兰文全站文本dump",
        source_url="https://dumps.wikimedia.org/plwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_109_wikipedia_pl",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/plwiki/latest/plwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_110",
        name="Wikipedia瑞典文dump",
        kb_type="general",
        description="Wikipedia瑞典文全站文本dump",
        source_url="https://dumps.wikimedia.org/svwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_110_wikipedia_sv",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/svwiki/latest/svwiki-latest-pages-articles.xml.bz2"},
    ),
    SourceConfig(
        kb_id="kb_111",
        name="Wikipedia土耳其文dump",
        kb_type="general",
        description="Wikipedia土耳其文全站文本dump",
        source_url="https://dumps.wikimedia.org/trwiki/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_111_wikipedia_tr",
        extra={"dump_url_pattern": "https://dumps.wikimedia.org/trwiki/latest/trwiki-latest-pages-articles.xml.bz2"},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 12: Common Crawl WET Files — Web-scale Text Corpus (20 KBs)
# Each segment: ~1-2GB compressed → ~5-10GB text
# ═══════════════════════════════════════════════════════════════════════════════

PHASE2_COMMONCRAWL: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_112",
        name="CommonCrawl WET 2024-51 段1",
        kb_type="general",
        description="Common Crawl 2024年12月爬取段1",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_112_commoncrawl_2024_51_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-51/wet.paths.gz", "max_files": 50},
    ),
    SourceConfig(
        kb_id="kb_113",
        name="CommonCrawl WET 2024-51 段2",
        kb_type="general",
        description="Common Crawl 2024年12月爬取段2",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_113_commoncrawl_2024_51_seg2",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-51/wet.paths.gz", "max_files": 50, "offset": 50},
    ),
    SourceConfig(
        kb_id="kb_114",
        name="CommonCrawl WET 2024-51 段3",
        kb_type="general",
        description="Common Crawl 2024年12月爬取段3",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_114_commoncrawl_2024_51_seg3",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-51/wet.paths.gz", "max_files": 50, "offset": 100},
    ),
    SourceConfig(
        kb_id="kb_115",
        name="CommonCrawl WET 2024-51 段4",
        kb_type="general",
        description="Common Crawl 2024年12月爬取段4",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_115_commoncrawl_2024_51_seg4",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-51/wet.paths.gz", "max_files": 50, "offset": 150},
    ),
    SourceConfig(
        kb_id="kb_116",
        name="CommonCrawl WET 2024-51 段5",
        kb_type="general",
        description="Common Crawl 2024年12月爬取段5",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_116_commoncrawl_2024_51_seg5",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-51/wet.paths.gz", "max_files": 50, "offset": 200},
    ),
    SourceConfig(
        kb_id="kb_117",
        name="CommonCrawl WET 2024-42 段1",
        kb_type="general",
        description="Common Crawl 2024年10月爬取段1",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_117_commoncrawl_2024_42_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-42/wet.paths.gz", "max_files": 50},
    ),
    SourceConfig(
        kb_id="kb_118",
        name="CommonCrawl WET 2024-42 段2",
        kb_type="general",
        description="Common Crawl 2024年10月爬取段2",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_118_commoncrawl_2024_42_seg2",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-42/wet.paths.gz", "max_files": 50, "offset": 50},
    ),
    SourceConfig(
        kb_id="kb_119",
        name="CommonCrawl WET 2024-33 段1",
        kb_type="general",
        description="Common Crawl 2024年8月爬取段1",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_119_commoncrawl_2024_33_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-33/wet.paths.gz", "max_files": 50},
    ),
    SourceConfig(
        kb_id="kb_120",
        name="CommonCrawl WET 2024-33 段2",
        kb_type="general",
        description="Common Crawl 2024年8月爬取段2",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_120_commoncrawl_2024_33_seg2",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-33/wet.paths.gz", "max_files": 50, "offset": 50},
    ),
    SourceConfig(
        kb_id="kb_121",
        name="CommonCrawl WET 2024-26 段1",
        kb_type="general",
        description="Common Crawl 2024年6月爬取段1",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_121_commoncrawl_2024_26_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-26/wet.paths.gz", "max_files": 50},
    ),
    SourceConfig(
        kb_id="kb_122",
        name="CommonCrawl WET 2024-18 段1",
        kb_type="general",
        description="Common Crawl 2024年4月爬取段1",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_122_commoncrawl_2024_18_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-18/wet.paths.gz", "max_files": 50},
    ),
    SourceConfig(
        kb_id="kb_123",
        name="CommonCrawl WET 2024-10 段1",
        kb_type="general",
        description="Common Crawl 2024年2月爬取段1",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_123_commoncrawl_2024_10_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-10/wet.paths.gz", "max_files": 50},
    ),
    SourceConfig(
        kb_id="kb_124",
        name="CommonCrawl WET 2023-50 段1",
        kb_type="general",
        description="Common Crawl 2023年12月爬取段1",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_124_commoncrawl_2023_50_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2023-50/wet.paths.gz", "max_files": 50},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 13: More GitHub Repos — Expanded Code Corpus (15 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE2_GITHUB_MORE: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_125",
        name="GitHub系统工具项目",
        kb_type="code",
        description="系统工具与命令行工具源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_125_github_system_tools",
        extra={"repos": [
            "tmux/tmux", "neovim/neovim", "vim/vim", "emacs-mirror/emacs",
            "htop-dev/htop", "bcicen/ctop", "dalance/procs", "sharkdp/fd",
            "sharkdp/bat", "sharkdp/ripgrep", "BurntSushi/ripgrep", "ogham/exa",
            "bootandy/dust", " ClementTsang/bottom", "cantino/huginn",
            "nushell/nushell", "starship/starship", "ajeetdsouza/zoxide",
            "junegunn/fzf", "zellij-org/zellij", "wez/wezterm", "alacritty/alacritty",
            "kovidgoyal/kitty", "tmate-io/tmate", "byobu/byobu",
        ]},
    ),
    SourceConfig(
        kb_id="kb_126",
        name="GitHub数据库项目",
        kb_type="code",
        description="数据库与存储引擎源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_126_github_databases",
        extra={"repos": [
            "mysql/mysql-server", "mariadb/server", "sqlite/sqlite",
            "facebook/rocksdb", "google/leveldb", "apache/cassandra",
            "apache/hbase", "neo4j/neo4j", "arangodb/arangodb",
            "scylladb/scylladb", "yugabytedb/yugabyte-db", "pingcap/tidb",
            "cockroachdb/cockroach", "vitessio/vitess", "timescale/timescaledb",
            "influxdata/influxdb", "prometheus/prometheus", " VictoriaMetrics/VictoriaMetrics",
            "grafana/loki", "etcd-io/etcd", "hashicorp/consul",
            "hashicorp/nomad", "minio/minio", "ceph/ceph",
        ]},
    ),
    SourceConfig(
        kb_id="kb_127",
        name="GitHubAI/ML项目",
        kb_type="code",
        description="人工智能与机器学习项目源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_127_github_ai_ml",
        extra={"repos": [
            "huggingface/transformers", "openai/whisper", " Stability-AI/stablediffusion",
            "comfyanonymous/ComfyUI", "AUTOMATIC1111/stable-diffusion-webui",
            "microsoft/DeepSpeed", "mosaicml/composer", "huggingface/datasets",
            "huggingface/accelerate", "pytorch/vision", "pytorch/audio",
            "pytorch/text", "keras-team/keras", "google/jax",
            "apple/ml-stable-diffusion", "lllyasviel/Fooocus", "oobabooga/text-generation-webui",
            "ggerganov/llama.cpp", "ml-explore/mlx", "microsoft/LLaVA-Med",
            "langchain-ai/langchain", "microsoft/autogen", "open-interpreter/open-interpreter",
            "gradio-app/gradio", "streamlit/streamlit", "mlflow/mlflow",
        ]},
    ),
    SourceConfig(
        kb_id="kb_128",
        name="GitHub前端项目",
        kb_type="code",
        description="前端框架与工具源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_128_github_frontend",
        extra={"repos": [
            "sveltejs/svelte", "solidjs/solid", "preactjs/preact",
            "lit/lit", "jquery/jquery", "emberjs/ember.js",
            "backbone/backbone", "senchalabs/connect", "expressjs/express",
            "koa/koa", "fastify/fastify", "nestjs/nest",
            "strapi/strapi", "directus/directus", "payloadcms/payload",
            "nextjs/next.js", "nuxt/nuxt", "remix-run/remix",
            "withastro/astro", "11ty/eleventy", "gatsbyjs/gatsby",
            "hexojs/hexo", "vuepress/vuepress", "docusaurus/docusaurus",
            "storybookjs/storybook", "jestjs/jest", "vitest-dev/vitest",
            "cypress-io/cypress", "playwright/playwright", "webpack/webpack",
            "vitejs/vite", "rollup/rollup", "parcel-bundler/parcel",
            "esbuild/esbuild", "evanw/esbuild", "swc-project/swc",
            "biomejs/biome", "tailwindlabs/tailwindcss", "sass/sass",
            "less/less.js", "postcss/postcss", "eslint/eslint",
            "prettier/prettier", "stylelint/stylelint",
        ]},
    ),
    SourceConfig(
        kb_id="kb_129",
        name="GitHub后端项目",
        kb_type="code",
        description="后端服务与中间件源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_129_github_backend",
        extra={"repos": [
            "spring-projects/spring-framework", "spring-projects/spring-boot",
            "micronaut-projects/micronaut-core", "quarkusio/quarkus",
            "eclipse-vertx/vert.x", "netty/netty", "reactor/reactor-core",
            "ratpack/ratpack", "dropwizard/dropwizard", "jooby-project/jooby",
            "apache/dubbo", "alibaba/nacos", "apache/skywalking",
            "apache/shardingsphere", "seata/seata", "sentinel-group/sentinel-alpha",
            "envoyproxy/envoy", "traefik/traefik", "caddyserver/caddy",
            "nginx/nginx", "apache/httpd", "lighttpd/lighttpd",
            "haproxy/haproxy", "varnishcache/varnish-cache", "squid-cache/squid",
            "kong/kong", "tyktechnologies/tyk", "zuul/zuul",
            "grpc/grpc", "apache/thrift", "capnproto/capnproto",
            "protocolbuffers/protobuf", "google/flatbuffers", "apache/avro",
        ]},
    ),
    SourceConfig(
        kb_id="kb_130",
        name="GitHub安全项目",
        kb_type="code",
        description="安全工具与框架源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_130_github_security",
        extra={"repos": [
            "OWASP/ZAP", "nmap/nmap", "sqlmapproject/sqlmap",
            "rapid7/metasploit-framework", "beefproject/beef",
            "HashiCorp/vault", "ansible-semaphore/semaphore",
            "Snort3/snort3", "suricata/suricata", "zeek/zeek",
            "osquery/osquery", "wazuh/wazuh", "crowdsecurity/crowdsec",
            "falco/falco", "aquasecurity/trivy", "anchore/syft",
            "anchore/grype", "slsa-framework/slsa", "sigstore/cosign",
            "open-policy-agent/opa", "cyberark/conjur", "keycloak/keycloak",
            "ory/hydra", "ory/kratos", "authelia/authelia",
            "dexidp/dex", "pomerium/pomerium", "vouch/vouch-proxy",
        ]},
    ),
    SourceConfig(
        kb_id="kb_131",
        name="GitHub语言编译器",
        kb_type="code",
        description="编程语言与编译器源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_131_github_compilers",
        extra={"repos": [
            "gcc-mirror/gcc", "llvm/llvm-project", "rust-lang/rust",
            "python/cpython", "openjdk/jdk", "dotnet/roslyn",
            "golang/go", "ruby/ruby", "php/php-src",
            "swiftlang/swift", "dart-lang/sdk", "scala/scala",
            "JetBrains/kotlin", "TypeScript/TypeScript", "elm/compiler",
            "purescript/purescript", "idris-lang/Idris2", "ziglang/zig",
            "nim-lang/Nim", "crystal-lang/crystal", "vlang/v",
            "odin-lang/Odin", "jai-lang/jai", "valelang/vale",
            "Wren-lang/wren", "red/red", "racket/racket",
            "ghc/ghc", "ocaml/ocaml", "coq/coq",
            "leanprover/lean4", "agda/agda", "idris-lang/Idris-dev",
        ]},
    ),
    SourceConfig(
        kb_id="kb_132",
        name="GitHub操作系统",
        kb_type="code",
        description="操作系统与内核源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_132_github_os",
        extra={"repos": [
            "torvalds/linux", "freebsd/freebsd-src", "openbsd/src",
            "netbsd/src", "dragonflybsd/dragonfly",
            "illumos/illumos-gate", "joyent/illumos-joyent",
            "haiku/haiku", "reactos/reactos", "menuetos/menuetos",
            "redox-os/redox", "HubrisOS/hubris", "tock/tock",
            "zephyrproject-rtos/zephyr", "FreeRTOS/FreeRTOS",
            "nuttx/nuttx", "RIOT-OS/RIOT", "contiki-ng/contiki-ng",
            "tinyos/tinyos-main", "MirageOS/mirage", "IncludeOS/includeos",
            "osdev/homebrew-osdev", "littlekernel/lk", " HelenOS/HelenOS",
            "fuchsia-mirror/fuchsia",
        ]},
    ),
    SourceConfig(
        kb_id="kb_133",
        name="GitHub移动开发",
        kb_type="code",
        description="移动开发框架与工具源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_133_github_mobile",
        extra={"repos": [
            "flutter/flutter", "react-native/react-native", "ionic-team/ionic-framework",
            "apache/cordova-ios", "apache/cordova-android", "nativescript/NativeScript",
            "capacitor-community/capacitor", "framework7io/framework7",
            "onsenui/OnsenUI", "quasarframework/quasar", "vuetifyjs/vuetify",
            "android/platform_frameworks_base", "android/platform_system_core",
            "android/platform_build", "android/platform_packages_apps_settings",
            "apple/swift", "apple/swift-corelibs-foundation",
            "apple/swift-package-manager", "apple/sourcekit-lsp",
            "Kotlin/kotlinx.coroutines", "Kotlin/kotlinx.serialization",
            "square/okhttp", "square/retrofit", "bumptech/glide",
            "facebook/fresco", "facebook/litho", "airbnb/lottie-android",
            "realm/realm-java", "greenrobot/greenDAO", "ObjectBox/objectbox-java",
            "alibaba/arouter", "alibaba/fastjson", "alibaba/druid",
            "scwang90/SmartRefreshLayout", "CymChad/BaseRecyclerViewAdapterHelper",
        ]},
    ),
    SourceConfig(
        kb_id="kb_134",
        name="GitHub游戏开发",
        kb_type="code",
        description="游戏引擎与游戏开发工具源码",
        source_url="https://github.com/",
        download_method="git",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_134_github_gamedev",
        extra={"repos": [
            "godotengine/godot", "cryengine/cryengine", "flarum/flarum",
            "cocos2d/cocos2d-x", "cocos/cocos-engine", "love2d/love",
            "libsdl-org/SDL", "glfw/glfw", "bulletphysics/bullet3",
            "recastnavigation/recastnavigation", " gameplay3d/gameplay",
            "urho3d/Urho3D", "AtomicGameEngine/AtomicGameEngine",
            "defold/defold", "enigma-dev/enigma-dev", "GDevelopApp/GDevelop",
            "bevyengine/bevy", "amethyst/amethyst", "FyroxEngine/Fyrox",
            "PistonDevelopers/piston", "ggez/ggez", "hecrj/iced",
            "raysan5/raylib", "raysan5/raygui", "ocornut/imgui",
            "epezent/implot", "nothings/stb", "handmadehero/misc",
            "makietools/makie", "JuliaPlots/Plots.jl", "plotly/plotly.py",
        ]},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 14: More Academic Papers — Expanded ArXiv (10 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE2_ACADEMIC_MORE: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_135",
        name="ArXiv计算机系统",
        kb_type="academic",
        description="ArXiv操作系统/网络/分布式系统",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_135_arxiv_systems",
        time_range=(2020, 2026),
        extra={"categories": ["cs.OS", "cs.NI", "cs.DC", "cs.DS"], "max_results": 25000},
    ),
    SourceConfig(
        kb_id="kb_136",
        name="ArXiv软件工程",
        kb_type="academic",
        description="ArXiv软件工程与编程语言",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_136_arxiv_se_pl",
        time_range=(2020, 2026),
        extra={"categories": ["cs.SE", "cs.PL", "cs.FL"], "max_results": 25000},
    ),
    SourceConfig(
        kb_id="kb_137",
        name="ArXiv人机交互",
        kb_type="academic",
        description="ArXiv人机交互与图形学",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_137_arxiv_hci_graphics",
        time_range=(2020, 2026),
        extra={"categories": ["cs.HC", "cs.GR", "cs.MM", "cs.SD"], "max_results": 20000},
    ),
    SourceConfig(
        kb_id="kb_138",
        name="ArXiv计算生物学",
        kb_type="academic",
        description="ArXiv计算生物学与生物信息学",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_138_arxiv_bio",
        time_range=(2020, 2026),
        extra={"categories": ["q-bio", "cs.CE"], "max_results": 20000},
    ),
    SourceConfig(
        kb_id="kb_139",
        name="ArXiv物理学",
        kb_type="academic",
        description="ArXiv物理学各领域",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_139_arxiv_physics",
        time_range=(2020, 2026),
        extra={"categories": ["physics", "astro-ph", "cond-mat", "hep-th", "hep-ex"], "max_results": 30000},
    ),
    SourceConfig(
        kb_id="kb_140",
        name="ArXiv统计与概率",
        kb_type="academic",
        description="ArXiv统计学与概率论",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_140_arxiv_stats",
        time_range=(2020, 2026),
        extra={"categories": ["stat.ML", "stat.TH", "stat.ME", "stat.AP", "stat.CO"], "max_results": 20000},
    ),
    SourceConfig(
        kb_id="kb_141",
        name="ArXiv电气工程",
        kb_type="academic",
        description="ArXiv电气工程与信号处理",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_141_arxiv_eess",
        time_range=(2020, 2026),
        extra={"categories": ["eess.SP", "eess.IV", "eess.AS", "eess.SY"], "max_results": 20000},
    ),
    SourceConfig(
        kb_id="kb_142",
        name="ArXiv经济学全类",
        kb_type="academic",
        description="ArXiv经济学全分类",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_142_arxiv_econ_full",
        time_range=(2020, 2026),
        extra={"categories": ["econ.EM", "econ.GN", "econ.TH", "q-fin.CP", "q-fin.MF"], "max_results": 15000},
    ),
    SourceConfig(
        kb_id="kb_143",
        name="ArXiv化学与材料",
        kb_type="academic",
        description="ArXiv化学与材料科学",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_143_arxiv_chem",
        time_range=(2020, 2026),
        extra={"categories": ["physics.chem-ph", "cond-mat.mtrl-sci", "cond-mat.soft"], "max_results": 15000},
    ),
    SourceConfig(
        kb_id="kb_144",
        name="ArXiv地球科学",
        kb_type="academic",
        description="ArXiv地球科学与环境",
        source_url="https://arxiv.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_144_arxiv_earth",
        time_range=(2020, 2026),
        extra={"categories": ["physics.ao-ph", "physics.geo-ph", "physics.space-ph", "astro-ph.EP"], "max_results": 15000},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 15: More Books — Gutenberg Additional Languages (8 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE2_BOOKS_MORE: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_145",
        name="Project Gutenberg法文",
        kb_type="book",
        description="公版法文文学",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_145_gutenberg_french",
        extra={"language": "fr", "max_books": 10000},
    ),
    SourceConfig(
        kb_id="kb_146",
        name="Project Gutenberg德文",
        kb_type="book",
        description="公版德文文学",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_146_gutenberg_german",
        extra={"language": "de", "max_books": 10000},
    ),
    SourceConfig(
        kb_id="kb_147",
        name="Project Gutenberg西班牙文",
        kb_type="book",
        description="公版西班牙文文学",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_147_gutenberg_spanish",
        extra={"language": "es", "max_books": 8000},
    ),
    SourceConfig(
        kb_id="kb_148",
        name="Project Gutenberg意大利文",
        kb_type="book",
        description="公版意大利文文学",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_148_gutenberg_italian",
        extra={"language": "it", "max_books": 6000},
    ),
    SourceConfig(
        kb_id="kb_149",
        name="Project Gutenberg葡萄牙文",
        kb_type="book",
        description="公版葡萄牙文文学",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_149_gutenberg_portuguese",
        extra={"language": "pt", "max_books": 5000},
    ),
    SourceConfig(
        kb_id="kb_150",
        name="Project Gutenberg俄文",
        kb_type="book",
        description="公版俄文文学",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_150_gutenberg_russian",
        extra={"language": "ru", "max_books": 5000},
    ),
    SourceConfig(
        kb_id="kb_151",
        name="Project Gutenberg荷兰文",
        kb_type="book",
        description="公版荷兰文文学",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_151_gutenberg_dutch",
        extra={"language": "nl", "max_books": 4000},
    ),
    SourceConfig(
        kb_id="kb_152",
        name="Project Gutenberg多语言合集",
        kb_type="book",
        description="其他语言公版书",
        source_url="https://www.gutenberg.org/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_152_gutenberg_other",
        extra={"language": "multi", "max_books": 10000, "languages": ["pl", "sv", "fi", "da", "el", "la", "ja"]},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 16: Sports Data (5 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE3_SPORTS: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_153",
        name="新浪体育新闻",
        kb_type="sports",
        description="新浪体育新闻聚合（足球、篮球、综合体育）",
        source_url="https://sports.sina.com.cn/",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_153_sina_sports",
        extra={"rss_urls": [
            "https://rss.sina.com.cn/roll/sports/hot_roll.xml",
            "https://rss.sina.com.cn/news/sports/focus.xml",
        ]},
    ),
    SourceConfig(
        kb_id="kb_154",
        name="ESPN体育新闻",
        kb_type="sports",
        description="ESPN全球体育新闻（英文）",
        source_url="https://www.espn.com/",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_154_espn_sports",
        extra={"rss_urls": [
            "https://www.espn.com/espn/rss/news",
            "https://www.espn.com/espn/rss/nba",
            "https://www.espn.com/espn/rss/soccer",
        ]},
    ),
    SourceConfig(
        kb_id="kb_155",
        name="NBA官方新闻",
        kb_type="sports",
        description="NBA官方网站新闻与数据",
        source_url="https://www.nba.com/news",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_155_nba_news",
        extra={"deep_crawl": True, "max_pages": 2000},
    ),
    SourceConfig(
        kb_id="kb_156",
        name="虎扑体育社区",
        kb_type="sports",
        description="虎扑体育新闻与社区热帖",
        source_url="https://www.hupu.com/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_156_hupu_sports",
        extra={"deep_crawl": True, "max_pages": 1000},
    ),
    SourceConfig(
        kb_id="kb_157",
        name="搜狐体育新闻",
        kb_type="sports",
        description="搜狐体育新闻聚合",
        source_url="https://sports.sohu.com/",
        download_method="rss",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_157_sohu_sports",
        extra={"rss_urls": [
            "https://rss.news.sohu.com/rss/sports.xml",
        ]},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 17: Big Four Banks + Major Banks (5 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE3_BANKS: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_158",
        name="工商银行年报公告",
        kb_type="finance",
        description="中国工商银行年度报告、季度报告、临时公告",
        source_url="http://www.icbc.com.cn/column/1438058319784067152.html",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_158_icbc_reports",
        time_range=(2018, 2026),
        extra={"deep_crawl": True, "pdf_download": True, "bank": "icbc"},
    ),
    SourceConfig(
        kb_id="kb_159",
        name="建设银行年报公告",
        kb_type="finance",
        description="中国建设银行年度报告、季度报告、临时公告",
        source_url="http://www.ccb.com/cn/investor/information/financial_index.html",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_159_ccb_reports",
        time_range=(2018, 2026),
        extra={"deep_crawl": True, "pdf_download": True, "bank": "ccb"},
    ),
    SourceConfig(
        kb_id="kb_160",
        name="农业银行年报公告",
        kb_type="finance",
        description="中国农业银行年度报告、季度报告、临时公告",
        source_url="http://www.abchina.com/cn/AboutABC/Investor_Relations/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_160_abc_reports",
        time_range=(2018, 2026),
        extra={"deep_crawl": True, "pdf_download": True, "bank": "abc"},
    ),
    SourceConfig(
        kb_id="kb_161",
        name="中国银行年报公告",
        kb_type="finance",
        description="中国银行年度报告、季度报告、临时公告",
        source_url="http://www.boc.cn/investor/ir3/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_161_boc_reports",
        time_range=(2018, 2026),
        extra={"deep_crawl": True, "pdf_download": True, "bank": "boc"},
    ),
    SourceConfig(
        kb_id="kb_162",
        name="交通银行年报公告",
        kb_type="finance",
        description="交通银行年度报告、季度报告、临时公告",
        source_url="http://www.bankcomm.com/BankCommSite/default.shtml",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_162_bocom_reports",
        time_range=(2018, 2026),
        extra={"deep_crawl": True, "pdf_download": True, "bank": "bocom"},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 18: Public Opinion / Social Media Sentiment (5 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE3_PUBLIC_OPINION: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_163",
        name="微博热搜舆情",
        kb_type="opinion",
        description="微博热搜榜单与热点话题",
        source_url="https://s.weibo.com/top/summary",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_163_weibo_hot",
        extra={"deep_crawl": False, "max_pages": 50, "refresh_interval": "hourly"},
    ),
    SourceConfig(
        kb_id="kb_164",
        name="知乎热榜舆情",
        kb_type="opinion",
        description="知乎热榜与热门问答",
        source_url="https://www.zhihu.com/hot",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_164_zhihu_hot",
        extra={"deep_crawl": False, "max_pages": 100},
    ),
    SourceConfig(
        kb_id="kb_165",
        name="百度热搜舆情",
        kb_type="opinion",
        description="百度热搜榜单",
        source_url="https://top.baidu.com/board",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_165_baidu_hot",
        extra={"deep_crawl": False, "max_pages": 50},
    ),
    SourceConfig(
        kb_id="kb_166",
        name="今日头条热点",
        kb_type="opinion",
        description="今日头条热点新闻聚合",
        source_url="https://www.toutiao.com/hot-event/hot-board/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_166_toutiao_hot",
        extra={"deep_crawl": False, "max_pages": 100},
    ),
    SourceConfig(
        kb_id="kb_167",
        name="人民网舆情频道",
        kb_type="opinion",
        description="人民网舆情监测与研究报告",
        source_url="http://yuqing.people.com.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_167_people_yuqing",
        time_range=(2020, 2026),
        extra={"deep_crawl": True, "max_pages": 500},
    ),
]



# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 19: Massive Structured Knowledge Bases (10 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE4_STRUCTURED: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_168",
        name="Wikidata完整知识图谱",
        kb_type="general",
        description="Wikidata完整JSON dump（约101GB压缩，88.7亿三元组）",
        source_url="https://dumps.wikimedia.org/wikidatawiki/entities/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_168_wikidata_full",
        extra={"dump_url": "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"},
    ),
    SourceConfig(
        kb_id="kb_169",
        name="DBpedia知识图谱",
        kb_type="general",
        description="DBpedia从Wikipedia提取的结构化数据",
        source_url="https://wiki.dbpedia.org/downloads",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_169_dbpedia",
        extra={"dump_url": "https://downloads.dbpedia.org/current/core-i18n/en/labels_en.ttl.bz2"},
    ),
    SourceConfig(
        kb_id="kb_170",
        name="GeoNames地理实体",
        kb_type="general",
        description="全球地理名称数据库（约1300万地点）",
        source_url="https://www.geonames.org/export/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_170_geonames",
        extra={"dump_url": "https://download.geonames.org/export/dump/allCountries.zip"},
    ),
    SourceConfig(
        kb_id="kb_171",
        name="PubChem化学物质",
        kb_type="academic",
        description="NIH PubChem化学化合物数据库",
        source_url="https://pubchem.ncbi.nlm.nih.gov/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_171_pubchem",
        extra={"max_compounds": 100000},
    ),
    SourceConfig(
        kb_id="kb_172",
        name="UniProt蛋白质数据库",
        kb_type="academic",
        description="UniProt蛋白质序列与功能注释",
        source_url="https://www.uniprot.org/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_172_uniprot",
        extra={"dump_url": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.xml.gz"},
    ),
    SourceConfig(
        kb_id="kb_173",
        name="OpenStreetMap数据",
        kb_type="general",
        description="OSM开放地图数据（中国区域）",
        source_url="https://download.geofabrik.de/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_173_osm_china",
        extra={"dump_url": "https://download.geofabrik.de/asia/china-latest.osm.pbf"},
    ),
    SourceConfig(
        kb_id="kb_174",
        name="美国人口普查数据",
        kb_type="intl",
        description="US Census Bureau开放数据",
        source_url="https://www.census.gov/data.html",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_174_us_census",
    ),
    SourceConfig(
        kb_id="kb_175",
        name="OpenAlex学术图谱",
        kb_type="academic",
        description="OpenAlex开放学术图谱（论文/作者/机构/概念）",
        source_url="https://openalex.org/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_175_openalex",
        extra={"snapshot_url": "https://api.openalex.org/works?per-page=200&page=1"},
    ),
    SourceConfig(
        kb_id="kb_176",
        name="PubMed Central全文",
        kb_type="academic",
        description="PubMed Central开放获取全文文章",
        source_url="https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_176_pmc_bulk",
        extra={"bulk_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/"},
    ),
    SourceConfig(
        kb_id="kb_177",
        name="Semantic Scholar学术数据",
        kb_type="academic",
        description="Semantic Scholar开放学术数据集",
        source_url="https://www.semanticscholar.org/product/api",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_177_semantic_scholar",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 20: Government Open Data Portals (8 KBs)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE4_GOVT_OPENDATA: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_178",
        name="国家数据统计局",
        kb_type="statistics",
        description="国家统计局完整统计数据",
        source_url="https://data.stats.gov.cn/",
        download_method="api_free",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_178_stats_gov_full",
    ),
    SourceConfig(
        kb_id="kb_179",
        name="中国裁判文书网",
        kb_type="law",
        description="中国法院裁判文书（公开部分）",
        source_url="https://wenshu.court.gov.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_179_wenshu",
        time_range=(2015, 2026),
        extra={"deep_crawl": True, "max_docs": 50000},
    ),
    SourceConfig(
        kb_id="kb_180",
        name="国家企业信用信息公示系统",
        kb_type="policy",
        description="企业信用信息公示数据",
        source_url="https://www.gsxt.gov.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_180_gsxt",
        extra={"deep_crawl": False, "max_companies": 10000},
    ),
    SourceConfig(
        kb_id="kb_181",
        name="全国标准信息公共服务平台",
        kb_type="policy",
        description="国家标准/行业标准/地方标准全文",
        source_url="https://std.samr.gov.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_181_standards",
        extra={"deep_crawl": True, "max_standards": 20000},
    ),
    SourceConfig(
        kb_id="kb_182",
        name="专利数据",
        kb_type="tech",
        description="中国专利全文数据",
        source_url="https://pss-system.cponline.cnipa.gov.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_182_patents",
        extra={"deep_crawl": True, "max_patents": 50000},
    ),
    SourceConfig(
        kb_id="kb_183",
        name="商标数据",
        kb_type="law",
        description="中国商标公告数据",
        source_url="https://sbj.cnipa.gov.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_183_trademarks",
        extra={"deep_crawl": False, "max_trademarks": 30000},
    ),
    SourceConfig(
        kb_id="kb_184",
        name="政府采购网",
        kb_type="policy",
        description="中国政府采购公告与中标信息",
        source_url="http://www.ccgp.gov.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_184_gov_procurement",
        extra={"deep_crawl": True, "max_notices": 50000},
    ),
    SourceConfig(
        kb_id="kb_185",
        name="国家哲学社会科学文献中心",
        kb_type="academic",
        description="社会科学学术论文与期刊",
        source_url="https://www.ncpssd.cn/",
        download_method="crawl",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_185_ncpssd",
        extra={"deep_crawl": True, "max_papers": 30000},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 21: Extended CommonCrawl (10 KBs) — More web-scale corpus
# ═══════════════════════════════════════════════════════════════════════════════

PHASE4_COMMONCRAWL_MORE: list[SourceConfig] = [
    SourceConfig(
        kb_id="kb_186",
        name="CommonCrawl WET 2025-08 段1",
        kb_type="general",
        description="Common Crawl 2025年2月爬取段",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_186_commoncrawl_2025_08_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-08/wet.paths.gz", "max_files": 100},
    ),
    SourceConfig(
        kb_id="kb_187",
        name="CommonCrawl WET 2025-13 段1",
        kb_type="general",
        description="Common Crawl 2025年3月爬取段",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_187_commoncrawl_2025_13_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-13/wet.paths.gz", "max_files": 100},
    ),
    SourceConfig(
        kb_id="kb_188",
        name="CommonCrawl WET 2025-18 段1",
        kb_type="general",
        description="Common Crawl 2025年4月爬取段",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_188_commoncrawl_2025_18_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-18/wet.paths.gz", "max_files": 100},
    ),
    SourceConfig(
        kb_id="kb_189",
        name="CommonCrawl WET 2025-24 段1",
        kb_type="general",
        description="Common Crawl 2025年6月爬取段",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_189_commoncrawl_2025_24_seg1",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-24/wet.paths.gz", "max_files": 100},
    ),
    SourceConfig(
        kb_id="kb_190",
        name="CommonCrawl WET 2024-51 段6",
        kb_type="general",
        description="Common Crawl 2024年12月补充段",
        source_url="https://commoncrawl.s3.amazonaws.com/",
        download_method="direct",
        output_dir="/Users/xuhongduo/Projects/deep-research/data/kb_sources/kb_190_commoncrawl_2024_51_seg6",
        extra={"wet_url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-51/wet.paths.gz", "max_files": 100, "offset": 250},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# ALL SOURCES COMBINED
# ═══════════════════════════════════════════════════════════════════════════════

ALL_SOURCES: list[SourceConfig] = (
    PHASE1_GOVERNMENT +
    PHASE1_NEWS +
    PHASE1_ACADEMIC +
    PHASE1_CODE +
    PHASE1_MATH +
    PHASE1_BOOKS +
    PHASE1_INTL +
    PHASE1_INDUSTRY +
    PHASE1_WIKIPEDIA +
    PHASE1_ADDITIONAL +
    PHASE2_WIKIPEDIA_LANGS +
    PHASE2_COMMONCRAWL +
    PHASE2_GITHUB_MORE +
    PHASE2_ACADEMIC_MORE +
    PHASE2_BOOKS_MORE +
    PHASE3_SPORTS +
    PHASE3_BANKS +
    PHASE3_PUBLIC_OPINION +
    PHASE4_STRUCTURED +
    PHASE4_GOVT_OPENDATA +
    PHASE4_COMMONCRAWL_MORE
)


def get_source_by_id(kb_id: str) -> SourceConfig | None:
    for s in ALL_SOURCES:
        if s.kb_id == kb_id:
            return s
    return None


def list_sources_by_type(kb_type: str) -> list[SourceConfig]:
    return [s for s in ALL_SOURCES if s.kb_type == kb_type]


def get_stats() -> dict[str, Any]:
    """Return statistics about all configured sources."""
    by_type: dict[str, int] = {}
    by_method: dict[str, int] = {}
    for s in ALL_SOURCES:
        by_type[s.kb_type] = by_type.get(s.kb_type, 0) + 1
        by_method[s.download_method] = by_method.get(s.download_method, 0) + 1
    return {
        "total_sources": len(ALL_SOURCES),
        "by_type": by_type,
        "by_method": by_method,
    }


if __name__ == "__main__":
    stats = get_stats()
    print(f"Total sources: {stats['total_sources']}")
    print("\nBy type:")
    for t, c in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
        print(f"  {t:20s}: {c:3d}")
    print("\nBy method:")
    for m, c in sorted(stats["by_method"].items(), key=lambda x: -x[1]):
        print(f"  {m:20s}: {c:3d}")
