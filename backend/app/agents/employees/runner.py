"""
EmployeeRunner — single dispatch point for running one employee on one task.

This is the minimum unit of "doing work" in Phase 2. Given:
  - an employee (role card from the registry)
  - a task spec (what section to write, what kind of output)
  - the report context (brief, clarifications, attached document digests)

…it builds a role-conditioned prompt, asks the LLM, and returns a normalized
result. If the LLM is unreachable, it returns a clearly-marked placeholder so
the pipeline still completes end-to-end (important for offline/intranet demos
before an LLM is wired in).

The runner is deliberately stateless and swappable: scoping, production, and
review all reuse this same function. The real per-employee "skills" live in
the system prompt assembly and in which sections Chief dispatches them to —
not in per-employee subclasses.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.employees.registry import get_employee
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task spec
# ---------------------------------------------------------------------------

@dataclass
class SectionTask:
    """One unit of work Chief hands to an employee."""

    section_id: str
    section_title: str
    section_kind: str  # narrative / narrative_with_chart / table_with_narrative / ...
    instruction: str = ""  # free-form guidance from Chief

    def as_user_message(self) -> str:
        return (
            f"请完成报告的下列章节。\n\n"
            f"- 章节 ID:{self.section_id}\n"
            f"- 标题:{self.section_title}\n"
            f"- 章节类型:{self.section_kind}\n"
            f"- 指示:{self.instruction or '按照你最擅长的方式撰写'}\n"
        )


@dataclass
class RunContext:
    """Shared report-level context passed to every employee invocation."""

    report_title: str
    report_type_label: str
    brief: str
    clarifications: List[Dict[str, str]] = field(default_factory=list)
    document_digests: List[Dict[str, str]] = field(default_factory=list)
    section_outline: List[Dict[str, Any]] = field(default_factory=list)
    # Per-call retrieval: top-K evidence chunks most relevant to the current
    # section. Populated by SupervisorService before dispatching the runner.
    evidence_snippets: List[Dict[str, Any]] = field(default_factory=list)

    def as_context_block(self) -> str:
        lines: List[str] = []
        lines.append(f"# 报告基础信息")
        lines.append(f"- 标题:{self.report_title}")
        lines.append(f"- 类型:{self.report_type_label}")
        lines.append(f"- 用户原始诉求:\n{self.brief.strip()}")

        if self.clarifications:
            lines.append("\n# 用户澄清")
            for c in self.clarifications:
                q = c.get("question", "").strip()
                a = (c.get("answer") or c.get("default_answer") or "").strip()
                if q and a:
                    lines.append(f"- Q:{q}\n  A:{a}")

        if self.section_outline:
            lines.append("\n# 整体章节骨架(供你了解上下文)")
            for s in self.section_outline:
                lines.append(f"- {s.get('title')}({s.get('id')})")

        if self.evidence_snippets:
            lines.append("\n# 与本章节最相关的证据片段")
            lines.append(
                "(引用时用方括号标注证据编号,例:见 [E12-1-ab12cd])"
            )
            for ev in self.evidence_snippets:
                eid = ev.get("evidence_id") or "E?"
                src = ev.get("file_name") or "未命名材料"
                loc = f"片段{(ev.get('chunk_index') or 0) + 1}"
                body = (ev.get("text") or ev.get("preview") or "").strip()
                if len(body) > 900:
                    body = body[:900] + "…"
                lines.append(f"\n## [{eid}] {src} · {loc}\n{body}")
        elif self.document_digests:
            lines.append("\n# 用户上传材料摘要")
            for d in self.document_digests:
                name = d.get("name", "未命名")
                text = (d.get("excerpt") or "").strip()
                if not text:
                    continue
                if len(text) > 1200:
                    text = text[:1200] + "…"
                lines.append(f"\n## {name}\n{text}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Employee role prompt
# ---------------------------------------------------------------------------

_ROLE_EXTRA_INSTRUCTIONS: dict = {
    "material_analyst": (
        "你的产出重点是从上传材料中提取并整理核心证据，每条证据必须标注来源文件和位置。"
        "按「发现 → 来源 → 关键数字或引文」结构输出，不要空谈。"
        "若材料中有明确数字、表格、比率，务必完整保留。"
    ),
    "data_wrangler": (
        "你的产出是结构化的数据呈现：优先使用 Markdown 表格展示数字，"
        "标注口径（统计周期、单位、计算方式）和数据质量备注。"
        "不要写流水文字，用表格 + 简短解读代替。"
    ),
    "chart_maker": (
        "你的产出必须包含 Markdown 表格格式的数据（系统会自动将这些表格渲染为真实图表图片）。\n"
        "格式要求：\n"
        "1. 先写一行 ## 章节标题（不超过20字）\n"
        "2. 在标题前写1-2句话说明图表类型（折线图/柱状图/饼图/散点图）和结论\n"
        "3. 紧接着输出完整的 Markdown 数据表格，格式：| 类别 | 数值 | ...\\n| --- | --- | ...\\n| A | 100 | ...\n"
        "4. 数据必须来自上传材料，不得编造。表格至少3行数据，最多20行。\n"
        "5. 每个图表只表达一个核心结论，不同视角用不同的独立表格（每个表格前加 ## 标题）。"
    ),
    "risk_auditor": (
        "你的产出是风险矩阵 + 叙事解读。矩阵用 Markdown 表格：行=风险维度，"
        "列=暴露度|缓释措施|剩余风险评级。每行的判断必须能追溯到材料中的证据。"
        "最后给出总体风险评级（低/中/高/极高）和最需关注的 2~3 个风险点。"
    ),
    "structured_writer": (
        "你的产出是连贯、有逻辑的叙事段落。每个段落只表达一个论点，"
        "论点后紧跟来自材料的数据或证据支撑。严禁空泛表达（如'整体表现良好'），"
        "必须用具体数字或事实支撑。段落之间要有承接关系。"
    ),
    "compliance_checker": (
        "你的产出是合规审查发现表：列出具体问题位置、原文、问题类型（术语/敏感/遗漏/不一致）、"
        "严重程度（高/中/低）、修改建议。用 Markdown 表格呈现。"
        "若无发现，明确写出'合规检查通过，无高优先级问题'。"
    ),
    "qa_reviewer": (
        "你的产出是质检报告：列出已验证的关键断言（断言 → 来源 → 核查结果），"
        "以及发现的不一致之处。用 Markdown 表格呈现。"
        "最后给出整体质检判定：通过 / 需修订 / 阻断。"
    ),
    "template_filler": (
        "严格按模板字段逐项填写，不改变结构。无法确定的字段标注 [需人工确认]。"
        "用 Markdown 表格逐字段呈现填写结果，附填写依据来源。"
    ),
}


def _role_system_prompt(employee: Dict[str, Any]) -> str:
    skills = "、".join(employee.get("skills") or []) or "通用报告工作"
    eid = employee.get("id", "")
    extra = _ROLE_EXTRA_INSTRUCTIONS.get(eid, "")
    return (
        f"你是数字员工 **{employee['first_name_en']}** ({employee.get('name','')}),"
        f"担任 **{employee['role_title_en']}**。\n"
        f"你的风格：{employee.get('tagline_en','')}\n"
        f"核心能力：{skills}\n\n"
        f"你现在受 Chief 调度，为一份内部报告撰写指定章节。\n\n"
        + (f"## 你的专项指南\n{extra}\n\n" if extra else "")
        + "## 通用规则\n"
        "1) 只基于用户提供的材料、证据片段与澄清，不编造外部事实，也不假装联网。\n"
        "   如果上下文给出「与本章节最相关的证据片段」，请在正文中引用对应的证据编号。\n"
        "2) 语言为简体中文，风格严谨，可直接交付给银行内部读者。\n"
        "3) 如果资料不足，请在 text 末尾明确写出「⚠ 信息缺口：缺少……」，不要瞎编。\n"
        "4) 输出必须是合法 JSON，结构如下（不要代码围栏）：\n"
        '   {"text": "<完整 Markdown 正文，不含章节标题，500~1200 字>",\n'
        '    "note": "<15~40 字的进度汇报，写给 Chief>"}'
    )


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    ok: bool
    text: str
    note: str
    raw: Optional[str] = None
    error: Optional[str] = None


class EmployeeRunner:
    """Stateless dispatcher. One public coroutine: ``run_section``.

    A single shared LLMService instance is used across runs so the default
    OpenAI client is constructed once per process.
    """

    _llm: Optional[LLMService] = None

    @classmethod
    def _llm_service(cls) -> LLMService:
        if cls._llm is None:
            cls._llm = LLMService()
        return cls._llm

    @classmethod
    async def run_section(
        cls,
        *,
        employee_id: str,
        task: SectionTask,
        context: RunContext,
        temperature: float = 0.45,
        max_tokens: int = 2400,
        timeout: float = 90.0,
    ) -> RunResult:
        employee = get_employee(employee_id)
        if not employee:
            return RunResult(
                ok=False, text="", note="",
                error=f"unknown employee {employee_id}",
            )

        messages = [
            {"role": "system", "content": _role_system_prompt(employee)},
            {
                "role": "user",
                "content": (
                    context.as_context_block()
                    + "\n\n---\n\n"
                    + task.as_user_message()
                ),
            },
        ]

        try:
            raw = await asyncio.wait_for(
                cls._llm_service().chat(
                    messages=messages,
                    stream=False,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=timeout,
            )
        except Exception as e:  # network, auth, timeout, schema, etc.
            logger.warning(
                "EmployeeRunner LLM call failed for %s/%s: %s",
                employee_id, task.section_id, e,
            )
            return cls._fallback(employee, task, context, str(e))

        return cls._parse(raw, employee, task, context)

    # ------------------------------------------------------------------
    # Parsing + fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(
        raw: str,
        employee: Dict[str, Any],
        task: SectionTask,
        context: RunContext,
    ) -> RunResult:
        raw_stripped = (raw or "").strip()
        # Strip code fences if the model ignored the "no fences" rule
        if raw_stripped.startswith("```"):
            raw_stripped = raw_stripped.strip("`")
            # Drop leading json tag if present
            first_nl = raw_stripped.find("\n")
            if first_nl >= 0:
                raw_stripped = raw_stripped[first_nl + 1 :]
            raw_stripped = raw_stripped.rstrip("`").strip()

        # Try JSON first
        try:
            obj = json.loads(raw_stripped)
            text = (obj.get("text") or "").strip()
            note = (obj.get("note") or "").strip()
            if text:
                return RunResult(ok=True, text=text, note=note or "完成", raw=raw)
        except Exception:
            pass

        # Best-effort: use the raw string as body, synthesize a note
        if raw_stripped:
            return RunResult(
                ok=True,
                text=raw_stripped,
                note=f"{employee['first_name_en']} 已产出章节",
                raw=raw,
            )

        return EmployeeRunner._fallback(
            employee, task, context, "empty LLM response",
        )

    @staticmethod
    def _fallback(
        employee: Dict[str, Any],
        task: SectionTask,
        context: RunContext,
        error: str,
    ) -> RunResult:
        # Deterministic stub that keeps the pipeline alive when the LLM is
        # unavailable (offline intranet, key not configured, etc.).
        text = (
            f"> _[本段由 {employee['first_name_en']} 占位 — LLM 暂不可用:"
            f"{error}]_\n\n"
            f"**章节目标**:{task.section_title}({task.section_kind})\n\n"
            f"结合用户诉求 “{context.brief[:120]}” 与已上传材料,"
            f"{employee['role_title_en']} 将在此处输出符合本章节类型的内容。"
            f"当前受限于环境,暂以结构占位呈现。"
        )
        return RunResult(
            ok=True,
            text=text,
            note=f"{employee['first_name_en']} 以占位完成(LLM 不可用)",
            raw=None,
            error=error,
        )


    # ------------------------------------------------------------------
    # Phase 1 — Requirement Analyst: generate structured execution plan
    # ------------------------------------------------------------------

    @classmethod
    async def run_planning(
        cls,
        *,
        brief: str,
        evidence_summary: str,
        clarifications: str,
        report_type_label: str,
        section_outline: list,
        timeout: float = 60.0,
    ) -> dict:
        """Ask intake_officer to produce a structured execution plan.

        Returns a dict with keys: execution_plan (list[PlanStep dicts]),
        data_needs (list of data queries), opening (str).
        Falls back to a minimal single-step plan on failure.
        """
        from app.agents.employees.registry import get_employee
        employee = get_employee("intake_officer") or {}
        outline_txt = "\n".join(
            f"  - {s.get('id')}: {s.get('title')} ({s.get('kind')})"
            for s in section_outline
        )

        sys_prompt = (
            "你是需求编译器 Elin（Intake Officer）。\n"
            "你的任务是把用户请求拆解为一份 **执行计划（execution_plan）**，"
            "告诉后续每一位同事「谁在哪个阶段做什么」。\n\n"
            "## 执行计划规则\n"
            "- phase 只有 3 种：data（数据获取）、synthesis（内容写作）、qa（质检）\n"
            "- data 步骤的 employee_id 必须是 data_wrangler 或 material_analyst\n"
            "- synthesis 步骤一一对应 section_outline 中的章节\n"
            "- qa 步骤的 employee_id 必须是 qa_reviewer\n"
            "- 只有上传材料中有明确数字/表格时才生成 data 步骤\n\n"
            "## 输出格式（严格 JSON，无代码围栏）\n"
            '{\n'
            '  "opening": "<一句话说明计划摘要，中文>",\n'
            '  "data_needs": ["<数据需求描述1>", ...],\n'
            '  "execution_plan": [\n'
            '    {"step_id":"<唯一id>","phase":"<data|synthesis|qa>","description":"<中文>",\n'
            '     "employee_id":"<id>","depends_on":["<step_id>"],"result_key":"<变量名>"}\n'
            '  ]\n'
            '}'
        )
        user_msg = (
            f"报告类型：{report_type_label}\n"
            f"用户需求：{brief}\n"
            f"已澄清：{clarifications or '无'}\n"
            f"材料摘要：\n{evidence_summary[:1500] or '（无上传材料）'}\n\n"
            f"章节骨架：\n{outline_txt}"
        )

        try:
            raw = await asyncio.wait_for(
                cls._llm_service().chat(
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    stream=False, temperature=0.3, max_tokens=1800,
                ),
                timeout=timeout,
            )
            raw = (raw or "").strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            plan_data = json.loads(raw)
        except Exception as exc:
            logger.warning("Planning LLM failed: %s", exc)
            plan_data = {
                "opening": "执行计划生成失败，使用默认流程",
                "data_needs": [],
                "execution_plan": [
                    {
                        "step_id": f"synth_{s.get('id','s'+str(i))}",
                        "phase": "synthesis",
                        "description": s.get("title", "章节"),
                        "employee_id": s.get("assigned_to", "structured_writer"),
                        "depends_on": [],
                        "result_key": s.get("id", f"s{i}"),
                    }
                    for i, s in enumerate(section_outline)
                ] + [{"step_id": "qa_final", "phase": "qa", "description": "最终质检",
                      "employee_id": "qa_reviewer", "depends_on": [], "result_key": "qa_verdict"}],
            }

        return plan_data

    # ------------------------------------------------------------------
    # Phase 2 — Data Engineer: generate Pandas code + sandbox execution
    # ------------------------------------------------------------------

    @classmethod
    async def run_data_step(
        cls,
        *,
        step_description: str,
        evidence_summary: str,
        data_context_so_far: dict,
        data_frames: dict,          # pre-loaded DataFrames for sandbox
        timeout_llm: float = 60.0,
        timeout_sandbox: float = 25.0,
    ) -> tuple:
        """Phase 2 core loop for one data step.

        1. Ask data_wrangler to write Pandas code.
        2. AST-check it.
        3. Execute in sandbox with pre-loaded DataFrames.
        4. Extract metrics from result.

        Returns (code: str, sandbox_result, metrics: dict, error: str|None).
        """
        from app.services.sandbox_service import execute, extract_metrics_from_result, SandboxSecurityError

        sys_prompt = (
            "你是数据整理员 Quinn（Data Wrangler）。\n"
            "根据用户给出的数据需求和已加载的 DataFrames，编写 Pandas 处理代码。\n\n"
            "## 规则\n"
            "1. 代码必须把关键指标赋给一个名为 `metrics` 的 Python dict，"
            "   如 `metrics = {'total_revenue': 1234, 'growth_rate': 0.12}`\n"
            "2. 禁止文件读写、网络、os、sys 等系统调用\n"
            "3. 可用变量：pd（pandas）、np（numpy）以及传入的 DataFrame 变量\n"
            "4. 只输出 Python 代码，不要解释，不要 markdown 围栏\n"
        )
        available_dfs = ", ".join(data_frames.keys()) if data_frames else "（无预加载 DataFrame）"
        context_summary = (
            "\n".join(f"  {k}: {v}" for k, v in list(data_context_so_far.items())[:10])
            or "（空）"
        )
        user_msg = (
            f"数据需求：{step_description}\n\n"
            f"可用 DataFrame 变量：{available_dfs}\n\n"
            f"已有 data_context：\n{context_summary}\n\n"
            f"材料摘要（供参考，不能联网）：\n{evidence_summary[:800]}"
        )

        code = ""
        try:
            code = await asyncio.wait_for(
                cls._llm_service().chat(
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    stream=False, temperature=0.2, max_tokens=800,
                ),
                timeout=timeout_llm,
            )
            code = (code or "").strip()
            # Strip markdown fences
            if code.startswith("```"):
                code = code.lstrip("`").lstrip("python\n").lstrip("\n").rstrip("`").strip()
        except Exception as exc:
            return "", None, {}, f"LLM failed: {exc}"

        # Execute in sandbox
        try:
            result = execute(code, extra_vars=data_frames, timeout_s=timeout_sandbox)
        except SandboxSecurityError as exc:
            return code, None, {}, f"Security violation: {exc}"

        metrics = extract_metrics_from_result(result) if result.ok else {}
        error = result.error if not result.ok else None
        return code, result, metrics, error

    # ------------------------------------------------------------------
    # Phase 3 — Synthesis with data_context injection
    # ------------------------------------------------------------------

    @classmethod
    async def run_synthesis(
        cls,
        *,
        employee_id: str,
        task: "SectionTask",
        context: "RunContext",
        data_context_summary: str,
        qa_retry_patch: str = "",
        steering_instruction: str = "",
        temperature: float = 0.5,
        max_tokens: int = 2800,
        timeout: float = 120.0,
    ) -> "RunResult":
        """Phase 3: synthesis with full data_context injected into prompt.

        steering_instruction: mid-flight 指令，由 Supervisor 通过 SubagentManager
        或 state.inject_steering() 注入，在 Employee 开始写作前附加到 prompt。
        这实现了 Fire-and-Steer 架构：Supervisor 可以在 subagent 执行期间
        修正执行路线，而不必等待任务完成后再重新派遣。

        qa_retry_patch: QA 反幻觉重试时注入的冲突修正说明。
        """
        employee = get_employee(employee_id)
        if not employee:
            return RunResult(ok=False, text="", note="", error=f"unknown employee {employee_id}")

        data_block = (
            "\n\n## ✅ 已验证数据（来自沙箱执行，可直接引用）\n"
            + data_context_summary
            if data_context_summary.strip() and data_context_summary != "（无已验证的数据）"
            else ""
        )
        retry_block = (
            "\n\n## ⚠️ 上一稿 QA 质检冲突（本次重写必须修正）\n" + qa_retry_patch
            if qa_retry_patch
            else ""
        )
        # mid-flight steering：Supervisor 在任务运行期间下发的修正指令
        steering_block = (
            "\n\n## 🎯 主管实时指令（优先级最高，必须体现在本章节中）\n" + steering_instruction
            if steering_instruction.strip()
            else ""
        )

        messages = [
            {"role": "system", "content": _role_system_prompt(employee)},
            {
                "role": "user",
                "content": (
                    context.as_context_block()
                    + data_block
                    + steering_block
                    + retry_block
                    + "\n\n---\n\n"
                    + task.as_user_message()
                ),
            },
        ]

        try:
            raw = await asyncio.wait_for(
                cls._llm_service().chat(
                    messages=messages, stream=False,
                    temperature=temperature, max_tokens=max_tokens,
                ),
                timeout=timeout,
            )
        except Exception as exc:
            logger.warning("Synthesis LLM failed for %s/%s: %s", employee_id, task.section_id, exc)
            return cls._fallback(employee, task, context, str(exc))

        return cls._parse(raw, employee, task, context)


# ---------------------------------------------------------------------------
# Section → employee mapping
# ---------------------------------------------------------------------------

# Fine-grained preference by section kind. Unknown kinds fall back to
# structured_writer, which is the "safe" default composer.
_KIND_TO_CATEGORY: Dict[str, str] = {
    "narrative": "writing",
    "narrative_with_chart": "chart",
    "table_with_narrative": "data",
    "matrix": "risk",
    "qa_list": "writing",
    "evidence_list": "material",
    "template_driven": "template",
}

_CATEGORY_FALLBACK_ORDER = [
    "writing", "material", "data", "chart", "risk",
    "compliance", "qa", "template", "layout", "intake",
]


def pick_employee_for_section(
    section: Dict[str, Any], team: List[str]
) -> str:
    """Return the best employee in ``team`` for the given section.

    Preference:
      1) ``assigned_to`` field in section (from LLM scoping plan)
      2) employee whose category matches the section's preferred category
      3) a structured_writer if present
      4) walk fallback categories
    """
    # 1) Honour explicit assignment from LLM scoping plan
    assigned = section.get("assigned_to", "")
    if assigned and assigned in team:
        return assigned

    wanted = _KIND_TO_CATEGORY.get(section.get("kind", ""), "writing")

    def _cat(eid: str) -> str:
        emp = get_employee(eid)
        return (emp or {}).get("category", "")

    # 2) Direct category match
    for eid in team:
        if _cat(eid) == wanted:
            return eid

    # 3) Structured writer is the universal composer
    for eid in team:
        if eid == "structured_writer":
            return eid

    # 4) Walk fallback categories
    for cat in _CATEGORY_FALLBACK_ORDER:
        for eid in team:
            if _cat(eid) == cat:
                return eid

    # Absolute last resort
    return team[0] if team else "structured_writer"
