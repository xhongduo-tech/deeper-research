"""Numeric claim extraction and verification utilities. Ported from simple_pipeline.py."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING


def _normalize_number_str(num: str) -> set[str]:
    """Return normalized variants for fuzzy numeric matching."""
    variants: set[str] = {num}
    stripped = num.replace(",", "").replace("，", "").strip()
    is_pct = stripped.endswith("%")
    core = stripped.rstrip("%").strip()
    try:
        val = float(core)
        if val == int(val):
            variants.update({str(int(val)), f"{int(val)}%", f"{int(val)}.0", f"{int(val)}.0%"})
        variants.update({
            f"{val:.1f}", f"{val:.2f}",
            f"{val:.1f}%", f"{val:.2f}%",
        })
        if is_pct:
            frac = val / 100
            variants.update({f"{frac:.2f}", f"{frac:.3f}", f"{frac:.4f}"})
    except (ValueError, OverflowError):
        pass
    return variants


def extract_numeric_baseline(uploaded_texts: list[str] | None) -> dict[str, dict]:
    """Extract all numeric claims from uploaded texts as a baseline dictionary."""
    if not uploaded_texts:
        return {}

    from app.services.claim_verification_service import extract_numeric_claims

    baseline: dict[str, dict] = {}
    for source in uploaded_texts:
        source_name = "参考材料"
        content = source
        m = re.match(r"【([^】]+)】\s*(.*)", source, re.DOTALL)
        if m:
            source_name = m.group(1)
            content = m.group(2)
        if source_name.startswith(("模板参考", "风格参考")):
            continue

        claims = extract_numeric_claims(content)
        for claim in claims:
            key = claim["text"][:80]
            baseline[key] = {
                "numbers": claim["numbers"],
                "source": source_name,
                "context": claim["text"],
                "claim_type": claim["claim_type"],
                "is_high_stakes": claim["is_high_stakes"],
            }
    return baseline


def build_number_lookup_set(numeric_baseline: dict, evidence_block: str) -> set[str]:
    """Build a normalized set of all known source numbers for fast lookup."""
    known: set[str] = set()
    for info in numeric_baseline.values():
        for n in info.get("numbers", []):
            known.update(_normalize_number_str(n))
    for raw_num in re.findall(r"\d[\d,，.]*\.?\d*%?", evidence_block or ""):
        known.update(_normalize_number_str(raw_num))
    return known


def verify_section_claims(
    content: str,
    numeric_baseline: dict,
    evidence_block: str,
    section_index: int = 0,
) -> float:
    """Verify numeric claims against baseline and evidence.

    Returns ratio of unverified claims (0.0 = all verified, 1.0 = none verified).
    """
    from app.services.claim_verification_service import extract_numeric_claims

    claims = extract_numeric_claims(content)
    if not claims:
        return 0.0

    known_numbers = build_number_lookup_set(numeric_baseline, evidence_block)

    eligible = 0
    unverified = 0
    for claim in claims:
        if claim.get("is_declared_assumption"):
            continue
        if claim.get("has_inline_source"):
            continue
        eligible += 1
        found = any(
            _normalize_number_str(n) & known_numbers
            for n in claim.get("numbers", [])
        )
        if not found:
            unverified += 1

    return unverified / eligible if eligible else 0.0


def parse_branch_context(uploaded_texts: list[str] | None) -> dict | None:
    """Parse structured branch/entity context embedded by excel_grounding."""
    if not uploaded_texts:
        return None
    for src in uploaded_texts:
        m = re.search(
            r"【分行结构】dimension_col=([^|]+)\s*\|\s*kpi_cols=([^|]+)\s*\|\s*branch_count=(\d+)\s*\|\s*branches=(.+?)(?:\n|$)",
            src,
        )
        if m:
            return {
                "is_branch_data": True,
                "dimension_col": m.group(1).strip(),
                "kpi_cols": [c.strip() for c in m.group(2).split(",") if c.strip()],
                "branch_count": int(m.group(3)),
                "branches_preview": m.group(4).strip(),
            }
    return None
