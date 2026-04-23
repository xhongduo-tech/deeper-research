"""
EscalationService -- Expert Escalation Engine.

当普通员工（Regular Employee）遇到以下情况时，自动或手动升级为对应的
Expert Agent（专家智能体）处理：

升级触发条件（优先级从高到低）：
  1. 手动触发（Manual）   -- 用户或 Supervisor 显式请求专家介入
  2. 质检阻断（QA Block） -- Sage 判定 block，连续 QA 重试次数 >= 2
  3. 复杂度超标（Complexity） -- 任务复杂度评分 > COMPLEXITY_THRESHOLD
  4. 执行失败（Error）    -- LLM 调用失败或沙箱安全拦截

专家能力特点（vs 普通员工）：
  - 使用更强的模型（expert_model，通常是更大参数版本）
  - 更长的 token 预算（max_tokens 翻倍）
  - 更长的超时（timeout 扩展 1.5x）
  - 多步推理提示（chain-of-thought + self-verification loop）
  - Expert 还接受失败上下文（前次错误 + 已产出内容），避免重蹈覆辙

复杂度评分维度（0~1 浮点数，加权求和）：
  - brief 长度 > 500 chars          +0.15
  - 证据片段数量 > 10                +0.20
  - 文档数量 > 3                    +0.10
  - 章节类型（matrix/chart/template）+0.20
  - 数据计算关键词命中               +0.15
  - 已有 QA 失败记录                +0.20（最高优先级附加分）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPLEXITY_THRESHOLD = 0.60     # 超过此值自动升级
QA_RETRY_ESCALATE_AT = 2        # QA 重试次数达到此值时强制升级
ERROR_ESCALATE_AT = 1           # 执行错误次数达到此值时升级

# 高复杂度章节类型
HIGH_COMPLEXITY_KINDS = frozenset({
    "matrix", "narrative_with_chart", "table_with_narrative",
    "risk_matrix", "multi_section_synthesis",
})

# 数据计算关键词（命中 > 2 个则加分）
DATA_KEYWORDS = frozenset({
    "分析", "计算", "对比", "预测", "回归", "趋势", "同比", "环比",
    "统计", "建模", "相关性", "异常", "聚类", "分布", "估算", "敞口",
})


# ---------------------------------------------------------------------------
# Escalation reason codes
# ---------------------------------------------------------------------------

class EscalationReason(str, Enum):
    MANUAL     = "manual"        # 用户/Supervisor 手动触发
    QA_BLOCK   = "qa_block"      # QA 阻断，连续失败
    COMPLEXITY = "complexity"    # 任务复杂度超标
    ERROR      = "error"         # LLM/沙箱执行失败
    NONE       = "none"          # 无需升级


# ---------------------------------------------------------------------------
# Escalation decision data class
# ---------------------------------------------------------------------------

@dataclass
class EscalationDecision:
    should_escalate: bool
    reason: EscalationReason
    complexity_score: float             # 0.0 ~ 1.0
    expert_employee_id: str             # 目标专家 employee ID
    context_note: str = ""             # 传给专家的上下文说明

    def as_briefing_block(self) -> str:
        """Return a text block to inject into the expert agent's prompt."""
        if not self.should_escalate:
            return ""
        lines = [
            "## 🔴 Expert Mode — 专家接管说明",
            f"触发原因：{self.reason.value}",
            f"任务复杂度评分：{self.complexity_score:.2f}",
        ]
        if self.context_note:
            lines.append(f"背景说明：{self.context_note}")
        lines += [
            "",
            "**专家行动要求**：",
            "1. 先用 50~100 字内部思考（Think）梳理关键难点",
            "2. 给出明确的处理方案（Plan）",
            "3. 按方案执行并产出最终结果（Execute）",
            "4. 在 note 字段中用一句话说明与普通处理的关键差异（Verify）",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Complexity scorer
# ---------------------------------------------------------------------------

def score_complexity(
    task_instruction: str,
    task_kind: str,
    brief: str,
    evidence_count: int,
    doc_count: int,
    qa_retry_count: int = 0,
    prior_error: Optional[str] = None,
) -> float:
    """Compute a task complexity score in [0, 1].

    Higher score = more likely to benefit from expert escalation.
    """
    score = 0.0

    # Brief verbosity — longer brief usually means more nuanced requirement
    if len(brief) > 500:
        score += 0.10
    if len(brief) > 1000:
        score += 0.05

    # Evidence volume — more snippets means higher cross-reference demand
    if evidence_count >= 6:
        score += 0.10
    if evidence_count >= 12:
        score += 0.10

    # Document volume
    if doc_count >= 3:
        score += 0.08
    if doc_count >= 6:
        score += 0.07

    # Section kind
    if task_kind in HIGH_COMPLEXITY_KINDS:
        score += 0.20

    # Data / analytical keywords in instruction
    hit_count = sum(1 for kw in DATA_KEYWORDS if kw in task_instruction)
    if hit_count >= 2:
        score += 0.10
    if hit_count >= 4:
        score += 0.05

    # Prior QA failures — strongest signal
    if qa_retry_count >= 1:
        score += 0.15
    if qa_retry_count >= QA_RETRY_ESCALATE_AT:
        score += 0.15   # guarantees > threshold

    # Prior execution error — immediate additional weight
    if prior_error:
        score += 0.10

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# EscalationService
# ---------------------------------------------------------------------------

class EscalationService:
    """Decides whether and how to escalate an employee task to its expert.

    This is purely stateless logic — state is tracked in SubagentManager
    and execution_state.  Call ``decide()`` once per task before dispatch.
    """

    @staticmethod
    def decide(
        *,
        employee_id: str,
        task_instruction: str,
        task_kind: str,
        brief: str,
        evidence_count: int,
        doc_count: int,
        qa_retry_count: int = 0,
        error_count: int = 0,
        prior_error: Optional[str] = None,
        manual_override: bool = False,
    ) -> EscalationDecision:
        """Return an EscalationDecision for the given task context."""
        from app.agents.employees.registry import get_expert_for

        expert_id = get_expert_for(employee_id)
        if not expert_id:
            # This employee has no expert — never escalate
            return EscalationDecision(
                should_escalate=False,
                reason=EscalationReason.NONE,
                complexity_score=0.0,
                expert_employee_id=employee_id,
            )

        # --- Check triggers in priority order ---

        # 1. Manual override
        if manual_override:
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.MANUAL,
                complexity_score=1.0,
                expert_employee_id=expert_id,
                context_note="由 Supervisor 手动触发专家介入",
            )

        # 2. QA block threshold
        if qa_retry_count >= QA_RETRY_ESCALATE_AT:
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.QA_BLOCK,
                complexity_score=1.0,
                expert_employee_id=expert_id,
                context_note=(
                    f"已连续 {qa_retry_count} 次 QA 质检未通过，"
                    f"普通员工无法修正，升级为专家处理"
                ),
            )

        # 3. Error threshold
        if error_count >= ERROR_ESCALATE_AT:
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.ERROR,
                complexity_score=0.9,
                expert_employee_id=expert_id,
                context_note=f"执行失败（{prior_error or '未知错误'}），升级为专家重试",
            )

        # 4. Complexity score
        complexity = score_complexity(
            task_instruction=task_instruction,
            task_kind=task_kind,
            brief=brief,
            evidence_count=evidence_count,
            doc_count=doc_count,
            qa_retry_count=qa_retry_count,
            prior_error=prior_error,
        )

        if complexity >= COMPLEXITY_THRESHOLD:
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.COMPLEXITY,
                complexity_score=complexity,
                expert_employee_id=expert_id,
                context_note=(
                    f"任务复杂度评分 {complexity:.2f} 超过阈值 {COMPLEXITY_THRESHOLD}，"
                    f"自动升级为专家模式"
                ),
            )

        # No escalation
        return EscalationDecision(
            should_escalate=False,
            reason=EscalationReason.NONE,
            complexity_score=complexity,
            expert_employee_id=employee_id,
        )

    @staticmethod
    def format_escalation_log(
        decision: EscalationDecision,
        original_employee_id: str,
    ) -> str:
        """Return a human-readable log entry for this escalation."""
        if not decision.should_escalate:
            return (
                f"[Escalation] {original_employee_id} 无需升级 "
                f"(complexity={decision.complexity_score:.2f})"
            )
        return (
            f"[Escalation] {original_employee_id} → {decision.expert_employee_id} "
            f"| reason={decision.reason.value} "
            f"| complexity={decision.complexity_score:.2f} "
            f"| note={decision.context_note}"
        )
