"""SqlValidator — Semantic pre-validation of generated SQL before execution.

SOTA gap closed: baseline pipeline executes generated SQL directly and only
discovers errors when DuckDB rejects them at runtime. By then we've wasted an
LLM round-trip + the user is staring at a broken query. SOTA systems (Vanna.ai,
DataChat, Google Tables API) pre-validate SQL via the database's own EXPLAIN
mechanism, which catches:

  • References to non-existent tables / columns (typo → "no such column")
  • Type mismatches that won't surface until first row materializes
  • Ambiguous column references (SELECT name FROM a JOIN b WHERE both have name)
  • Use of reserved keywords without quoting

Why use EXPLAIN instead of just executing:
  • Free: no actual data scan, no row materialization
  • Catches semantic errors before LLM commits to wrong SQL
  • Enables auto-repair on a much cheaper signal

Why use DuckDB's `EXPLAIN` specifically:
  • DuckDB exposes the parsed + bound query plan, surfacing column/table errors
  • Failure mode is identical to actual execution (so what we catch in EXPLAIN
    would have failed at execute() anyway)

Additional checks beyond EXPLAIN:
  • Static danger detection (DROP / DELETE / UPDATE / INSERT etc.)
  • LIMIT enforcement (auto-append LIMIT if missing for large tables)
  • Cost heuristics (cartesian joins, nested loops on >100k rows)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Static safety checks (no DB connection required)
# ─────────────────────────────────────────────────────────────────────────────

_DANGEROUS_KEYWORDS = (
    "DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER",
    "CREATE", "REPLACE", "GRANT", "REVOKE", "ATTACH", "COPY",
    "EXPORT", "IMPORT", "PRAGMA",
)

_RE_DANGEROUS = re.compile(
    r"\b(" + "|".join(_DANGEROUS_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

_RE_LIMIT = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)
_RE_QUALIFY = re.compile(r"\bQUALIFY\b", re.IGNORECASE)


@dataclass
class ValidationResult:
    """Outcome of pre-validating a SQL query."""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    auto_fixed_sql: str = ""        # SQL with auto-fixes applied (LIMIT injected, etc.)
    estimated_cost: str = "low"     # low | medium | high
    plan_summary: str = ""          # human-readable plan snippet

    def __bool__(self) -> bool:
        return self.is_valid


def static_safety_check(sql: str) -> ValidationResult:
    """Lightweight syntactic checks — no DB needed."""
    result = ValidationResult()
    if not sql or not sql.strip():
        result.is_valid = False
        result.errors.append("empty SQL")
        return result

    # 1. Block dangerous statements
    # Important: SELECT can contain CREATE in column names ("created_at"),
    # so we look for the keyword as the FIRST significant token of any statement.
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        first_word = stmt.split()[0].upper() if stmt.split() else ""
        if first_word in _DANGEROUS_KEYWORDS:
            result.is_valid = False
            result.errors.append(f"forbidden statement type: {first_word}")
            return result

    # 2. Only SELECT / WITH / EXPLAIN allowed
    main_stmt = statements[-1] if statements else ""
    first_word = main_stmt.split()[0].upper() if main_stmt.split() else ""
    if first_word not in {"SELECT", "WITH", "EXPLAIN"}:
        result.is_valid = False
        result.errors.append(f"only SELECT/WITH/EXPLAIN permitted, got {first_word!r}")
        return result

    # 3. Cost heuristics
    if "CROSS JOIN" in sql.upper() or re.search(r"FROM\s+\w+\s*,\s*\w+", sql, re.IGNORECASE):
        result.warnings.append("cartesian/cross join detected — may be expensive")
        result.estimated_cost = "high"

    join_count = len(re.findall(r"\bJOIN\b", sql, re.IGNORECASE))
    if join_count >= 4:
        result.warnings.append(f"high JOIN count ({join_count}) — verify intent")
        result.estimated_cost = "high"

    # 4. LIMIT enforcement — auto-inject if missing (and no aggregation)
    auto_fixed = sql.strip().rstrip(";")
    if (
        not _RE_LIMIT.search(auto_fixed)
        and not _RE_QUALIFY.search(auto_fixed)
        and not re.search(r"\bGROUP\s+BY\b", auto_fixed, re.IGNORECASE)
    ):
        auto_fixed = f"{auto_fixed}\nLIMIT 500"
        result.warnings.append("no LIMIT or aggregation — auto-appended LIMIT 500")
    result.auto_fixed_sql = auto_fixed

    return result


# ─────────────────────────────────────────────────────────────────────────────
# EXPLAIN-based validation (requires DuckDB connection)
# ─────────────────────────────────────────────────────────────────────────────

def explain_validate(conn, sql: str) -> ValidationResult:
    """Use DuckDB's EXPLAIN to catch semantic errors before execution.

    The query is wrapped in `EXPLAIN` so DuckDB binds + analyzes it without
    materializing rows. Any binding error (missing table/column, type mismatch,
    ambiguous reference) surfaces here.

    Args:
        conn: a DuckDB connection
        sql: the SELECT/WITH statement to validate

    Returns:
        ValidationResult with .plan_summary populated on success, .errors on failure.
    """
    result = static_safety_check(sql)
    if not result.is_valid:
        return result

    # Use the auto-fixed SQL (with LIMIT injected) for plan analysis
    sql_to_check = result.auto_fixed_sql or sql

    try:
        # Strip trailing semicolons to avoid "multiple statements" issues
        clean_sql = sql_to_check.strip().rstrip(";")
        explain_sql = f"EXPLAIN {clean_sql}"
        rows = conn.execute(explain_sql).fetchall()
        # rows: list of (key, value) tuples — concatenate for human-readable summary
        plan_text = "\n".join(str(r[-1]) for r in rows if r)
        # Compress to ~300 chars for telemetry
        result.plan_summary = plan_text[:300]

        # ── Cost estimation from plan keywords ──
        plan_upper = plan_text.upper()
        if "NESTED_LOOP_JOIN" in plan_upper:
            result.warnings.append("plan contains NESTED_LOOP_JOIN — may be slow")
            result.estimated_cost = "high"
        if "FULL_OUTER_JOIN" in plan_upper:
            result.warnings.append("plan contains FULL_OUTER_JOIN")
            if result.estimated_cost == "low":
                result.estimated_cost = "medium"

        return result

    except Exception as exc:
        # Parse DuckDB error to surface the actionable bit
        msg = str(exc)
        err_clean = _clean_duckdb_error(msg)
        result.is_valid = False
        result.errors.append(err_clean)
        return result


def _clean_duckdb_error(msg: str) -> str:
    """Strip DuckDB error verbosity to leave actionable bits.

    Examples:
      "Binder Error: Referenced column \"foo\" not found in FROM clause! Candidate bindings: \"bar\""
      → "缺少列 \"foo\"（可能拼写为 \"bar\"）"
    """
    if not msg:
        return "未知错误"

    # Binder error patterns
    bind_match = re.search(
        r"Referenced column\s+\"?([^\"]+?)\"?\s+not found.*?Candidate bindings:\s*\"?([^\"]+?)\"?",
        msg, re.IGNORECASE,
    )
    if bind_match:
        return f"缺少列 \"{bind_match.group(1)}\"（请检查列名，相似列：\"{bind_match.group(2)}\"）"

    table_match = re.search(r"Table\s+\"?([^\"]+?)\"?\s+does not exist", msg, re.IGNORECASE)
    if table_match:
        return f"表 \"{table_match.group(1)}\" 不存在"

    syntax_match = re.search(r"Parser Error:\s*(.+?)(?:\n|LINE|$)", msg, re.IGNORECASE | re.DOTALL)
    if syntax_match:
        return f"语法错误：{syntax_match.group(1).strip()[:200]}"

    # Generic: take first 200 chars after the error prefix
    cleaned = re.sub(r"^\s*\w+\s*Error:\s*", "", msg, flags=re.IGNORECASE)
    return cleaned.split("\n")[0][:200]


# ─────────────────────────────────────────────────────────────────────────────
# Full validate + repair workflow
# ─────────────────────────────────────────────────────────────────────────────

def validate_with_repair_hint(conn, sql: str) -> tuple[ValidationResult, str]:
    """Validate SQL and, on failure, generate a repair hint for the LLM.

    Returns:
        (result, repair_hint) — repair_hint is "" if valid, otherwise a
        compact instruction the caller can append to its repair-prompt.
    """
    result = explain_validate(conn, sql)
    if result.is_valid:
        return result, ""

    hint_lines = [
        "## SQL 预验证失败",
        "以下问题在执行前已检测到，请修复：",
    ]
    for err in result.errors:
        hint_lines.append(f"  • {err}")
    if result.warnings:
        hint_lines.append("\n## 提示")
        for w in result.warnings:
            hint_lines.append(f"  • {w}")
    return result, "\n".join(hint_lines)
