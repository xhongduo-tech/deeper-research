"""
Knowledge Enricher — offline research depth compensation.

核心设计：无法连接互联网时，通过深度激活 LLM 内部知识储备来弥补。
- 为每条研究发现添加行业基准、历史背景、监管框架、最佳实践
- 激发 LLM 用结构化框架（SWOT/PEST/Porter等）分析主题
- 注入预打包的行业基准数据（offline_data/industry_benchmarks.json）
- 生成可引用的行业洞察和数据估算
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from app.skills.base import Skill
from app.services.llm_service import chat

logger = logging.getLogger(__name__)

# ── Load pre-packaged offline benchmark data ──────────────────────────────────
_BENCHMARKS: dict = {}
try:
    _data_dir = Path(__file__).parent.parent.parent / "prompt_assets" / "offline_data"
    _bench_file = _data_dir / "industry_benchmarks.json"
    if _bench_file.exists():
        _BENCHMARKS = json.loads(_bench_file.read_text(encoding="utf-8"))
        logger.info("[KnowledgeEnricher] Loaded offline benchmarks: %s", str(_bench_file))
except Exception as _e:
    logger.warning("[KnowledgeEnricher] Could not load offline benchmarks: %s", _e)


class KnowledgeEnricherSkill(Skill):
    name = "enrich_knowledge"
    description = "离线知识深化：将简短研究发现扩充为有行业背景、数据基准和框架支撑的深度洞察，弥补无互联网连接的能力缺口"
    category = "offline"
    parameters = {
        "topic": {"type": "string", "description": "研究主题或核心问题"},
        "findings": {"type": "string", "description": "已有研究发现（可为空，则从零深化）"},
        "report_type": {"type": "string", "description": "报告类型（影响知识深化方向）"},
        "enrich_mode": {
            "type": "string",
            "description": "深化模式: benchmarks（行业基准数据）| frameworks（分析框架）| mechanisms（底层机制）| scenarios（情景推演）| all",
            "default": "all",
        },
        "domain": {
            "type": "string",
            "description": "领域标签，提升知识深化精准度，如 finance / manufacturing / retail / technology / healthcare",
            "default": "general",
        },
    }

    DOMAIN_CONTEXT = {
        "finance": "金融行业，关注监管合规（银保监/证监会）、利率风险、信用风险、流动性管理、资本充足率",
        "manufacturing": "制造业，关注产能利用率、库存周转、精益生产、供应链弹性、碳排放合规",
        "retail": "零售行业，关注坪效、库存周转天数、客户获取成本（CAC）、复购率、线上线下融合",
        "technology": "科技行业，关注技术迭代周期、研发投入占比、用户增长、留存率、单位经济模型",
        "healthcare": "医疗健康行业，关注DRG/DIP医保政策、合规要求、临床路径、药械采购",
        "real_estate": "房地产行业，关注去化率、土地储备、融资成本、政策调控、城市化率",
        "general": "通用商业场景，关注收入增长、成本控制、市场份额、运营效率、风险管理",
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        topic = params.get("topic", "")
        findings = params.get("findings", "")
        report_type = params.get("report_type", "")
        enrich_mode = params.get("enrich_mode", "all")
        domain = params.get("domain", "general")

        if not topic:
            return {"result": "", "error": "topic is required"}

        domain_hint = self.DOMAIN_CONTEXT.get(domain, self.DOMAIN_CONTEXT["general"])

        findings_block = f"\n\n## 已有研究发现（请在此基础上深化）\n{findings[:2000]}" if findings else ""

        mode_instructions = self._build_mode_instructions(enrich_mode, domain)

        # Inject pre-packaged offline benchmark data relevant to this domain
        benchmark_block = self._build_benchmark_block(domain)

        messages = [
            {
                "role": "system",
                "content": f"""你是顶级行业分析师，拥有深厚的内部知识储备。你的任务是在无互联网访问的情况下，通过激活已有知识为研究提供高质量的深度支撑。

领域背景：{domain_hint}
报告类型：{report_type}

核心原则：
1. 优先引用下方【离线基准数据库】中的数字，标注"（离线数据库）"
2. 基于训练知识补充具体数据时，标注"（行业均值）""（通常水平）"
3. 优先提供结构化、可量化的洞察，而非泛泛而谈
4. 识别该领域的关键变量和驱动因素
5. 提供同类企业/项目的参照系

{benchmark_block}""",
            },
            {
                "role": "user",
                "content": f"""请为以下主题提供深度知识支撑。{findings_block}

## 研究主题
{topic}

## 知识深化任务
{mode_instructions}

输出格式要求：
- 使用 ### 标题组织内容
- 数据估算需标注来源类型（行业均值/历史数据/专家估算/模型推算）
- 关键数字加粗：**18.5%**
- 每个模块输出200-400字""",
            },
        ]
        result = await chat(messages, temperature=0.35, max_tokens=2500)
        return {"result": result, "mode": enrich_mode, "domain": domain}

    def _build_benchmark_block(self, domain: str) -> str:
        """Build a compact benchmark reference block from pre-packaged JSON data."""
        if not _BENCHMARKS:
            return ""
        try:
            sections: list[str] = ["【离线基准数据库（可直接引用）】"]

            # Financial ratios — gross margin for the domain
            gm = _BENCHMARKS.get("financial_ratios", {}).get("gross_margin", {})
            domain_map = {
                "technology": "software_saas", "finance": "financial_services",
                "healthcare": "healthcare", "manufacturing": "manufacturing",
                "retail": "retail", "real_estate": "real_estate",
                "logistics": "logistics", "education": "education",
            }
            key = domain_map.get(domain, "software_saas")
            if key in gm:
                d = gm[key]
                sections.append(
                    f"毛利率基准（{key}）: 低档={d['low']*100:.0f}% / 中位={d['median']*100:.0f}% / 高档={d['high']*100:.0f}%"
                )

            # NPS benchmarks
            nps = _BENCHMARKS.get("operational_kpis", {}).get("nps_benchmarks", {})
            if nps:
                nps_by_ind = nps.get("by_industry", {})
                nps_line = "NPS基准: 世界级>70 / 优秀50-70 / 良好30-50 / 需改进0-30"
                sections.append(nps_line)

            # Analysis frameworks (brief list)
            frameworks = _BENCHMARKS.get("analysis_frameworks", {})
            if frameworks:
                fw_names = " / ".join(frameworks.keys())
                sections.append(f"可用分析框架: {fw_names}")

            # Market size snapshot
            markets = _BENCHMARKS.get("market_size_china", {})
            if markets:
                ai = markets.get("ai_market_2024", {})
                digital = markets.get("digital_economy_total_2023", {})
                if ai and digital:
                    sections.append(
                        f"中国市场规模参考: AI市场2024={ai.get('value','')} ({ai.get('yoy_growth','')}增); "
                        f"数字经济总量2023={digital.get('value','')} ({digital.get('yoy_growth','')}增)"
                    )

            # Risk categories
            risks = _BENCHMARKS.get("risk_categories", {})
            if risks:
                risk_cats = " | ".join(f"{k}: {', '.join(v[:2])}" for k, v in list(risks.items())[:3])
                sections.append(f"主要风险类别参考: {risk_cats}")

            return "\n".join(sections) if len(sections) > 1 else ""
        except Exception as e:
            logger.debug("[KnowledgeEnricher] benchmark block error: %s", e)
            return ""

    def _build_mode_instructions(self, mode: str, domain: str) -> str:
        modes = {
            "benchmarks": """### 行业基准数据深化
请提供：
1. **核心财务/运营指标基准**（行业中位数、优秀水平、落后水平三档）
2. **关键比率参照**（如毛利率区间、周转天数、增速基准）
3. **竞争格局数量感知**（市场集中度 CR3/CR5 估算、头部规模）
4. **发展阶段判断标准**（用什么指标区分初期/成长/成熟/衰退）""",

            "frameworks": """### 分析框架应用
请分别用以下框架对主题进行分析：
1. **SWOT分析** — 列出各2-3条具体的优势/劣势/机会/威胁
2. **PEST分析** — 政策/经济/社会/技术四维度的具体影响因素
3. **波特五力分析** — 行业竞争强度的结构性判断
4. **关键成功因素** — 该领域3-5个决定性竞争要素""",

            "mechanisms": """### 底层机制与因果链分析
请揭示：
1. **核心驱动机制**（什么因素在驱动增长/下滑，因果链是什么）
2. **关键约束因素**（什么是最大瓶颈，为什么）
3. **滞后效应分析**（政策/市场变化通常需要多久传导到结果层）
4. **历史规律参照**（类似情况在历史上的演变模式）""",

            "scenarios": """### 情景推演与预测
请构建：
1. **基准情景**（60%概率，维持现有趋势的推演）
2. **乐观情景**（25%概率，最有利条件下的推演）
3. **悲观情景**（15%概率，主要风险触发时的推演）
4. **关键转折点**（哪些信号表明正在向哪个情景演变）""",

            "all": """请按以下顺序提供全面的知识深化：

### 1. 行业基准数据
核心指标的典型区间（行业均值/优秀水平），数据来源标注"（行业估算）"

### 2. 分析框架速览
SWOT要点（各2条）+ 关键成功因素（3-5条）

### 3. 底层驱动机制
核心增长/风险驱动因素，以及典型的因果传导路径

### 4. 情景推演
基准/乐观/悲观三情景的核心差异和关键前提

### 5. 专家洞察
基于领域知识的2-3条非显而易见的高价值洞察""",
        }
        return modes.get(mode, modes["all"])
