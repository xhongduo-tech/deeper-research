"""
QAValidationService — data-point extraction and anti-hallucination checking.

Workflow (Phase 3 → Phase 4 gate):
  1. Extract all numeric/percentage claims from the synthesised markdown text.
  2. For each claim, look up the nearest matching key in ExecutionState.data_context.
  3. Compare: if the value differs by > tolerance → flag as hallucination.
  4. Return a structured verdict:  pass | fix_and_retry | block

The service is intentionally deterministic (regex-based) so it works without
an extra LLM call.  The *rationale* strings are human-readable and get injected
back into the re-synthesis prompt when a retry is needed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.execution_state import ExecutionState


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

# Matches patterns like  "85%", "1,234.56", "¥ 1.2亿", "123万"
_NUM_PATTERN = re.compile(
    r"""
    (?:                          # optional currency / unit prefix
        [¥$€£]\s*
    )?
    (?:
        -?                       # optional negative sign
        \d{1,3}(?:,\d{3})*       # comma-grouped integer
        (?:\.\d+)?               # optional decimal
        |
        -?\d+\.\d+               # plain decimal
        |
        -?\d+                    # plain integer
    )
    \s*
    (?:                          # optional unit / scale suffix
        %|万|亿|千|百|
        [Kk][Gg]?|[Mm][Bb]?|
        元|美元|千元|万元|亿元
    )?
    """,
    re.VERBOSE,
)

# Context window: capture up to 60 chars before the number as "label"
_CLAIM_CONTEXT = re.compile(
    r"(?P<label>[^\n]{0,60}?)\s+(?P<num>"
    + _NUM_PATTERN.pattern
    + r")\s*(?P<suffix>[^，。\n]{0,30})?",
    re.VERBOSE,
)


@dataclass
class DataClaim:
    label: str           # surrounding text used as key hint
    raw_value: str       # the number as it appears in the text
    float_value: Optional[float]


def extract_claims(text: str) -> List[DataClaim]:
    """Return all numeric claims found in a markdown string."""
    claims = []
    for m in _CLAIM_CONTEXT.finditer(text):
        raw = m.group("num").strip()
        # Normalise to float for comparison
        try:
            clean = re.sub(r"[¥$€£,\s%万亿千百元美kmKMGB]", "", raw)
            fv: Optional[float] = float(clean) if clean else None
        except ValueError:
            fv = None
        claims.append(DataClaim(
            label=(m.group("label") or "").strip(),
            raw_value=raw,
            float_value=fv,
        ))
    return claims


# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

@dataclass
class ClaimVerdict:
    claim: DataClaim
    matched_key: Optional[str]
    expected_value: Optional[Any]
    passed: bool
    reason: str


@dataclass
class QAVerdict:
    section_id: str
    overall: str                         # "pass" | "fix_and_retry" | "block"
    claim_verdicts: List[ClaimVerdict] = field(default_factory=list)
    hallucination_count: int = 0
    retry_prompt_patch: str = ""         # injected into re-synthesis prompt

    @property
    def ok(self) -> bool:
        return self.overall == "pass"


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _fuzzy_key_match(label: str, data_context: Dict[str, Any]) -> Optional[str]:
    """Return the best-matching data_context key for a claim label."""
    if not data_context:
        return None
    label_lower = label.lower()
    # Exact substring match
    for key in data_context:
        if key.lower() in label_lower or label_lower in key.lower():
            return key
    # Token overlap
    label_tokens = set(re.split(r"\W+", label_lower))
    best_key, best_score = None, 0
    for key in data_context:
        key_tokens = set(re.split(r"\W+", key.lower()))
        score = len(label_tokens & key_tokens)
        if score > best_score:
            best_score, best_key = score, key
    return best_key if best_score > 0 else None


def _values_match(claim_float: Optional[float], expected: Any, tolerance: float = 0.05) -> bool:
    """True if claim value is within tolerance of the expected value."""
    if claim_float is None:
        return True  # can't check non-numeric claims
    try:
        exp_float = float(re.sub(r"[^0-9.\-]", "", str(expected)))
    except (ValueError, TypeError):
        return True  # can't parse expected → don't flag
    if exp_float == 0:
        return abs(claim_float) < 1
    return abs(claim_float - exp_float) / abs(exp_float) <= tolerance


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_section(
    section_id: str,
    text: str,
    state: ExecutionState,
    tolerance: float = 0.05,
    max_unverified: int = 3,
) -> QAVerdict:
    """
    Validate all numeric claims in *text* against state.data_context.

    Returns a QAVerdict with overall = "pass" / "fix_and_retry" / "block".
    """
    claims = extract_claims(text)
    verdicts: List[ClaimVerdict] = []
    hallucination_count = 0

    for claim in claims:
        matched_key = _fuzzy_key_match(claim.label, state.data_context)
        if matched_key:
            entry = state.data_context[matched_key]
            expected_val = entry.get("value")
            passed = _values_match(claim.float_value, expected_val, tolerance)
            reason = (
                "✓ matches data_context"
                if passed
                else f"✗ claim={claim.raw_value} but data_context[{matched_key}]={expected_val}"
            )
            if not passed:
                hallucination_count += 1
        else:
            # No matching metric found — only flag if code_verified data exists
            # and claim is large (> 100 or %) to avoid false positives on
            # simple ordinal numbers ("第1章", "3条建议" etc.)
            is_suspect = (
                claim.float_value is not None
                and (claim.raw_value.endswith("%") or (claim.float_value or 0) > 100)
                and bool(state.data_context)
            )
            passed = not is_suspect
            matched_key = None
            expected_val = None
            reason = (
                "⚠ unverified large number (no matching data_context key)"
                if is_suspect
                else "– small/ordinal number, skipped"
            )
            if is_suspect:
                hallucination_count += 1

        verdicts.append(ClaimVerdict(
            claim=claim,
            matched_key=matched_key,
            expected_value=expected_val,
            passed=passed,
            reason=reason,
        ))

    # Decide overall verdict
    if hallucination_count == 0:
        overall = "pass"
    elif hallucination_count <= max_unverified:
        overall = "fix_and_retry"
    else:
        overall = "block"

    # Build retry prompt patch
    patch_lines: List[str] = []
    for v in verdicts:
        if not v.passed:
            patch_lines.append(
                f"- 数据冲突：「{v.claim.raw_value}」（出现在「{v.claim.label[:50]}」附近）"
                f" — {v.reason}。请修正或删除该数据声明。"
            )
    retry_patch = (
        "\n\n⚠️ QA 发现以下数据冲突，请在重写时逐条修正：\n"
        + "\n".join(patch_lines)
        if patch_lines
        else ""
    )

    return QAVerdict(
        section_id=section_id,
        overall=overall,
        claim_verdicts=verdicts,
        hallucination_count=hallucination_count,
        retry_prompt_patch=retry_patch,
    )


# ---------------------------------------------------------------------------
# Security scanning helper
# ---------------------------------------------------------------------------

# Patterns that indicate PII / sensitive data leaked into outputs
_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{15,18}\b"),                              # ID card / bank account
    re.compile(r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[012])(?:0[1-9]|[12]\d|3[01])\d{3}[\dX]\b"),  # ID number
    re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"),  # credit card
    re.compile(r"\b1[3-9]\d{9}\b"),                           # CN mobile
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
]


def security_scan(text: str) -> Tuple[bool, List[str]]:
    """
    Scan *text* for sensitive patterns.
    Returns (clean: bool, findings: list[str]).
    """
    findings = []
    for pattern in _SENSITIVE_PATTERNS:
        for m in pattern.finditer(text):
            findings.append(f"Sensitive match: {m.group()[:12]}... (pattern: {pattern.pattern[:40]})")
    return len(findings) == 0, findings
