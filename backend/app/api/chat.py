"""Plain chat API for DataAgent home Q&A."""
from __future__ import annotations

import json
import asyncio
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.middleware.auth_middleware import get_current_user
from app.models.message import Message
from app.models.report import Report
from app.models.system_config import SystemConfig
from app.models.user import User
from app.schemas.message import ChatRequest, ChatResponse, MessageResponse
from app.services.llm_service import chat, chat_stream, selected_llm_profile, effort_context
from app.services.orchestrator import add_message
from app.services.report_service import get_report_messages, _attach_uploaded_files
from app.services.sandbox import execute_python

router = APIRouter(prefix="/api/chat", tags=["chat"])

_WEEKDAYS_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _local_timezone() -> ZoneInfo | timezone:
    tz_name = (os.getenv("APP_TIMEZONE") or os.getenv("TZ") or "Asia/Shanghai").strip()
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


def _normalize_short_query(prompt: str) -> str:
    return re.sub(r"[\s，。！？?!.、:：；;\"'“”‘’（）()\[\]{}<>《》]+", "", prompt.lower())


def _answer_with_current_datetime_tool(prompt: str, now: datetime | None = None) -> str | None:
    """Answer narrow local date/time questions without asking the LLM to guess."""
    q = _normalize_short_query(prompt)
    if not q or len(q) > 32:
        return None

    date_terms = ("今天", "今日", "当前日期", "现在日期", "日期", "几月几日", "几号")
    time_terms = ("几点", "时间", "现在", "当前时间")
    weekday_terms = ("星期", "周几", "礼拜")
    asks_date = any(term in q for term in date_terms)
    asks_time = any(term in q for term in time_terms)
    asks_weekday = any(term in q for term in weekday_terms)
    if not (asks_date or asks_time or asks_weekday):
        return None

    if any(term in q for term in ("明天", "昨天", "后天", "前天")):
        return None
    if any(term in q for term in ("天气", "新闻", "行情", "股价", "汇率", "搜索", "查一下")):
        return None

    local_now = now.astimezone(_local_timezone()) if now else datetime.now(_local_timezone())
    weekday = _WEEKDAYS_ZH[local_now.weekday()]
    full_date = f"{local_now.year}年{local_now.month}月{local_now.day}日"
    month_day = f"{local_now.month}月{local_now.day}日"
    clock = local_now.strftime("%H:%M")

    if asks_time and asks_date:
        return f"现在是{full_date} {clock}，{weekday}。"
    if asks_time and not asks_date and not asks_weekday:
        return f"现在是{clock}。"
    if asks_weekday:
        return f"今天是{full_date}，{weekday}。"
    if "年" in q or "日期" in q:
        return f"今天是{full_date}。"
    return f"今天是{month_day}。"


class CodeExecuteRequest(BaseModel):
    language: str = "python"
    code: str


class ChatRegenerateRequest(BaseModel):
    report_id: int
    message_id: int
    prompt: str
    model_id: str | None = None
    effort: str = "low"


def _json_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


async def _build_or_get_chat_report(
    db: AsyncSession,
    current_user: User,
    data: ChatRequest,
    prompt: str,
) -> Report:
    if data.conversation_id:
        report = await db.get(Report, data.conversation_id)
        if not report:
            raise HTTPException(status_code=404, detail="对话不存在")
        if report.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="无权访问")
        report.status = "running"
        report.progress = 0.2
        report.phase = "正在回复"
        report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        return report

    report = Report(
        user_id=current_user.id,
        project_id=data.project_id,
        title=prompt[:100],
        brief=prompt,
        report_type="普通问答",
        output_format="chat",
        status="running",
        progress=0.2,
        phase="正在回复",
        data_context={"model_id": data.model_id} if data.model_id else None,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def _resolve_kb_ids(db: AsyncSession, kb_ids: list[int], include_system: bool) -> list[int]:
    """Resolve user-provided kb_ids, optionally adding all corp-scope system KBs."""
    all_ids = list(kb_ids)
    if include_system:
        from app.models.knowledge_base import KnowledgeBase
        system_kb_ids = (await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.scope == "corp")
        )).scalars().all()
        for kb_id in system_kb_ids:
            if kb_id not in all_ids:
                all_ids.append(kb_id)
    return all_ids


async def _build_rag_context(
    db: AsyncSession, kb_ids: list[int], query: str
) -> tuple[str, list[dict]]:
    """Search provided KBs.

    Returns:
        (context_string, sources_list)
        sources_list items: {"source": str, "snippet": str}
    """
    if not kb_ids:
        return "", []
    from app.services.rag_service import search_kb
    try:
        results = await search_kb(db, kb_ids=kb_ids, query=query, top_k=6, score_threshold=0.15)
        if not results:
            return "", []
        snippets: list[str] = []
        sources: list[dict] = []
        for r in results:
            content = r.get("content", "")
            source = r.get("source", "未知来源")
            if content:
                snippets.append(f"【{source}】{content[:400]}")
                sources.append({"source": source, "snippet": content[:120]})
        return "\n\n".join(snippets), sources
    except Exception:
        return "", []


# ── Layer 3: 本体论意图路由器 ──────────────────────────────────────────────────
# 轻量规则匹配（无 LLM 调用），为特定领域注入专业系统提示。

_ONTOLOGY_SYSTEM_HINTS: dict[str, str] = {
    "business_research": (
        "当前场景：商业研究与行业分析。请使用行业标准术语，区分宏观/中观/微观层次，"
        "引用数据时注明时效性，结论需有来源支撑。对不确定信息使用【可能】【或】【估计】等限定词。"
    ),
    "structured_data": (
        "当前场景：结构化数据分析。优先用数字和表格呈现结论，指明字段名/维度名，"
        "区分绝对值与比率，说明计算逻辑，避免模糊描述。"
    ),
    "software_engineering": (
        "当前场景：代码诊断与工程分析。回答须包含：问题根因、最小可复现示例、修复方案、"
        "验证步骤。引用具体行号/函数名/类名，注明适用的语言版本或框架版本。"
    ),
    "document_retrieval": (
        "当前场景：文档问答。回答须明确引用原文依据，区分文档内容与你自身推断，"
        "无法从文档中找到的信息须明确说明。"
    ),
    "graph_knowledge": (
        "当前场景：知识图谱。注意区分实体、关系、属性三类概念，"
        "回答时用（主体 → 关系 → 客体）的三元组形式说明核心结构。"
    ),
}


async def _build_llm_messages(
    db: AsyncSession,
    report: Report,
    uploaded_texts: list[str],
    kb_ids: list[int] | None = None,
    include_system_kb: bool = False,
    query: str = "",
) -> tuple[list[dict], list[dict], str]:
    """Build LLM message list with RAG context and ontology intent routing.

    Returns:
        (llm_messages, rag_sources, intent_domain)
    """
    history = await get_report_messages(db, report.id, limit=20)

    # ── Layer 1 + 2: RAG 检索 ────────────────────────────────────────────────
    rag_context = ""
    rag_sources: list[dict] = []
    if kb_ids or include_system_kb:
        resolved_ids = await _resolve_kb_ids(db, kb_ids or [], include_system_kb)
        if resolved_ids:
            rag_context, rag_sources = await _build_rag_context(db, resolved_ids, query)

    # ── Layer 3: 本体论意图路由（纯关键词，零延迟）──────────────────────────
    intent_domain = "general"
    ontology_hint = ""
    if query:
        try:
            from app.knowledge.intent_router import IntentRouter
            intent = await IntentRouter.route(query, use_llm=False)
            intent_domain = intent.ontology_domain
            ontology_hint = _ONTOLOGY_SYSTEM_HINTS.get(intent_domain, "")
        except Exception:
            pass  # 路由失败不影响主流程

    # ── 构建消息列表 ─────────────────────────────────────────────────────────
    base_system = (
        "你是 DataAgent 的智能问答助手。回答要清晰、实用、自然；"
        "需要结构化时使用 Markdown，可使用 **加粗**、*斜体*、列表和 Markdown 表格。"
        "需要提高可读性时可少量使用增强样式，但必须遵守固定语义："
        "{red:重要结论/风险/必须注意的动作}，{blue:文件名、对象名、表名或引用名称}，"
        "==核心关键词==用于同一类需要反复识别的主题词；同一类核心内容只要出现就保持一致标注。"
        "{soft-red:警示短语}、{soft-blue:信息短语}、{badge:短标签}只用于很短内容。"
        "不要为了好看而染色；不要整句整段染色；每段最多 1-2 处增强标注。"
        "如果信息不足，先说明假设并给出可执行建议。不要假装已经生成文件。"
    )
    if ontology_hint:
        base_system = base_system + "\n\n" + ontology_hint

    llm_messages: list[dict] = [{"role": "system", "content": base_system}]

    if rag_context:
        llm_messages.append({
            "role": "system",
            "content": "以下是从知识库中检索到的相关上下文，请优先依据这些内容回答：\n\n" + rag_context[:10000],
        })
    if uploaded_texts:
        llm_messages.append({
            "role": "system",
            "content": "以下是用户上传文件的解析内容，可作为本轮问答依据：\n\n" + "\n\n".join(uploaded_texts)[:12000],
        })
    for msg in history[-12:]:
        if msg.role in {"user", "assistant"} and (msg.content or "").strip():
            llm_messages.append({"role": msg.role, "content": msg.content})

    return llm_messages, rag_sources, intent_domain


async def _selected_model_profile(db: AsyncSession, model_id: str | None) -> dict | None:
    if not model_id:
        return None
    clean_id = str(model_id).replace("pool:", "", 1)
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "model_pool"))
    ).scalar_one_or_none()
    if not row or not row.value:
        return None
    try:
        items = json.loads(row.value)
    except Exception:
        return None
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        if str(item.get("id") or item.get("model")) == clean_id:
            return {
                "model": str(item.get("model") or "").strip(),
                "base_url": str(item.get("base_url") or "").strip().rstrip("/"),
                "api_key": str(item.get("api_key") or "ollama").strip(),
            }
    return None


async def _persist_assistant_answer(db: AsyncSession, report: Report, answer: str) -> None:
    await add_message(
        db,
        report.id,
        "assistant",
        answer,
        author_id="dataagent",
        author_name="DataAgent",
    )
    report.status = "completed"
    report.progress = 1.0
    report.phase = "已回复"
    report.brief = answer
    report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def send_plain_chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = (data.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="请输入问题")

    report = await _build_or_get_chat_report(db, current_user, data, prompt)

    uploaded_texts = []
    if data.uploaded_files:
        uploaded_texts = await _attach_uploaded_files(db, report, current_user.id, data.uploaded_files)

    await add_message(
        db,
        report.id,
        "user",
        prompt,
        author_id=str(current_user.id),
        author_name=current_user.username,
    )

    local_tool_answer = _answer_with_current_datetime_tool(prompt)
    if local_tool_answer:
        await _persist_assistant_answer(db, report, local_tool_answer)
        messages = await get_report_messages(db, report.id, limit=100)
        return ChatResponse(
            report_id=report.id,
            answer=local_tool_answer,
            messages=[MessageResponse.model_validate(m) for m in messages],
        )

    llm_messages, rag_sources, intent_domain = await _build_llm_messages(
        db, report, uploaded_texts,
        kb_ids=data.kb_ids, include_system_kb=data.include_system_kb, query=prompt,
    )

    profile = await _selected_model_profile(db, data.model_id)
    try:
        with effort_context(data.effort):
            if profile:
                with selected_llm_profile(profile):
                    answer = await chat(llm_messages, temperature=0.35, max_tokens=1800)
            else:
                answer = await chat(llm_messages, temperature=0.35, max_tokens=1800)
    except Exception as exc:
        report.status = "failed"
        report.phase = "回复失败"
        report.error_message = str(exc)
        report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from exc

    await _persist_assistant_answer(db, report, answer)

    messages = await get_report_messages(db, report.id, limit=100)
    from app.schemas.message import RagSource
    return ChatResponse(
        report_id=report.id,
        answer=answer,
        messages=[MessageResponse.model_validate(m) for m in messages],
        sources=[RagSource(**s) for s in rag_sources],
        intent_domain=intent_domain if intent_domain != "general" else None,
    )


@router.post("/regenerate", response_model=ChatResponse)
async def regenerate_plain_chat(
    data: ChatRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = (data.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="请输入问题")

    report = await db.get(Report, data.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="对话不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")

    user_message = await db.get(Message, data.message_id)
    if not user_message or user_message.report_id != report.id or user_message.role != "user":
        raise HTTPException(status_code=404, detail="用户消息不存在")

    user_message.content = prompt
    report.status = "running"
    report.progress = 0.2
    report.phase = "正在回复"
    report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        delete(Message).where(
            Message.report_id == report.id,
            Message.id > user_message.id,
        )
    )
    await db.commit()

    local_tool_answer = _answer_with_current_datetime_tool(prompt)
    if local_tool_answer:
        await _persist_assistant_answer(db, report, local_tool_answer)
        messages = await get_report_messages(db, report.id, limit=100)
        return ChatResponse(
            report_id=report.id,
            answer=local_tool_answer,
            messages=[MessageResponse.model_validate(m) for m in messages],
        )

    llm_messages, rag_sources, intent_domain = await _build_llm_messages(
        db, report, [], query=prompt,
        kb_ids=[], include_system_kb=True,
    )
    profile = await _selected_model_profile(db, data.model_id)
    try:
        with effort_context(data.effort):
            if profile:
                with selected_llm_profile(profile):
                    answer = await chat(llm_messages, temperature=0.35, max_tokens=1800)
            else:
                answer = await chat(llm_messages, temperature=0.35, max_tokens=1800)
    except Exception as exc:
        report.status = "failed"
        report.phase = "回复失败"
        report.error_message = str(exc)
        report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from exc

    await _persist_assistant_answer(db, report, answer)
    messages = await get_report_messages(db, report.id, limit=100)
    from app.schemas.message import RagSource
    return ChatResponse(
        report_id=report.id,
        answer=answer,
        messages=[MessageResponse.model_validate(m) for m in messages],
        sources=[RagSource(**s) for s in rag_sources],
        intent_domain=intent_domain if intent_domain != "general" else None,
    )


@router.post("/stream")
async def stream_plain_chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = (data.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="请输入问题")

    report = await _build_or_get_chat_report(db, current_user, data, prompt)
    uploaded_texts = []
    if data.uploaded_files:
        uploaded_texts = await _attach_uploaded_files(db, report, current_user.id, data.uploaded_files)
    await add_message(
        db,
        report.id,
        "user",
        prompt,
        author_id=str(current_user.id),
        author_name=current_user.username,
    )

    local_tool_answer = _answer_with_current_datetime_tool(prompt)
    if local_tool_answer:
        await _persist_assistant_answer(db, report, local_tool_answer)

        async def local_event_stream():
            yield _json_line({"type": "start", "report_id": report.id})
            yield _json_line({"type": "delta", "delta": local_tool_answer})
            yield _json_line({
                "type": "done",
                "report_id": report.id,
                "answer": local_tool_answer,
            })

        return StreamingResponse(
            local_event_stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    llm_messages, rag_sources, intent_domain = await _build_llm_messages(
        db, report, uploaded_texts,
        kb_ids=data.kb_ids, include_system_kb=data.include_system_kb, query=prompt,
    )
    profile = await _selected_model_profile(db, data.model_id)

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        answer_holder = {"text": ""}

        async def on_token(delta: str, accumulated: str):
            answer_holder["text"] = accumulated
            await queue.put({"type": "delta", "delta": delta})

        async def run_model():
            try:
                with effort_context(data.effort):
                    if profile:
                        with selected_llm_profile(profile):
                            answer = await chat_stream(llm_messages, temperature=0.35, max_tokens=1800, on_token=on_token)
                    else:
                        answer = await chat_stream(llm_messages, temperature=0.35, max_tokens=1800, on_token=on_token)
                answer_holder["text"] = answer
                async with async_session() as write_db:
                    write_report = await write_db.get(Report, report.id)
                    if not write_report:
                        raise RuntimeError("对话已不存在")
                    await add_message(
                        write_db,
                        report.id,
                        "assistant",
                        answer,
                        author_id="dataagent",
                        author_name="DataAgent",
                    )
                    write_report.status = "completed"
                    write_report.progress = 1.0
                    write_report.phase = "已回复"
                    write_report.brief = answer
                    write_report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await write_db.commit()
                # Only send a lightweight done signal; the frontend fetches
                # messages via a separate GET to avoid large JSON payloads
                # that can cause mid-stream connection drops.
                await queue.put({
                    "type": "done",
                    "report_id": report.id,
                    "answer": answer,
                    "sources": rag_sources,
                    "intent_domain": intent_domain if intent_domain != "general" else None,
                })
            except Exception as exc:
                async with async_session() as write_db:
                    write_report = await write_db.get(Report, report.id)
                    if write_report:
                        write_report.status = "failed"
                        write_report.phase = "回复失败"
                        write_report.error_message = str(exc)
                        write_report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                        await write_db.commit()
                await queue.put({"type": "error", "detail": f"模型调用失败：{exc}"})
            finally:
                await queue.put(None)

        yield _json_line({"type": "start", "report_id": report.id})
        task = asyncio.create_task(run_model())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=12)
                except asyncio.TimeoutError:
                    yield _json_line({"type": "heartbeat"})
                    continue
                if item is None:
                    break
                yield _json_line(item)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/execute")
async def execute_chat_code(
    data: CodeExecuteRequest,
    current_user: User = Depends(get_current_user),
):
    language = (data.language or "python").strip().lower()
    code = (data.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="请输入要执行的代码")
    if language not in {"python", "py"}:
        raise HTTPException(status_code=400, detail="当前后端执行仅支持 Python")

    result = await execute_python(code, timeout=10)
    return {
        "ok": not bool(result.get("error")),
        "stdout": result.get("stdout") or "",
        "stderr": result.get("stderr") or "",
        "error": result.get("error"),
        "variables": result.get("variables") or {},
        "figures": result.get("figures") or [],
        "exec_ms": result.get("exec_ms") or 0,
    }
