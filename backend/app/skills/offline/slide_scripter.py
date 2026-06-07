"""
Slide Scripter — per-slide JSON structure generator for layout-aware PPTX.

Emulates Manus-style presentation authoring: each slide gets a concrete
layout type, content blueprint, and speaker notes before the PPTX renderer
touches it.
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat


class SlideScripterSkill(Skill):
    name = "script_slides"
    description = "将报告大纲/内容转化为每页PPT的结构化JSON脚本，包含布局类型、标题、要点、数据、备注，驱动专业PPT生成"
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

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        outline = params.get("outline", "")
        topic = params.get("topic", "")
        report_type = params.get("report_type", "")
        slide_count = params.get("slide_count", 12)
        audience = params.get("audience", "executive")

        if not outline and not topic:
            return {"result": "", "slides": [], "error": "outline or topic required"}

        audience_hint = self.AUDIENCE_TONE.get(audience, self.AUDIENCE_TONE["executive"])
        layout_guide = "\n".join(f"- **{k}**: {v}" for k, v in self.LAYOUT_TYPES.items())

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
5. speaker_notes 包含演讲时的口头说明（2-3句）""",
            },
            {
                "role": "user",
                "content": f"""请为以下报告生成完整的PPT幻灯片脚本（JSON格式）。

## 报告主题
{topic}

## 报告大纲/内容
{outline[:3000]}

## 要求
- 生成 {slide_count} 张内容页（加上封面、目录共约{slide_count + 3}张）
- 每张幻灯片包含：layout, title, key_message, content（列表或字符串）, speaker_notes
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
    "speaker_notes": "开场白..."
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

        return {
            "result": raw,
            "slides": slides,
            "slide_count": len(slides),
            "audience": audience,
        }

    def _fallback_slides(self, topic: str, outline: str) -> list:
        lines = [l.strip() for l in outline.split("\n") if l.strip().startswith("##")]
        slides = [
            {"slide_number": 1, "layout": "cover", "title": topic,
             "key_message": topic, "content": {"subtitle": "深度研究报告"}, "speaker_notes": ""},
            {"slide_number": 2, "layout": "agenda", "title": "报告目录",
             "key_message": "本报告结构", "content": [l.lstrip("#").strip() for l in lines[:8]],
             "speaker_notes": ""},
        ]
        for i, line in enumerate(lines[:10], start=3):
            slides.append({
                "slide_number": i,
                "layout": "bullet_list",
                "title": line.lstrip("#").strip(),
                "key_message": "",
                "content": [],
                "speaker_notes": "",
            })
        return slides
