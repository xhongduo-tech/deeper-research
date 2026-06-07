"""IncrementalEditor — Edit specific sections without full regeneration.

Supports localized modifications to completed reports:
  1. Load section context (neighboring sections for coherence)
  2. Apply edit instruction while maintaining style consistency
  3. Update related citations and cross-references
  4. Return modified section with change summary
"""
from __future__ import annotations

import logging
from typing import Optional

from app.services.llm_service import chat_json
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)


class IncrementalEditor:
    """Edit specific report sections without regenerating the entire document.

    Key capabilities:
    - Context-aware: loads neighboring sections for coherence
    - Style-preserving: matches existing writing style
    - Reference-updating: adjusts citations and cross-references
    - Change tracking: returns before/after diff
    """

    def __init__(self, db=None):
        self.db = db
        self._router = get_model_router()

    async def edit_section(
        self,
        report_id: int,
        section_id: str,
        instruction: str,
        current_content: str,
        neighbor_sections: Optional[list[dict]] = None,
        report_title: str = "",
    ) -> dict:
        """Edit a single section based on user instruction.

        Args:
            report_id: The report ID
            section_id: Section identifier (e.g., "section_3" or outline ID)
            instruction: User's edit instruction
            current_content: Current section content
            neighbor_sections: Adjacent sections for context (prev/next)
            report_title: Report title for tone consistency

        Returns:
            Dict with edited_content, changes_summary, and consistency_notes
        """
        logger.info(f"[IncrementalEditor] Editing section {section_id} for report {report_id}")

        # Build context
        context = self._build_context(
            report_title=report_title,
            current_content=current_content,
            neighbor_sections=neighbor_sections or [],
        )

        # Route to standard model (writing task)
        model, base_url, api_key = self._router.route_for_chat(
            agent_type="li_bai",
            messages=[{"role": "user", "content": instruction}],
        )

        # Generate edit
        prompt = f"""你是一位专业的文档编辑专家。请根据用户的编辑指令，修改以下报告章节。

编辑指令：{instruction}

{context}

当前章节内容：
```
{current_content}
```

请输出JSON格式结果：
{{
  "edited_content": "修改后的完整章节内容（Markdown格式）",
  "changes_summary": "修改内容摘要（列出具体改动点）",
  "consistency_notes": "与前后章节一致性说明",
  "affected_references": ["受影响的引用/交叉引用列表"],
  "word_count_delta": 字数变化（整数，可为负）
}}

编辑要求：
1. 保持与原文一致的写作风格和专业术语
2. 只修改与指令相关的内容，保留其他部分不变
3. 确保修改后的内容与前后章节逻辑连贯
4. 如果涉及数据修改，更新相关的引用标记
5. 如果指令要求删减，确保不丢失关键论点
"""

        try:
            result = await chat_json(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=0.5,
                max_tokens=4000,
            )
            result["section_id"] = section_id
            result["instruction"] = instruction
            result["success"] = True
            logger.info(f"[IncrementalEditor] Section {section_id} edited successfully")
            return result
        except Exception as e:
            logger.exception(f"[IncrementalEditor] Edit failed: {e}")
            return {
                "section_id": section_id,
                "instruction": instruction,
                "edited_content": current_content,
                "changes_summary": f"编辑失败：{str(e)}",
                "consistency_notes": "",
                "affected_references": [],
                "word_count_delta": 0,
                "success": False,
                "error": str(e),
            }

    async def edit_paragraph(
        self,
        report_id: int,
        section_id: str,
        paragraph_index: int,
        instruction: str,
        current_content: str,
        report_title: str = "",
    ) -> dict:
        """Edit a specific paragraph within a section.

        More granular than edit_section — targets a single paragraph
        by index, useful for UI-driven "edit this paragraph" features.
        """
        paragraphs = [p for p in current_content.split("\n\n") if p.strip()]
        if paragraph_index >= len(paragraphs):
            return {
                "success": False,
                "error": f"段落索引 {paragraph_index} 超出范围（共 {len(paragraphs)} 段）",
                "edited_content": current_content,
            }

        target_paragraph = paragraphs[paragraph_index]

        model, base_url, api_key = self._router.route_for_chat(
            agent_type="li_bai",
            messages=[{"role": "user", "content": instruction}],
        )

        prompt = f"""请修改报告中的指定段落。

编辑指令：{instruction}
报告标题：{report_title}

目标段落：
```
{target_paragraph}
```

章节上下文（前后段落）：
{self._format_neighbors(paragraphs, paragraph_index)}

请输出JSON格式结果：
{{
  "edited_paragraph": "修改后的段落",
  "rationale": "修改理由",
  "style_match_score": 1-10
}}
"""

        try:
            result = await chat_json(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=0.5,
                max_tokens=2000,
            )

            # Replace paragraph in content
            paragraphs[paragraph_index] = result.get("edited_paragraph", target_paragraph)
            edited_content = "\n\n".join(paragraphs)

            return {
                "success": True,
                "section_id": section_id,
                "paragraph_index": paragraph_index,
                "edited_content": edited_content,
                "edited_paragraph": result.get("edited_paragraph", target_paragraph),
                "rationale": result.get("rationale", ""),
                "style_match_score": result.get("style_match_score", 0),
            }
        except Exception as e:
            logger.exception(f"[IncrementalEditor] Paragraph edit failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "edited_content": current_content,
            }

    def _build_context(
        self,
        report_title: str,
        current_content: str,
        neighbor_sections: list[dict],
    ) -> str:
        """Build editing context from neighboring sections."""
        parts = [f"报告标题：{report_title}"]

        for sec in neighbor_sections:
            rel = sec.get("relation", "相关章节")
            title = sec.get("title", "")
            content = sec.get("content", "")[:500]
            parts.append(f"\n{rel}：{title}\n```\n{content}\n```")

        return "\n".join(parts)

    def _format_neighbors(self, paragraphs: list[str], idx: int) -> str:
        """Format surrounding paragraphs for context."""
        parts = []
        if idx > 0:
            parts.append(f"前一段：\n{paragraphs[idx - 1][:300]}")
        if idx < len(paragraphs) - 1:
            parts.append(f"后一段：\n{paragraphs[idx + 1][:300]}")
        return "\n\n".join(parts) if parts else "（无相邻段落）"
