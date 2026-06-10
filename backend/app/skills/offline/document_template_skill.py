"""
Document Template Skill — SOTA-enhanced professional document generation.

Enhancements over v1:
1. Chain-of-Thought outline planning
2. Cross-section consistency verification
3. Format compliance checking
4. Quality scoring with structured feedback

Each document type follows national/industry standards:
- 学术论文: GB/T 7713.2-2022
- 法定公文: GB/T 9704-2012
- 商业计划书: VC/PE industry standards
- 述职报告: Corporate annual review standards
"""
from app.skills.base import Skill
from app.services.llm_service import chat
from app.skills.offline.sota_utils import self_critique, adversarial_review


# ── 各文档类型标准格式规范 ─────────────────────────────────────────────────────────

DOCUMENT_TEMPLATES: dict[str, dict] = {

    "学术论文": {
        "standard": "参照 GB/T 7713.2-2022《学术论文编写规则》",
        "structure": [
            "题目（Title）：简明准确，≤25字，中英双语",
            "作者及单位",
            "摘要（Abstract）：目的-方法-结果-结论四要素，中文200-300字，英文150-250词",
            "关键词（Keywords）：3-8个，中英双语",
            "引言（Introduction）：研究背景、文献综述、研究空白、本文目的与贡献",
            "研究方法（Methods）：研究设计、数据来源、分析工具、可重现性说明",
            "结果与分析（Results & Discussion）：数据呈现、统计显著性、与假设的对应",
            "结论（Conclusion）：核心发现、研究局限性、未来方向",
            "参考文献（References）：GB/T 7714-2015 顺序编码制",
            "附录（Appendix）：原始数据、补充材料（如有）",
        ],
        "style_rules": [
            "第三人称客观叙述，避免 '我认为'",
            "数字规范：测量值±标准差，P值精确到0.001",
            "图表：每图/表有独立编号、标题和数据来源说明",
            "标题层级：一级用 # 加粗，二级用 ## ，三级用 ###",
            "引用格式：文中 [序号] 角标，文末按序排列",
        ],
    },

    "实验报告": {
        "standard": "参照高校实验报告通用规范",
        "structure": [
            "实验名称与基本信息（日期、地点、合作者）",
            "实验目的：明确要验证/探究的科学问题",
            "实验原理：相关理论基础，关键公式推导",
            "实验仪器与材料：型号、规格、数量、精度",
            "实验步骤：编号的操作步骤，含注意事项",
            "数据记录与处理：原始数据表格、计算过程、误差分析",
            "实验结果：图表呈现，结论是否符合预期",
            "误差分析：误差来源分类（系统误差/随机误差）、影响评估",
            "思考与讨论：异常数据解释、改进建议",
            "结论：简洁总结实验验证情况",
        ],
        "style_rules": [
            "数据记录使用规范表格，含单位行/列",
            "所有计算过程展示中间步骤",
            "图形标注：坐标轴名称+单位，图例清晰",
            "有效数字遵守仪器精度规则",
            "误差用绝对误差和相对误差两种形式表达",
        ],
    },

    "述职报告": {
        "standard": "企业年度绩效考核述职规范",
        "structure": [
            "基本信息（姓名、岗位、考核周期）",
            "岗位职责概述：本职工作范围与核心目标",
            "主要工作成果（量化为主）：",
            "  - 完成的核心项目/任务（STAR法则：情境-任务-行动-结果）",
            "  - 关键绩效指标完成情况（KPI达成率对比）",
            "  - 具体数字：金额、百分比、数量、周期",
            "工作亮点与创新：超出预期的贡献、创新举措",
            "不足与改进：客观分析差距，承担责任，不推诿",
            "能力提升：本期学习成长，技能认证，培训情况",
            "下期工作计划：SMART目标（具体-可量化-可实现-相关-有时限）",
            "需要支持的资源与协作",
        ],
        "style_rules": [
            "数字先行：每项成果必须有量化数据",
            "STAR法则叙述重要项目",
            "避免空洞表述：'努力工作' 改为 '完成X项目，节省Y万元'",
            "不足部分诚恳务实，配改进措施",
            "语气自信客观，不自谦也不夸大",
        ],
    },

    "商业计划书": {
        "standard": "VC/PE 行业投融资商业计划书惯例",
        "structure": [
            "封面：公司名称、日期、联系方式、保密声明",
            "执行摘要（1页）：一页纸说明核心投资逻辑",
            "问题与机会：市场痛点量化、TAM/SAM/SOM 市场规模",
            "解决方案：产品/服务描述、核心差异化、竞争壁垒",
            "商业模式：收入来源、定价策略、单位经济模型（Unit Economics）",
            "市场分析：行业规模、增速、关键趋势、政策环境",
            "竞争格局：竞争对手矩阵、我方差异化优势",
            "产品/技术：核心技术/产品路线图、技术壁垒",
            "营销与销售：获客策略、渠道、LTV/CAC 比率",
            "团队介绍：创始人背景、关键人员、顾问",
            "财务预测（3-5年）：P&L、现金流、关键假设说明",
            "融资需求：本轮金额、估值逻辑、资金用途分配（饼图）、里程碑",
        ],
        "style_rules": [
            "数字务必精确，来源可追溯（引用权威报告）",
            "每页一个核心观点，不超过7条要点",
            "财务模型需附关键假设列表",
            "竞争对手分析用矩阵表格，不主观贬低竞品",
            "总长度控制在15-25页（PPT版）或3000-5000字（Word版）",
        ],
    },

    "会议总结": {
        "standard": "企业会议纪要规范（参照 ISO 15489 文件管理）",
        "structure": [
            "会议基本信息（时间、地点、主持人、记录人、参会人员）",
            "会议议程",
            "会议讨论要点（按议题分组）：",
            "  - 各方发言要点（第三人称客观记录，不主观解读）",
            "  - 争议点与解决方式",
            "决议事项（CRAP格式：Conclusion-Rationale-Action-Party）：",
            "  | 序号 | 决议内容 | 负责人 | 完成时间 | 验收标准 |",
            "待办行动项（Action Items）：明确责任人和截止日期",
            "下次会议安排：时间、地点、议题",
            "会议纪要确认：签字/审核流程说明",
        ],
        "style_rules": [
            "客观记录，不加入记录人的判断",
            "行动项必须有明确责任人+时间节点，不允许模糊表述",
            "决议内容用加粗或特殊标注区分",
            "字数精炼，会议内容完整覆盖即可，不重复不遗漏",
            "24小时内发出初稿，48小时内完成确认",
        ],
    },

    "法定公文": {
        "standard": "《党政机关公文格式》GB/T 9704-2012",
        "structure": [
            "版头：发文机关标志（红色套红）、发文字号（机关代字〔年份〕第X号）",
            "分隔线",
            "标题：事由+文种，不加书名号，居中三号宋体",
            "主送机关：顶格，后加冒号",
            "正文：",
            "  - 开头：来文缘由或依据（'根据…特制定本…'）",
            "  - 主体：分条列项，一事一条，用'一、（一）1.'三级序号",
            "  - 结尾：执行要求或号召性语句",
            "附件说明（如有）：'附件：X.附件名称'",
            "发文机关署名（加盖印章）",
            "成文日期（阿拉伯数字年月日）",
            "附注（如有）：左下角括号注明",
        ],
        "style_rules": [
            "语言庄重简洁，一律使用规范汉字",
            "禁用口语、俚语、网络词汇",
            "数字：年份用阿拉伯数字，序号用汉字",
            "一份公文只有一个发文机关",
            "严格使用法定文种：决定/通知/通报/报告/请示/批复/意见/函/纪要",
        ],
    },

    "企业制度": {
        "standard": "企业内部管理制度编写规范",
        "structure": [
            "封面：制度名称、文件编号、版本号、生效日期",
            "第一章 总则：立法目的、适用范围、基本原则",
            "第二章 定义与解释：专业术语定义",
            "第三章 职责分工：",
            "  - 主管部门职责",
            "  - 执行部门职责",
            "  - 各岗位具体职责（RACI矩阵）",
            "第四章 管理规定：核心管理要求，逐条列明",
            "第五章 业务流程：",
            "  - 流程图（文字版，含判断节点）",
            "  - 各环节操作规程",
            "第六章 监督与考核：检查机制、绩效挂钩",
            "第七章 违规处理：违规情形分级、对应处理措施",
            "第八章 附则：解释权归属、生效日期、版本历史",
        ],
        "style_rules": [
            "条款用'第X条'格式，具体规定下用（一）（二）",
            "语言准确无歧义，避免'适当''尽量'等模糊词",
            "义务性条款用'应当'，禁止性条款用'不得'，授权性条款用'可以'",
            "违规处理条款需可操作，写明主体和后果",
            "与上位法、国家标准保持一致",
        ],
    },

    "产品文档": {
        "standard": "软件产品文档规范（参照 IEEE 830）",
        "structure": [
            "文档信息：产品名称、版本、作者、更新日期、适用读者",
            "产品概述：是什么、解决什么问题、核心价值主张",
            "快速开始（Quick Start）：5分钟上手指引",
            "功能详解：",
            "  - 功能模块一览（表格：功能名/描述/入口路径）",
            "  - 各功能操作说明（截图+步骤）",
            "  - 参数说明表（参数名/类型/必填/默认值/说明）",
            "使用场景与最佳实践",
            "常见问题（FAQ）：Q&A 格式，按频率排序",
            "故障排除（Troubleshooting）：症状→原因→解决方法",
            "API 参考（如有）：端点、请求/响应格式、错误码",
            "更新日志（Changelog）：版本→日期→变更内容",
        ],
        "style_rules": [
            "读者视角：以'您/用户'为主语，步骤从用户操作出发",
            "每个功能配操作步骤（编号列表）",
            "注意事项用警告框标注（⚠️ 注意：…）",
            "代码块使用等宽字体，命令前加 $",
            "截图配图说（Figure X: 说明）",
        ],
    },

    "测试报告": {
        "standard": "软件测试报告规范（参照 GB/T 15532-2008）",
        "structure": [
            "报告基本信息：项目名称、版本、测试时间、测试人员",
            "测试概述：测试目标、范围、策略、环境",
            "测试执行摘要：",
            "  - 用例总数 / 通过 / 失败 / 阻塞 / 未执行",
            "  - 缺陷总数 / 严重 / 主要 / 次要 / 轻微",
            "  - 通过率：XX% （附趋势图数据）",
            "功能测试结果：按模块列表，每模块：用例数/通过/失败/备注",
            "缺陷统计分析：",
            "  | 缺陷ID | 严重级别 | 模块 | 描述 | 状态 | 负责人 |",
            "  - 缺陷分布饼图数据",
            "  - 高风险缺陷详述",
            "性能测试结果（如有）：响应时间、并发量、吞吐量对比基准",
            "测试结论与建议：是否建议发布、遗留问题风险评估",
            "附件：测试用例清单、环境配置信息",
        ],
        "style_rules": [
            "数字精确，不用模糊词（不写'较多缺陷'，写'34个缺陷'）",
            "缺陷严重级别统一：P0-致命/P1-严重/P2-主要/P3-次要/P4-轻微",
            "结论明确表态：'建议发布'或'不建议发布'，理由清晰",
            "遗留缺陷需说明风险等级和是否可接受",
        ],
    },

    "个人简历": {
        "standard": "简历规范（参照 HR 行业惯例）",
        "structure": [
            "基本信息：姓名 | 联系方式 | 城市 | 求职意向",
            "个人简介（可选）：2-3句话的职业定位陈述",
            "工作经历（倒序）：",
            "  公司名称 | 职位 | 时间段",
            "  - 职责与成就（STAR法则，量化数据）",
            "  - 每段2-4条要点，以动词开头",
            "教育背景（倒序）：学校、专业、学位、时间",
            "技能清单：按类别分组（语言/框架/工具/证书）",
            "项目经历（如有）：项目名 | 角色 | 成果",
            "其他（可选）：开源贡献、获奖、出版物、语言能力",
        ],
        "style_rules": [
            "每条成就从量化结果开始：'提升XX%'、'完成X项目'",
            "使用动词开头：主导/设计/实现/优化/推动/建立",
            "避免第一人称和主观形容词",
            "控制在1-2页，信息密度高",
            "时间线倒序，工作经历最重要放最前",
        ],
    },

    "运维报告": {
        "standard": "IT 运维服务报告规范（参照 ITIL v4）",
        "structure": [
            "报告周期与基本信息",
            "服务级别协议（SLA）执行情况：",
            "  | 指标 | 目标值 | 实际值 | 达标情况 |",
            "  - 可用性：系统正常运行时间 / 总时间 × 100%",
            "  - 响应时间、解决时间 MTTR/MTTF",
            "基础设施运行状况：CPU/内存/存储/网络利用率趋势图数据",
            "事件管理：",
            "  - 本期事件汇总（总数/P0-P4分级统计）",
            "  - 重大事件 RCA（根因分析）：故障描述→根因→影响→措施→预防",
            "变更管理：本期变更清单、成功率、回滚情况",
            "安全状况：漏洞扫描结果、已修复/待修复、安全事件",
            "容量规划：趋势预测、资源不足预警",
            "问题与改进：已识别问题、优化建议、下期计划",
        ],
        "style_rules": [
            "数字精确到小数点后两位（如：可用性 99.97%）",
            "重大事件必须有完整 RCA",
            "趋势数据配图（折线图数据表格）",
            "改进建议具体可落地，附负责人和时间",
        ],
    },
}


class DocumentTemplateSkill(Skill):
    name = "generate_document_template"
    description = (
        "按标准格式规范生成各类专业文档。支持：学术论文、实验报告、述职报告、商业计划书、"
        "会议总结、法定公文、企业制度、产品文档、测试报告、个人简历、运维报告等。"
        "生成内容符合对应国标/行业标准的格式要求。"
    )
    category = "offline"
    parameters = {
        "doc_type": {
            "type": "string",
            "description": (
                "文档类型，支持：学术论文|实验报告|述职报告|商业计划书|会议总结|"
                "法定公文|企业制度|产品文档|测试报告|个人简历|运维报告"
            ),
        },
        "topic": {"type": "string", "description": "文档主题/标题"},
        "key_info": {"type": "string", "description": "核心信息/要点（用于填充内容，可为空）"},
        "output_format": {
            "type": "string",
            "description": "输出格式: word|ppt|excel",
            "default": "word",
        },
        "target_words": {
            "type": "integer",
            "description": "目标字数（0=使用模板默认）",
            "default": 0,
        },
        "generate_mode": {
            "type": "string",
            "description": "skeleton=只生成结构骨架 | full=完整内容",
            "default": "full",
        },
        "enable_critique": {
            "type": "boolean",
            "description": "启用跨章节一致性检查和质量自评",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队挑战",
            "default": True,
        },
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        doc_type = params.get("doc_type", "")
        topic = params.get("topic", "")
        key_info = params.get("key_info", "")
        output_format = params.get("output_format", "word").lower()
        target_words = int(params.get("target_words", 0))
        generate_mode = params.get("generate_mode", "full")
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)

        # Look up template
        template = DOCUMENT_TEMPLATES.get(doc_type)
        if not template:
            # Fuzzy match
            for k in DOCUMENT_TEMPLATES:
                if k in doc_type or doc_type in k:
                    template = DOCUMENT_TEMPLATES[k]
                    doc_type = k
                    break

        if not template:
            # Fallback: generic professional document
            return await self._generic_document(topic, key_info, output_format, target_words)

        standard = template["standard"]
        structure = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(template["structure"]))
        style_rules = "\n".join(f"  • {r}" for r in template["style_rules"])

        default_words = 1200 if output_format == "word" else 600
        words = target_words if target_words > 0 else default_words

        if generate_mode == "skeleton":
            return await self._generate_skeleton(doc_type, topic, structure, style_rules, standard)

        # Full generation with CoT + critique
        result = await self._generate_full(
            doc_type, topic, key_info, structure, style_rules, standard, output_format, words
        )

        # Cross-section consistency check
        if enable_critique:
            consistency = await self._check_consistency(
                result["result"], doc_type, topic, structure
            )
            result["consistency_check"] = consistency

            # Self-critique
            critique = await self_critique(
                draft=result["result"],
                topic=f"{doc_type} - {topic}",
                dimensions=["structural_clarity", "constraint_compliance", "audience_fit"],
            )
            result["critique"] = critique
            result["quality_score"] = round(critique["overall_score"] * 10)

        # SOTA: Adversarial review
        if enable_adversarial and result.get("result"):
            try:
                adv = await adversarial_review(
                    output=result["result"][:3000],
                    topic=f"{doc_type} - {topic}",
                )
                result["adversarial"] = adv
            except Exception:
                pass

        return result

    async def _generate_skeleton(self, doc_type, topic, structure, style_rules, standard):
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是专业{doc_type}撰写专家。请严格按照{standard}输出文档骨架结构。"
                    "只输出标题层级和每章节的简短说明，不输出正文内容。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"请为以下主题生成「{doc_type}」的标准结构骨架：\n\n"
                    f"**主题**：{topic}\n\n"
                    f"**标准结构要求**：\n{structure}\n\n"
                    "输出格式：Markdown 标题层级（# ## ###），每个章节下用1-2句话说明该章节应包含的内容。"
                ),
            },
        ]
        result = await chat(messages, temperature=0.3, max_tokens=800)
        return {"result": result, "doc_type": doc_type, "mode": "skeleton"}

    async def _generate_full(
        self, doc_type, topic, key_info, structure, style_rules, standard, output_format, words
    ):
        format_note = {
            "ppt": "\n\n**PPT输出要求**：每个章节转化为简洁的幻灯片要点，每页≤6条，数字加粗，去掉长段落。",
            "excel": "\n\n**Excel输出要求**：将内容结构化为可填入表格的格式，优先输出表格和数据。",
        }.get(output_format, "")

        key_info_block = f"\n\n**已知核心信息（请基于此填充内容）**：\n{key_info[:3000]}" if key_info else ""

        messages = [
            {
                "role": "system",
                "content": (
                    f"你是经验丰富的{doc_type}撰写专家。"
                    f"本次生成严格遵循{standard}。\n\n"
                    f"格式规范要求：\n{style_rules}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"请撰写一份完整的「{doc_type}」，主题为：**{topic}**\n\n"
                    f"**必须遵循的标准结构（按此顺序完整展开）**：\n{structure}"
                    f"{format_note}"
                    f"{key_info_block}\n\n"
                    "**输出要求**：\n"
                    f"- 目标字数：约 {words} 字\n"
                    "- 使用 Markdown 格式，标题层级清晰（# ## ###）\n"
                    "- 每个必要章节都必须出现，不得跳过\n"
                    "- 数字、日期、单位格式符合上述规范\n"
                    "- 如缺少具体信息，用 [请填写：XXX] 占位符标注\n"
                    "- 直接输出文档正文，不要解释或前言"
                ),
            },
        ]
        result = await chat(messages, temperature=0.4, max_tokens=max(2000, words * 4))
        return {
            "result": result,
            "doc_type": doc_type,
            "standard": standard,
            "mode": "full",
            "output_format": output_format,
        }

    async def _generic_document(self, topic, key_info, output_format, words):
        """Fallback for unknown doc types."""
        messages = [
            {"role": "system", "content": "你是专业文档撰写专家，输出结构清晰、内容专业的文档。"},
            {
                "role": "user",
                "content": (
                    f"请撰写关于「{topic}」的专业文档。\n"
                    f"{'已知信息：' + key_info[:2000] if key_info else ''}\n"
                    f"目标字数：约 {words or 800} 字。使用 Markdown 格式，层次分明。"
                ),
            },
        ]
        result = await chat(messages, temperature=0.4, max_tokens=2000)
        return {"result": result, "doc_type": "通用文档", "mode": "full"}

    async def _check_consistency(self, text: str, doc_type: str, topic: str, structure: str) -> dict:
        """Check cross-section consistency in generated document."""
        system = """你是文档质量审核师。检查文档各章节之间是否存在逻辑矛盾、数据不一致或结构缺失。

检查维度：
1. **数据一致性**：同一数据在不同章节中是否一致
2. **逻辑连贯性**：前后章节是否逻辑衔接
3. **结构完整性**：是否遗漏了标准结构中的必要章节
4. **格式合规性**：是否符合文档类型的格式规范

输出JSON：
{
  "consistent": true/false,
  "issues": [{"section": "章节名", "issue": "问题描述", "severity": "high|medium|low"}],
  "missing_sections": ["缺失章节1"],
  "suggestions": ["修正建议1"]
}"""

        user = f"""请检查以下「{doc_type}」的逻辑一致性。

## 标准结构
{structure[:1000]}

## 生成内容
{text[:2500]}

## 主题
{topic}

请输出JSON格式的审核结果。"""

        from app.services.llm_service import chat_json
        parsed = await chat_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.25,
            max_tokens=1000,
        )

        if "error" in parsed:
            return {"consistent": True, "issues": [], "missing_sections": [], "suggestions": []}

        return {
            "consistent": parsed.get("consistent", True),
            "issues": parsed.get("issues", []),
            "missing_sections": parsed.get("missing_sections", []),
            "suggestions": parsed.get("suggestions", []),
        }
