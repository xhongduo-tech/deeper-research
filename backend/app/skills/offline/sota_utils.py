"""SOTA Skill Enhancement Utilities.

Provides reusable patterns for high-quality LLM skill execution:
- Chain-of-Thought (CoT) forcing
- Self-critique + rewrite loops
- Adversarial (red-team) review
- Quality scoring with calibration
- Structured JSON output with validation

Reference patterns:
- OpenAI's "6 strategies for getting better results"
- Anthropic's prompt engineering guide
- Google's "Prompt Engineering Whitepaper"
- Stanford's DSPy framework patterns
"""
import json
import logging
from typing import Any, Callable

from app.services.llm_service import chat, chat_json

logger = logging.getLogger(__name__)


# ── Quality Dimensions (shared across skills) ────────────────────────────────

QUALITY_DIMENSIONS = {
    "data_grounding": "所有数字/事实有明确来源，无幻觉数据",
    "logical_rigor": "因果链条清晰，推论从证据中自然推导",
    "specificity": "无空洞表述，每个论点有具体案例/数字支撑",
    "insight_depth": "提供非显而易见的洞察，而非常识重述",
    "structural_clarity": "层级清晰，读者能快速提取核心信息",
    "actionability": "建议具体可执行，有明确责任方和时间节点",
    "audience_fit": "语言风格和深度适配目标受众",
    "constraint_compliance": "满足所有格式、长度、规范约束",
}


# ── Chain-of-Thought Writer ──────────────────────────────────────────────────

async def cot_write(
    system_persona: str,
    task_description: str,
    thinking_prompt: str,
    writing_prompt: str,
    temperature: float = 0.4,
    max_tokens: int = 2000,
) -> str:
    """Force CoT: first thinking/outline, then writing.

    Pattern: System(persona) → User(thinking) → Assistant(thinking)
             → User(writing) → Assistant(writing)
    """
    messages = [
        {"role": "system", "content": system_persona},
        {"role": "user", "content": thinking_prompt},
    ]
    thinking = await chat(messages, temperature=temperature, max_tokens=max_tokens)

    messages.append({"role": "assistant", "content": thinking})
    messages.append({"role": "user", "content": writing_prompt})

    output = await chat(messages, temperature=temperature, max_tokens=max_tokens)
    return output


# ── Self-Critique ────────────────────────────────────────────────────────────

async def self_critique(
    draft: str,
    topic: str,
    dimensions: list[str] | None = None,
    persona: str = "严格的质量评审专家",
    temperature: float = 0.25,
) -> dict[str, Any]:
    """Multi-dimensional self-critique with structured scoring.

    Returns:
        {
            "critique_text": "原始评审文本",
            "scores": {"维度名": {"score": 0-10, "issue": "问题描述", "fix": "改进建议"}},
            "overall_score": 0-10,
            "top_issues": ["issue1", "issue2"],
        }
    """
    dims = dimensions or list(QUALITY_DIMENSIONS.keys())
    dim_descriptions = "\n".join(
        f"{i+1}. **{k}**（{QUALITY_DIMENSIONS[k]}）"
        for i, k in enumerate(dims)
    )

    system = f"""你是{persona}。你的任务是对文本进行多维度质量评审。

对每个维度给出：
- score: 1-10分（10=完美，1=严重缺陷）
- issue: 具体发现了什么问题（引用原文片段）
- fix: 可执行的改进建议

输出必须是JSON格式：
{{
  "scores": {{
    "维度名": {{"score": 8, "issue": "...", "fix": "..."}}
  }},
  "overall_score": 7.5,
  "top_issues": ["最重要的问题1", "问题2"],
  "rewrite_priority": ["最需要重写的部分1", "部分2"]
}}"""

    user = f"""请评审以下关于"{topic}"的草稿。

## 草稿内容
{draft[:3000]}

## 评审维度
{dim_descriptions}

请输出JSON格式的评审结果。"""

    parsed = await chat_json(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=2000,
    )

    if "error" in parsed and "_raw_response" not in parsed:
        # Fallback: return text critique
        fallback = await chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=2000,
        )
        return {
            "critique_text": fallback,
            "scores": {},
            "overall_score": 5.0,
            "top_issues": ["JSON解析失败，使用文本评审"],
        }

    scores = parsed.get("scores", {})
    overall = parsed.get("overall_score", 5.0)
    top_issues = parsed.get("top_issues", [])

    # Compute overall from individual scores if missing
    if not overall and scores:
        overall = round(
            sum(s.get("score", 5) for s in scores.values()) / len(scores), 1
        )

    return {
        "critique_text": json.dumps(parsed, ensure_ascii=False, indent=2),
        "scores": scores,
        "overall_score": overall or 5.0,
        "top_issues": top_issues,
        "rewrite_priority": parsed.get("rewrite_priority", []),
    }


# ── Adversarial Review ───────────────────────────────────────────────────────

async def adversarial_review(
    output: str,
    topic: str,
    reviewer_persona: str = "挑剔的红队分析师",
    temperature: float = 0.35,
) -> dict[str, Any]:
    """Red-team review: challenge assumptions, find weak evidence, spot hallucinations.

    Returns:
        {
            "challenges": [{"claim": "被挑战的论点", "weakness": "弱点", "severity": "high|medium|low"}],
            "hallucination_risk": "评估文本中是否存在幻觉数据",
            "mitigation": "如何修正每个挑战",
        }
    """
    system = f"""你是{reviewer_persona}。你的任务是像诉讼中的对方律师一样，
尽全力找出文本中的漏洞、弱证据、过度推论和可能的幻觉。

挑战类型：
1. **证据不足**：某个结论缺乏足够数据支撑
2. **因果跳跃**：从A到B的推导缺少中间环节
3. **选择性偏差**：只呈现了支持观点的证据
4. **过度概括**：从有限样本推出普遍结论
5. **数字幻觉**：某个数字看起来像是编造的
6. **时效性问题**：使用了过时或即将失效的数据
7. **幸存者偏差**：只分析了成功案例

输出JSON格式：
{{
  "challenges": [
    {{"claim": "被挑战的具体论点", "weakness": "弱点描述", "severity": "high|medium|low"}}
  ],
  "hallucination_risk": "高/中/低，并说明原因",
  "overall_verdict": "文本整体可信度评估",
  "mitigation_suggestions": ["修正建议1", "建议2"]
}}"""

    user = f"""请对以下关于"{topic}"的内容进行红队挑战评审。

## 内容
{output[:3000]}

请输出JSON格式的评审结果。"""

    parsed = await chat_json(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=2000,
    )

    if "error" in parsed:
        return {
            "challenges": [],
            "hallucination_risk": "unknown",
            "overall_verdict": "评审失败",
            "mitigation_suggestions": [],
        }

    return {
        "challenges": parsed.get("challenges", []),
        "hallucination_risk": parsed.get("hallucination_risk", "unknown"),
        "overall_verdict": parsed.get("overall_verdict", ""),
        "mitigation_suggestions": parsed.get("mitigation_suggestions", []),
    }


# ── Rewrite with Critique ────────────────────────────────────────────────────

async def rewrite_with_critique(
    draft: str,
    critique: dict,
    topic: str,
    persona: str,
    format_rules: str = "",
    temperature: float = 0.35,
    max_tokens: int = 2000,
) -> str:
    """Rewrite draft addressing all critique issues."""
    top_issues = "\n".join(
        f"{i+1}. {issue}" for i, issue in enumerate(critique.get("top_issues", [])[:5])
    )
    rewrite_priority = "\n".join(
        f"{i+1}. {item}" for i, item in enumerate(critique.get("rewrite_priority", [])[:5])
    )

    system = f"""你是{persona}。你收到了评审意见，需要基于这些意见对草稿进行实质性重写。

重写原则：
- 直接解决评审中指出的每个问题
- 保留原稿中好的部分
- 不引入新的问题
- 输出完整的重写后正文"""

    user = f"""请根据以下评审意见，对草稿进行实质性重写。

## 原始草稿
{draft[:2500]}

## 评审发现的主要问题
{top_issues or "（无具体问题记录）"}

## 优先重写部分
{rewrite_priority or "（无优先级记录）"}

## 格式要求
{format_rules or "保持原有格式"}

请直接输出重写后的完整正文。"""

    return await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ── Quality Gate ───────────────────────────────────────────────────────────────

async def quality_gate(
    output: str,
    topic: str,
    min_score: float = 7.0,
    enable_adversarial: bool = True,
) -> dict[str, Any]:
    """Full quality gate: critique + adversarial + score.

    Returns comprehensive quality report.
    """
    critique = await self_critique(output, topic)
    adversarial = await adversarial_review(output, topic) if enable_adversarial else None

    overall = critique["overall_score"]
    passed = overall >= min_score

    report = {
        "passed": passed,
        "overall_score": overall,
        "min_score": min_score,
        "critique": critique,
        "adversarial": adversarial,
        "recommendation": "PASS" if passed else "REWRITE",
    }

    if not passed:
        report["improvement_areas"] = critique.get("top_issues", [])
        if adversarial:
            high_sev = [c for c in adversarial.get("challenges", []) if c.get("severity") == "high"]
            if high_sev:
                report["improvement_areas"].append(
                    f"红队发现{len(high_sev)}个高风险挑战需处理"
                )

    return report


# ── Structured JSON Output with Repair ─────────────────────────────────────────

async def structured_generate(
    system: str,
    user: str,
    schema_description: str,
    output_schema: dict,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    max_repair: int = 2,
) -> dict[str, Any]:
    """Generate structured JSON with auto-repair on validation failure.

    Args:
        system: System prompt
        user: User prompt
        schema_description: Human-readable schema description
        output_schema: Expected JSON schema shape
        temperature: LLM temperature
        max_tokens: Max tokens
        max_repair: Max repair attempts

    Returns:
        {"data": parsed_dict, "raw": original_text, "repair_count": n, "error": None|str}
    """
    schema_json = json.dumps(output_schema, ensure_ascii=False, indent=2)

    full_system = f"""{system}

你必须输出严格符合以下JSON Schema的JSON对象，不要包含任何其他文本：

{schema_description}

Schema:
{schema_json}

输出规则：
1. 只输出JSON，不要markdown代码块
2. 所有必填字段必须有值
3. 字符串字段不能为空""
4. 数组字段不能为空[]（除非schema允许）"""

    parsed = await chat_json(
        [{"role": "system", "content": full_system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    repair_count = 0
    while "error" in parsed and repair_count < max_repair:
        repair_prompt = f"""你之前的JSON输出有错误：{parsed.get('error')}

请修正JSON输出，确保完全符合schema要求。

Schema:
{schema_json}

请只输出修正后的JSON对象。"""

        parsed = await chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": parsed.get("_raw_response", "")},
                {"role": "user", "content": repair_prompt},
            ],
            temperature=max(0.1, temperature - 0.1),
            max_tokens=max_tokens,
        )
        repair_count += 1

    if "error" in parsed:
        return {
            "data": None,
            "raw": parsed.get("_raw_response", ""),
            "repair_count": repair_count,
            "error": parsed["error"],
        }

    return {
        "data": parsed,
        "raw": parsed.get("_raw_response", json.dumps(parsed, ensure_ascii=False)),
        "repair_count": repair_count,
        "error": None,
    }
