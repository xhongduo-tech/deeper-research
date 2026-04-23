"""
SupervisorService — the Chief's brain.

Responsibilities:
  - on_report_created: greet, do LLM-assisted scoping (tailored team + outline
    + 2-4 targeted clarifications with safe defaults), post structured
    messages and timeline events.
  - on_user_reply / on_user_interject: acknowledge and — when appropriate —
    forward the content into the in-flight production context.
  - start_production: background orchestration across scoping → producing →
    reviewing → delivered.

Everything tolerates LLM failures: if the model is unreachable (offline
intranet demo, misconfigured key, timeout) the service degrades to the
deterministic defaults baked into the report-type registry, so the UI still
shows a coherent end-to-end flow.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.employees.registry import (
    EMPLOYEES,
    SUPERVISOR,
    get_employee,
)
from app.agents.employees.runner import (
    EmployeeRunner,
    RunContext,
    SectionTask,
    pick_employee_for_section,
)
from app.database import AsyncSessionLocal
from app.models.report import Report, ReportStatus
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.llm_service import LLMService
from app.services.report_service import (
    ClarificationService,
    EvidenceService,
    MessageService,
    ReportService,
    TimelineService,
)
from app.services.report_types import get_report_type

logger = logging.getLogger(__name__)


# Hard bounds to keep prompt size + UI noise tame.
_MAX_CLARIFICATIONS = 4
_MAX_SECTIONS = 9
_DOC_EXCERPT_CHARS = 1800

# ---------------------------------------------------------------------------
# Active ExecutionState registry — 供 API 层通过 report_id 查询 / steer
# ---------------------------------------------------------------------------
_ACTIVE_STATES: Dict[int, Any] = {}


def _get_active_state(report_id: int) -> Optional[Any]:
    """返回正在运行的 report 的 ExecutionState，若不存在返回 None。"""
    return _ACTIVE_STATES.get(report_id)


def _register_state(report_id: int, state: Any) -> None:
    _ACTIVE_STATES[report_id] = state


def _deregister_state(report_id: int) -> None:
    _ACTIVE_STATES.pop(report_id, None)


class SupervisorService:
    # ------------------------------------------------------------------
    # Entry points called by the API layer
    # ------------------------------------------------------------------

    @classmethod
    async def on_report_created(
        cls,
        db: AsyncSession,
        report: Report,
        *,
        skip_clarifications: bool = False,
    ) -> None:
        from app.services.report_types import resolve_report_type
        rt = (await resolve_report_type(db, report.report_type)) or {}
        rt_label = rt.get("label", "专项报告")

        await ReportService.update_status(
            db, report,
            status=ReportStatus.intake.value,
            phase="intake",
            progress=0.05,
        )

        # Build the task knowledge base from uploaded files. This is also the
        # moment we persist Evidence rows — all downstream steps read from
        # Evidence rather than reading raw files again.
        kb = await cls._build_kb(db, report.id)
        digests = await cls._document_digests(db, report.id, kb=kb)

        # Try to LLM-plan; fall back to registry defaults.
        plan = await cls._plan_with_llm(report, rt, digests)
        outline = plan["outline"]
        team = plan["team"]
        clarifications = plan["clarifications"]
        opening = plan["opening"]

        await ReportService.save_scoping_plan(
            db, report,
            plan={
                "source": plan["source"],
                "rationale": plan.get("rationale", ""),
                "digest_count": len(digests),
            },
            outline=outline,
            team=team,
        )

        team_names = ", ".join(
            get_employee(eid)["first_name_en"]
            for eid in team
            if get_employee(eid)
        ) or "待定"

        await MessageService.append(
            db,
            report_id=report.id,
            role="supervisor_say",
            author_id=SUPERVISOR["id"],
            author_name=SUPERVISOR["first_name_en"],
            content=opening
            or (
                f"我收到你的请求:**{report.title}**({rt_label})。"
                f"初步阵容:{team_names}。"
            ),
            meta={"team": team, "plan_source": plan["source"]},
        )

        await TimelineService.append(
            db, report_id=report.id,
            event_type="phase_enter", label="进入需求确认阶段",
            payload={"phase": "intake", "plan_source": plan["source"]},
        )

        if clarifications:
            clar_rows = await ClarificationService.create_many(
                db, report_id=report.id, items=clarifications,
            )
            if skip_clarifications:
                # Auto-answer every question with its default — no UI ping-pong.
                for c in clar_rows or []:
                    try:
                        await ClarificationService.answer(
                            db, c, answer=None, use_default=True,
                        )
                    except Exception:
                        logger.exception(
                            "Auto-default clarification failed for %s", c.id
                        )
                await MessageService.append(
                    db,
                    report_id=report.id,
                    role="supervisor_say",
                    author_id=SUPERVISOR["id"],
                    author_name=SUPERVISOR["first_name_en"],
                    content=(
                        f"依据调用方要求，已跳过确认环节，"
                        f"为 {len(clarifications)} 条关键问题直接采纳默认答案，准备开工。"
                    ),
                    meta={
                        "clarification_count": len(clarifications),
                        "auto_defaulted": True,
                    },
                )
            else:
                await MessageService.append(
                    db,
                    report_id=report.id,
                    role="supervisor_ask",
                    author_id=SUPERVISOR["id"],
                    author_name=SUPERVISOR["first_name_en"],
                    content=(
                        "以下问题请你确认或直接采用默认,"
                        "我可以先按默认开工,你中途随时插话改。"
                    ),
                    meta={"clarification_count": len(clarifications)},
                )

    @classmethod
    async def on_user_reply(
        cls, db: AsyncSession, report: Report, content: str
    ) -> None:
        await MessageService.append(
            db, report_id=report.id, role="user_reply", content=content,
        )
        # Keep the in-prod ack short & deterministic — we don't block the
        # producing phase on this; the content is already persisted and
        # future section runs will see it via the report brief + messages.
        await MessageService.append(
            db, report_id=report.id,
            role="supervisor_say",
            author_id=SUPERVISOR["id"],
            author_name=SUPERVISOR["first_name_en"],
            content="收到,我把这条纳入当前计划,相关同事会在下一轮产出里体现。",
        )

    @classmethod
    async def on_user_interject(
        cls, db: AsyncSession, report: Report, content: str
    ) -> None:
        await MessageService.append(
            db, report_id=report.id, role="user_interject", content=content,
        )
        await MessageService.append(
            db, report_id=report.id,
            role="supervisor_say",
            author_id=SUPERVISOR["id"],
            author_name=SUPERVISOR["first_name_en"],
            content="好,我让当前正在产出的同事按这条指示调整当前章节。",
        )

    @classmethod
    async def start_production(cls, report_id: int) -> None:
        """Kick off production in the background — runs in its own session
        so it outlives the HTTP request lifecycle."""
        asyncio.create_task(cls._run_production(report_id))

    # ------------------------------------------------------------------
    # Scoping (LLM-assisted; falls back to registry defaults)
    # ------------------------------------------------------------------

    @classmethod
    async def _plan_with_llm(
        cls,
        report: Report,
        rt: Dict[str, Any],
        digests: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        default_team: List[str] = list(rt.get("default_team") or [])
        default_outline: List[Dict[str, Any]] = list(rt.get("section_skeleton") or [])
        default_plan = {
            "source": "defaults",
            "outline": default_outline,
            "team": default_team,
            "clarifications": cls._default_clarifications(report),
            "opening": None,
            "rationale": "使用报告类型默认阵容与章节骨架",
        }

        # Build the scoping prompt
        roster_desc = "\n".join(
            f"- {e['id']} · {e['first_name_en']} ({e['role_title_en']}) — {e['tagline_en']}"
            for e in EMPLOYEES
        )
        rt_default_team = "、".join(default_team) or "无默认"
        rt_outline_txt = "\n".join(
            f"- {s['id']} · {s['title']}({s['kind']})" for s in default_outline
        ) or "无默认章节"

        docs_block = ""
        if digests:
            docs_block = "\n\n用户上传材料摘要:\n" + "\n".join(
                f"## {d['name']}\n{d['excerpt']}" for d in digests
            )

        auto_detect_instruction = (
            "## 自动识别报告类型\n"
            "根据用户的 brief 和上传材料，自动判断最适合的报告类型，并在 opening 中说明识别出的类型及理由：\n"
            "- ops_review：运营/业务/绩效述职、经营分析\n"
            "- internal_research：内部专题研究、调研报告\n"
            "- risk_assessment：风险评估、合规检查\n"
            "- regulatory_filing：监管报送、格式化填报\n"
            "- training_material：培训资料、知识整理\n\n"
            if report.report_type == "internal_research"
            else ""
        )
        sys_prompt = (
            "你是 Chief(Production Supervisor),负责为一份内部报告拟定作战计划。\n"
            "你必须基于用户提供的 brief 与上传材料挑选员工与章节,不要假装联网。\n\n"
            + auto_detect_instruction
            + "## 员工与章节类型对应规则（必须遵守）\n"
            "- narrative（叙事段落）→ 分配给 structured_writer\n"
            "- narrative_with_chart（叙事+图表）→ 分配给 chart_maker（需数据时也纳入 data_wrangler）\n"
            "- table_with_narrative（表格+解读）→ 分配给 data_wrangler\n"
            "- matrix（风险矩阵）→ 分配给 risk_auditor\n"
            "- evidence_list（证据摘录）→ 分配给 material_analyst\n"
            "- template_driven（模板填写）→ 分配给 template_filler\n"
            "- qa_list（问答检核）→ 分配给 qa_reviewer 或 compliance_checker\n"
            "每份报告必须根据内容使用 **2~4 种不同章节类型**，让不同员工各司其职。\n\n"
            "## 信息缺口检测规则（高优先级）\n"
            "在分析用户需求和上传材料时，主动检测以下情况并列为高优先级澄清问题：\n"
            "- 报告要描述某时期的结果，但用户没有上传该时期的数据文件\n"
            "- 报告涉及对比分析，但只有一方的数据\n"
            "- 要生成未来计划/总结，但只有历史数据没有新的目标/计划文档\n"
            "- 关键数字、时间范围、主体名称不明确\n"
            "此类缺口问题的 priority 设为 'high'，其余问题设为 'medium' 或 'low'。\n\n"
            "## 输出格式（严格 JSON，不要代码围栏）\n"
            '{\n'
            '  "opening": "<一句话开场白，面向用户，中文，指出已理解的任务+初步阵容>",\n'
            '  "team": ["<employee_id>", ...],\n'
            '  "outline": [{"id":"<唯一短id>","title":"<中文标题>","kind":"<narrative|narrative_with_chart|table_with_narrative|matrix|qa_list|evidence_list|template_driven>","assigned_to":"<employee_id>"}],\n'
            '  "clarifications": [{"question":"<关键问题>","default_answer":"<合理默认>","priority":"<high|medium|low>","reason":"<为什么要问>"}],\n'
            '  "rationale": "<内部备注>"\n'
            "}\n\n"
            f"硬性约束:\n"
            f"- team 只能从给定 roster 里选\n"
            f"- 章节不超过 {_MAX_SECTIONS} 个\n"
            f"- clarifications 不超过 {_MAX_CLARIFICATIONS} 条，每条必须有 default_answer 和 priority\n"
            f"- 若检测到明显信息缺口（如缺少关键数据文件），必须设为 high priority 并明确说明\n"
            f"- 不同章节尽量分配给不同员工，避免全部分给 structured_writer"
        )

        user_prompt = (
            f"# 报告\n"
            f"- 标题:{report.title}\n"
            f"- 类型:{rt.get('label','未知')}({report.report_type})\n"
            f"- 用户诉求:\n{report.brief.strip()}\n\n"
            f"# 可用员工 (roster)\n{roster_desc}\n\n"
            f"# 报告类型默认阵容\n{rt_default_team}\n\n"
            f"# 报告类型默认章节\n{rt_outline_txt}"
            f"{docs_block}"
        )

        try:
            llm = LLMService()
            raw = await asyncio.wait_for(
                llm.chat(
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1400,
                ),
                timeout=45.0,
            )
        except Exception as e:
            logger.warning("Supervisor scoping LLM failed: %s", e)
            return default_plan

        parsed = cls._parse_scoping_json(raw)
        if not parsed:
            return default_plan

        # Sanitize: drop unknown employees, clamp list lengths, backfill.
        valid_ids = {e["id"] for e in EMPLOYEES}
        team = [eid for eid in parsed.get("team", []) if eid in valid_ids]
        if not team:
            team = default_team

        outline = []
        for s in parsed.get("outline", [])[:_MAX_SECTIONS]:
            sid = str(s.get("id") or "").strip()
            title = str(s.get("title") or "").strip()
            kind = str(s.get("kind") or "narrative").strip()
            if sid and title:
                entry: dict = {"id": sid, "title": title, "kind": kind}
                assigned = str(s.get("assigned_to") or "").strip()
                if assigned:
                    entry["assigned_to"] = assigned
                outline.append(entry)
        if not outline:
            outline = default_outline

        clarifications = []
        for c in parsed.get("clarifications", [])[:_MAX_CLARIFICATIONS]:
            q = str(c.get("question") or "").strip()
            d = str(c.get("default_answer") or "").strip()
            if q and d:
                entry: dict = {"question": q, "default_answer": d}
                p = str(c.get("priority") or "medium").strip().lower()
                if p not in ("high", "medium", "low"):
                    p = "medium"
                entry["priority"] = p
                reason = str(c.get("reason") or "").strip()
                if reason:
                    entry["reason"] = reason
                clarifications.append(entry)
        if not clarifications:
            clarifications = cls._default_clarifications(report)

        opening = str(parsed.get("opening") or "").strip() or None
        rationale = str(parsed.get("rationale") or "").strip()

        return {
            "source": "llm",
            "team": team,
            "outline": outline,
            "clarifications": clarifications,
            "opening": opening,
            "rationale": rationale,
        }

    @staticmethod
    def _parse_scoping_json(raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        s = raw.strip()
        if s.startswith("```"):
            s = s.strip("`")
            nl = s.find("\n")
            if nl >= 0:
                s = s[nl + 1 :]
            s = s.rstrip("`").strip()
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    @staticmethod
    def _default_clarifications(report: Report) -> List[Dict[str, str]]:
        rt = report.report_type
        if rt == "ops_review":
            return [
                {"question": "本次分析的时间口径是?",
                 "default_answer": "最近一个完整季度,同比去年同期"},
                {"question": "要不要把重点分行/产品线单独拆一章?",
                 "default_answer": "是,按贡献排名前 5 个单独拆"},
            ]
        if rt == "risk_assessment":
            return [
                {"question": "评估对象主体是否以上传材料中的授信主体为准?",
                 "default_answer": "是"},
            ]
        if rt == "regulatory_filing":
            return [
                {"question": "是否以上传的监管模板为唯一结构依据?",
                 "default_answer": "是,结构不修改,仅填字段"},
            ]
        if rt == "training_material":
            return [
                {"question": "目标受众的业务熟悉度?",
                 "default_answer": "初级员工(刚入职 0-1 年)"},
            ]
        return [
            {"question": "研究的核心问题可以用一句话概括吗?",
             "default_answer": "以用户提供的 brief 为准"},
        ]

    # ------------------------------------------------------------------
    # Production run — 4-Phase Pipeline
    # ------------------------------------------------------------------

    @classmethod
    async def _run_production(cls, report_id: int) -> None:
        """
        4-Phase pipeline:
          Phase 1 – Requirement Analyst  → ExecutionState.execution_plan
          Phase 2 – Data Gathering Loop  → ExecutionState.data_context  (sandbox)
          Phase 3 – Synthesis            → section drafts with data_context
          Phase 4 – QA validation + Delivery (with hallucination retry)
        """
        try:
            # ===== Bootstrap =============================================
            async with AsyncSessionLocal() as db:
                report = await ReportService.get(db, report_id)
                if not report:
                    return
                kb = await cls._build_kb(db, report_id)
                digests = await cls._document_digests(db, report_id, kb=kb)
                clar_list = await cls._answered_clarifications(db, report_id)
                from app.services.report_types import resolve_report_type as _resolve_rt
                rt = (await _resolve_rt(db, report.report_type)) or {}
                context = RunContext(
                    report_title=report.title,
                    report_type_label=rt.get("label", "专项报告"),
                    brief=report.brief,
                    clarifications=clar_list,
                    document_digests=digests,
                    section_outline=list(report.section_outline or []),
                )
                kb_chunks: List[Dict[str, Any]] = list(kb.get("chunks") or [])
                outline: List[Dict[str, Any]] = list(report.section_outline or [])
                team: List[str] = list(report.team_roster or [])

                # Transition to producing
                await ReportService.update_status(
                    db, report,
                    status=ReportStatus.producing.value,
                    phase="producing", progress=0.05,
                )
                await TimelineService.append(
                    db, report_id=report.id,
                    event_type="phase_enter", label="进入生产阶段",
                    payload={"phase": "producing"},
                )
                await db.commit()

            # Build the shared ExecutionState for this run and register
            # it so the API layer can inject steering instructions mid-flight
            from app.services.execution_state import ExecutionState, PlanStep
            state = ExecutionState(
                report_id=report_id,
                brief=report.brief,
                report_type=report.report_type,
            )
            _register_state(report_id, state)

            evidence_summary = "\n\n".join(
                f"【{d['name']}】\n{d['excerpt']}" for d in digests
            )

            # ===== Phase 1 – Requirement Analyst (Elin) ==================
            await cls._phase1_plan(report_id, outline, context, state, evidence_summary, clar_list)

            # ===== Phase 2 – Data Gathering (Quinn) ======================
            await cls._phase2_data(report_id, state, context, kb_chunks, evidence_summary)

            # ===== Phase 3 – Synthesis ===================================
            section_results: Dict[str, Any] = await cls._phase3_synthesis(
                report_id, outline, team, context, state, kb_chunks
            )

            # ===== Phase 4 – QA validation + Delivery ===================
            await cls._phase4_qa_and_deliver(
                report_id, outline, team, context, state, section_results, kb_chunks
            )

        except Exception as exc:
            logger.exception("_run_production failed for report %s: %s", report_id, exc)
            async with AsyncSessionLocal() as db:
                r = await ReportService.get(db, report_id)
                if r:
                    await ReportService.update_status(
                        db, r,
                        status=ReportStatus.failed.value,
                        phase="failed",
                        error_message=str(exc)[:800],
                    )
                    await db.commit()
        finally:
            _deregister_state(report_id)

    # ------------------------------------------------------------------
    # Phase 1 — Requirement Analyst
    # ------------------------------------------------------------------

    @classmethod
    async def _phase1_plan(
        cls,
        report_id: int,
        outline: List[Dict[str, Any]],
        context: RunContext,
        state: "ExecutionState",
        evidence_summary: str,
        clar_list: List[Dict[str, Any]],
    ) -> None:
        """Elin turns the brief into a structured execution plan."""
        from app.services.execution_state import PlanStep
        async with AsyncSessionLocal() as db:
            r = await ReportService.get(db, report_id)
            if not r or r.status == ReportStatus.cancelled.value:
                return
            await ReportService.update_status(db, r, progress=0.08)
            await MessageService.append(
                db, report_id=report_id,
                role="phase_transition",
                author_id="intake_officer",
                author_name="Elin",
                content="**Elin** 正在编译需求，生成执行计划…",
                meta={"phase": "planning"},
            )
            await db.commit()

        clar_text = "; ".join(
            f"{c.get('question','?')} → {c.get('answer') or c.get('default_answer','默认')}"
            for c in clar_list
        )
        plan_data = await EmployeeRunner.run_planning(
            brief=context.brief,
            evidence_summary=evidence_summary,
            clarifications=clar_text,
            report_type_label=context.report_type_label,
            section_outline=outline,
        )
        state.record("intake_officer", "llm_call",
                     "planning", plan_data.get("opening", "")[:200])

        # Parse steps into PlanStep objects
        raw_steps: List[Dict[str, Any]] = plan_data.get("execution_plan") or []
        for s in raw_steps:
            state.execution_plan.append(PlanStep(
                step_id=s.get("step_id", f"step_{len(state.execution_plan)}"),
                phase=s.get("phase", "synthesis"),
                description=s.get("description", ""),
                employee_id=s.get("employee_id", "structured_writer"),
                depends_on=s.get("depends_on") or [],
                result_key=s.get("result_key"),
            ))
        state.phase = "data_gathering"

        async with AsyncSessionLocal() as db:
            r = await ReportService.get(db, report_id)
            if not r:
                return
            await MessageService.append(
                db, report_id=report_id,
                role="supervisor_say",
                author_id="intake_officer",
                author_name="Elin",
                content=(
                    plan_data.get("opening") or
                    f"计划就绪。共 {len(state.execution_plan)} 步，"
                    f"含 {sum(1 for s in state.execution_plan if s.phase=='data')} 个数据步骤。"
                ),
                meta={"plan_steps": len(state.execution_plan)},
            )
            await ReportService.update_status(db, r, progress=0.12)
            await db.commit()

    # ------------------------------------------------------------------
    # Phase 2 — Data Gathering with sandbox execution (并行依赖感知版)
    # ------------------------------------------------------------------

    @classmethod
    async def _phase2_data(
        cls,
        report_id: int,
        state: "ExecutionState",
        context: RunContext,
        kb_chunks: List[Dict[str, Any]],
        evidence_summary: str,
    ) -> None:
        """Quinn + 并行执行：依赖感知的拓扑分批并行数据步骤。

        传统串行版：6 步 × 20s = 120s
        新并行版：只需 max_depth × 20s（无依赖时一批完成）

        依赖规则：steps with empty depends_on 同批并行发射；
        只有依赖全部完成的步骤才进入下一批。
        """
        from app.services.qa_validation_service import security_scan
        from app.services.subagent_manager import SubagentManager

        data_steps = [s for s in state.execution_plan if s.phase == "data"]
        if not data_steps:
            state.record("supervisor", "skip", "phase2", "No data steps in plan, skipping.")
            return

        async with AsyncSessionLocal() as db:
            r = await ReportService.get(db, report_id)
            if not r or r.status == ReportStatus.cancelled.value:
                return
            await MessageService.append(
                db, report_id=report_id,
                role="phase_transition",
                author_id=SUPERVISOR["id"],
                author_name=SUPERVISOR["first_name_en"],
                content=(
                    f"**数据阶段** 开始。Quinn 将并行执行 {len(data_steps)} 个数据步骤"
                    f"（依赖感知分批，目标减少等待时间）。"
                ),
                meta={"phase": "data", "parallel": True},
            )
            await ReportService.update_status(db, r, phase="data_gathering", progress=0.15)
            await db.commit()

        data_frames = await cls._load_dataframes(report_id)
        manager = SubagentManager.get()

        # 拓扑分批：BFS 按依赖层次分批并行
        step_map = {s.step_id: s for s in data_steps}
        completed_ids: set = set()
        processed = 0
        total = max(1, len(data_steps))

        while True:
            if state.cancelled:
                return
            # 找出所有依赖已满足的 pending 步骤
            ready = [
                s for s in data_steps
                if s.status == "pending"
                and all(dep in completed_ids for dep in s.depends_on)
            ]
            if not ready:
                break

            # 并行发射这一批
            batch_task_ids = []
            for step in ready:
                step.status = "running"
                emp = get_employee(step.employee_id) or get_employee("data_wrangler") or SUPERVISOR

                async with AsyncSessionLocal() as db:
                    r = await ReportService.get(db, report_id)
                    if not r or r.status == ReportStatus.cancelled.value:
                        return
                    await MessageService.append(
                        db, report_id=report_id,
                        role="team_change",
                        author_id=step.employee_id,
                        author_name=emp["first_name_en"],
                        content=f"**{emp['first_name_en']}** 并行处理数据步骤：{step.description}",
                        meta={"step_id": step.step_id, "phase": "data", "parallel": True},
                    )
                    await db.commit()

                # 为每个数据步骤生成一个独立的协程并注册到 SubagentManager
                coro = EmployeeRunner.run_data_step(
                    step_description=step.description,
                    evidence_summary=evidence_summary,
                    data_context_so_far=dict(state.data_context),  # 快照隔离
                    data_frames=data_frames,
                    brief=context.brief,
                )
                tid = manager.launch(
                    coro=coro,
                    employee_id=step.employee_id,
                    description=step.description,
                    report_id=report_id,
                    phase="data",
                )
                state.register_task_id(step.step_id, tid)
                batch_task_ids.append((step, tid))

            # 等待这一批全部完成
            await manager.collect([tid for _, tid in batch_task_ids], timeout=120.0)

            # 处理结果
            for step, tid in batch_task_ids:
                sub_task = manager.get_task(tid)
                if not sub_task or sub_task.result is None:
                    step.status = "error"
                    state.record(step.employee_id, "code_exec",
                                 step.description, "task failed or timed out")
                    completed_ids.add(step.step_id)
                    processed += 1
                    continue

                code, sandbox_result, metrics, error = sub_task.result
                # 首轮无指标或沙箱失败时，以 error_count=1 触发专家级 Quinn+ 重试一次
                if (not metrics or error) and sub_task.result is not None:
                    code2, sr2, met2, err2 = await EmployeeRunner.run_data_step(
                        step_description=step.description,
                        evidence_summary=evidence_summary,
                        data_context_so_far=dict(state.data_context),
                        data_frames=data_frames,
                        brief=context.brief,
                        error_count=1,
                        prior_error=error or "no metrics from first attempt",
                    )
                    if met2:
                        code, sandbox_result, metrics, error = code2, sr2, met2, err2
                        async with AsyncSessionLocal() as db:
                            r = await ReportService.get(db, report_id)
                            if r:
                                await MessageService.append(
                                    db, report_id=report_id,
                                    role="employee_note",
                                    author_id="data_wrangler",
                                    author_name="Quinn+",
                                    content="首轮数据步骤未产出有效指标，已自动升级为 **专家模式** 重试并成功。",
                                    meta={"step_id": step.step_id, "expert_retry": True},
                                )
                                await db.commit()

                emp = get_employee(step.employee_id) or get_employee("data_wrangler") or SUPERVISOR
                emp_name = emp["first_name_en"]

                state.record(
                    step.employee_id, "code_exec",
                    input_summary=step.description,
                    output_summary=str(metrics)[:300] if metrics else (error or "no output"),
                    code=code,
                    code_result=sandbox_result.summary() if sandbox_result else error,
                    error=error,
                )

                if metrics:
                    metrics_text = str(metrics)
                    clean, findings = security_scan(metrics_text)
                    state.mark_security(step.step_id, "pass" if clean else "blocked")
                    if clean:
                        for key, val in metrics.items():
                            state.store_metric(key=str(key), value=val,
                                               source=step.description, code_verified=True)
                        step.status = "done"
                        note = f"{emp_name} 完成数据步骤，提取 {len(metrics)} 项指标。"
                    else:
                        step.status = "error"
                        note = (f"{emp_name} 数据步骤完成，但 Security Agent 发现敏感信息，"
                                f"已屏蔽 {len(findings)} 项。")
                        state.record("security_agent", "security_scan",
                                     step.step_id, f"BLOCKED: {findings[:3]}")
                else:
                    step.status = "error" if error else "skipped"
                    note = f"{emp_name} 数据步骤未产出指标。" + (f"（错误：{error[:100]}）" if error else "")

                async with AsyncSessionLocal() as db:
                    r = await ReportService.get(db, report_id)
                    if not r:
                        completed_ids.add(step.step_id)
                        processed += 1
                        continue
                    await MessageService.append(
                        db, report_id=report_id,
                        role="employee_note",
                        author_id=step.employee_id,
                        author_name=emp_name,
                        content=note,
                        meta={"step_id": step.step_id, "metrics_count": len(metrics) if metrics else 0},
                    )
                    processed += 1
                    progress = 0.15 + 0.15 * (processed / total)
                    await ReportService.update_status(db, r, progress=progress)
                    r.data_context = state.data_context
                    await db.commit()

                completed_ids.add(step.step_id)

        state.phase = "synthesis"

    # ------------------------------------------------------------------
    # Phase 3 — Synthesis（拓扑并行版 + SubagentManager + Steering）
    # ------------------------------------------------------------------

    @classmethod
    async def _phase3_synthesis(
        cls,
        report_id: int,
        outline: List[Dict[str, Any]],
        team: List[str],
        context: RunContext,
        state: "ExecutionState",
        kb_chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """拓扑并行合成：同一依赖层次的章节并行发射，SubagentManager 管理生命周期。

        传统串行：N 章节 × T秒/章节 = N×T 秒
        并行优化：max_depth_layers × T秒（无依赖时一批完成，最少 1 个 T 周期）

        Steering 支持：Supervisor 通过 state.inject_steering(section_id, instruction)
        注入的指令会在 Employee 开始写作前被消费并附加到 prompt 中。
        """
        from app.services.subagent_manager import SubagentManager

        async with AsyncSessionLocal() as db:
            r = await ReportService.get(db, report_id)
            if not r or r.status == ReportStatus.cancelled.value:
                return {}
            await MessageService.append(
                db, report_id=report_id,
                role="phase_transition",
                author_id=SUPERVISOR["id"],
                author_name=SUPERVISOR["first_name_en"],
                content=(
                    f"**写作阶段** 开始（并行模式）。"
                    f"已验证 {len(state.data_context)} 项数据指标，"
                    f"共 {len(outline)} 个章节并行产出。"
                ),
                meta={"phase": "synthesis", "parallel": True, "data_keys": len(state.data_context)},
            )
            await ReportService.update_status(db, r, phase="synthesis", progress=0.30)
            await db.commit()

        section_results: Dict[str, Any] = {}
        total = max(1, len(outline))
        data_summary = state.all_metrics_summary()
        manager = SubagentManager.get()

        # 为每个 section 构建任务元数据，全部并行发射（无依赖约束时）
        # 若将来 section 有 depends_on 字段，可在此扩展为拓扑分批
        section_task_ids: List[tuple] = []  # (section_meta_dict, task_id)

        for section in outline:
            if state.cancelled:
                return section_results

            section_id = section.get("id") or f"section_{len(section_task_ids)}"
            section_title = section.get("title") or section_id
            employee_id = pick_employee_for_section(section, team)
            emp = get_employee(employee_id) or SUPERVISOR

            # 通知 UI：这个 employee 已被派遣
            async with AsyncSessionLocal() as db:
                r = await ReportService.get(db, report_id)
                if not r or r.status == ReportStatus.cancelled.value:
                    return section_results
                await MessageService.append(
                    db, report_id=report_id,
                    role="team_change",
                    author_id=SUPERVISOR["id"],
                    author_name=SUPERVISOR["first_name_en"],
                    content=f"**{emp['first_name_en']}** 并行启动「{section_title}」。",
                    meta={"section_id": section_id, "employee_id": employee_id, "parallel": True},
                )
                await db.commit()

            # 检索相关证据
            evidence_snippets: List[Dict[str, Any]] = []
            if kb_chunks:
                query = f"{section_title} {section.get('instruction','')} {context.brief}"
                try:
                    evidence_snippets = KnowledgeBaseService().select_relevant(
                        {"chunks": kb_chunks, "top_k": 6},
                        query=query, top_k=6,
                    )
                except Exception:
                    pass

            # 消费 Supervisor 注入的 steering 指令
            steering = state.pop_steering(section_id)

            section_context = dataclasses.replace(context, evidence_snippets=evidence_snippets)
            task = SectionTask(
                section_id=section_id,
                section_title=section_title,
                section_kind=section.get("kind", "narrative"),
                instruction=section.get("instruction", ""),
            )

            # 将合成协程注册到 SubagentManager，立即返回 task_id（Fire-and-Steer）
            coro = EmployeeRunner.run_synthesis(
                employee_id=employee_id,
                task=task,
                context=section_context,
                data_context_summary=data_summary,
                steering_instruction=steering or "",
                qa_retry_count=0,
                error_count=0,
            )
            tid = manager.launch(
                coro=coro,
                employee_id=employee_id,
                description=section_title,
                report_id=report_id,
                phase="synthesis",
                section_id=section_id,
            )
            state.register_task_id(section_id, tid)
            section_task_ids.append((section, employee_id, tid))

        # 等待所有 synthesis 任务完成（超时保护：每章节最长 150s）
        all_tids = [tid for _, _, tid in section_task_ids]
        await manager.collect(all_tids, timeout=150.0 * max(1, len(outline)))

        # 收集结果，更新 UI 与数据库
        for idx, (section, employee_id, tid) in enumerate(section_task_ids):
            section_id = section.get("id") or f"section_{idx}"
            section_title = section.get("title") or section_id
            emp = get_employee(employee_id) or SUPERVISOR
            sub_task = manager.get_task(tid)

            if sub_task and sub_task.result is not None:
                result = sub_task.result
            else:
                # 超时或失败时使用占位
                from app.agents.employees.runner import RunResult
                result = RunResult(
                    ok=False, text="", note="超时或失败",
                    error=f"subagent task {tid} did not complete",
                )

            state.record(
                employee_id, "llm_call",
                input_summary=section_title,
                output_summary=result.text[:200] if result.text else (result.error or ""),
            )
            state.section_drafts[section_id] = result.text or ""

            chart_image_paths: List[str] = []
            if employee_id == "chart_maker" and result.text:
                chart_image_paths = await cls._render_charts_from_text(
                    result.text, section_id, report_id
                )

            entry = {
                "text": result.text,
                "employee_id": employee_id,
                "employee_name": emp["first_name_en"],
                "note": result.note,
                "error": result.error,
                "image_paths": chart_image_paths,
                "task_id": tid,
            }
            section_results[section_id] = entry

            async with AsyncSessionLocal() as sdb:
                r2 = await ReportService.get(sdb, report_id)
                if not r2 or r2.status == ReportStatus.cancelled.value:
                    continue
                await ReportService.save_output_section(
                    sdb, r2, section_id=section_id, payload=entry,
                )
                await MessageService.append(
                    sdb, report_id=report_id,
                    role="employee_note",
                    author_id=employee_id,
                    author_name=emp["first_name_en"],
                    content=result.note or f"{emp['first_name_en']} 完成章节初稿",
                    meta={"section_id": section_id, "llm_ok": result.ok, "task_id": tid},
                )
                progress = 0.30 + 0.45 * ((idx + 1) / total)
                await ReportService.update_status(sdb, r2, progress=progress)
                await sdb.commit()

        state.phase = "qa"
        return section_results

    # ------------------------------------------------------------------
    # Phase 4 — QA validation + anti-hallucination retry + delivery
    # ------------------------------------------------------------------

    @classmethod
    async def _phase4_qa_and_deliver(
        cls,
        report_id: int,
        outline: List[Dict[str, Any]],
        team: List[str],
        context: RunContext,
        state: "ExecutionState",
        section_results: Dict[str, Any],
        kb_chunks: List[Dict[str, Any]],
    ) -> None:
        from app.services.qa_validation_service import validate_section

        async with AsyncSessionLocal() as db:
            r = await ReportService.get(db, report_id)
            if not r or r.status == ReportStatus.cancelled.value:
                return
            await ReportService.update_status(
                db, r,
                status=ReportStatus.reviewing.value,
                phase="reviewing", progress=0.76,
            )
            await TimelineService.append(
                db, report_id=report_id,
                event_type="phase_enter", label="进入质检阶段",
                payload={"phase": "reviewing"},
            )
            await MessageService.append(
                db, report_id=report_id,
                role="phase_transition",
                author_id=SUPERVISOR["id"],
                author_name=SUPERVISOR["first_name_en"],
                content=(
                    f"**质检阶段** 开始。Sage 将验证所有章节数据声明。"
                    f"（data_context 含 {len(state.data_context)} 项已验证指标）"
                ),
                meta={"phase": "reviewing"},
            )
            await db.commit()

        _MAX_QA_RETRIES = 2

        for section in outline:
            section_id = section.get("id") or f"s_{section.get('title','')}"
            entry = section_results.get(section_id, {})
            if not entry.get("text"):
                continue

            for attempt in range(_MAX_QA_RETRIES + 1):
                text = entry["text"]
                verdict = validate_section(section_id, text, state)
                state.qa_flags[section_id] = [
                    {"claim": v.claim.raw_value, "passed": v.passed, "reason": v.reason}
                    for v in verdict.claim_verdicts
                ]
                state.record(
                    "qa_reviewer", "qa_check",
                    input_summary=section_id,
                    output_summary=f"{verdict.overall} | {verdict.hallucination_count} issues",
                    error=None if verdict.ok else verdict.retry_prompt_patch[:200],
                )

                if verdict.ok or not verdict.retry_prompt_patch:
                    state.section_finals[section_id] = text
                    break

                if attempt < _MAX_QA_RETRIES:
                    # Retry with conflict patch
                    employee_id = entry.get("employee_id", "structured_writer")
                    emp = get_employee(employee_id) or SUPERVISOR
                    async with AsyncSessionLocal() as db:
                        r = await ReportService.get(db, report_id)
                        if r:
                            await MessageService.append(
                                db, report_id=report_id,
                                role="employee_note",
                                author_id="qa_reviewer",
                                author_name="Sage",
                                content=(
                                    f"⚠️ 章节「{section.get('title',section_id)}」发现 "
                                    f"{verdict.hallucination_count} 处数据冲突，已退回 "
                                    f"{emp['first_name_en']} 修正（第 {attempt+1} 次重试）。"
                                ),
                                meta={"section_id": section_id, "attempt": attempt},
                            )
                            await db.commit()

                    evidence_snippets: List[Dict[str, Any]] = []
                    if kb_chunks:
                        try:
                            evidence_snippets = KnowledgeBaseService().select_relevant(
                                {"chunks": kb_chunks, "top_k": 6},
                                query=section.get("title", ""),
                                top_k=6,
                            )
                        except Exception:
                            pass

                    retry_context = dataclasses.replace(context, evidence_snippets=evidence_snippets)
                    retry_task = SectionTask(
                        section_id=section_id,
                        section_title=section.get("title") or section_id,
                        section_kind=section.get("kind", "narrative"),
                        instruction=section.get("instruction", ""),
                    )
                    retry_result = await EmployeeRunner.run_synthesis(
                        employee_id=employee_id,
                        task=retry_task,
                        context=retry_context,
                        data_context_summary=state.all_metrics_summary(),
                        qa_retry_patch=verdict.retry_prompt_patch,
                        qa_retry_count=attempt + 1,
                    )
                    if retry_result.text:
                        entry["text"] = retry_result.text
                        state.section_drafts[section_id] = retry_result.text
                        # Update the UI preview
                        async with AsyncSessionLocal() as sdb:
                            r2 = await ReportService.get(sdb, report_id)
                            if r2:
                                entry_to_save = dict(entry)
                                entry_to_save["text"] = retry_result.text
                                await ReportService.save_output_section(
                                    sdb, r2, section_id=section_id,
                                    payload=entry_to_save,
                                )
                                await sdb.commit()
                else:
                    # Blocked after all retries — keep the last draft
                    state.section_finals[section_id] = text

            if section_id not in state.section_finals:
                state.section_finals[section_id] = entry.get("text", "")

        # QA summary message
        total_issues = sum(
            sum(1 for v in flags if not v["passed"])
            for flags in state.qa_flags.values()
        )
        async with AsyncSessionLocal() as db:
            r = await ReportService.get(db, report_id)
            if not r or r.status == ReportStatus.cancelled.value:
                return
            await MessageService.append(
                db, report_id=report_id,
                role="employee_note",
                author_id="qa_reviewer",
                author_name="Sage",
                content=(
                    f"质检完成。总计扫描 {len(outline)} 个章节，"
                    f"修正 {total_issues} 处数据声明。"
                    if total_issues else
                    "质检通过。所有数据声明均与 data_context 一致。"
                ),
                meta={"total_issues": total_issues},
            )
            await db.commit()

        # ------- Render final .docx -------
        final_path, final_name = await cls._render_final_docx(
            report_id=report_id,
            context=context,
            review_note="",  # review note now inline in QA messages
        )

        # ------- Persist trace + delivery -------
        async with AsyncSessionLocal() as db:
            r = await ReportService.get(db, report_id)
            if not r or r.status == ReportStatus.cancelled.value:
                return
            if final_path and final_name:
                r.final_file_path = final_path
                r.final_file_name = final_name
            # Persist full audit trace
            r.trace_log = state.serialise()
            r.data_context = state.data_context
            await ReportService.update_status(
                db, r,
                status=ReportStatus.delivered.value,
                phase="delivered", progress=1.0,
            )
            await TimelineService.append(
                db, report_id=r.id,
                event_type="delivered", label="报告交付",
                payload={"phase": "delivered"},
            )
            await MessageService.append(
                db, report_id=r.id,
                role="supervisor_say",
                author_id=SUPERVISOR["id"],
                author_name=SUPERVISOR["first_name_en"],
                content=(
                    f"报告已交付。"
                    + (f"可点击右侧「下载 Word」获取文件。" if final_name else "")
                    + f"\n\n**执行摘要**: 执行计划 {len(state.execution_plan)} 步 · "
                    f"验证数据 {len(state.data_context)} 项 · "
                    f"QA 修正 {total_issues} 处 · "
                    f"总耗时 {round(state.serialise()['elapsed_s'], 0):.0f}s"
                ),
                meta={"final_file_name": final_name},
            )
            await db.commit()

    # ------------------------------------------------------------------
    # DataFrame pre-loading for sandbox
    # ------------------------------------------------------------------

    @classmethod
    async def _load_dataframes(cls, report_id: int) -> Dict[str, Any]:
        """Load Excel/CSV uploads into pandas DataFrames for sandbox use."""
        frames: Dict[str, Any] = {}
        try:
            import pandas as pd
            async with AsyncSessionLocal() as db:
                from app.models.uploaded_file import UploadedFile
                from sqlalchemy import select as sa_select
                result = await db.execute(
                    sa_select(UploadedFile).where(
                        UploadedFile.report_id == report_id,
                        UploadedFile.is_template.is_(False),
                    )
                )
                files = result.scalars().all()
            for f in files:
                path = getattr(f, "file_path", None)
                name = getattr(f, "original_name", None) or f"file_{f.id}"
                if not path or not os.path.exists(path):
                    continue
                ext = os.path.splitext(name)[-1].lower()
                try:
                    if ext in (".xlsx", ".xls"):
                        df = pd.read_excel(path)
                        var_name = re.sub(r"\W+", "_", os.path.splitext(name)[0])[:30]
                        frames[var_name] = df
                    elif ext == ".csv":
                        df = pd.read_csv(path)
                        var_name = re.sub(r"\W+", "_", os.path.splitext(name)[0])[:30]
                        frames[var_name] = df
                except Exception as exc:
                    logger.warning("Could not load DataFrame from %s: %s", name, exc)
        except ImportError:
            pass
        return frames

    # ------------------------------------------------------------------
    # Review summary (1 LLM call; falls back to deterministic text)
    # ------------------------------------------------------------------

    @classmethod
    async def _review_summary(
        cls,
        report: Report,
        context: RunContext,
        reviewer_id: Optional[str],
    ) -> str:
        sections = list((report.output_index or {}).keys())
        fallback = (
            f"**质检完成**。已复核 {len(sections)} 个章节的逻辑一致性与"
            f"对上传材料的引用,未发现需要打回的硬性问题。"
        )
        if not reviewer_id:
            return fallback

        output_index: Dict[str, Any] = report.output_index or {}
        body_digest = "\n\n".join(
            f"## {sid}\n{(v.get('text') or '')[:500]}"
            for sid, v in output_index.items()
        )
        sys_prompt = (
            "你是 QA Reviewer Sage,在 30-60 字之内用中文给出对下列报告章节草稿的"
            "总体质检结论,突出最需要关注的 1 个点。不要输出章节列表,不要列点。"
        )
        try:
            raw = await asyncio.wait_for(
                LLMService().chat(
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": body_digest or report.brief},
                    ],
                    temperature=0.3, max_tokens=200,
                ),
                timeout=30.0,
            )
            raw = (raw or "").strip()
            return raw or fallback
        except Exception as e:
            logger.warning("Review summary LLM failed: %s", e)
            return fallback

    # ------------------------------------------------------------------
    # Chart generation from chart_maker text output
    # ------------------------------------------------------------------

    @classmethod
    async def _render_charts_from_text(
        cls, text: str, section_id: str, report_id: int
    ) -> List[str]:
        """Parse markdown tables from chart_maker output and generate PNG files.

        Returns a list of absolute file paths to the generated PNGs.
        The caller stores these paths in the section's output payload so
        WordGenerator can embed them.
        """
        from app.config import settings
        from app.generators.chart_generator import ChartGenerator

        out_dir = os.path.join(settings.UPLOAD_DIR, "charts")
        os.makedirs(out_dir, exist_ok=True)
        paths: List[str] = []

        # Find all markdown table blocks in the text
        table_pattern = re.compile(
            r"((?:\|[^\n]+\|\n)+(?:\|[\s\-:|]+\|\n)(?:\|[^\n]+\|\n)*)",
            re.MULTILINE,
        )
        # Extract chart-type hint from surrounding text
        def _infer_chart_type(context_text: str) -> str:
            ctx = context_text.lower()
            if any(w in ctx for w in ["占比", "比例", "结构", "构成", "饼"]):
                return "pie"
            if any(w in ctx for w in ["趋势", "变化", "走势", "折线"]):
                return "line"
            return "bar"

        for idx, m in enumerate(table_pattern.finditer(text)):
            table_block = m.group(0)
            # Get ~200 chars before table for chart type hint
            pre = text[max(0, m.start() - 200) : m.start()]
            chart_type = _infer_chart_type(pre + table_block)
            # Derive title from the nearest ## or ### heading before the table
            heading_match = re.search(r"(?:^|\n)#{1,3}\s+(.+)", pre)
            title = heading_match.group(1).strip() if heading_match else ""

            try:
                png = ChartGenerator.from_markdown_table(
                    table_block, chart_type, title=title
                )
                if png and len(png) > 1000:
                    fname = f"chart_{report_id}_{section_id}_{idx}.png"
                    fpath = os.path.join(out_dir, fname)
                    with open(fpath, "wb") as fp:
                        fp.write(png)
                    paths.append(fpath)
            except Exception as exc:
                logger.warning("Chart generation failed for %s/%s: %s", section_id, idx, exc)

        return paths

    # ------------------------------------------------------------------
    # Final Word rendering
    # ------------------------------------------------------------------

    @classmethod
    async def _render_final_docx(
        cls,
        *,
        report_id: int,
        context: RunContext,
        review_note: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """Render the aggregated ``output_index`` into a .docx file on disk.

        Returns (absolute_path, display_filename) or (None, None) on failure.
        The caller persists the path onto the Report row.
        """
        from datetime import datetime

        from app.config import settings
        from app.generators.word_generator import WordGenerator

        try:
            async with AsyncSessionLocal() as db:
                r = await ReportService.get(db, report_id)
                if not r:
                    return None, None
                outputs: Dict[str, Dict[str, Any]] = dict(r.output_index or {})
                outline: List[Dict[str, Any]] = list(r.section_outline or [])
                title = r.title or "专项报告"
                brief = r.brief or ""
                report_type_label = context.report_type_label

                # Resolve template path if user chose one
                template_path: Optional[str] = None
                if r.template_file_id:
                    from sqlalchemy import select as _select
                    from app.models.uploaded_file import UploadedFile as _UF
                    tf_result = await db.execute(
                        _select(_UF).where(_UF.id == r.template_file_id)
                    )
                    tf = tf_result.scalar_one_or_none()
                    if tf and os.path.exists(tf.file_path):
                        template_path = tf.file_path

            # Assemble content blocks in the order of the outline so sections
            # render in a sensible flow.
            sections_payload: List[Dict[str, Any]] = []
            for s in outline:
                sid = s.get("id")
                heading = s.get("title") or sid or "章节"
                out_entry = outputs.get(sid) or {}
                body = out_entry.get("text") or ""
                # Strip code fences the LLM left behind
                body = re.sub(r"^```[a-zA-Z]*\n?", "", body).rstrip("` \n")
                # Strip evidence citation IDs [E10-1-xxx] — internal use only
                body = re.sub(r"\[E\d+[-\w]*\]", "", body)
                body = re.sub(r"\s{2,}", " ", body)
                sec: Dict[str, Any] = {
                    "heading": heading,
                    "level": 1,
                    "content": body or "（本节无内容）",
                }
                img_paths = out_entry.get("image_paths") or []
                if img_paths:
                    sec["image_paths"] = [p for p in img_paths if os.path.exists(p)]
                sections_payload.append(sec)
            # Do NOT append QA review notes — users only want core section content.

            content = {
                "title": title,
                "subtitle": report_type_label,
                "author": "dataagent · 深度研究数据分析智能体",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "abstract": brief[:600],
                "sections": sections_payload,
            }

            docx_bytes = await WordGenerator().generate(content, template_path=template_path)
            out_dir = os.path.join(settings.UPLOAD_DIR, "outputs")
            os.makedirs(out_dir, exist_ok=True)
            safe_title = re.sub(r"[\\/:*?\"<>|]", "_", title).strip() or "report"
            display_name = f"{safe_title}-{report_id}.docx"
            abs_path = os.path.abspath(os.path.join(out_dir, display_name))
            with open(abs_path, "wb") as fp:
                fp.write(docx_bytes)
            return abs_path, display_name
        except Exception:
            logger.exception("Final .docx render failed for report %s", report_id)
            return None, None

    # ------------------------------------------------------------------
    # Helpers — document digests & answered clarifications
    # ------------------------------------------------------------------

    @staticmethod
    async def _document_digests(
        db: AsyncSession,
        report_id: int,
        kb: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        # Prefer KB chunk previews when available: they're deduplicated and
        # already bounded. Otherwise fall back to the raw extracted_text.
        if kb and kb.get("chunks"):
            per_file: Dict[str, List[str]] = {}
            for chunk in kb["chunks"]:
                name = chunk.get("file_name") or "未命名材料"
                per_file.setdefault(name, []).append(chunk.get("preview") or "")
            digests: List[Dict[str, str]] = []
            for name, previews in per_file.items():
                excerpt = "\n".join(p for p in previews[:6] if p)
                if len(excerpt) > _DOC_EXCERPT_CHARS:
                    excerpt = excerpt[:_DOC_EXCERPT_CHARS] + "…"
                digests.append({"name": name, "excerpt": excerpt})
            return digests

        files = await ReportService.list_files(db, report_id)
        digests = []
        for f in files:
            text = (f.extracted_text or "").strip()
            if not text:
                continue
            if len(text) > _DOC_EXCERPT_CHARS:
                text = text[:_DOC_EXCERPT_CHARS] + "…"
            digests.append({"name": f.original_name, "excerpt": text})
        return digests

    @staticmethod
    async def _build_kb(db: AsyncSession, report_id: int) -> Dict[str, Any]:
        """Build the per-report knowledge base, persist Evidence, return the
        in-memory KB (chunks + metadata)."""
        files = await ReportService.list_files(db, report_id)
        file_payload = [
            {
                "id": f.id,
                "name": f.original_name,
                "type": f.file_type,
                "size": f.file_size,
                "content": f.extracted_text or "",
            }
            for f in files
        ]
        try:
            kb = await KnowledgeBaseService(db).build_for_task(file_payload)
        except Exception:
            logger.exception("KB build failed; continuing without evidence")
            return {"chunks": [], "enabled": False}

        try:
            await EvidenceService.replace_for_report(
                db, report_id=report_id, chunks=kb.get("chunks") or []
            )
            await db.commit()
        except Exception:
            logger.exception("Evidence persistence failed")
            await db.rollback()
        return kb

    @staticmethod
    async def _answered_clarifications(
        db: AsyncSession, report_id: int
    ) -> List[Dict[str, str]]:
        items = await ClarificationService.list_for_report(db, report_id)
        out: List[Dict[str, str]] = []
        for c in items:
            ans = c.answer or c.default_answer
            if ans:
                out.append({
                    "question": c.question,
                    "answer": ans,
                    "default_answer": c.default_answer or "",
                })
        return out
