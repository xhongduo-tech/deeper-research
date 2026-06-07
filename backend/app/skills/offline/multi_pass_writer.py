"""
Multi-Pass Writer — write → self-critique → rewrite loop for high-quality output.

Emulates expert human writing process: first draft → identify weaknesses →
targeted rewrite. Produces measurably better output than single-pass generation.
"""
from app.skills.base import Skill
from app.services.llm_service import chat


class MultiPassWriterSkill(Skill):
    name = "multi_pass_write"
    description = "多轮精写：初稿→自评→重写循环，生成高质量报告章节。解决单次LLM生成的空洞表述、缺乏数据支撑和逻辑跳跃问题"
    category = "offline"
    parameters = {
        "topic": {"type": "string", "description": "章节主题或问题"},
        "section_type": {
            "type": "string",
            "description": "章节类型: analysis | recommendation | executive_summary | conclusion | background",
            "default": "analysis",
        },
        "findings": {"type": "string", "description": "研究发现和数据支撑（可为空）"},
        "output_format": {
            "type": "string",
            "description": "输出格式: ppt | word | excel，影响写作风格",
            "default": "word",
        },
        "word_count": {
            "type": "integer",
            "description": "目标字数",
            "default": 500,
        },
        "passes": {
            "type": "integer",
            "description": "迭代轮数（1=仅初稿，2=初稿+重写，3=三轮精写）",
            "default": 2,
        },
    }

    SECTION_PERSONAS = {
        "analysis": "资深行业分析师，擅长数据解读和因果分析，写作风格严谨客观",
        "recommendation": "战略顾问，擅长提出可执行建议，写作聚焦行动性和优先级",
        "executive_summary": "管理咨询合伙人，擅长用最少篇幅传达最大价值，结论先行",
        "conclusion": "研究报告主笔，擅长总结洞察和展望，逻辑收尾完整",
        "background": "行业研究员，擅长背景铺垫和框架建立，深入浅出",
    }

    CRITIQUE_DIMENSIONS = [
        "数据支撑：是否有具体数字/比率/区间？是否标注了数据来源类型？",
        "逻辑链条：因果关系是否清晰？结论是否从证据中自然推导？",
        "具体性：是否有泛泛而谈的空洞表述需要替换为具体陈述？",
        "洞察深度：是否提供了非显而易见的洞察？还是仅重复常识？",
        "结构清晰：段落间是否有逻辑过渡？读者能否快速提取核心信息？",
    ]

    FORMAT_STYLE = {
        "ppt": "每段≤3句，要点化，数字加粗，结论先行",
        "word": "完整段落叙述，数据+分析+结论三段式，适当使用小标题",
        "excel": "简洁说明性文字，配合表格数据，聚焦数字和指标解读",
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        topic = params.get("topic", "")
        section_type = params.get("section_type", "analysis")
        findings = params.get("findings", "")
        output_format = params.get("output_format", "word")
        word_count = params.get("word_count", 500)
        passes = min(params.get("passes", 2), 3)

        if not topic:
            return {"result": "", "error": "topic is required"}

        persona = self.SECTION_PERSONAS.get(section_type, self.SECTION_PERSONAS["analysis"])
        format_style = self.FORMAT_STYLE.get(output_format, self.FORMAT_STYLE["word"])
        findings_block = f"\n\n## 研究发现与数据\n{findings[:2000]}" if findings else ""

        # Pass 1: First draft
        draft = await self._write_draft(topic, persona, findings_block, format_style, word_count)

        if passes == 1:
            return {"result": draft, "passes_completed": 1, "final": draft}

        # Pass 2: Self-critique + rewrite
        critique = await self._critique(draft, topic)
        rewrite = await self._rewrite(draft, critique, topic, persona, format_style, word_count)

        if passes == 2:
            return {"result": rewrite, "passes_completed": 2, "draft": draft,
                    "critique": critique, "final": rewrite}

        # Pass 3: Polish
        polished = await self._polish(rewrite, output_format, word_count)
        return {"result": polished, "passes_completed": 3, "draft": draft,
                "critique": critique, "rewrite": rewrite, "final": polished}

    async def _write_draft(self, topic, persona, findings_block, format_style, word_count):
        messages = [
            {
                "role": "system",
                "content": f"你是{persona}。写作风格要求：{format_style}。直接开始写内容，不要解释你在做什么。",
            },
            {
                "role": "user",
                "content": f"""请撰写关于以下主题的报告章节初稿。{findings_block}

## 章节主题
{topic}

## 要求
- 目标字数：约{word_count}字
- 包含具体数据（即使是估算区间，也要标注"（行业估算）"）
- 逻辑清晰，结论可追溯
- 直接输出正文内容""",
            },
        ]
        return await chat(messages, temperature=0.5, max_tokens=1500)

    async def _critique(self, draft, topic):
        criteria = "\n".join(f"{i+1}. {c}" for i, c in enumerate(self.CRITIQUE_DIMENSIONS))
        messages = [
            {
                "role": "system",
                "content": "你是严格的报告质量评审专家。你的任务是找出草稿的具体弱点，给出可执行的改进建议。",
            },
            {
                "role": "user",
                "content": f"""请评审以下关于"{topic}"的报告草稿。

## 草稿内容
{draft}

## 评审维度
{criteria}

请逐条指出具体问题和改进方向（每条2-3句）。格式：
**[维度名]**: 问题描述 → 改进建议""",
            },
        ]
        return await chat(messages, temperature=0.3, max_tokens=800)

    async def _rewrite(self, draft, critique, topic, persona, format_style, word_count):
        messages = [
            {
                "role": "system",
                "content": f"你是{persona}。写作风格：{format_style}。基于评审意见重写，要有实质性改进，不只是小修小改。",
            },
            {
                "role": "user",
                "content": f"""请根据以下评审意见，对草稿进行实质性重写。

## 原始草稿
{draft}

## 评审意见
{critique}

## 重写要求
- 直接针对评审中指出的每个问题进行改进
- 保留原稿中好的部分
- 目标字数：约{word_count}字
- 直接输出重写后的正文""",
            },
        ]
        return await chat(messages, temperature=0.4, max_tokens=1500)

    async def _polish(self, text, output_format, word_count):
        format_rules = {
            "ppt": "将内容压缩为要点形式，每个要点≤25字，保留所有关键数据，去掉过渡语",
            "word": "确保段落流畅，数字格式统一，小标题清晰，补充必要的过渡句",
            "excel": "提炼为简洁的说明性段落，突出数字和指标，方便与表格数据配合",
        }
        rule = format_rules.get(output_format, format_rules["word"])
        messages = [
            {
                "role": "system",
                "content": "你是专业文字润色专家。专注于格式规范和表达精炼，不改变内容实质。",
            },
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
        return await chat(messages, temperature=0.2, max_tokens=1500)
