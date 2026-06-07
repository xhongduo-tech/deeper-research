"""SQL Query Skill — LLM generates SQL, executes via DuckDB, returns structured results.

This skill is the counterpart to RAG search for structured data (Excel/CSV).
When a knowledge base contains structured tables (ingested via StructuredDataService),
the LLM should use this skill instead of (or in addition to) vector search.

Flow:
  1. Fetch table schema descriptions from StructuredDataService
  2. Build a few-shot SQL generation prompt
  3. LLM generates a SELECT statement
  4. Execute against the DuckDB table
  5. Return results as a markdown table + raw records
"""
from __future__ import annotations

import json
import logging

from app.skills.base import Skill
from app.services.llm_service import chat

logger = logging.getLogger(__name__)


class SqlQuerySkill(Skill):
    name = "sql_query"
    description = (
        "当知识库中包含 Excel/CSV 结构化数据表时，生成并执行 SQL 查询，返回精确的表格结果。"
        "适合：按分行/部门汇总指标、排名分析、同比环比计算、筛选特定条件数据。"
    )
    category = "offline"
    parameters = {
        "question": {"type": "string", "description": "用自然语言描述的数据查询问题"},
        "kb_ids": {
            "type": "array",
            "description": "知识库 ID 列表，用于定位 DuckDB 表",
        },
        "max_rows": {
            "type": "integer",
            "description": "返回最大行数，默认 100",
            "default": 100,
        },
        "output_format": {
            "type": "string",
            "description": "markdown | json | both，默认 markdown",
            "default": "markdown",
        },
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        from app.services.structured_data_service import get_structured_data_service

        question = params.get("question", "")
        kb_ids: list[str] = params.get("kb_ids") or []
        max_rows: int = int(params.get("max_rows", 100))
        output_format: str = params.get("output_format", "markdown")

        if not question:
            return {"error": "question 参数不能为空"}
        if not kb_ids:
            return {"error": "kb_ids 参数不能为空"}

        sds = get_structured_data_service()

        # Collect schema descriptions from all specified KBs
        schema_blocks: list[str] = []
        table_registry: dict[str, str] = {}  # table_name → kb_id

        for kb_id in kb_ids:
            schema = sds.describe_tables(kb_id)
            if schema:
                schema_blocks.append(f"[知识库 {kb_id}]\n{schema}")
            for t in sds.list_tables(kb_id):
                table_registry[t["table_name"]] = kb_id

        if not schema_blocks:
            return {
                "error": "指定的知识库中没有结构化数据表。请先上传 Excel 或 CSV 文件。",
                "tip": "如需查询文档内容，请使用 RAG 搜索技能。",
            }

        schema_str = "\n\n".join(schema_blocks)

        # ── Few-shot: retrieve similar past successful queries (Vanna.ai pattern) ──
        # This dramatically improves SQL accuracy on real production schemas: the
        # LLM sees actual examples from THIS user's KB, not generic templates.
        few_shot_examples: list[dict] = []
        for kb_id in kb_ids:
            try:
                examples = sds.get_few_shot_examples(kb_id, question, top_k=3)
                few_shot_examples.extend(examples)
            except Exception as exc:
                logger.debug("Few-shot retrieval failed for %s: %s", kb_id, exc)

        # ── Cross-table relationships (foreign-key inference) ──
        # When the user's question implicates multiple tables, the LLM needs to
        # know which columns can JOIN. We auto-infer high-confidence (≥0.7) pairs.
        relationships_block = ""
        try:
            all_rels: list[dict] = []
            for kb_id in kb_ids:
                rels = sds.get_table_relationships(kb_id)
                all_rels.extend(r for r in rels if r["confidence"] >= 0.7)
            if all_rels:
                lines = ["## 表间关系（推断的JOIN键）"]
                for r in all_rels[:6]:
                    lines.append(
                        f"  • {r['table_a']}.\"{r['col_a']}\"  ↔  "
                        f"{r['table_b']}.\"{r['col_b']}\"  ({r['reason']})"
                    )
                relationships_block = "\n".join(lines) + "\n"
        except Exception as exc:
            logger.debug("Relationship inference failed: %s", exc)

        # Fallback: synthesized examples if no cache hits yet
        few_shot_block = ""
        if few_shot_examples:
            few_shot_block = "## 历史相似查询参考（基于本知识库的成功查询）\n"
            for i, ex in enumerate(few_shot_examples[:3], 1):
                few_shot_block += (
                    f"\n示例 {i}：\n"
                    f"  -- 问题：{ex['question'][:120]}\n"
                    f"  {ex['sql']}\n"
                )
        else:
            sample_sqls = []
            for kb_id in kb_ids:
                sample_sqls.extend(sds.get_sample_queries(kb_id))
            few_shot_block = "## 示例查询模板\n" + "\n".join(f"  -- {q}" for q in sample_sqls[:4])

        # Build SQL generation prompt
        system_prompt = _SQL_SYSTEM_PROMPT

        user_prompt = f"""## 数据库表结构
{schema_str}

{relationships_block}
{few_shot_block}

## 用户问题
{question}

请生成对应的 DuckDB SQL 查询语句（只输出 SQL，不加任何说明）："""

        generated_sql = ""
        try:
            raw = await chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.05,
            )
            generated_sql = _clean_sql(raw)
            logger.info("Generated SQL: %s", generated_sql)
        except Exception as exc:
            logger.error("LLM SQL generation failed: %s", exc)
            return {"error": f"SQL 生成失败: {exc}", "question": question}

        if not generated_sql:
            return {"error": "LLM 未生成有效 SQL", "question": question}

        # Determine which KB to execute against (use the first KB that has tables)
        exec_kb_id = kb_ids[0]
        for tbl in table_registry:
            if tbl in generated_sql:
                exec_kb_id = table_registry[tbl]
                break

        # Execute — with two-pass auto-repair
        records, generated_sql = await _execute_with_repair(
            sds, exec_kb_id, generated_sql, max_rows, question,
            schema_str, system_prompt
        )
        if records is None:
            return {
                "error": "SQL 执行失败，已尝试自动修复但仍无法执行",
                "sql": generated_sql,
                "question": question,
            }

        if not records:
            return {
                "result_markdown": "查询结果为空。",
                "result_json": [],
                "sql": generated_sql,
                "row_count": 0,
            }

        # ── Post-execution result sanity verification ────────────────────────
        # Catches issues SQL didn't error on but logically wrong: all-NaN columns,
        # epoch-default dates, percentages outside [-100%, +1000%], etc.
        verification_summary: dict = {}
        try:
            from app.services.result_verifier import auto_verify
            v_report = auto_verify(records)
            verification_summary = v_report.to_dict()
            if v_report.has_errors:
                logger.warning(
                    "SQL result has %d data-quality errors: %s",
                    len([i for i in v_report.issues if i.severity == "error"]),
                    [i.message for i in v_report.issues if i.severity == "error"][:3],
                )
        except Exception as exc:
            logger.debug("Result verification failed: %s", exc)

        # Format output
        result: dict = {"sql": generated_sql, "row_count": len(records)}
        if verification_summary:
            result["verification"] = verification_summary

        if output_format in {"markdown", "both"}:
            result["result_markdown"] = _records_to_markdown(records)

        if output_format in {"json", "both"}:
            result["result_json"] = records
        elif output_format == "markdown":
            result["result_json"] = records  # always include raw for downstream use

        return result


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SQL_SYSTEM_PROMPT = """\
你是资深数据分析师，精通 DuckDB SQL（兼容 PostgreSQL 语法）。
根据用户问题和数据库表结构，生成一条精确、高效的 SELECT 查询。

## 核心规则
1. 只输出纯 SQL，不加解释、注释或代码块标记（不加 ```sql 包裹）
2. 只允许 SELECT / WITH（CTE）语句，严禁 INSERT/UPDATE/DELETE/DROP
3. 始终用双引号包裹含中文或空格的列名和表名："分行名称", "branch data"
4. 纯 ASCII 无空格的列名也建议双引号以防止关键字冲突
5. LIMIT 默认 100，最大 500

## DuckDB 高级特性（按需使用）
- CTE / 递归:
  WITH ranked AS (SELECT *, ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rn FROM t)
  SELECT * FROM ranked WHERE rn <= 10
- 窗口聚合:
  SUM(amount) OVER (PARTITION BY dept ORDER BY month) AS cumulative
  AVG(value) OVER (PARTITION BY branch ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS ma3
- 同比/环比:
  LAG("金额", 12) OVER (PARTITION BY "分行" ORDER BY "月份") AS "去年同期"
  LAG("金额", 1)  OVER (PARTITION BY "分行" ORDER BY "月份") AS "上月"
  ROUND(("金额" - LAG("金额",12) OVER (...)) * 100.0 / NULLIF(LAG("金额",12) OVER (...), 0), 2) AS "同比增速%"
- 安全类型转换: TRY_CAST(col AS DOUBLE)  → NULL on failure, never throws
- 空值处理: COALESCE(col, 0), NULLIF(denom, 0), IFNULL(col, '未知')
- 日期: DATE_TRUNC('month', dt), STRFTIME('%Y-%m', dt), DATEDIFF('day', d1, d2)
- 字符串: REGEXP_REPLACE(col, '[^0-9.]', ''), TRIM(col), LIKE '%关键词%'
- 分位数: PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col) AS "中位数"
- 统计: STDDEV(col), VARIANCE(col), CORR(x, y)
- 原生透视:
  PIVOT "sales" ON "quarter" USING SUM("revenue") GROUP BY "branch"
- 条件聚合:
  SUM(CASE WHEN type = '贷款' THEN amount ELSE 0 END) AS "贷款总额"
  COUNT(CASE WHEN status = '逾期' THEN 1 END) AS "逾期笔数"

## 数值精度与格式
- 所有非整数结果 ROUND(..., 2)
- 零除保护：/ NULLIF(denominator, 0)  → NULL 而非报错
- 避免 INTEGER / INTEGER → 整数截断：乘以 1.0 或 TRY_CAST

## 输出质量规范
- GROUP BY 结果必须加 ORDER BY（业务优先排序：金额/余额 DESC）
- 列别名使用中文业务名称：AS "贷款余额(万元)", AS "同比增速(%)"
- 多指标写在同一 SELECT，减少子查询层数
- 关键 TOP-N 用 QUALIFY ROW_NUMBER() OVER (...) <= N（DuckDB 专属，最简洁）
- 结果行数预期 > 50 行时加 LIMIT，预期 ≤ 50 行可不加

## 常见错误预防
- 列名含括号: "余额(万元)" 必须用双引号
- 中文关键字冲突（如 FROM/WHERE 是汉字）: 双引号可规避
- 混合类型列: 先 TRY_CAST 再 SUM/AVG
- 空表/无匹配行: 聚合函数返回 NULL，用 COALESCE 包装
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _execute_with_repair(
    sds, kb_id: str, sql: str, max_rows: int,
    question: str, schema_str: str, system_prompt: str
) -> tuple:
    """Try to execute SQL; on failure, ask LLM to repair and retry once more.

    Pre-execution semantic validation via EXPLAIN catches missing-column /
    wrong-table errors BEFORE we waste an execution round.
    """
    # ── Pass 0: EXPLAIN-based pre-validation (no row scan) ──────────────────
    try:
        from app.services.sql_validator import validate_with_repair_hint
        from app.services.structured_data_service import _get_conn
        conn = _get_conn(kb_id)
        pre_result, pre_hint = validate_with_repair_hint(conn, sql)
        if not pre_result.is_valid:
            # Try LLM repair using the EXPLAIN error as a concrete hint
            logger.info("SQL pre-validation failed: %s", pre_result.errors)
            from app.services.llm_service import chat
            repair_prompt = (
                f"{pre_hint}\n\n"
                f"原始 SQL:\n{sql}\n\n"
                f"表结构参考:\n{schema_str[:2000]}\n\n"
                f"原始问题: {question}\n\n"
                f"请输出修复后的 SQL（只输出 SQL，不加说明）："
            )
            raw_repaired = await chat(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": repair_prompt}],
                temperature=0.0,
            )
            repaired_sql = _clean_sql(raw_repaired)
            if repaired_sql and repaired_sql != sql:
                sql = repaired_sql  # downstream uses the repaired version
                logger.info("SQL repaired via pre-validation hint")
        elif pre_result.auto_fixed_sql and pre_result.auto_fixed_sql != sql.strip().rstrip(";"):
            # Apply harmless auto-fixes (LIMIT injection)
            sql = pre_result.auto_fixed_sql
    except Exception as exc:
        # Validator failed — proceed with original SQL (graceful degradation)
        logger.debug("SQL pre-validation skipped due to error: %s", exc)

    # Pass 1: direct execution (caches on success via question param)
    try:
        records = sds.execute_query(kb_id, sql, max_rows=max_rows, question=question)
        return records, sql
    except Exception as exc1:
        logger.warning("SQL pass-1 failed: %s\nSQL: %s", exc1, sql)

    # Pass 2: LLM auto-repair
    try:
        repair_prompt = (
            f"以下 DuckDB SQL 执行出错，请修复后只输出修复后的 SQL（不加任何说明）。\n\n"
            f"错误信息: {str(exc1)[:400]}\n\n"
            f"原始 SQL:\n{sql}\n\n"
            f"表结构参考:\n{schema_str[:2000]}\n\n"
            f"原始问题: {question}"
        )
        from app.services.llm_service import chat
        raw_repaired = await chat(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": repair_prompt}],
            temperature=0.0,
        )
        repaired_sql = _clean_sql(raw_repaired)
        if repaired_sql and repaired_sql != sql:
            records = sds.execute_query(kb_id, repaired_sql, max_rows=max_rows, question=question)
            logger.info("SQL repaired successfully")
            return records, repaired_sql
    except Exception as exc2:
        logger.error("SQL repair also failed: %s", exc2)

    return None, sql

def _clean_sql(raw: str) -> str:
    """Strip markdown code fences and extra whitespace from LLM SQL output."""
    text = raw.strip()
    # Remove ```sql ... ``` or ``` ... ```
    text = text.lstrip("`").rstrip("`").strip()
    if text.lower().startswith("sql"):
        text = text[3:].strip()
    # Remove any leading explanation before SELECT/WITH
    for kw in ("SELECT", "WITH", "EXPLAIN"):
        idx = text.upper().find(kw)
        if idx != -1:
            text = text[idx:]
            break
    return text.strip()


def _records_to_markdown(records: list[dict]) -> str:
    """Convert a list of dicts to a GitHub-flavored markdown table."""
    if not records:
        return ""
    headers = list(records[0].keys())
    header_row = "| " + " | ".join(str(h) for h in headers) + " |"
    sep_row = "| " + " | ".join("---" for _ in headers) + " |"
    data_rows = []
    for rec in records:
        cells = []
        for h in headers:
            v = rec.get(h)
            if isinstance(v, float):
                cells.append(f"{v:,.2f}" if abs(v) >= 0.01 else str(v))
            elif v is None:
                cells.append("-")
            else:
                cells.append(str(v).replace("|", "｜"))
        data_rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_row, sep_row, *data_rows])
