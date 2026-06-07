"""
DataAgent 世界观数据库架构 v1.0 — 10层知识分层配置
按用户《大模型世界观数据库架构规范 v1.0》设计

总存储预算: ≤ 3.5TB
分层原则: 热数据 → 温数据 → 冷数据
每条知识携带: 置信度[0.0-1.0] | 时间戳 | 来源溯源
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LayerConfig:
    """世界观知识层配置"""
    layer_id: str          # L0-L9
    layer_name: str        # 中文名称
    layer_name_en: str     # 英文名称
    budget_gb: float       # 存储预算(GB)
    description: str       # 描述
    data_sources: list[SourceConfig] = field(default_factory=list)


@dataclass
class SourceConfig:
    """单个数据源配置"""
    kb_id: str
    name: str
    kb_type: str
    description: str
    source_url: str
    download_method: str
    output_dir: str
    time_range: tuple[int, int] = (2020, 2026)
    file_pattern: str = "*.md"
    extra: dict = field(default_factory=dict)
    confidence_default: float = 0.8   # 默认置信度
    source_priority: str = "P2"       # P0-P4 来源优先级
    layer_tags: list[str] = field(default_factory=list)  # 所属知识层


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 0: 元知识层 (Meta-Knowledge) — 预算 50GB
# 本体定义、schema、概念体系、版本控制
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_0_META = LayerConfig(
    layer_id="L0",
    layer_name="元知识层",
    layer_name_en="Meta-Knowledge",
    budget_gb=50.0,
    description="数据库自身的元数据、本体定义、版本控制信息",
    data_sources=[
        SourceConfig(
            kb_id="L0_001",
            name="Wikidata Schema本体",
            kb_type="ontology",
            description="Wikidata属性/类/约束schema（从dump提取）",
            source_url="https://dumps.wikimedia.org/wikidatawiki/entities/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L0_meta/wikidata_schema",
            extra={"dump_url": "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2", "extract_schema_only": True},
            confidence_default=1.0,
            source_priority="P1",
            layer_tags=["L0", "ontology"],
        ),
        SourceConfig(
            kb_id="L0_002",
            name="Schema.org本体",
            kb_type="ontology",
            description="Schema.org结构化数据schema",
            source_url="https://schema.org/version/latest/schemaorg-current-https.jsonld",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L0_meta/schema_org",
            confidence_default=1.0,
            source_priority="P1",
            layer_tags=["L0", "ontology"],
        ),
        SourceConfig(
            kb_id="L0_003",
            name="DBpedia本体",
            kb_type="ontology",
            description="DBpedia本体定义与属性映射",
            source_url="https://downloads.dbpedia.org/current/core-i18n/en/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L0_meta/dbpedia_ontology",
            extra={"dump_url": "https://downloads.dbpedia.org/current/core-i18n/en/labels_en.ttl.bz2"},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L0", "ontology"],
        ),
        SourceConfig(
            kb_id="L0_004",
            name="WordNet词汇本体",
            kb_type="ontology",
            description="普林斯顿WordNet英语词汇语义网络",
            source_url="https://wordnet.princeton.edu/download/current-version",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L0_meta/wordnet",
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L0", "ontology", "language"],
        ),
        SourceConfig(
            kb_id="L0_005",
            name="Wikipedia分类体系",
            kb_type="ontology",
            description="Wikipedia分类层级与主题体系",
            source_url="https://dumps.wikimedia.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L0_meta/wikipedia_categories",
            extra={"dump_url": "https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-categorylinks.sql.gz"},
            confidence_default=0.9,
            source_priority="P1",
            layer_tags=["L0", "taxonomy"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1: 基础事实层 (Ground Facts) — 预算 800GB
# 物理世界 + 人类社会的基础实体与属性
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_1_FACTS = LayerConfig(
    layer_id="L1",
    layer_name="基础事实层",
    layer_name_en="Ground Facts",
    budget_gb=800.0,
    description="物理世界与人类社会的基础实体与属性",
    data_sources=[
        # ── 物理世界 ──
        SourceConfig(
            kb_id="L1_001",
            name="Wikidata完整实体",
            kb_type="entity",
            description="Wikidata全部实体与属性（88.7亿三元组）",
            source_url="https://dumps.wikimedia.org/wikidatawiki/entities/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/wikidata_entities",
            extra={"dump_url": "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L1", "entity", "cross_domain"],
        ),
        SourceConfig(
            kb_id="L1_002",
            name="GeoNames全球地点",
            kb_type="entity",
            description="全球1300万地理名称与坐标",
            source_url="https://download.geonames.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/geonames",
            extra={"dump_url": "https://download.geonames.org/export/dump/allCountries.zip"},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L1", "entity", "geography"],
        ),
        SourceConfig(
            kb_id="L1_003",
            name="OpenStreetMap中国",
            kb_type="entity",
            description="OSM开放地图数据（中国区域）",
            source_url="https://download.geofabrik.de/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/osm_china",
            extra={"dump_url": "https://download.geofabrik.de/asia/china-latest.osm.pbf"},
            confidence_default=0.9,
            source_priority="P2",
            layer_tags=["L1", "entity", "geography"],
        ),
        SourceConfig(
            kb_id="L1_004",
            name="PubChem化学物质",
            kb_type="entity",
            description="NIH化学化合物数据库（1.1亿+化合物）",
            source_url="https://pubchem.ncbi.nlm.nih.gov/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/pubchem",
            extra={"max_compounds": 500000},
            confidence_default=0.95,
            source_priority="P0",
            layer_tags=["L1", "entity", "chemistry"],
        ),
        SourceConfig(
            kb_id="L1_005",
            name="UniProt蛋白质",
            kb_type="entity",
            description="UniProt蛋白质序列与功能注释",
            source_url="https://www.uniprot.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/uniprot",
            extra={"dump_url": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.xml.gz"},
            confidence_default=0.98,
            source_priority="P0",
            layer_tags=["L1", "entity", "biology"],
        ),
        # ── 人类社会 ──
        SourceConfig(
            kb_id="L1_006",
            name="Wikipedia多语言实体",
            kb_type="entity",
            description="Wikipedia多语言全文（10+语种）",
            source_url="https://dumps.wikimedia.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/wikipedia_multilang",
            extra={"languages": ["zh", "en", "de", "ja", "fr", "es", "it", "ru", "ko", "ar"]},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L1", "entity", "cross_domain"],
        ),
        SourceConfig(
            kb_id="L1_007",
            name="世界银行开放数据",
            kb_type="statistics",
            description="World Bank全球经济与发展指标",
            source_url="https://data.worldbank.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/world_bank",
            time_range=(1960, 2026),
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L1", "property", "economy"],
        ),
        SourceConfig(
            kb_id="L1_008",
            name="联合国数据",
            kb_type="statistics",
            description="UN Data Portal全球统计",
            source_url="https://data.un.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/un_data",
            time_range=(2000, 2026),
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L1", "property", "society"],
        ),
        SourceConfig(
            kb_id="L1_009",
            name="CIA世界概况",
            kb_type="statistics",
            description="CIA World Factbook国家概况",
            source_url="https://www.cia.gov/the-world-factbook/",
            download_method="wget",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/cia_factbook",
            confidence_default=0.9,
            source_priority="P1",
            layer_tags=["L1", "property", "society"],
        ),
        SourceConfig(
            kb_id="L1_010",
            name="国家统计局完整数据",
            kb_type="statistics",
            description="中国国家统计局完整统计数据",
            source_url="https://data.stats.gov.cn/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/stats_gov_cn",
            time_range=(1990, 2026),
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L1", "property", "economy"],
        ),
        SourceConfig(
            kb_id="L1_011",
            name="巨潮资讯A股年报",
            kb_type="finance",
            description="全部A股上市公司年度报告（上交所+深交所）",
            source_url="http://www.cninfo.com.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/cninfo_annual",
            time_range=(2015, 2026),
            extra={"deep_crawl": True, "pdf_download": True},
            confidence_default=0.9,
            source_priority="P0",
            layer_tags=["L1", "entity", "property", "finance"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: 关系网络层 (Relation Networks) — 预算 600GB
# 实体间结构化关联，知识图谱的边
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_2_RELATIONS = LayerConfig(
    layer_id="L2",
    layer_name="关系网络层",
    layer_name_en="Relation Networks",
    budget_gb=600.0,
    description="实体间的结构化关联，构成知识图谱的边",
    data_sources=[
        SourceConfig(
            kb_id="L2_001",
            name="Wikidata三元组关系",
            kb_type="relation",
            description="Wikidata完整三元组（主语-谓语-宾语）",
            source_url="https://dumps.wikimedia.org/wikidatawiki/entities/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L2_relations/wikidata_triples",
            extra={"dump_url": "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2", "extract_triples": True},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L2", "relation", "cross_domain"],
        ),
        SourceConfig(
            kb_id="L2_002",
            name="DBpedia关系图谱",
            kb_type="relation",
            description="DBpedia实体关系与属性映射",
            source_url="https://downloads.dbpedia.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L2_relations/dbpedia_relations",
            extra={"dump_url": "https://downloads.dbpedia.org/current/core-i18n/en/mappingbased_objects_en.ttl.bz2"},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L2", "relation", "cross_domain"],
        ),
        SourceConfig(
            kb_id="L2_003",
            name="OpenStreetMap空间关系",
            kb_type="relation",
            description="地理实体空间关系（相邻/包含/位于）",
            source_url="https://download.geofabrik.de/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L2_relations/osm_relations",
            extra={"dump_url": "https://download.geofabrik.de/asia/china-latest.osm.pbf"},
            confidence_default=0.9,
            source_priority="P2",
            layer_tags=["L2", "relation", "spatial"],
        ),
        SourceConfig(
            kb_id="L2_004",
            name="GitHub项目依赖关系",
            kb_type="relation",
            description="开源项目间的依赖与引用关系",
            source_url="https://github.com/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L2_relations/github_dependencies",
            extra={"max_repos": 100000},
            confidence_default=0.9,
            source_priority="P2",
            layer_tags=["L2", "relation", "technology"],
        ),
        SourceConfig(
            kb_id="L2_005",
            name="学术论文引用网络",
            kb_type="relation",
            description="ArXiv/学术论文引用关系",
            source_url="https://export.arxiv.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L2_relations/paper_citations",
            time_range=(2015, 2026),
            extra={"categories": ["cs.*", "math.*", "physics.*", "q-fin.*"], "max_papers": 100000},
            confidence_default=0.9,
            source_priority="P0",
            layer_tags=["L2", "relation", "knowledge"],
        ),
        SourceConfig(
            kb_id="L2_006",
            name="CommonCrawl网页链接图",
            kb_type="relation",
            description="Web-scale页面链接关系",
            source_url="https://commoncrawl.s3.amazonaws.com/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L2_relations/commoncrawl_links",
            extra={"segments": ["CC-MAIN-2024-51", "CC-MAIN-2024-42", "CC-MAIN-2025-08"], "max_files": 200},
            confidence_default=0.7,
            source_priority="P3",
            layer_tags=["L2", "relation", "web"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 3: 因果与机制层 (Causal & Mechanistic) — 预算 400GB
# 解释"为什么"和"如何运作"的深度知识
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_3_CAUSAL = LayerConfig(
    layer_id="L3",
    layer_name="因果与机制层",
    layer_name_en="Causal & Mechanistic",
    budget_gb=400.0,
    description="解释为什么和如何运作的深度知识",
    data_sources=[
        SourceConfig(
            kb_id="L3_001",
            name="ArXiv全领域论文",
            kb_type="mechanism",
            description="ArXiv科学论文（含机制解释、因果推断）",
            source_url="https://arxiv.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal/arxiv_all",
            time_range=(2015, 2026),
            extra={"categories": ["cs", "math", "physics", "q-bio", "q-fin", "stat", "eess", "econ"], "max_results": 200000},
            confidence_default=0.8,
            source_priority="P0",
            layer_tags=["L3", "mechanism", "science"],
        ),
        SourceConfig(
            kb_id="L3_002",
            name="PubMed生物医学机制",
            kb_type="mechanism",
            description="PubMed高影响力生物医学论文（机制研究）",
            source_url="https://pubmed.ncbi.nlm.nih.gov/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal/pubmed_mechanisms",
            time_range=(2015, 2026),
            extra={"search_terms": ["mechanism", "pathway", "causal", "signaling"], "max_results": 100000},
            confidence_default=0.85,
            source_priority="P0",
            layer_tags=["L3", "mechanism", "biology", "medicine"],
        ),
        SourceConfig(
            kb_id="L3_003",
            name="OpenStax科学教材",
            kb_type="mechanism",
            description="OpenStax免费科学教材（物理/化学/生物/经济）",
            source_url="https://openstax.org/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal/openstax_textbooks",
            extra={"subjects": ["physics", "chemistry", "biology", "economics"], "deep_crawl": True},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L3", "mechanism", "science"],
        ),
        SourceConfig(
            kb_id="L3_004",
            name="MIT OCW自然科学课程",
            kb_type="mechanism",
            description="MIT开放课程（物理/化学/生物/地球科学）",
            source_url="https://ocw.mit.edu/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal/mit_ocw_science",
            extra={"courses": ["8.01", "8.02", "5.111", "7.01", "12.001"], "deep_crawl": True},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L3", "mechanism", "science"],
        ),
        SourceConfig(
            kb_id="L3_005",
            name="央行货币政策机制",
            kb_type="mechanism",
            description="中国人民银行货币政策执行报告（含传导机制分析）",
            source_url="http://www.pbc.gov.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal/pbc_monetary_mechanism",
            time_range=(2015, 2026),
            extra={"deep_crawl": True, "quarterly": True},
            confidence_default=0.9,
            source_priority="P1",
            layer_tags=["L3", "mechanism", "economics"],
        ),
        SourceConfig(
            kb_id="L3_006",
            name="中国经济机制研究",
            kb_type="mechanism",
            description="国务院发展研究中心/发改委研究报告（经济机制）",
            source_url="https://www.drc.gov.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal/drc_research",
            time_range=(2015, 2026),
            extra={"deep_crawl": True, "pdf_download": True},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L3", "mechanism", "economics"],
        ),
        SourceConfig(
            kb_id="L3_007",
            name="CommonCrawl机制语料",
            kb_type="mechanism",
            description="从CommonCrawl提取的科学技术、经济机制类网页文本",
            source_url="https://data.commoncrawl.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal/cc_causal",
            extra={"segments": ["CC-MAIN-2024-51", "CC-MAIN-2025-08"], "max_files": 500},
            confidence_default=0.6,
            source_priority="P3",
            layer_tags=["L3", "mechanism", "web"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 4: 价值与规范层 (Normative Knowledge) — 预算 100GB
# 伦理、法律、社会规范等"应然"知识
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_4_NORMATIVE = LayerConfig(
    layer_id="L4",
    layer_name="价值与规范层",
    layer_name_en="Normative Knowledge",
    budget_gb=100.0,
    description="伦理、法律、社会规范等应然知识",
    data_sources=[
        SourceConfig(
            kb_id="L4_001",
            name="中国法律法规全文",
            kb_type="law",
            description="全国人大法律法规 + 国务院行政法规",
            source_url="https://www.npc.gov.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/china_laws",
            time_range=(1949, 2026),
            extra={"deep_crawl": True, "full_text": True},
            confidence_default=1.0,
            source_priority="P0",
            layer_tags=["L4", "law", "norm"],
        ),
        SourceConfig(
            kb_id="L4_002",
            name="司法解释与判例",
            kb_type="law",
            description="最高法司法解释 + 裁判文书网公开判例",
            source_url="https://wenshu.court.gov.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/court_judgments",
            time_range=(2015, 2026),
            extra={"deep_crawl": True, "max_docs": 100000},
            confidence_default=0.9,
            source_priority="P0",
            layer_tags=["L4", "law", "precedent"],
        ),
        SourceConfig(
            kb_id="L4_003",
            name="金融监管规则",
            kb_type="law",
            description="银保监会/证监会/金融监管总局规章",
            source_url="https://www.nfra.gov.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/finance_regulations",
            time_range=(2018, 2026),
            extra={"deep_crawl": True},
            confidence_default=0.95,
            source_priority="P0",
            layer_tags=["L4", "law", "finance"],
        ),
        SourceConfig(
            kb_id="L4_004",
            name="国际公约与条约",
            kb_type="law",
            description="联合国宪章/国际公约/海洋法/战争法",
            source_url="https://treaties.un.org/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/un_treaties",
            confidence_default=0.95,
            source_priority="P0",
            layer_tags=["L4", "law", "international"],
        ),
        SourceConfig(
            kb_id="L4_005",
            name="AI伦理准则",
            kb_type="ethics",
            description="全球AI伦理准则与框架（欧盟/中国/美国）",
            source_url="https://unesdoc.unesco.org/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/ai_ethics",
            extra={"deep_crawl": True, "max_docs": 5000},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L4", "ethics", "technology"],
        ),
        SourceConfig(
            kb_id="L4_006",
            name="儒家伦理经典",
            kb_type="ethics",
            description="中国哲学书电子化计划（儒家/道家/佛家经典）",
            source_url="https://ctext.org/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/chinese_classics",
            extra={"max_texts": 5000, "deep_crawl": True},
            confidence_default=0.9,
            source_priority="P1",
            layer_tags=["L4", "ethics", "culture"],
        ),
        SourceConfig(
            kb_id="L4_007",
            name="CommonCrawl规范文本",
            kb_type="law",
            description="从CommonCrawl提取的政策、法律、社会规范类网页文本",
            source_url="https://data.commoncrawl.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/cc_regulations",
            extra={"segments": ["CC-MAIN-2024-51", "CC-MAIN-2025-08"], "max_files": 300},
            confidence_default=0.6,
            source_priority="P3",
            layer_tags=["L4", "law", "web"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 5: 认知与思维层 (Cognitive Frameworks) — 预算 150GB
# 逻辑、方法论、思维模型等"如何思考"的知识
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_5_COGNITIVE = LayerConfig(
    layer_id="L5",
    layer_name="认知与思维层",
    layer_name_en="Cognitive Frameworks",
    budget_gb=150.0,
    description="逻辑、方法论、思维模型等如何思考的知识",
    data_sources=[
        SourceConfig(
            kb_id="L5_001",
            name="MIT OCW数学与逻辑",
            kb_type="cognitive",
            description="MIT数学课程（微积分/线性代数/概率论/离散数学）",
            source_url="https://ocw.mit.edu/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L5_cognitive/mit_ocw_math",
            extra={"courses": ["18.01", "18.02", "18.03", "18.06", "18.6501", "6.042J"], "deep_crawl": True},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L5", "logic", "math"],
        ),
        SourceConfig(
            kb_id="L5_002",
            name="ArXiv纯数学与应用数学",
            kb_type="cognitive",
            description="ArXiv数学论文（证明方法/抽象思维）",
            source_url="https://arxiv.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L5_cognitive/arxiv_math",
            time_range=(2015, 2026),
            extra={"categories": ["math.AG", "math.AT", "math.GT", "math.NT", "math.AP", "math.NA", "math.OC", "math.ST", "math.PR"], "max_results": 50000},
            confidence_default=0.85,
            source_priority="P0",
            layer_tags=["L5", "logic", "math"],
        ),
        SourceConfig(
            kb_id="L5_003",
            name="统计学习方法教材",
            kb_type="cognitive",
            description="统计学习经典教材与方法论",
            source_url="https://web.stanford.edu/~hastie/ElemStatLearn/",
            download_method="wget",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L5_cognitive/statistical_learning",
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L5", "methodology", "statistics"],
        ),
        SourceConfig(
            kb_id="L5_004",
            name="NIST数学函数手册",
            kb_type="cognitive",
            description="NIST DLMF数学函数参考手册",
            source_url="https://dlmf.nist.gov/",
            download_method="wget",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L5_cognitive/nist_dlmf",
            confidence_default=0.98,
            source_priority="P0",
            layer_tags=["L5", "reference", "math"],
        ),
        SourceConfig(
            kb_id="L5_005",
            name="哲学思维经典",
            kb_type="cognitive",
            description="西方哲学经典文本（Gutenberg哲学类）",
            source_url="https://www.gutenberg.org/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L5_cognitive/philosophy_classics",
            extra={"subject": "philosophy", "max_books": 5000},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L5", "philosophy", "thinking"],
        ),
        SourceConfig(
            kb_id="L5_006",
            name="科学方法论文献",
            kb_type="cognitive",
            description="科学哲学与方法论（观察/实验/建模/证伪）",
            source_url="https://arxiv.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L5_cognitive/scientific_method",
            time_range=(2015, 2026),
            extra={"categories": ["physics.hist-ph", "cs.CY"], "max_results": 10000},
            confidence_default=0.85,
            source_priority="P0",
            layer_tags=["L5", "methodology", "science"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 6: 程序与实用层 (Procedural Knowledge) — 预算 300GB
# 如何做、操作性知识
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_6_PROCEDURAL = LayerConfig(
    layer_id="L6",
    layer_name="程序与实用层",
    layer_name_en="Procedural Knowledge",
    budget_gb=300.0,
    description="如何做的操作性知识",
    data_sources=[
        SourceConfig(
            kb_id="L6_001",
            name="编程语言官方文档全集",
            kb_type="procedural",
            description="Python/JavaScript/Go/Rust/Java等官方文档",
            source_url="https://docs.python.org/",
            download_method="wget",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L6_procedural/language_docs",
            extra={"docs": ["python", "javascript", "go", "rust", "java", "cpp", "csharp", "kotlin", "swift"]},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L6", "tool", "code"],
        ),
        SourceConfig(
            kb_id="L6_002",
            name="框架与工具文档",
            kb_type="procedural",
            description="PyTorch/React/Vue/Docker/K8s等框架文档",
            source_url="https://pytorch.org/docs/",
            download_method="wget",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L6_procedural/framework_docs",
            extra={"frameworks": ["pytorch", "tensorflow", "react", "vue", "docker", "kubernetes", "spring"]},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L6", "tool", "framework"],
        ),
        SourceConfig(
            kb_id="L6_003",
            name="GitHub开源项目源码",
            kb_type="procedural",
            description="精选开源项目源码与文档（Linux/Chrome/TensorFlow等）",
            source_url="https://github.com/",
            download_method="git",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L6_procedural/github_source",
            extra={"repos": ["torvalds/linux", "chromium/chromium", "tensorflow/tensorflow", "pytorch/pytorch", "microsoft/vscode"]},
            confidence_default=0.9,
            source_priority="P2",
            layer_tags=["L6", "tool", "code"],
        ),
        SourceConfig(
            kb_id="L6_004",
            name="StackOverflow技术问答",
            kb_type="procedural",
            description="StackOverflow热门技术问答与解决方案",
            source_url="https://archive.org/details/stackexchange",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L6_procedural/stackoverflow",
            extra={"dump_url": "https://archive.org/download/stackexchange/stackoverflow.com-Posts.7z"},
            confidence_default=0.85,
            source_priority="P2",
            layer_tags=["L6", "faq", "troubleshooting"],
        ),
        SourceConfig(
            kb_id="L6_005",
            name="算法题解与模式",
            kb_type="procedural",
            description="LeetCode题解与算法设计模式",
            source_url="https://leetcode.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L6_procedural/leetcode",
            confidence_default=0.85,
            source_priority="P2",
            layer_tags=["L6", "algorithm", "pattern"],
        ),
        SourceConfig(
            kb_id="L6_006",
            name="标准操作程序",
            kb_type="procedural",
            description="国家标准/行业标准/ISO标准全文",
            source_url="https://std.samr.gov.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L6_procedural/standards_sop",
            extra={"deep_crawl": True, "max_standards": 50000},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L6", "sop", "standard"],
        ),
        SourceConfig(
            kb_id="L6_007",
            name="CommonCrawl程序知识",
            kb_type="procedural",
            description="从CommonCrawl提取的技术文档、教程、博客等程序性知识",
            source_url="https://data.commoncrawl.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L6_procedural/cc_procedural",
            extra={"segments": ["CC-MAIN-2024-51", "CC-MAIN-2025-08"], "max_files": 400},
            confidence_default=0.6,
            source_priority="P3",
            layer_tags=["L6", "tool", "web"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 7: 多模态对齐层 (Multimodal Alignment) — 预算 800GB
# 跨模态的实体对齐与语义关联
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_7_MULTIMODAL = LayerConfig(
    layer_id="L7",
    layer_name="多模态对齐层",
    layer_name_en="Multimodal Alignment",
    budget_gb=800.0,
    description="跨模态的实体对齐与语义关联",
    data_sources=[
        SourceConfig(
            kb_id="L7_001",
            name="Wikipedia图像描述",
            kb_type="multimodal",
            description="Wikipedia图像与对应描述文本",
            source_url="https://dumps.wikimedia.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L7_multimodal/wikipedia_images",
            extra={"dump_type": "image_descriptions", "languages": ["zh", "en"]},
            confidence_default=0.85,
            source_priority="P1",
            layer_tags=["L7", "image", "text"],
        ),
        SourceConfig(
            kb_id="L7_002",
            name="CommonCrawl图文对",
            kb_type="multimodal",
            description="从CC提取的网页图像-Alt文本-上下文对齐",
            source_url="https://commoncrawl.s3.amazonaws.com/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L7_multimodal/cc_image_text",
            extra={"segments": ["CC-MAIN-2024-51", "CC-MAIN-2025-08"], "extract_image_text": True, "max_files": 300},
            confidence_default=0.7,
            source_priority="P3",
            layer_tags=["L7", "image", "text", "web"],
        ),
        SourceConfig(
            kb_id="L7_003",
            name="地理空间多模态",
            kb_type="multimodal",
            description="GeoNames坐标 + OSM地图 + Wikipedia地点描述",
            source_url="https://download.geonames.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L7_multimodal/geo_multimodal",
            extra={"dump_url": "https://download.geonames.org/export/dump/allCountries.zip"},
            confidence_default=0.9,
            source_priority="P1",
            layer_tags=["L7", "spatial", "text", "geo"],
        ),
        SourceConfig(
            kb_id="L7_004",
            name="学术论文图表",
            kb_type="multimodal",
            description="ArXiv论文中的图表与对应说明文字",
            source_url="https://arxiv.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L7_multimodal/arxiv_figures",
            time_range=(2020, 2026),
            extra={"categories": ["cs.CV", "cs.LG", "physics"], "extract_figures": True, "max_results": 50000},
            confidence_default=0.8,
            source_priority="P0",
            layer_tags=["L7", "image", "text", "science"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 8: 时序与演化层 (Temporal & Evolutionary) — 预算 200GB
# 知识的动态变化与历史演进
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_8_TEMPORAL = LayerConfig(
    layer_id="L8",
    layer_name="时序与演化层",
    layer_name_en="Temporal & Evolutionary",
    budget_gb=200.0,
    description="知识的动态变化与历史演进",
    data_sources=[
        SourceConfig(
            kb_id="L8_001",
            name="A股上市公司年报序列",
            kb_type="temporal",
            description="全部A股公司历年年报（时序财务数据）",
            source_url="http://www.cninfo.com.cn/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L8_temporal/cninfo_annual_series",
            time_range=(2010, 2026),
            extra={"deep_crawl": True, "pdf_download": True, "all_exchanges": True},
            confidence_default=0.9,
            source_priority="P0",
            layer_tags=["L8", "temporal", "finance"],
        ),
        SourceConfig(
            kb_id="L8_002",
            name="政府工作报告时间线",
            kb_type="temporal",
            description="国务院政府工作报告（2014-2025，政策演变）",
            source_url="https://www.gov.cn/premier/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L8_temporal/gov_work_reports",
            time_range=(2014, 2025),
            extra={"deep_crawl": True, "pdf_pattern": r"\.pdf$", "content_selector": ".pages_content"},
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L8", "temporal", "policy"],
        ),
        SourceConfig(
            kb_id="L8_003",
            name="IMF世界经济展望序列",
            kb_type="temporal",
            description="IMF WEO历年报告（全球经济预测演变）",
            source_url="https://www.imf.org/en/Publications/WEO",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L8_temporal/imf_weo_series",
            time_range=(2000, 2026),
            extra={"deep_crawl": True, "pdf_download": True},
            confidence_default=0.9,
            source_priority="P1",
            layer_tags=["L8", "temporal", "economy"],
        ),
        SourceConfig(
            kb_id="L8_004",
            name="世界银行时序数据",
            kb_type="temporal",
            description="World Bank全球发展指标时间序列",
            source_url="https://data.worldbank.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L8_temporal/world_bank_timeseries",
            time_range=(1960, 2026),
            confidence_default=0.95,
            source_priority="P1",
            layer_tags=["L8", "temporal", "statistics"],
        ),
        SourceConfig(
            kb_id="L8_005",
            name="Wikipedia历史修订",
            kb_type="temporal",
            description="Wikipedia页面历史修订记录（知识演化）",
            source_url="https://dumps.wikimedia.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L8_temporal/wikipedia_revisions",
            extra={"dump_type": "revision_history", "languages": ["zh", "en"]},
            confidence_default=0.85,
            source_priority="P2",
            layer_tags=["L8", "temporal", "knowledge_evolution"],
        ),
        SourceConfig(
            kb_id="L8_006",
            name="CommonCrawl时序网页",
            kb_type="temporal",
            description="跨时间窗口的CommonCrawl网页文本，用于观察语言和社会话题演化",
            source_url="https://data.commoncrawl.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L8_temporal/cc_temporal",
            extra={"segments": ["CC-MAIN-2024-51", "CC-MAIN-2025-08"], "max_files": 300},
            confidence_default=0.6,
            source_priority="P3",
            layer_tags=["L8", "temporal", "web"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 9: 不确定性与边界层 (Uncertainty & Boundaries) — 预算 100GB
# 明确标注不知道和有争议的元知识
# ═══════════════════════════════════════════════════════════════════════════════

LAYER_9_UNCERTAINTY = LayerConfig(
    layer_id="L9",
    layer_name="不确定性与边界层",
    layer_name_en="Uncertainty & Boundaries",
    budget_gb=100.0,
    description="明确标注不知道和有争议的元知识",
    data_sources=[
        SourceConfig(
            kb_id="L9_001",
            name="科学前沿争议",
            kb_type="uncertainty",
            description="科学前沿未解问题与争议（弦理论/意识/气候敏感度）",
            source_url="https://arxiv.org/",
            download_method="api_free",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L9_uncertainty/scientific_controversies",
            time_range=(2020, 2026),
            extra={"search_terms": ["controversy", "debate", "uncertainty", "open problem"], "max_results": 30000},
            confidence_default=0.6,
            source_priority="P0",
            layer_tags=["L9", "uncertainty", "science"],
        ),
        SourceConfig(
            kb_id="L9_002",
            name="历史解释争议",
            kb_type="uncertainty",
            description="历史事件的不同解释与评价争议",
            source_url="https://www.jstor.org/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L9_uncertainty/historical_debates",
            extra={"deep_crawl": True, "max_articles": 10000},
            confidence_default=0.6,
            source_priority="P1",
            layer_tags=["L9", "uncertainty", "history"],
        ),
        SourceConfig(
            kb_id="L9_003",
            name="伦理争议案例库",
            kb_type="uncertainty",
            description="伦理困境与争议案例（电车难题/基因编辑/AI权利）",
            source_url="https://plato.stanford.edu/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L9_uncertainty/ethical_debates",
            extra={"deep_crawl": True, "topics": ["ethics", "moral_dilemma", "ai_ethics"]},
            confidence_default=0.65,
            source_priority="P1",
            layer_tags=["L9", "controversy", "ethics"],
        ),
        SourceConfig(
            kb_id="L9_004",
            name="经济预测分歧",
            kb_type="uncertainty",
            description="经济学派分歧与预测差异（IMF/世行/各国央行）",
            source_url="https://www.imf.org/",
            download_method="crawl",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L9_uncertainty/economic_forecast_divergence",
            time_range=(2015, 2026),
            extra={"deep_crawl": True, "pdf_download": True},
            confidence_default=0.7,
            source_priority="P1",
            layer_tags=["L9", "uncertainty", "economics"],
        ),
        SourceConfig(
            kb_id="L9_005",
            name="Wikipedia争议标记",
            kb_type="uncertainty",
            description="Wikipedia争议性条目标记与多方观点",
            source_url="https://dumps.wikimedia.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L9_uncertainty/wikipedia_disputes",
            extra={"dump_type": "disputed_pages", "languages": ["zh", "en"]},
            confidence_default=0.7,
            source_priority="P2",
            layer_tags=["L9", "controversy", "multiperspective"],
        ),
        SourceConfig(
            kb_id="L9_006",
            name="CommonCrawl争议语料",
            kb_type="uncertainty",
            description="从CommonCrawl提取的争议性、对抗性网页文本语料",
            source_url="https://data.commoncrawl.org/",
            download_method="direct",
            output_dir="/Users/xuhongduo/Projects/deep-research/data/worldview/L9_uncertainty/commoncrawl_divergence",
            extra={"segments": ["CC-MAIN-2024-51", "CC-MAIN-2025-08"], "max_files": 500},
            confidence_default=0.6,
            source_priority="P3",
            layer_tags=["L9", "controversy", "web"],
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# ALL LAYERS COMBINED
# ═══════════════════════════════════════════════════════════════════════════════

ALL_LAYERS: list[LayerConfig] = [
    LAYER_0_META,
    LAYER_1_FACTS,
    LAYER_2_RELATIONS,
    LAYER_3_CAUSAL,
    LAYER_4_NORMATIVE,
    LAYER_5_COGNITIVE,
    LAYER_6_PROCEDURAL,
    LAYER_7_MULTIMODAL,
    LAYER_8_TEMPORAL,
    LAYER_9_UNCERTAINTY,
]


def get_layer_by_id(layer_id: str) -> LayerConfig | None:
    for layer in ALL_LAYERS:
        if layer.layer_id == layer_id:
            return layer
    return None


def get_all_sources() -> list[SourceConfig]:
    sources = []
    for layer in ALL_LAYERS:
        sources.extend(layer.data_sources)
    return sources


def get_stats() -> dict[str, Any]:
    """返回10层架构统计信息"""
    stats = {
        "total_layers": len(ALL_LAYERS),
        "total_sources": 0,
        "total_budget_gb": 0.0,
        "layers": [],
    }
    for layer in ALL_LAYERS:
        n_sources = len(layer.data_sources)
        stats["total_sources"] += n_sources
        stats["total_budget_gb"] += layer.budget_gb
        stats["layers"].append({
            "id": layer.layer_id,
            "name": layer.layer_name,
            "budget_gb": layer.budget_gb,
            "sources": n_sources,
        })
    return stats


if __name__ == "__main__":
    stats = get_stats()
    print(f"╔══════════════════════════════════════════════════════════════╗")
    print(f"║  DataAgent 世界观数据库架构 v1.0 — 10层知识分层              ║")
    print(f"╠══════════════════════════════════════════════════════════════╣")
    print(f"║  总数据源: {stats['total_sources']:3d} 个                                     ║")
    print(f"║  存储预算: {stats['total_budget_gb']:6.1f} GB (目标 ≤ 3500 GB)                ║")
    print(f"╠══════════════════════════════════════════════════════════════╣")
    for layer in stats["layers"]:
        bar = "█" * int(layer["budget_gb"] / 50)
        print(f"║  {layer['id']} {layer['name']:12s} | {layer['sources']:2d}源 | {layer['budget_gb']:6.1f}GB | {bar}  ║")
    print(f"╚══════════════════════════════════════════════════════════════╝")
