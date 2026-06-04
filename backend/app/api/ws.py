import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.report import Report
from app.models.timeline_event import TimelineEvent

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory registry: report_id -> set of websockets
_connections: dict[int, set[WebSocket]] = {}


class WSEvent(BaseModel):
    """Structured WebSocket event envelope."""
    type: str
    timestamp: str
    payload: dict


def _decode_ws_token(token: str | None) -> int | None:
    """Decode JWT from WebSocket query param; return user_id or None on failure."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        uid = payload.get("sub")
        return int(uid) if uid is not None else None
    except (JWTError, ValueError):
        return None


@router.websocket("/ws/reports/{report_id}")
async def report_progress(websocket: WebSocket, report_id: int, token: str | None = None):
    user_id = _decode_ws_token(token)
    if user_id is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    if report_id not in _connections:
        _connections[report_id] = set()
    _connections[report_id].add(websocket)

    try:
        # Send current state on connect
        async with async_session() as db:
            result = await db.execute(select(Report).where(Report.id == report_id))
            report = result.scalar_one_or_none()
            if not report or report.user_id != user_id:
                await websocket.close(code=4403)
                _connections[report_id].discard(websocket)
                return
            if report:
                await _send_event(websocket, "research.status", {
                    "report_id": report_id,
                    "status": report.status,
                    "progress_pct": int(report.progress * 100),
                    "phase": report.phase,
                })

                # Send existing timeline
                timeline_result = await db.execute(
                    select(TimelineEvent)
                    .where(TimelineEvent.report_id == report_id)
                    .order_by(TimelineEvent.created_at)
                )
                for event in timeline_result.scalars().all():
                    await _send_event(websocket, "research.timeline", {
                        "event_type": event.event_type,
                        "label": event.label,
                        "payload": event.payload,
                        "created_at": event.created_at.isoformat() if event.created_at else None,
                    })

        # Keep connection alive, listen for client messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if report_id in _connections:
            _connections[report_id].discard(websocket)
            if not _connections[report_id]:
                del _connections[report_id]


async def _send_event(ws: WebSocket, event_type: str, payload: dict):
    """Send a single structured event to a websocket."""
    event = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    await ws.send_json(event)


async def broadcast_event(report_id: int, event_type: str, payload: dict):
    """Broadcast a structured event to all connected clients for a report."""
    if report_id not in _connections:
        return

    event = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    message = json.dumps(event)
    dead = set()

    for ws in _connections[report_id]:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)

    for ws in dead:
        _connections[report_id].discard(ws)


async def broadcast_progress(report_id: int, data: dict):
    """Legacy compatibility wrapper."""
    await broadcast_event(report_id, "research.progress", data)


# ── Swarm Events ──

async def broadcast_swarm_agent_spawned(report_id: int, agent_id: str, persona_id: str, name: str) -> None:
    await broadcast_event(report_id, "swarm.agent.spawned", {
        "agent_id": agent_id,
        "persona_id": persona_id,
        "name": name,
    })


async def broadcast_swarm_agent_status(report_id: int, agent_id: str, status: str, current_task_id: str | None = None) -> None:
    await broadcast_event(report_id, "swarm.agent.status", {
        "agent_id": agent_id,
        "status": status,
        "current_task_id": current_task_id,
    })


async def broadcast_swarm_task_added(report_id: int, task_id: str, query: str, agent_type: str, dependencies: list[str]) -> None:
    await broadcast_event(report_id, "swarm.task.added", {
        "task_id": task_id,
        "query": query,
        "agent_type": agent_type,
        "dependencies": dependencies,
    })


async def broadcast_swarm_task_started(report_id: int, task_id: str, agent_id: str) -> None:
    await broadcast_event(report_id, "swarm.task.started", {
        "task_id": task_id,
        "agent_id": agent_id,
    })


async def broadcast_swarm_task_completed(report_id: int, task_id: str, agent_id: str, summary: str = "") -> None:
    await broadcast_event(report_id, "swarm.task.completed", {
        "task_id": task_id,
        "agent_id": agent_id,
        "summary": summary,
    })


async def broadcast_swarm_task_failed(report_id: int, task_id: str, agent_id: str, error: str) -> None:
    await broadcast_event(report_id, "swarm.task.failed", {
        "task_id": task_id,
        "agent_id": agent_id,
        "error": error,
    })


async def broadcast_swarm_message(report_id: int, msg_id: str, from_agent: str, to_agent: str | None, topic: str, payload: dict) -> None:
    await broadcast_event(report_id, "swarm.agent.message", {
        "msg_id": msg_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "topic": topic,
        "payload": payload,
    })


async def broadcast_swarm_consensus(report_id: int, passed: bool, confidence: float, failed_tasks: list[str]) -> None:
    await broadcast_event(report_id, "swarm.consensus.result", {
        "passed": passed,
        "confidence": confidence,
        "failed_tasks": failed_tasks,
    })


# ── Document Intermediate Output Events ──

async def broadcast_section_draft(report_id: int, section_idx: int, title: str, content: str, word_count: int = 0) -> None:
    """Stream a section draft to frontend during writing phase."""
    await broadcast_event(report_id, "document.section.draft", {
        "section_idx": section_idx,
        "title": title,
        "content": content,
        "word_count": word_count,
    })


async def broadcast_section_reviewed(report_id: int, section_idx: int, title: str, score: int, verdict: str, issues: list[dict]) -> None:
    """Broadcast section review results."""
    await broadcast_event(report_id, "document.section.reviewed", {
        "section_idx": section_idx,
        "title": title,
        "score": score,
        "verdict": verdict,
        "issues": issues,
    })


async def broadcast_citation_verified(report_id: int, verified_count: int, unverified_count: int, missing_count: int) -> None:
    """Broadcast citation verification results."""
    await broadcast_event(report_id, "document.citation.verified", {
        "verified_count": verified_count,
        "unverified_count": unverified_count,
        "missing_count": missing_count,
    })


async def broadcast_interactive_prompt(report_id: int, prompt_type: str, question: str, options: list[str] | None = None) -> None:
    """Request user input/confirmation during report generation."""
    await broadcast_event(report_id, "document.interactive.prompt", {
        "prompt_type": prompt_type,
        "question": question,
        "options": options or [],
    })


async def broadcast_chart_figures(
    report_id: int,
    figures: list[dict],
    skill_name: str = "",
    task_id: str = "",
    insight: str = "",
) -> None:
    """Broadcast Python-rendered chart figures (base64 PNG) to the frontend.

    Each figure: {"format": "png", "base64": "<b64>", "size_kb": N}
    Fires whenever DataAnalyzerSkill / PythonChartSkill produces figures.
    """
    if not figures:
        return
    await broadcast_event(report_id, "analysis.figures", {
        "figures": figures,           # list of base64 PNGs
        "skill_name": skill_name,     # which skill produced them
        "task_id": task_id,           # which research sub-task
        "insight": insight,           # LLM-generated description
        "count": len(figures),
    })


async def broadcast_critical_path(report_id: int, critical_length: int, total_tasks: int, efficiency: float, suggestions: list[str]) -> None:
    """Broadcast critical path analysis for the task graph."""
    await broadcast_event(report_id, "swarm.critical_path", {
        "critical_path_length": critical_length,
        "total_tasks": total_tasks,
        "parallel_efficiency": round(efficiency, 2),
        "bottleneck_tasks": suggestions,
    })


# ── SOTA Algorithm Events ──

async def broadcast_pipeline_routed(
    report_id: int,
    format_track: str,
    track_label: str,
    algo_chain: str,
    complexity_label: str,
) -> None:
    """Broadcast format track detection and SOTA algorithm chain selection."""
    await broadcast_event(report_id, "sota.pipeline_routed", {
        "format_track": format_track,
        "track_label": track_label,
        "algo_chain": algo_chain,
        "complexity_label": complexity_label,
    })


async def broadcast_sota_pmrc(
    report_id: int,
    narrative_type: str,
    slide_count: int,
    story_thread: str,
    opening_hook: str = "",
) -> None:
    """Broadcast PMRC narrative restructuring completion."""
    await broadcast_event(report_id, "sota.pmrc_complete", {
        "narrative_type": narrative_type,
        "slide_count": slide_count,
        "story_thread": story_thread,
        "opening_hook": opening_hook,
    })


async def broadcast_sota_decrim_start(
    report_id: int,
    constraint_count: int,
) -> None:
    """Broadcast DECRIM critique-refine loop start."""
    await broadcast_event(report_id, "sota.decrim_start", {
        "constraint_count": constraint_count,
    })


async def broadcast_sota_decrim_complete(
    report_id: int,
    initial_score: float,
    final_score: float,
    iterations: int,
    improvements: list[str],
) -> None:
    """Broadcast DECRIM critique-refine loop completion with score delta."""
    await broadcast_event(report_id, "sota.decrim_complete", {
        "initial_score": round(initial_score, 1),
        "final_score": round(final_score, 1),
        "iterations": iterations,
        "improvements": improvements[:4],
        "delta": round(final_score - initial_score, 1),
    })


# ── Thinking & Tool Events ──

async def broadcast_thinking(report_id: int, phase: str, content: str) -> None:
    """Stream a Kimi-style collapsible thinking block to the frontend."""
    await broadcast_event(report_id, "thinking.block", {
        "phase": phase,
        "content": content,
    })


async def broadcast_tool_file_read(report_id: int, path: str, label: str, content_preview: str = "") -> None:
    """Broadcast a file-read tool-call event (clickable row in the thought stream)."""
    await broadcast_event(report_id, "tool.file_read", {
        "path": path,
        "label": label,
        "content_preview": content_preview,
    })


# ── Token Streaming Events ──

async def broadcast_token_delta(
    report_id: int,
    section_idx: int,
    delta: str,
    accumulated_len: int,
) -> None:
    """Stream a partial token chunk during section generation.

    Emitted by chat_stream callbacks. Frontend appends to active section card
    for typewriter effect; reduces perceived latency dramatically.
    """
    await broadcast_event(report_id, "llm.token_delta", {
        "section_idx": section_idx,
        "delta": delta,
        "accumulated_len": accumulated_len,
    })


async def broadcast_llm_first_token(
    report_id: int,
    section_idx: int,
    latency_ms: int,
    model: str = "",
) -> None:
    """Broadcast time-to-first-token for observability."""
    await broadcast_event(report_id, "llm.first_token", {
        "section_idx": section_idx,
        "latency_ms": latency_ms,
        "model": model,
    })


# ── Tool & Retrieval Tracing Events ──

async def broadcast_rag_query(
    report_id: int,
    query: str,
    section_id: str = "",
    top_k: int = 0,
    method: str = "hybrid",
) -> None:
    """Trace a single RAG query — query text, target section, retrieval method.

    Frontend shows as inline 🔍 chip in the activity feed (matches Perplexity's
    'Searching for X...' UX).
    """
    await broadcast_event(report_id, "tool.rag_query", {
        "query": query[:200],
        "section_id": section_id,
        "top_k": top_k,
        "method": method,
    })


async def broadcast_rag_result(
    report_id: int,
    query_id: str,
    chunks_found: int,
    top_score: float = 0.0,
    sources: list[str] | None = None,
) -> None:
    """Broadcast RAG retrieval results — counts + top sources."""
    await broadcast_event(report_id, "tool.rag_result", {
        "query_id": query_id,
        "chunks_found": chunks_found,
        "top_score": round(top_score, 3),
        "sources": (sources or [])[:5],
    })


# ── Claim Grounding Events ──

async def broadcast_claim_extracted(
    report_id: int,
    section_id: str,
    total_claims: int,
    numeric_claims: int,
    categorical_claims: int = 0,
) -> None:
    """Broadcast claim extraction phase — how many factual claims need grounding."""
    await broadcast_event(report_id, "grounding.claims_extracted", {
        "section_id": section_id,
        "total_claims": total_claims,
        "numeric_claims": numeric_claims,
        "categorical_claims": categorical_claims,
    })


async def broadcast_grounding_check(
    report_id: int,
    section_id: str,
    grounded_count: int,
    ungrounded_count: int,
    confidence: float,
    ungrounded_samples: list[str] | None = None,
) -> None:
    """Broadcast post-generation grounding verdict for a section.

    Frontend shows pass/fail badge with the % of claims that mapped to evidence.
    """
    await broadcast_event(report_id, "grounding.section_verified", {
        "section_id": section_id,
        "grounded_count": grounded_count,
        "ungrounded_count": ungrounded_count,
        "confidence": round(confidence, 2),
        "ungrounded_samples": (ungrounded_samples or [])[:3],
    })


async def broadcast_refinement_loop(
    report_id: int,
    section_id: str,
    iteration: int,
    refinement_queries: list[str],
    new_evidence_chunks: int,
) -> None:
    """Broadcast retrieval refinement iteration — what new queries ran and what came back."""
    await broadcast_event(report_id, "grounding.refinement", {
        "section_id": section_id,
        "iteration": iteration,
        "refinement_queries": (refinement_queries or [])[:4],
        "new_evidence_chunks": new_evidence_chunks,
    })


# ── Official Database Query Events ──

async def broadcast_db_query_start(report_id: int, source_key: str, source_name: str, query: str) -> None:
    """Broadcast the start of an official data source query."""
    await broadcast_event(report_id, "db.query.start", {
        "source_key": source_key,
        "source_name": source_name,
        "query": query,
    })


async def broadcast_db_query_result(
    report_id: int,
    source_key: str,
    source_name: str,
    result_type: str,
    data: dict,
    row_count: int = 0,
) -> None:
    """Broadcast a successful official data source query result."""
    await broadcast_event(report_id, "db.query.result", {
        "source_key": source_key,
        "source_name": source_name,
        "result_type": result_type,
        "data": data,
        "row_count": row_count,
    })


async def broadcast_db_query_error(report_id: int, source_key: str, source_name: str, error: str) -> None:
    """Broadcast an official data source query failure."""
    await broadcast_event(report_id, "db.query.error", {
        "source_key": source_key,
        "source_name": source_name,
        "error": error,
    })
