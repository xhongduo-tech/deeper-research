"""P3-3: Multi-turn chat service for interacting with a generated report.

Intent classification routes the user message to one of three handlers:
  - revise_section: Re-run SPEC_GEN+DOC_RENDER for the named section
  - answer_question: Answer questions about the report content via LLM
  - full_regen: Trigger a full pipeline re-run (used for major scope changes)
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.report import Report

logger = logging.getLogger(__name__)

_INTENT_SYSTEM = """\
你是文档助手意图分类器。根据用户消息判断意图，输出以下三种之一：
- "revise_section" — 用户要修改/改写某个章节的内容
- "answer_question" — 用户在询问报告内容、数据或背景知识
- "full_regen" — 用户要大幅调整报告方向或结构，需重新生成

只输出JSON：{"intent": "revise_section"|"answer_question"|"full_regen", "section_hint": "章节标题提示（如有）"}
"""


async def handle_report_chat(
    db: "AsyncSession",
    report: "Report",
    message: str,
    user_id: int,
) -> dict:
    """Route user message to the appropriate handler, return chat response dict."""
    from app.pipeline.llm_helpers import call_llm_json, call_llm_text

    # Step 1: Classify intent
    try:
        intent_raw = await call_llm_json(
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user", "content": f"报告标题：{report.title}\n\n用户消息：{message}"},
            ],
            temperature=0.1,
            max_tokens=200,
            tier="standard",
        )
        intent = intent_raw.get("intent", "answer_question")
        section_hint = intent_raw.get("section_hint", "")
    except Exception as exc:
        logger.warning("[Chat] Intent classification failed: %s", exc)
        intent = "answer_question"
        section_hint = ""

    logger.info("[Chat] report=%d intent=%s section_hint=%r", report.id, intent, section_hint)

    # Step 2: Route
    if intent == "revise_section":
        return await _handle_revise(db, report, message, section_hint)
    elif intent == "full_regen":
        return await _handle_full_regen(db, report, message)
    else:
        return await _handle_answer(report, message)


async def _handle_revise(
    db: "AsyncSession",
    report: "Report",
    instruction: str,
    section_hint: str,
) -> dict:
    """Identify which section to revise and kick off pipeline revision."""
    from app.pipeline.run import run_section_revision
    from app.api.reports import get_report_detail

    scoping = dict(report.scoping_plan or {})
    spec_json = scoping.get("spec_json", {})
    section_id = _find_section_id(spec_json, section_hint)

    if not section_id:
        return {
            "intent": "revise_section",
            "reply": (
                f"无法自动识别您要修改的章节（提示：'{section_hint}'）。"
                "请通过 revise-section 接口并指定 section_id 进行精确修订。"
            ),
            "action": None,
        }

    async def _run():
        async for _db in __import__("app.database", fromlist=["get_db"]).get_db():
            fresh = await get_report_detail(_db, report.id)
            if fresh:
                await run_section_revision(_db, fresh, section_id, instruction)
            break

    asyncio.create_task(_run())
    return {
        "intent": "revise_section",
        "reply": f"正在重新生成章节「{section_hint or section_id}」，完成后文档将自动更新。",
        "action": {"type": "revise_section", "section_id": section_id},
    }


async def _handle_answer(report: "Report", question: str) -> dict:
    """Answer a question about the report using its stored content."""
    from app.pipeline.llm_helpers import call_llm_text

    scoping = dict(report.scoping_plan or {})
    spec_json = scoping.get("spec_json", {})

    # Build a compact context from the spec
    context_parts = [f"报告标题：{report.title}"]
    sections = spec_json.get("sections") or spec_json.get("slides") or spec_json.get("sheets") or []
    for sec in sections[:8]:
        title = sec.get("title") or sec.get("assertion_title") or sec.get("name", "")
        paras = sec.get("paragraphs") or []
        bullets = sec.get("bullets") or []
        excerpt = " ".join((paras + bullets)[:2])[:200]
        if title:
            context_parts.append(f"【{title}】{excerpt}")

    context = "\n".join(context_parts)[:3000]

    try:
        reply = await call_llm_text(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是文档助手，根据以下报告内容回答用户问题。"
                        "请简明扼要，引用报告原文时加引号。\n\n" + context
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=800,
            tier="standard",
        )
    except Exception as exc:
        logger.warning("[Chat] Answer LLM call failed: %s", exc)
        reply = "抱歉，回答生成失败，请稍后重试。"

    return {"intent": "answer_question", "reply": reply, "action": None}


async def _handle_full_regen(db: "AsyncSession", report: "Report", instruction: str) -> dict:
    """Trigger a full pipeline re-run when user wants major changes."""
    return {
        "intent": "full_regen",
        "reply": (
            "您的修改幅度较大，建议重新提交报告需求以完整重新生成。"
            "如只需修改单个章节，请说明具体章节名称，我可以定向修订。"
        ),
        "action": {"type": "full_regen_suggested", "instruction": instruction},
    }


def _find_section_id(spec_json: dict, section_hint: str) -> str:
    """Best-effort: find section id from spec_json by fuzzy-matching section_hint."""
    if not spec_json or not section_hint:
        return ""
    sections = spec_json.get("sections") or spec_json.get("slides") or spec_json.get("sheets") or []
    hint_lower = section_hint.lower()
    best_id = ""
    best_overlap = 0
    for sec in sections:
        title = (sec.get("title") or sec.get("assertion_title") or sec.get("name") or "").lower()
        overlap = sum(1 for ch in hint_lower if ch in title)
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = sec.get("id", "")
    return best_id if best_overlap >= 2 else ""
