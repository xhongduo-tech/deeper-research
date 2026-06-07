"""Offline claim and numeric evidence verification for report delivery."""
from __future__ import annotations

import re
from collections import Counter

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|％|万|亿|元|万元|亿元|年|月|日|项|个|次|倍|人|人次)?")
SOURCE_MARKER_RE = re.compile(r"(来源|口径|资料缺口|假设|测算|估算|上传|知识库|见文末)")
HIGH_STAKES_RE = re.compile(r"(收入|成本|利润|增长|下降|同比|环比|占比|金额|预算|预测|估值|风险|合规|赔偿|罚款|ROI|KPI)", re.I)


def extract_numeric_claims(text: str) -> list[dict]:
    """Extract sentences/table rows containing numeric claims."""
    claims: list[dict] = []
    blocks = re.split(r"(?<=[。！？!?])\s+|\n+", text or "")
    for idx, block in enumerate(blocks):
        line = block.strip()
        if not line:
            continue
        nums = NUMBER_RE.findall(line)
        if not nums:
            continue
        if re.match(r"^\|?\s*[-:| ]+\|?\s*$", line):
            continue
        claims.append({
            "id": f"C{len(claims) + 1:03d}",
            "text": line[:260],
            "numbers": [n.strip() for n in nums[:8]],
            "claim_type": _infer_claim_type(line),
            "location": f"block:{idx + 1}",
            "has_inline_source": bool(SOURCE_MARKER_RE.search(line)),
            "is_declared_assumption": bool(re.search(r"资料缺口|假设|估算|测算", line)),
            "is_high_stakes": bool(HIGH_STAKES_RE.search(line)),
        })
    return claims


def _infer_claim_type(text: str) -> str:
    if re.search(r"(同比|环比|增长|下降|提升|降低|趋势|CAGR)", text or "", re.I):
        return "trend"
    if re.search(r"(因为|导致|推动|归因|原因|影响|带来)", text or ""):
        return "causal"
    if re.search(r"(预测|预计|估算|测算|假设|目标)", text or ""):
        return "forecast_or_assumption"
    return "number"


def _tokens(text: str) -> set[str]:
    cn = re.findall(r"[\u4e00-\u9fff]{2,}", text or "")
    latin = re.findall(r"[A-Za-z0-9_]{2,}", text or "")
    return set(cn + [t.lower() for t in latin])


def _source_anchor(content: str, numbers: list[str], claim_tokens: set[str]) -> str:
    if not content:
        return ""
    sentences = re.split(r"(?<=[。！？!?])\s+|\n+", content)
    best = ""
    best_score = -1
    for sentence in sentences[:120]:
        compact_sentence = re.sub(r"\s+", "", sentence)
        number_hits = sum(
            1 for number in numbers
            if re.sub(r"\s+", "", number) in compact_sentence
        )
        token_hits = len(_tokens(sentence) & claim_tokens)
        score = number_hits * 3 + token_hits
        if score > best_score:
            best_score = score
            best = sentence.strip()
    return best[:220]


def _source_match_score(claim: dict, source: dict) -> tuple[float, str, dict]:
    content = source.get("content", "") or ""
    title = source.get("title", "") or ""
    if not content:
        return 0.0, "来源无可检索文本", {
            "support_level": "unverified",
            "number_coverage": 0,
            "matched_numbers": [],
            "matched_terms": [],
            "source_anchor": "",
        }

    score = 0.0
    reasons = []
    content_compact = re.sub(r"\s+", "", content)
    matched_numbers = []
    for number in claim.get("numbers", []):
        compact_number = re.sub(r"\s+", "", number)
        if compact_number and compact_number in content_compact:
            matched_numbers.append(number)
    number_coverage = len(matched_numbers) / max(len(claim.get("numbers", [])), 1)
    if matched_numbers:
        score += 0.48 + min(0.18, number_coverage * 0.18)
        reasons.append("数字覆盖:" + ",".join(matched_numbers[:4]))

    claim_tokens = _tokens(claim.get("text", ""))
    source_tokens = _tokens(title + "\n" + content[:4000])
    matched_terms = sorted(claim_tokens & source_tokens)[:12]
    if claim_tokens and source_tokens:
        overlap = len(claim_tokens & source_tokens) / max(len(claim_tokens), 1)
        score += min(0.4, overlap * 0.8)
        if overlap >= 0.25:
            reasons.append(f"关键词重合:{overlap:.0%}")

    if claim.get("has_inline_source"):
        score += 0.08
        reasons.append("正文含来源/口径提示")

    support_level = "direct" if number_coverage >= 0.99 and matched_terms else "calculated" if matched_numbers else "inferred" if matched_terms else "unverified"
    lineage = {
        "support_level": support_level,
        "number_coverage": round(number_coverage, 3),
        "matched_numbers": matched_numbers[:8],
        "matched_terms": matched_terms,
        "source_anchor": _source_anchor(content, claim.get("numbers", []), claim_tokens),
    }
    return min(score, 1.0), "；".join(reasons) or "未发现强匹配", lineage


def verify_claims_against_sources(text: str, source_registry: list[dict]) -> dict:
    """Verify numeric claims against uploaded files / KB evidence offline."""
    claims = extract_numeric_claims(text)
    verified = []
    unverified = []
    assumed = []

    for claim in claims:
        if claim["is_declared_assumption"]:
            claim["status"] = "assumption"
            claim["confidence"] = 0.55 if claim["has_inline_source"] else 0.45
            claim["source_id"] = None
            claim["source_anchor"] = ""
            claim["support_level"] = "assumption"
            claim["numeric_lineage"] = {
                "numbers": claim.get("numbers", []),
                "formula_or_method": "正文已声明为资料缺口/假设/测算",
                "unit_period_scope": "见原句",
            }
            claim["evidence"] = "正文已声明为资料缺口/假设/测算"
            assumed.append(claim)
            continue

        best = (0.0, None, "未匹配", {})
        for source in source_registry or []:
            score, reason, lineage = _source_match_score(claim, source)
            if score > best[0]:
                best = (score, source, reason, lineage)

        score, source, reason, lineage = best
        number_coverage = lineage.get("number_coverage", 0)
        status = (
            "verified"
            if score >= 0.62 and (not claim.get("numbers") or number_coverage >= 0.99)
            else "weak"
            if score >= 0.38
            else "unverified"
        )
        enriched = {
            **claim,
            "confidence": round(score, 2),
            "source_id": source.get("id") if source else None,
            "source_title": source.get("title") if source else None,
            "source_anchor": lineage.get("source_anchor", ""),
            "support_level": lineage.get("support_level", "unverified"),
            "number_coverage": lineage.get("number_coverage", 0),
            "matched_numbers": lineage.get("matched_numbers", []),
            "matched_terms": lineage.get("matched_terms", []),
            "numeric_lineage": {
                "numbers": claim.get("numbers", []),
                "source_id": source.get("id") if source else None,
                "source_anchor": lineage.get("source_anchor", ""),
                "support_level": lineage.get("support_level", "unverified"),
                "formula_or_method": "direct_source_match" if lineage.get("support_level") == "direct" else "semantic_or_partial_match",
                "unit_period_scope": "见原句和来源锚点",
            },
            "evidence": reason,
            "status": status,
        }
        if enriched["status"] == "verified":
            verified.append(enriched)
        else:
            unverified.append(enriched)

    total = len(claims)
    verified_ratio = (len(verified) + 0.5 * len(assumed)) / total if total else 1.0
    severe = [
        c for c in unverified
        if (
            len(c.get("numbers", [])) > 0
            and (c.get("is_high_stakes") or not c.get("has_inline_source") or c.get("number_coverage", 0) < 0.5)
        )
    ]
    status_counts = Counter(c["status"] for c in verified + unverified + assumed)
    claim_source_map = []
    for item in verified + assumed + unverified:
        claim_source_map.append({
            "claim_id": item.get("id"),
            "claim": item.get("text"),
            "claim_type": item.get("claim_type"),
            "source_id": item.get("source_id"),
            "source_anchor": item.get("source_anchor", ""),
            "support_level": item.get("support_level"),
            "confidence": item.get("confidence"),
            "status": item.get("status"),
            "numeric_lineage": item.get("numeric_lineage"),
        })
    return {
        "claim_count": total,
        "verified_count": len(verified),
        "assumption_count": len(assumed),
        "unverified_count": len(unverified),
        "verified_ratio": round(verified_ratio, 3),
        "passed": total == 0 or (verified_ratio >= 0.78 and not severe),
        "severe_unverified_count": len(severe),
        "status_counts": dict(status_counts),
        "claim_source_map": claim_source_map[:80],
        "verified_claims": verified[:30],
        "assumptions": assumed[:20],
        "unverified_claims": unverified[:30],
    }


def append_claim_verification_appendix(markdown_content: str, verification: dict) -> str:
    """Append compact claim verification summary to Word markdown."""
    if "逐项数字核验说明" in (markdown_content or ""):
        return markdown_content
    lines = [
        "## 逐项数字核验说明",
        "",
        f"- 数字/事实型声明：{verification.get('claim_count', 0)} 条",
        f"- 已匹配来源：{verification.get('verified_count', 0)} 条",
        f"- 明确假设/测算：{verification.get('assumption_count', 0)} 条",
        f"- 未强匹配：{verification.get('unverified_count', 0)} 条",
    ]
    unverified = verification.get("unverified_claims") or []
    if unverified:
        lines.append("- 需人工复核的高风险数字：")
        for item in unverified[:8]:
            lines.append(f"  - {item.get('id')}: {item.get('text')}（{item.get('evidence')}）")
    else:
        lines.append("- 未发现未强匹配的数字型声明。")
    claim_map = verification.get("claim_source_map") or []
    if claim_map:
        lines.extend(["", "### Claim-Source Map（节选）"])
        for item in claim_map[:12]:
            source = item.get("source_id") or item.get("support_level") or "未绑定"
            lines.append(
                f"- {item.get('claim_id')}: {item.get('status')} / {source} / "
                f"confidence={item.get('confidence')} / {item.get('claim')}"
            )
    return f"{(markdown_content or '').strip()}\n\n" + "\n".join(lines)
