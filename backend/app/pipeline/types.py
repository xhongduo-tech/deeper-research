"""Core types and utilities shared across all pipeline phases."""
from __future__ import annotations

import re
import time as _time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.report import Report


# ── Errors ──────────────────────────────────────────────────────────────────

@dataclass
class PipelineError(Exception):
    """Raised by any pipeline phase to signal an unrecoverable failure."""
    phase: str
    message: str
    section_id: Optional[str] = None

    def __str__(self) -> str:
        if self.section_id:
            return f"[{self.phase}/{self.section_id}] {self.message}"
        return f"[{self.phase}] {self.message}"


# ── Agent contracts ──────────────────────────────────────────────────────────

@dataclass
class AgentTask:
    task_id: str
    task_type: str
    inputs: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    task_id: str
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Pipeline context ─────────────────────────────────────────────────────────

class PipelineContext:
    """Shared state container threaded through all pipeline phases."""

    def __init__(
        self,
        report: "Report",
        db: "AsyncSession",
        uploaded_texts: list[str] | None = None,
        kb_ids: list[int] | None = None,
        skills: list[str] | None = None,
        skip_clarify: bool = False,
        progress_callback: Callable | None = None,
    ):
        self.report = report
        self.db = db
        self.uploaded_texts = uploaded_texts or []
        self.kb_ids = kb_ids or []
        self.skills = skills or []
        self.skip_clarify = skip_clarify
        self.progress_callback = progress_callback

        # Populated by phases as they run
        self.brief: str = report.brief
        self.output_format: str = (report.output_format or "word").lower()
        self.report_type: str = report.report_type or "经营分析"

        self.understanding: dict[str, Any] = {}   # UNDERSTAND output
        self.outline: dict[str, Any] = {}          # PLAN output
        self.research_findings: dict[str, str] = {}  # RESEARCH output: section_id → evidence
        self.spec: Any = None                      # SPEC_GEN output: DocumentSpec instance
        self.rendered_bytes: bytes | None = None   # DOC_RENDER output
        self.rendered_ext: str = "docx"            # file extension
        self.completed_with_warnings: bool = False  # P2-5: set True when sections degrade

        # ── LLM-OS 扩展字段 ────────────────────────────────────────────────────
        self.intent: Any = None                    # RoutedIntent（知识三角路由结果）
        self.ingress_assets: list[Any] = []        # ParsedAsset 列表（Ingress 解析输出）
        self.vfs_tree: str = ""                    # VFS 目录树文本
        self.duckdb_session_id: str = ""           # DuckDB 会话 ID
        self.duckdb_schema: str = ""               # 已注册的表 Schema 摘要
        self.triad_result: Any = None              # TriadResult（三角检索结果）
        self.template_meta: Any = None             # TemplateMeta（模板占位符信息）
        self.widget_html_blocks: list[str] = []    # 动态 Widget HTML 块
        # ── R18-OBS: Structured event log ─────────────────────────────────────
        self._event_log: list[dict[str, Any]] = []
        self._start_ts: float = _time.time()

    def log_event(self, phase: str, event: str, **data: Any) -> None:
        """Record a structured pipeline event (phase transitions, retries, QA results, etc.)."""
        self._event_log.append({
            "phase": phase,
            "event": event,
            "elapsed_s": round(_time.time() - self._start_ts, 2),
            **data,
        })

    @classmethod
    async def build(
        cls,
        report: "Report",
        db: "AsyncSession",
        uploaded_texts: list[str] | None = None,
        kb_ids: list[int] | None = None,
        skills: list[str] | None = None,
        skip_clarify: bool = False,
        progress_callback: Callable | None = None,
    ) -> "PipelineContext":
        ctx = cls(report, db, uploaded_texts, kb_ids, skills, skip_clarify, progress_callback)
        return ctx


# ── Content quality helpers ─────────────────────────────────────────────────

_PLACEHOLDER_PATTERNS = [
    r"\[.*?(待|补充|placeholder|todo|tbd|内容|此处|这里).*?\]",
    r"(?:此处|这里|这里写|请补充|待补充|待填写|TODO|TBD|placeholder)",
]
_PLACEHOLDER_RE = re.compile("|".join(_PLACEHOLDER_PATTERNS), re.IGNORECASE)

_MINIMUM_CHARS = 150  # below this, definitely placeholder (raised from 60)


def is_placeholder_content(text: str) -> bool:
    """Return True if the text is clearly a placeholder / empty shell."""
    if not text or len(text.strip()) < _MINIMUM_CHARS:
        return True
    return bool(_PLACEHOLDER_RE.search(text))


def is_poor_quality_content(text: str, target_chars: int = 400) -> bool:
    """Return True if the text is too short relative to the target."""
    actual = len(re.sub(r"\s+", "", text))
    return actual < max(target_chars * 0.35, _MINIMUM_CHARS)


def clean_generated_content(text: str) -> str:
    """Strip LLM meta-commentary artefacts from generated text."""
    if not text:
        return text
    # Remove leading apologies / acknowledgements
    text = re.sub(
        r"^(好的[，,。！]?|明白了[，,。！]?|当然[，,。！]?|以下是|下面是|如下[：:])\s*",
        "", text, flags=re.MULTILINE,
    )
    # Remove trailing "如有需要…" filler
    text = re.sub(
        r"\n*(如有.*?需要.*?[。！\n]|以上.*?供参考.*?[。！\n]|希望.*?有所帮助.*?[。！\n])$",
        "", text.rstrip(),
    )
    return text.strip()
