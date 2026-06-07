"""HTML Report API — generates self-contained HTML files from research content."""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.services.html_generator import generate_html_report
from app.services.llm_service import chat
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/html", tags=["html"])


class HtmlGenerateRequest(BaseModel):
    prompt: str
    content: str = ""
    title: str = "DataAgent 报告"
    template_style: str = "report"   # dashboard | report | minimal | vivid
    tags: Optional[list[str]] = None
    kb_ids: list[int] = []
    include_system_kb: bool = False


@router.post("/generate")
async def generate_html(req: HtmlGenerateRequest):
    """Generate a self-contained HTML report from prompt + optional content."""
    # If content given, use it directly; otherwise ask LLM to generate
    if req.content.strip():
        final_content = req.content
    else:
        rag_context = ""
        if req.kb_ids or req.include_system_kb:
            from app.services.rag_service import search_kb
            from app.database import async_session
            async with async_session() as db:
                kb_ids = list(req.kb_ids)
                if req.include_system_kb:
                    from app.models.knowledge_base import KnowledgeBase
                    from sqlalchemy import select
                    system_kb_ids = (await db.execute(
                        select(KnowledgeBase.id).where(KnowledgeBase.scope == "corp")
                    )).scalars().all()
                    for kb_id in system_kb_ids:
                        if kb_id not in kb_ids:
                            kb_ids.append(kb_id)
                if kb_ids:
                    try:
                        results = await search_kb(db, kb_ids=kb_ids, query=req.prompt, top_k=6, score_threshold=0.15)
                        if results:
                            snippets = []
                            for r in results:
                                content = r.get("content", "")
                                source = r.get("source", "未知来源")
                                if content:
                                    snippets.append(f"【{source}】{content[:400]}")
                            rag_context = "\n\n".join(snippets)
                    except Exception:
                        pass

        messages = [
            {
                "role": "system",
                "content": "你是专业内容撰写专家。根据用户描述，生成结构清晰的 Markdown 格式内容，包含标题、段落、列表和关键数据。",
            },
        ]
        if rag_context:
            messages.append({
                "role": "system",
                "content": "以下是从知识库中检索到的相关上下文，请优先依据这些内容回答：\n\n" + rag_context[:10000],
            })
        messages.append({
            "role": "user",
            "content": f"请根据以下需求生成网页内容（Markdown格式，500-1000字）：\n\n{req.prompt}",
        })
        router_svc = get_model_router()
        model, base_url, api_key = router_svc.route_for_chat(agent_type="nova", messages=messages)
        final_content = await chat(
            messages, model=model, base_url=base_url, api_key=api_key,
            temperature=0.4, max_tokens=1500
        )

    html = generate_html_report(
        title=req.title,
        content=final_content,
        template_style=req.template_style,
        subtitle=req.prompt[:80] if req.prompt else "",
        tags=req.tags,
    )

    return {
        "html": html,
        "title": req.title,
        "template_style": req.template_style,
        "char_count": len(html),
    }
