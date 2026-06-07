"""
Business Framework Analyzer — structured application of SWOT, PEST, Porter, BCG, etc.

Provides structured strategic analysis using proven business frameworks,
compensating for lack of live data with deep LLM domain knowledge.
"""
from app.skills.base import Skill
from app.services.llm_service import chat


class BusinessFrameworkSkill(Skill):
    name = "apply_framework"
    description = "应用商业分析框架（SWOT/PEST/波特五力/BCG矩阵/麦肯锡7S等）对研究主题进行结构化战略分析，输出可直接引用的分析内容"
    category = "offline"
    parameters = {
        "topic": {"type": "string", "description": "分析主题（公司/行业/项目/产品）"},
        "framework": {
            "type": "string",
            "description": "分析框架: swot | pest | porter5 | bcg | mckinsey7s | ansoff | value_chain | all_strategic",
            "default": "swot",
        },
        "context": {"type": "string", "description": "已有背景信息（可为空）"},
        "industry": {
            "type": "string",
            "description": "所属行业，提升分析精准度",
            "default": "general",
        },
        "output_style": {
            "type": "string",
            "description": "输出风格: table（表格）| narrative（叙述）| bullets（要点）",
            "default": "table",
        },
    }

    FRAMEWORK_PROMPTS = {
        "swot": {
            "name": "SWOT分析",
            "instruction": """请进行完整的SWOT分析，每个维度提供3-5个具体要点：

### 优势 (Strengths)
（内部有利因素，当前具备的核心竞争力）
- 每条优势要具体，可量化最好

### 劣势 (Weaknesses)
（内部不利因素，当前存在的短板）
- 包含改进建议

### 机会 (Opportunities)
（外部有利因素，可利用的市场机遇）
- 结合行业趋势和政策环境

### 威胁 (Threats)
（外部不利因素，需防范的风险）
- 按紧迫程度排序

### SWOT交叉策略
| | 优势S | 劣势W |
|---|---|---|
| **机会O** | SO策略（用优势把握机会） | WO策略（借机会克服劣势） |
| **威胁T** | ST策略（用优势对抗威胁） | WT策略（减少劣势避免威胁） |""",
        },

        "pest": {
            "name": "PEST分析",
            "instruction": """请进行PESTEL分析（政治、经济、社会、技术、环境、法律）：

### 政治因素 (Political)
- 相关政策法规、监管环境、政治稳定性

### 经济因素 (Economic)
- 宏观经济指标、市场规模、成本结构

### 社会因素 (Social)
- 人口结构、消费趋势、文化变迁

### 技术因素 (Technological)
- 技术创新、数字化转型、研发趋势

### 环境因素 (Environmental)
- 可持续发展、碳排放、ESG要求

### 法律因素 (Legal)
- 行业法规、合规要求、知识产权

### 综合影响评估
用表格总结各因素的影响程度（高/中/低）和应对建议""",
        },

        "porter5": {
            "name": "波特五力分析",
            "instruction": """请进行波特五力竞争分析：

### 行业竞争强度（现有竞争者）
- 竞争者数量、市场集中度、价格战风险、差异化程度
- **综合判断**：强/中/弱，并说明原因

### 新进入者威胁
- 进入壁垒（资本、技术、品牌、渠道）、政策限制
- **综合判断**：高/中/低威胁

### 替代品威胁
- 替代品类型、替代成本、客户转换意愿
- **综合判断**：高/中/低威胁

### 供应商议价能力
- 供应商集中度、原材料稀缺性、前向整合能力
- **综合判断**：强/中/弱

### 买方议价能力
- 客户集中度、采购量、信息对称程度、后向整合能力
- **综合判断**：强/中/弱

### 五力综合评估
| 竞争力量 | 强度 | 趋势 | 战略含义 |
|---|---|---|---|
| 行业竞争 | - | - | - |
| 新进入者 | - | - | - |
| 替代品 | - | - | - |
| 供应商 | - | - | - |
| 买方 | - | - | - |""",
        },

        "bcg": {
            "name": "BCG矩阵分析",
            "instruction": """请应用BCG（波士顿）矩阵分析产品/业务组合：

### 矩阵象限定义
- **明星（Star）**：高增长+高份额，需要持续投入
- **现金牛（Cash Cow）**：低增长+高份额，产生现金流
- **问题儿童（Question Mark）**：高增长+低份额，需要决策
- **瘦狗（Dog）**：低增长+低份额，考虑退出

### 业务/产品组合定位
请将主要业务/产品线归入各象限，并说明依据

### 资源配置建议
基于BCG矩阵，给出投资优先级和资源调配建议

### 动态演进预测
预测未来2-3年各业务在矩阵中的移动方向""",
        },

        "mckinsey7s": {
            "name": "麦肯锡7S框架",
            "instruction": """请用麦肯锡7S框架分析组织能力：

**硬性要素（Hard Elements）：**
### 战略 (Strategy)
### 结构 (Structure)
### 系统 (Systems)

**软性要素（Soft Elements）：**
### 共同价值观 (Shared Values)
### 风格 (Style)
### 员工 (Staff)
### 技能 (Skills)

### 7S协调性评估
各要素之间是否对齐？哪些存在冲突？如何改进？""",
        },

        "ansoff": {
            "name": "安索夫矩阵分析",
            "instruction": """请用安索夫矩阵分析增长策略：

### 市场渗透（现有产品×现有市场）
- 可行性分析、具体手段、预期效果

### 市场开发（现有产品×新市场）
- 目标新市场、进入策略、主要障碍

### 产品开发（新产品×现有市场）
- 产品创新方向、研发要求、客户需求匹配

### 多元化（新产品×新市场）
- 相关多元化vs非相关多元化分析、风险评估

### 策略优先级推荐
综合风险/回报分析，推荐最优增长路径""",
        },

        "value_chain": {
            "name": "价值链分析",
            "instruction": """请进行波特价值链分析：

**基本活动：**
### 内向物流 → 运营 → 外向物流 → 市场营销 → 售后服务
对每个环节进行竞争优势和改进空间分析

**支持活动：**
### 采购 / 技术开发 / 人力资源管理 / 基础设施

### 价值链优化机会
找出可创造差异化优势或降本的关键环节

### 行业价值链对比
与行业标杆的价值链结构对比，找出差距""",
        },

        "all_strategic": {
            "name": "综合战略分析",
            "instruction": """请进行简化版综合战略分析：

### 1. SWOT速览
各维度列2条核心要点（共8条）

### 2. 竞争格局（波特五力简析）
五力各一句话结论 + 整体竞争强度评级（1-5分）

### 3. 战略定位建议
基于以上分析，推荐1种主要战略方向（成本领先/差异化/聚焦），并给出3条具体行动建议

### 4. 关键成功因素
该行业/领域3-5个决定竞争成败的核心要素

### 5. 风险与缓释
前3大战略风险及对应缓释措施""",
        },
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        topic = params.get("topic", "")
        framework = params.get("framework", "swot")
        bg_context = params.get("context", "")
        industry = params.get("industry", "general")
        output_style = params.get("output_style", "table")

        if not topic:
            return {"result": "", "error": "topic is required"}

        fw = self.FRAMEWORK_PROMPTS.get(framework, self.FRAMEWORK_PROMPTS["swot"])
        fw_name = fw["name"]
        fw_instruction = fw["instruction"]

        context_block = f"\n\n## 背景信息\n{bg_context[:1500]}" if bg_context else ""

        style_note = {
            "table": "尽量使用Markdown表格呈现对比信息",
            "narrative": "使用叙述性段落，逻辑流畅，适合Word报告",
            "bullets": "使用简洁要点列表，每条≤20字，适合PPT",
        }.get(output_style, "使用表格和要点结合")

        messages = [
            {
                "role": "system",
                "content": f"""你是顶级战略咨询师，精通各类商业分析框架。你的分析具体、有数据支撑、可操作。
行业背景：{industry}
输出要求：{style_note}""",
            },
            {
                "role": "user",
                "content": f"""请对以下主题进行**{fw_name}**分析。{context_block}

## 分析主题
{topic}

## 分析框架和输出结构
{fw_instruction}

重要：
- 所有数据估算需标注（行业估算）或（通常水平）
- 结论需具体，避免"需要关注""可能影响"等空洞表述
- 如无具体数据，用行业典型区间代替""",
            },
        ]

        result = await chat(messages, temperature=0.35, max_tokens=3000)
        return {
            "result": result,
            "framework": framework,
            "framework_name": fw_name,
            "topic": topic,
        }
