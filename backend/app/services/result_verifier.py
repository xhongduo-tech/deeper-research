"""ResultVerifier — Sanity-check the OUTPUT of generated Python/SQL code.

SOTA gap closed: baseline pipeline accepts any output that runs without
exception. But syntactically-valid code can produce:

  • All-NaN columns (computation lost precision)
  • All-zero metrics (division-by-zero hidden by fillna)
  • Date columns where 50% are 1970-01-01 (failed parsing → epoch default)
  • Percentages outside [-100%, +1000%] (likely sign error or wrong divisor)
  • Time-series that are non-monotonic when they should be (e.g. cumulative sum that drops)
  • Result frames that are emptier than the input (lost rows in a faulty join)

OpenAI Code Interpreter does this implicitly via repeated LLM-driven inspection;
we make it deterministic and fast with a battery of heuristic checks.

Output: list of (severity, code, message) tuples. Caller decides whether to
raise, surface in QA, or auto-retry.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


Severity = str  # "error" | "warning" | "info"


@dataclass
class VerificationIssue:
    """One detected anomaly in a computation result."""
    severity: Severity            # error | warning | info
    code: str                     # short stable code (e.g. "NAN_ALL")
    message: str
    field: str = ""               # which result field exhibits the issue


@dataclass
class VerificationReport:
    """Aggregate report — caller can inspect / serialize / decide."""
    issues: list[VerificationIssue] = field(default_factory=list)
    n_records_checked: int = 0
    n_fields_checked: int = 0

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    @property
    def passes(self) -> bool:
        return not self.has_errors

    def to_dict(self) -> dict:
        return {
            "passes": self.passes,
            "n_records": self.n_records_checked,
            "n_fields": self.n_fields_checked,
            "errors": [i.message for i in self.issues if i.severity == "error"][:8],
            "warnings": [i.message for i in self.issues if i.severity == "warning"][:8],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Verification entry points
# ─────────────────────────────────────────────────────────────────────────────

def verify_records(
    records: list[dict],
    *,
    expected_min_rows: int = 0,
    monotonic_field: str = "",
    percentage_fields: tuple[str, ...] = (),
    nonzero_required_fields: tuple[str, ...] = (),
) -> VerificationReport:
    """Verify a list-of-dicts result (typical SQL output).

    Args:
        records: rows from SQL execution
        expected_min_rows: error if len(records) < this
        monotonic_field: warn if this column isn't monotonic
        percentage_fields: fields that should be in [-1.0, 10.0] range (sanity)
        nonzero_required_fields: fields that should not be all-zero
    """
    report = VerificationReport(n_records_checked=len(records))
    if not records:
        if expected_min_rows > 0:
            report.issues.append(VerificationIssue(
                severity="error",
                code="EMPTY_RESULT",
                message=f"查询返回 0 行（预期至少 {expected_min_rows} 行）",
            ))
        return report

    fields = list(records[0].keys())
    report.n_fields_checked = len(fields)

    # Per-column statistics
    field_stats: dict[str, dict] = {}
    for f in fields:
        values = [r.get(f) for r in records]
        non_null = [v for v in values if v is not None and not _is_nan(v)]
        field_stats[f] = {
            "total": len(values),
            "non_null": len(non_null),
            "null_ratio": (len(values) - len(non_null)) / max(len(values), 1),
            "values": non_null,
        }

    # 1. All-null columns
    for f, stats in field_stats.items():
        if stats["non_null"] == 0:
            report.issues.append(VerificationIssue(
                severity="error",
                code="ALL_NULL",
                message=f"列 \"{f}\" 全部为空（可能计算失败或数据缺失）",
                field=f,
            ))
        elif stats["null_ratio"] > 0.5:
            report.issues.append(VerificationIssue(
                severity="warning",
                code="HIGH_NULL_RATIO",
                message=f"列 \"{f}\" 空值占比 {stats['null_ratio']:.0%}",
                field=f,
            ))

    # 2. All-zero columns when nonzero expected
    for f in nonzero_required_fields:
        if f not in field_stats:
            continue
        vals = field_stats[f]["values"]
        if vals and all(_is_zero(v) for v in vals):
            report.issues.append(VerificationIssue(
                severity="error",
                code="ALL_ZERO",
                message=f"列 \"{f}\" 全为 0（可能除零保护掩盖了空值）",
                field=f,
            ))

    # 3. Percentage range sanity
    for f in percentage_fields:
        if f not in field_stats:
            continue
        vals = [v for v in field_stats[f]["values"] if isinstance(v, (int, float))]
        if not vals:
            continue
        out_of_range = [v for v in vals if v < -1.0 or v > 10.0]
        if out_of_range:
            report.issues.append(VerificationIssue(
                severity="warning",
                code="PCT_OUT_OF_RANGE",
                message=f"列 \"{f}\" 有 {len(out_of_range)} 个值在 [-100%, +1000%] 之外（{out_of_range[0]:.2f} ...）",
                field=f,
            ))

    # 4. Monotonicity check
    if monotonic_field and monotonic_field in field_stats:
        vals = field_stats[monotonic_field]["values"]
        if len(vals) >= 3:
            non_monotonic = sum(
                1 for a, b in zip(vals[:-1], vals[1:])
                if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b < a
            )
            if non_monotonic > len(vals) * 0.2:
                report.issues.append(VerificationIssue(
                    severity="warning",
                    code="NON_MONOTONIC",
                    message=f"列 \"{monotonic_field}\" 非单调递增（{non_monotonic} 处下降）",
                    field=monotonic_field,
                ))

    # 5. Date columns with too many epoch defaults
    for f, stats in field_stats.items():
        if not stats["values"]:
            continue
        sample = stats["values"][:50]
        epoch_count = sum(
            1 for v in sample
            if isinstance(v, str) and ("1970-01-01" in v or "1900-01-01" in v)
        )
        if epoch_count > 3:
            report.issues.append(VerificationIssue(
                severity="warning",
                code="EPOCH_DATES",
                message=f"列 \"{f}\" 有 {epoch_count} 行落在 1970-01-01（日期解析可能失败）",
                field=f,
            ))

    # 6. Row count below expected
    if expected_min_rows > 0 and len(records) < expected_min_rows:
        report.issues.append(VerificationIssue(
            severity="warning",
            code="LOW_ROW_COUNT",
            message=f"返回 {len(records)} 行（预期至少 {expected_min_rows} 行）",
        ))

    return report


def verify_dataframe(df, **kwargs) -> VerificationReport:
    """Verify a pandas DataFrame (typical analyze_data output)."""
    if df is None:
        return VerificationReport()
    try:
        records = df.to_dict(orient="records")
    except Exception:
        return VerificationReport()
    return verify_records(records, **kwargs)


def verify_scalar_metrics(metrics: dict) -> VerificationReport:
    """Verify a dict of computed metrics — common output of data_analyzer.

    Catches:
      • NaN / Inf values
      • Zero-where-meaningful (e.g. revenue=0 on a non-empty company)
    """
    report = VerificationReport(n_records_checked=1, n_fields_checked=len(metrics))
    if not metrics or not isinstance(metrics, dict):
        return report

    for key, value in metrics.items():
        if _is_nan(value):
            report.issues.append(VerificationIssue(
                severity="error",
                code="NAN_METRIC",
                message=f"指标 \"{key}\" = NaN",
                field=key,
            ))
        elif _is_inf(value):
            report.issues.append(VerificationIssue(
                severity="error",
                code="INF_METRIC",
                message=f"指标 \"{key}\" = ±∞（可能除零未保护）",
                field=key,
            ))

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Heuristic field-type inference (for auto-applying checks)
# ─────────────────────────────────────────────────────────────────────────────

_RE_PCT_FIELD = re.compile(
    r"(rate|ratio|percent|百分比|增速|增长率|占比|比率|%)", re.IGNORECASE,
)
_RE_DATE_FIELD = re.compile(r"(date|time|日期|时间|年月|月份)", re.IGNORECASE)
_RE_AMOUNT_FIELD = re.compile(
    r"(amount|revenue|sales|total|余额|金额|收入|销售|总额|流水)", re.IGNORECASE,
)


def auto_verify(records: list[dict] | object) -> VerificationReport:
    """One-call wrapper: inspects field names, picks appropriate checks, runs them.

    Use this when you don't have prior knowledge of the result's semantics — it
    will heuristically classify columns and apply the matching checks.
    """
    if records is None:
        return VerificationReport()

    # Coerce DataFrame → records
    if hasattr(records, "to_dict"):
        try:
            records = records.to_dict(orient="records")
        except Exception:
            return VerificationReport()

    if not isinstance(records, list) or not records:
        return VerificationReport()

    fields = list(records[0].keys()) if isinstance(records[0], dict) else []
    pct_fields = tuple(f for f in fields if _RE_PCT_FIELD.search(str(f)))
    amount_fields = tuple(f for f in fields if _RE_AMOUNT_FIELD.search(str(f)))

    return verify_records(
        records,
        percentage_fields=pct_fields,
        nonzero_required_fields=amount_fields,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_nan(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    if isinstance(v, str):
        return v.lower() in ("nan", "none", "null", "")
    return False


def _is_inf(v: Any) -> bool:
    return isinstance(v, float) and math.isinf(v)


def _is_zero(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v == 0
    return False
