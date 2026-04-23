"""
ExecutionState — the global shared-memory bus that threads through the entire
4-phase production pipeline:

  Phase 1  Planning         intake_officer   → execution_plan
  Phase 2  Data Gathering   data_wrangler    → data_context   (via sandbox)
  Phase 3  Synthesis        structured_writer → section_drafts
  Phase 4  QA + Deliver     qa_reviewer       → final sections + trace_log

v2 升级：
  - steering_instructions: Supervisor 可在生产中途向某个 section 注入修正指令
  - task_id_map: step_id → SubagentManager task_id，供 API 层查询 / steer
  - section_locks: 每个 section 的 asyncio.Lock，防止并行写入竞争
  - parallel_section_results: 并行合成阶段的中间产出暂存区

Every agent reads & writes to a single ExecutionState instance that lives in
memory for the duration of one report's production run.  After delivery it is
serialised to the Report.trace_log JSON column for audit.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Execution Plan Step
# ---------------------------------------------------------------------------

@dataclass
class PlanStep:
    """One concrete step in the plan produced by the Requirement Analyst."""
    step_id: str
    phase: str          # "data" | "synthesis" | "qa"
    description: str    # human-readable
    employee_id: str    # who should execute this
    depends_on: List[str] = field(default_factory=list)   # step_ids
    status: str = "pending"   # pending | running | done | skipped | error
    result_key: Optional[str] = None  # key in data_context / section_outputs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "phase": self.phase,
            "description": self.description,
            "employee_id": self.employee_id,
            "depends_on": self.depends_on,
            "status": self.status,
            "result_key": self.result_key,
        }


# ---------------------------------------------------------------------------
# TraceEntry — one action recorded for audit
# ---------------------------------------------------------------------------

@dataclass
class TraceEntry:
    """Immutable record of a single agent action."""
    ts: float               # unix timestamp
    agent_id: str
    action: str             # "llm_call" | "code_exec" | "security_scan" | "qa_check" | "retry"
    input_summary: str
    output_summary: str
    code: Optional[str] = None           # if action == "code_exec"
    code_result: Optional[str] = None    # stdout from sandbox
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "agent_id": self.agent_id,
            "action": self.action,
            "input_summary": self.input_summary[:400],
            "output_summary": self.output_summary[:400],
            "code": self.code,
            "code_result": (self.code_result or "")[:1000],
            "error": self.error,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# ExecutionState — the single shared bus
# ---------------------------------------------------------------------------

class ExecutionState:
    """Mutable shared state threaded through all pipeline phases."""

    def __init__(self, report_id: int, brief: str, report_type: str):
        self.report_id = report_id
        self.brief = brief
        self.report_type = report_type

        # Phase 1 output
        self.execution_plan: List[PlanStep] = []

        # Phase 2 output: accumulated "clean metrics"
        # Keys are metric names (e.g. "total_revenue", "q1_net_profit")
        # Values are dicts: {value, unit, source_file, code_verified: bool}
        self.data_context: Dict[str, Any] = {}

        # Phase 3 output: section_id → draft markdown
        self.section_drafts: Dict[str, str] = {}

        # Phase 4 output: section_id → verified markdown
        self.section_finals: Dict[str, str] = {}

        # QA flags: section_id → list of {claim, expected, found, passed}
        self.qa_flags: Dict[str, List[Dict[str, Any]]] = {}

        # Full audit trail
        self.trace: List[TraceEntry] = []

        # Security clearance marks: key → "pass" | "blocked"
        self.security_marks: Dict[str, str] = {}

        self.started_at = time.time()
        self.phase = "planning"

        # ---- v2 Async State Machine 扩展 --------------------------------

        # Supervisor 中途注入的 steering 指令：section_id → instruction
        # Employee 在开始写作前检查此字典，若有指令则附加到 prompt
        self.steering_instructions: Dict[str, str] = {}

        # step_id / section_id → SubagentManager task_id
        # 供 API 层通过 /subagents/{task_id}/steer 端点查询和控制
        self.task_id_map: Dict[str, str] = {}

        # 每个 section 的写锁，防止并行阶段写竞争
        self._section_locks: Dict[str, asyncio.Lock] = {}

        # 并行 Phase 3 的中间产出暂存（汇入 section_drafts 前的缓冲）
        self.parallel_section_results: Dict[str, Any] = {}

        # 取消信号：置为 True 时所有 phase 应尽快退出
        self.cancelled: bool = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record(
        self,
        agent_id: str,
        action: str,
        input_summary: str,
        output_summary: str,
        code: Optional[str] = None,
        code_result: Optional[str] = None,
        error: Optional[str] = None,
        **meta: Any,
    ) -> None:
        self.trace.append(TraceEntry(
            ts=time.time(),
            agent_id=agent_id,
            action=action,
            input_summary=input_summary,
            output_summary=output_summary,
            code=code,
            code_result=code_result,
            error=error,
            metadata=meta,
        ))

    def store_metric(
        self,
        key: str,
        value: Any,
        unit: str = "",
        source: str = "",
        code_verified: bool = False,
    ) -> None:
        self.data_context[key] = {
            "value": value,
            "unit": unit,
            "source": source,
            "code_verified": code_verified,
        }

    def mark_security(self, key: str, verdict: str) -> None:
        self.security_marks[key] = verdict

    # ---- v2 Steering helpers -------------------------------------------

    def inject_steering(self, section_id: str, instruction: str) -> None:
        """Supervisor 向某个 section 注入 mid-flight 修正指令。"""
        existing = self.steering_instructions.get(section_id, "")
        if existing:
            self.steering_instructions[section_id] = existing + "\n" + instruction
        else:
            self.steering_instructions[section_id] = instruction

    def pop_steering(self, section_id: str) -> Optional[str]:
        """Employee 在执行前消费 steering 指令（一次性读取并清除）。"""
        return self.steering_instructions.pop(section_id, None)

    def register_task_id(self, step_id: str, task_id: str) -> None:
        self.task_id_map[step_id] = task_id

    def section_lock(self, section_id: str) -> asyncio.Lock:
        """获取或创建该 section 的写锁。"""
        if section_id not in self._section_locks:
            self._section_locks[section_id] = asyncio.Lock()
        return self._section_locks[section_id]

    def all_metrics_summary(self) -> str:
        """Human-readable summary of data_context for prompts."""
        lines = []
        for k, v in self.data_context.items():
            val = v.get("value", "")
            unit = v.get("unit", "")
            src = v.get("source", "")
            verified = "✓" if v.get("code_verified") else "~"
            lines.append(f"  {verified} {k}: {val}{unit}  [{src}]")
        return "\n".join(lines) if lines else "（无已验证的数据）"

    def serialise(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dict for DB persistence."""
        return {
            "report_id": self.report_id,
            "brief": self.brief[:200],
            "report_type": self.report_type,
            "execution_plan": [s.to_dict() for s in self.execution_plan],
            "data_context": self.data_context,
            "section_drafts_count": len(self.section_drafts),
            "section_finals_count": len(self.section_finals),
            "qa_flags": self.qa_flags,
            "security_marks": self.security_marks,
            "trace": [t.to_dict() for t in self.trace],
            "elapsed_s": round(time.time() - self.started_at, 1),
            # v2
            "task_id_map": self.task_id_map,
            "parallel_sections": len(self.parallel_section_results),
        }
