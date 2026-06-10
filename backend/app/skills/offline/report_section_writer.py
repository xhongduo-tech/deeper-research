"""Report Section Writer — SOTA-enhanced professional report section generation.

Enhancements over v1:
1. Chain-of-Thought planning: outline → content
2. Self-critique with structured scoring (8 dimensions)
3. Adversarial red-team review
4. Quality-gated rewrite loop
5. Quality score output (0-100)
6. Persona rotation: writer → critic → rewriter → polisher

Reference: Anthropic's "Building effective agents", OpenAI's "6 strategies"
"""
from app.skills.base import Skill
from app.services.llm_service import chat
from app.skills.offline.sota_utils import (
    cot_write,
    self_critique,
    adversarial_review,
    rewrite_with_critique,
    quality_gate,
)

REPORT_TYPE_FORMAT_RULES: dict[str, str] = {
    "学术论文": (
        "严格学术规范：客观第三人称，每个论点有文献或数据支撑，"
        "使用规范标题层级(一、二级用中文序号，三级用###)，"
        "数字遵守有效数字规则，引用标注[序号]。"
    ),
    "实验报告": (
        "实验报告规范：操作步骤编号列表，数据用表格呈现（含单位行），"
        "结论部分区分'符合预期'和'偏差原因'，误差必须量化。"
    ),
    "述职报告": (
        "述职报告规范：结果量化（数字先行），STAR法则叙述项目，"
        "用动词开头的要点（主导/完成/推动/优化），避免空洞形容词。"
    ),
    "商业计划书": (
        "商业计划书规范：结论先行，每页/段一个核心观点，"
        "财务数据加注假设来源，市场规模用 TAM/SAM/SOM 框架。"
    ),
    "会议总结": (
        "会议纪要规范：客观第三人称记录，行动项必须有负责人+时间，"
        "决议用加粗标注，语言简洁不重复。"
    ),
    "法定公文": (
        "公文规范(GB/T 9704-2012)：庄重简洁，序号用一、（一）1.三级，"
        "义务条款用'应当'，禁止用'不得'，无口语俚语。"
    ),
    "企业制度": (
        "制度规范：条款用'第X条'格式，语言准确无歧义，"
        "避免'适当''尽量'等模糊词，违规条款明确后果。"
    ),
    "产品文档": (
        "产品文档规范：以用户视角（'您'为主语），步骤编号列表，"
        "警告信息用⚠️标注，代码用等宽块。"
    ),
    "测试报告": (
        "测试报告规范：数字精确（不用'较多'），缺陷严重级别P0-P4，"
        "结论明确表态是否建议发布，遗留缺陷说明风险。"
    ),
    "运维报告": (
        "运维报告规范（ITIL v4）：SLA指标表格化，重大事件必须RCA，"
        "可用性精确到小数点后两位，改进建议含负责人和时间。"
    ),
}


class ReportSectionWriterSkill(Skill):
    name = "write_section"
    description = (
        "SOTA报告章节写作：基于CoT规划→写作→自评→红队挑战→重写→润色的"
        "多轮精写流程，输出带质量分数的专业报告章节"
    )
    category = "offline"
    parameters = {
        "section_type": {
            "type": "string",
            "description": "exec_summary|analysis|risk|recommendation|conclusion|data_table|comparison",
        },
        "findings": {"type": "string", "description": "研究发现摘要（含具体数据）"},
        "rag_context": {"type": "string", "description": "知识库检索内容（可选）"},
        "report_type": {"type": "string", "description": "报告类型"},
        "target_words": {"type": "integer", "description": "目标字数", "default": 600},
        "output_format": {
            "type": "string",
            "description": "输出格式: word|ppt|excel，影响行文风格",
            "default": "word",
        },
        "enable_cot": {
            "type": "boolean",
            "description": "启用Chain-of-Thought规划",
            "default": True,
        },
        "enable_critique": {
            "type": "boolean",
            "description": "启用自评+重写",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队挑战",
            "default": True,
        },
        "quality_threshold": {
            "type": "number",
            "description": "质量通过门槛(0-10)，低于此分数触发重写",
            "default": 7.0,
        },
    }

    SECTION_CONFIGS = {
        "exec_summary": {
            "name": "执行摘要",
            "writer_persona": "资深报告撰写专家，擅长将复杂分析浓缩为高管一目了然的摘要",
            "critic_persona": "挑剔的高管读者，时间有限，要求每句话都有信息增量",
            "thinking_prompt": """请先为执行摘要制定写作大纲。

思考步骤：
1. 从findings中提取最重要的3-5个数据点
2. 识别最关键的1-2个风险
3. 确定优先级最高的2-3个行动建议
4. 规划每部分的篇幅（背景1-2句，发现3-5条，风险1-2条，建议2-3条，结论1句）

输出你的思考过程和大纲。""",
            "instruction": """撰写执行摘要，供高层决策者在2分钟内获取全貌。

结构要求：
1. **背景与目的**（1-2句）：本报告解决什么核心问题
2. **核心发现**（3-5条要点）：最重要的数据性结论，每条含具体数字
3. **主要风险**（1-2条）：需要决策层关注的关键风险
4. **建议行动**（2-3条）：优先级排序的可执行建议，含责任方
5. **结论一句话**：最重要的单一判断

写作标准：语言精炼，每句有实质内容；数字具体（避免"较多"改用具体百分比）；建议可执行（有明确主语和时间）。""",
        },
        "analysis": {
            "name": "深度分析",
            "writer_persona": "专业分析师，擅长从数据中挖掘洞察，构建严密的分析框架",
            "critic_persona": "严谨的数据科学家，要求每个推论都有数据支撑，不接受直觉判断",
            "thinking_prompt": """请先为深度分析章节制定分析框架。

思考步骤：
1. 确定分析角度（财务/市场/运营/技术等）
2. 从findings中提取关键数据点，标注来源
3. 构建因果链条：现象→原因→影响
4. 识别2-3条深层洞察（非显而易见的）
5. 规划表格呈现方式

输出你的分析框架和思考过程。""",
            "instruction": """撰写深度分析章节，展现专业分析能力。

结构要求：
1. **分析框架**（一句话点明分析角度和方法）
2. **现状描述**（含具体数字、时间段、对比维度）
3. **趋势与驱动因素**（用数据说明趋势，识别关键驱动）
   - 使用 ### 子标题组织（如：### 增长驱动分析）
4. **深层洞察**（超出表面数据的判断，2-3条）
5. **对标与差距**（与行业基准/竞品对比，如有数据）
6. **数据表格**（如有多维对比数据，用Markdown表格呈现）

写作标准：每个论点有数字支撑；区分事实（数据）和判断（分析）；逻辑递进，不堆砌数据。""",
        },
        "risk": {
            "name": "风险评估",
            "writer_persona": "风险管理专家，擅长系统识别、量化和管理各类风险",
            "critic_persona": "保守的首席风险官，要求每个风险都有量化影响和具体缓释方案",
            "thinking_prompt": """请先为风险评估制定风险识别框架。

思考步骤：
1. 从findings中识别所有潜在风险点
2. 按概率×影响对每个风险评级（高/中/低）
3. 确定TOP 3高风险项
4. 为每个高风险设计缓释方案
5. 规划风险矩阵表格

输出你的风险识别框架。""",
            "instruction": """撰写风险评估章节，为决策提供风险视角。

结构要求：
1. **风险全景**（一段话概述主要风险类别）
2. **风险矩阵**（Markdown表格）：
   | 风险名称 | 类别 | 概率 | 影响程度 | 综合等级 | 缓释措施 |
   |---------|------|------|---------|---------|---------|
   （至少列出4-6个具体风险，概率用高/中/低，影响用高/中/低，综合等级用颜色词：红/橙/黄/绿）

3. **重点风险详析**（选2-3个高优先级风险深度展开）
   - 风险描述（量化说明影响程度）
   - 触发条件
   - 缓释方案

4. **风险应对建议**（按优先级排列的具体行动项）

写作标准：风险描述具体可识别；影响量化（如"可能导致收入减少XX%"）；缓释措施具体可行。""",
        },
        "recommendation": {
            "name": "建议与行动计划",
            "writer_persona": "管理顾问，擅长将分析洞察转化为清晰可执行的战略建议",
            "critic_persona": "务实的项目总监，要求每条建议都有责任人、时间节点和可量化效果",
            "thinking_prompt": """请先为建议章节制定优先级框架。

思考步骤：
1. 从findings中提取所有可行的改进方向
2. 按影响力×可行性对建议排序（影响大/易实施优先）
3. 为每条核心建议设计行动步骤
4. 确定责任方和时间节点
5. 规划实施路线图表格

输出你的建议优先级框架。""",
            "instruction": """撰写建议与行动计划章节，为组织提供清晰的行动路线。

结构要求：
1. **建议原则**（1-2句话说明建议的整体思路和优先级逻辑）
2. **核心建议**（3-5条，按重要性/紧迫性排序）
   每条建议格式：
   ### 建议X：[建议标题]
   - **核心主张**：（一句话）
   - **行动步骤**：（2-4个具体行动）
   - **预期效果**：（量化指标，如"预计提升XX%"）
   - **负责方**：（部门/角色）
   - **时间节点**：（明确时间）

3. **实施路线图**（Markdown表格）：
   | 优先级 | 行动项 | 负责方 | 完成时间 | 预期效果 |
   |-------|-------|-------|---------|---------|

4. **资源需求**（人力/资金/技术，如有）

写作标准：建议有明确主语；效果可量化可追踪；时间节点现实可行。""",
        },
        "conclusion": {
            "name": "结论",
            "writer_persona": "资深报告编辑，擅长将整体研究提炼为有力结论",
            "critic_persona": "要求严格的董事会秘书，要求结论简洁有力，不重复前文",
            "thinking_prompt": """请先为结论制定提炼框架。

思考步骤：
1. 回顾全文最重要的3个发现
2. 确定核心判断（最重要的单一结论）
3. 识别1-2个未来趋势/展望
4. 设计行动呼吁
5. 确保结论不重复前文，而是综合提升

输出你的结论提炼框架。""",
            "instruction": """撰写结论章节，为整份报告画上有力的句点。

结构要求：
1. **核心判断**（1-2段，基于全文分析的最重要结论，有数据支撑）
2. **关键洞察回顾**（3-4条要点，快速重申最重要的发现）
3. **未来展望**（1段，基于现有趋势的客观判断，区分短期/中长期）
4. **行动呼吁**（1-2句话，激励读者采取行动的结尾）

写作标准：结论不简单重复前文；提出有价值的新视角或综合判断；语气坚定但不夸大；数字精确。""",
        },
        "data_table": {
            "name": "数据表格",
            "writer_persona": "数据分析师，擅长将复杂数据整理为清晰专业的表格",
            "critic_persona": "追求精确的数据审计师，要求数字格式统一、口径清晰、无遗漏",
            "thinking_prompt": """请先为数据表格制定整理方案。

思考步骤：
1. 确定表格的核心维度和指标
2. 统一数值格式（金额/百分比/数量）
3. 设计表头（含单位）
4. 规划合计/平均行
5. 准备2-3条关键数据解读

输出你的表格整理方案。""",
            "instruction": """将数据整理为专业的数据表格章节。

结构要求：
1. **表格说明**（1-2句话说明表格的数据来源、时间范围、口径说明）
2. **主数据表**（Markdown表格，包含表头和数据行）
   - 表头清晰，含计量单位
   - 数值格式统一（如：金额统一万元，百分比统一X.X%）
   - 如有合计/平均行，放在最后并加粗标注
3. **补充说明**（注释：特殊处理、数据来源、口径差异）
4. **关键数据解读**（2-3条基于表格数据的洞察）

写作标准：数字精确；表格完整可读；口径说明清晰。""",
        },
        "comparison": {
            "name": "对比分析",
            "writer_persona": "战略分析师，擅长构建多维度对比框架",
            "critic_persona": "公正的第三方评估师，要求对比客观、维度全面、不偏袒任何一方",
            "thinking_prompt": """请先为对比分析制定框架。

思考步骤：
1. 确定对比对象和维度
2. 为每个维度设计评分标准
3. 收集各方在各维度上的表现数据
4. 确定综合评价逻辑
5. 规划对比表格

输出你的对比分析框架。""",
            "instruction": """撰写对比分析章节，清晰呈现多方对比。

结构要求：
1. **对比框架**（说明对比维度、对象和选取标准）
2. **核心对比表**（Markdown表格）：
   | 维度 | 方案A/对象A | 方案B/对象B | 方案C/对象C | 评价 |
   （至少5个对比维度，评价列用优/中/差或具体判断）
3. **维度深析**（选2-3个关键维度展开对比说明）
4. **综合评价**（基于对比的整体判断，推荐选项及理由）

写作标准：对比客观公正；维度有代表性；结论有据可依。""",
        },
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        section_type = params.get("section_type", "analysis")
        findings = params.get("findings", "")
        rag_context = params.get("rag_context", "")
        report_type = params.get("report_type", "")
        target_words = int(params.get("target_words", 600))
        output_format = params.get("output_format", "word").lower()
        enable_cot = params.get("enable_cot", True)
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)
        quality_threshold = params.get("quality_threshold", 7.0)

        config = self.SECTION_CONFIGS.get(section_type, self.SECTION_CONFIGS["analysis"])
        section_name = config["name"]
        writer_persona = config["writer_persona"]
        critic_persona = config["critic_persona"]
        instruction = config["instruction"]
        thinking_prompt = config.get("thinking_prompt", "")

        # Document type format rules
        doc_type_rule = ""
        for keyword, rule in REPORT_TYPE_FORMAT_RULES.items():
            if keyword in (report_type or ""):
                doc_type_rule = f"\n\n**【{keyword}专用格式规范】**\n{rule}"
                break

        # Format adjustments
        if output_format in ("ppt", "pptx", "powerpoint"):
            format_note = "\n\n**PPT格式要求**: 输出更简洁，要点不超过6条，数字加粗，避免长段文字，重点用列表呈现。"
        elif output_format in ("excel", "sheet", "xlsx", "xls"):
            format_note = "\n\n**Excel格式要求**: 优先输出结构化表格，文字说明精简，数据以表格为主，便于填入单元格。"
        else:
            format_note = ""

        rag_block = f"\n\n**【知识库参考内容】**\n{rag_context[:2500]}" if rag_context else ""

        format_rules = f"{doc_type_rule}{format_note}"

        # ── Phase 1: CoT Planning (optional) ─────────────────────────────────────
        thinking = ""
        if enable_cot and thinking_prompt:
            thinking = await chat(
                [
                    {"role": "system", "content": writer_persona},
                    {"role": "user", "content": f"""{thinking_prompt}

## 研究发现
{findings[:2000] if findings else '（基于报告主题合理推断）'}
{rag_block}"""},
                ],
                temperature=0.4,
                max_tokens=1000,
            )

        # ── Phase 2: First Draft ─────────────────────────────────────────────────
        thinking_block = f"\n\n**【写作大纲】**\n{thinking}\n\n请基于以上大纲撰写正文。" if thinking else ""

        draft_messages = [
            {
                "role": "system",
                "content": f"{writer_persona}。你正在为「{report_type}」类报告撰写「{section_name}」章节。使用规范、简洁的商务中文。{format_rules}",
            },
            {
                "role": "user",
                "content": f"""请撰写「{section_name}」章节。{thinking_block}

## 撰写要求
{instruction}{format_note}

## 研究发现（请基于这些发现撰写，不能与数据矛盾）
{findings[:3500] if findings else '（请基于报告主题合理推断生成专业内容）'}
{rag_block}

## 质量要求
- 目标字数: 约 {target_words} 字（PPT格式可适当减少）
- 每个论点必须有具体数字或案例支撑
- 使用### 二级标题组织内容
- 语言专业、逻辑清晰、数据精确
- 严格遵守上述文档类型格式规范（如有）""",
            },
        ]
        draft = await chat(draft_messages, temperature=0.4, max_tokens=max(1200, target_words * 4))

        if not enable_critique:
            return {
                "result": draft,
                "thinking": thinking,
                "quality_score": None,
                "critique": None,
                "adversarial": None,
                "passes": 1,
            }

        # ── Phase 3: Self-Critique ───────────────────────────────────────────────
        critique = await self_critique(
            draft=draft,
            topic=f"{report_type} - {section_name}",
            persona=critic_persona,
        )

        # ── Phase 4: Adversarial Review (optional) ───────────────────────────────
        adversarial = None
        if enable_adversarial:
            adversarial = await adversarial_review(
                output=draft,
                topic=f"{report_type} - {section_name}",
            )

        # ── Phase 5: Quality Gate & Rewrite ──────────────────────────────────────
        overall_score = critique["overall_score"]
        final = draft
        passes = 1

        if overall_score < quality_threshold:
            # Rewrite based on critique
            rewrite = await rewrite_with_critique(
                draft=draft,
                critique=critique,
                topic=f"{report_type} - {section_name}",
                persona=writer_persona,
                format_rules=format_rules,
            )
            final = rewrite
            passes = 2

            # Re-critique after rewrite
            critique2 = await self_critique(
                draft=rewrite,
                topic=f"{report_type} - {section_name}",
                persona=critic_persona,
            )
            overall_score = critique2["overall_score"]
            critique = critique2

        # ── Phase 6: Final Polish ────────────────────────────────────────────────
        if passes > 1 or overall_score >= quality_threshold:
            polish = await self._polish(final, output_format, target_words)
            final = polish

        # Normalize score to 0-100
        quality_score = round(overall_score * 10)

        return {
            "result": final,
            "thinking": thinking,
            "quality_score": quality_score,
            "critique": critique,
            "adversarial": adversarial,
            "passes": passes,
            "section_type": section_type,
            "report_type": report_type,
        }

    async def _polish(self, text: str, output_format: str, word_count: int) -> str:
        format_rules = {
            "ppt": "将内容压缩为要点形式，每个要点≤25字，保留所有关键数据，去掉过渡语",
            "word": "确保段落流畅，数字格式统一，小标题清晰，补充必要的过渡句",
            "excel": "提炼为简洁的说明性段落，突出数字和指标，方便与表格数据配合",
        }
        rule = format_rules.get(output_format, format_rules["word"])
        messages = [
            {"role": "system", "content": "你是专业文字润色专家。专注于格式规范和表达精炼，不改变内容实质。"},
            {
                "role": "user",
                "content": f"""请对以下内容进行最终润色。

## 润色规则
{rule}

## 内容
{text}

直接输出润色后的内容。""",
            },
        ]
        return await chat(messages, temperature=0.2, max_tokens=2000)
