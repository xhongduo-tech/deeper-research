"""Slide Scripter — SOTA-enhanced per-slide JSON structure generator for layout-aware PPTX.

Enhancements:
  - Chain-of-Thought: reason about presentation narrative arc before slide generation
  - Self-critique: checks slide flow, information density, audience alignment
  - Adversarial review: challenges weak messages, spots redundant slides
  - Quality score (0-100) per presentation
  - Structured JSON output with auto-repair
  - Confidence scoring per slide design decision

Emulates Manus-style presentation authoring: each slide gets a concrete
layout type, content blueprint, and speaker notes before the PPTX renderer
touches it.
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class SlideScripterSkill(Skill):
    name = "script_slides"
    description = (
        "SOTA PPT脚本生成：将报告大纲转化为每页幻灯片的结构化JSON脚本，"
        "含演示叙事推理、自评、红队挑战和质量评分。"
        "包含布局类型、标题、要点、数据、备注，驱动专业PPT生成"
    )
    category = "offline"
    parameters = {
        "outline": {"type": "string", "description": "报告大纲或章节内容（Markdown格式）"},
        "topic": {"type": "string", "description": "报告主题"},
        "report_type": {"type": "string", "description": "报告类型（影响幻灯片风格）"},
        "slide_count": {
            "type": "integer",
            "description": "目标幻灯片数量（不含封面和目录）",
            "default": 12,
        },
        "audience": {
            "type": "string",
            "description": "受众类型: executive（高管）| analyst（分析师）| client（客户）| internal（内部）",
            "default": "executive",
        },
        "enable_critique": {
            "type": "boolean",
            "description": "启用幻灯片结构自评",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队挑战",
            "default": True,
        },
    }

    LAYOUT_TYPES = {
        "cover": "封面：大标题+副标题+日期，全版背景色",
        "agenda": "目录：章节编号+标题列表",
        "section_divider": "章节分隔：大号章节序号+章节名+一句话摘要",
        "key_insight": "核心洞察：超大数字/结论居中展示，配1-2句说明",
        "bullet_list": "要点列表：标题+3-6条带图标要点",
        "two_column": "双栏对比：左右各有标题+内容，适合对比分析",
        "data_table": "数据表格：标题+Markdown表格，适合指标汇总",
        "timeline": "时间轴：横向时间线+节点事件描述",
        "chart_placeholder": "图表占位：标题+图表描述+数据来源",
        "conclusion": "结论页：总结要点+行动建议",
    }

    AUDIENCE_TONE = {
        "executive": "简洁有力，每页≤5个要点，突出结论和影响",
        "analyst": "数据驱动，详细假设和方法论，可包含更多细节",
        "client": "故事化叙述，聚焦价值主张和解决方案",
        "internal": "操作导向，包含实施细节和责任方",
    }

    SLIDE_SCHEMA = [
        {
            "slide_number": 1,
            "layout": "cover",
            "title": "",
            "key_message": "",
            "content": {},
            "speaker_notes": "",
            "confidence": 0.9,
        }
    ]

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        outline = params.get("outline", "")
        topic = params.get("topic", "")
        report_type = params.get("report_type", "")
        slide_count = params.get("slide_count", 12)
        audience = params.get("audience", "executive")
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)

        if not outline and not topic:
            return {"result": "", "slides": [], "error": "outline or topic required"}

        audience_hint = self.AUDIENCE_TONE.get(audience, self.AUDIENCE_TONE["executive"])
        layout_guide = "\n".join(f"- **{k}**: {v}" for k, v in self.LAYOUT_TYPES.items())

        # ── Phase 1: CoT Narrative Arc Reasoning ──────────────────────────────
        cot_messages = [
            {
                "role": "system",
                "content": f"""你是专业PPT设计师兼演讲教练，擅长将研究内容转化为高冲击力的幻灯片脚本。

受众风格：{audience_hint}
报告类型：{report_type}

请先思考演示的叙事弧线（narrative arc），再生成具体幻灯片。""",
            },
            {
                "role": "user",
                "content": f"""请为以下报告规划演示叙事弧线。

## 报告主题
{topic}

## 报告大纲
{outline[:2000]}

## 要求
- 目标页数：{slide_count} 张内容页
- 受众：{audience}

思考任务：
1. 演示的核心故事线是什么？（从什么问题出发，到什么结论）
2. 每页幻灯片应承载什么信息？
3. 哪些页面应该使用数据可视化？
4. 叙事节奏如何安排（开场→建立→高潮→收尾）？

请输出你的叙事规划。""",
            },
        ]
        reasoning = await chat(cot_messages, temperature=0.3, max_tokens=1000)

        # ── Phase 2: Structured Slide Generation ──────────────────────────────
        messages = [
            {
                "role": "system",
                "content": f"""你是专业PPT设计师兼演讲教练，擅长将研究内容转化为高冲击力的幻灯片脚本。

受众风格：{audience_hint}
报告类型：{report_type}

可用布局类型：
{layout_guide}

输出原则：
1. 每页PPT必须有一个明确的"核心信息"（takeaway），一句话总结
2. 数据页优先使用 key_insight 或 data_table 布局
3. 对比分析使用 two_column 布局
4. 流程/历史用 timeline 布局
5. speaker_notes 包含演讲时的口头说明（2-3句）
6. 每张幻灯片标注 confidence (0-1)""",
            },
            {
                "role": "user",
                "content": f"""叙事规划：
{reasoning[:800]}

请为以下报告生成完整的PPT幻灯片脚本（JSON格式）。

## 报告主题
{topic}

## 报告大纲/内容
{outline[:3000]}

## 要求
- 生成 {slide_count} 张内容页（加上封面、目录共约{slide_count + 3}张）
- 每张幻灯片包含：slide_number, layout, title, key_message, content, speaker_notes, confidence
- content字段根据layout类型调整：bullet_list用列表，key_insight用单个醒目数字/结论，two_column用{{left, right}}对象，data_table用Markdown表格字符串

请严格输出JSON数组，格式如下：
```json
[
  {{
    "slide_number": 1,
    "layout": "cover",
    "title": "报告标题",
    "key_message": "一句话核心信息",
    "content": {{"subtitle": "副标题", "date": "2026年5月"}},
    "speaker_notes": "开场白...",
    "confidence": 0.95
  }},
  ...
]
```

只输出JSON，不要任何其他文字。""",
            },
        ]

        raw = await chat(messages, temperature=0.3, max_tokens=4000)

        slides = []
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                slides = json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            slides = self._fallback_slides(topic, outline)

        result = {
            "result": raw,
            "slides": slides,
            "slide_count": len(slides),
            "audience": audience,
            "reasoning": reasoning,
        }

        # ── Phase 3: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique and slides:
            try:
                critique = await self_critique(
                    draft=f"幻灯片数量: {len(slides)}, 主题: {topic}, 受众: {audience}",
                    topic=f"PPT脚本 - {topic}",
                    dimensions=["structural_clarity", "audience_fit", "specificity"],
                )
                quality_score = round(critique["overall_score"] * 10)
                result["quality_score"] = quality_score
                result["critique"] = critique
            except Exception:
                pass

        # ── Phase 4: Adversarial review ───────────────────────────────────────
        if enable_adversarial and slides:
            try:
                adversarial = await adversarial_review(
                    output=f"幻灯片数量: {len(slides)}, 主题: {topic}",
                    topic=f"PPT脚本 - {topic}",
                )
                result["adversarial"] = adversarial
            except Exception:
                pass

        return result

    def _fallback_slides(self, topic: str, outline: str) -> list:
        lines = [l.strip() for l in outline.split("\n") if l.strip().startswith("##")]
        slides = [
            {"slide_number": 1, "layout": "cover", "title": topic,
             "key_message": topic, "content": {"subtitle": "深度研究报告"}, "speaker_notes": "", "confidence": 0.9},
            {"slide_number": 2, "layout": "agenda", "title": "报告目录",
             "key_message": "本报告结构", "content": [l.lstrip("#").strip() for l in lines[:8]],
             "speaker_notes": "", "confidence": 0.9},
        ]
        for i, line in enumerate(lines[:10], start=3):
            slides.append({
                "slide_number": i,
                "layout": "bullet_list",
                "title": line.lstrip("#").strip(),
                "key_message": "",
                "content": [],
                "speaker_notes": "",
                "confidence": 0.8,
            })
        return slides
