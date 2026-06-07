"""DuckDB 内存分析引擎 — 针对 Excel/CSV 多维宽表毫秒级 SQL 查询.

功能：
  1. 从 Excel/CSV/Parquet/JSON 文件一键建立内存表
  2. SQL-Agent：接受自然语言指令，调 LLM 生成 SQL，执行并返回结果
  3. 结果序列化为 LLM 可读的 Markdown 表格 + JSON
"""
from __future__ import annotations

import io
import json
import logging
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

_MAX_ROWS_DISPLAY = 200  # 结果超过此行数时截断显示


@dataclass
class QueryResult:
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    error: str | None = None
    exec_ms: float = 0.0

    def to_markdown(self, max_rows: int = 50) -> str:
        if self.error:
            return f"❌ SQL Error: {self.error}"
        if not self.rows:
            return f"查询返回 0 行。\n`{self.sql}`"
        header = "| " + " | ".join(str(c) for c in self.columns) + " |"
        sep = "| " + " | ".join("---" for _ in self.columns) + " |"
        body_rows = self.rows[:max_rows]
        body = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in body_rows)
        note = f"\n\n_显示前 {max_rows} 行，共 {self.row_count} 行_" if self.row_count > max_rows else ""
        return f"{header}\n{sep}\n{body}{note}"

    def to_json_records(self, max_rows: int = _MAX_ROWS_DISPLAY) -> list[dict]:
        return [dict(zip(self.columns, row)) for row in self.rows[:max_rows]]

    def summary(self) -> str:
        if self.error:
            return f"查询失败: {self.error}"
        return f"返回 {self.row_count} 行 × {len(self.columns)} 列，耗时 {self.exec_ms:.0f}ms"


class DuckDBEngine:
    """会话级 DuckDB 内存分析引擎.

    使用 session_id 保持多次调用的表注册状态。
    每个 session 使用独立的 in-memory DuckDB 连接。
    """

    _sessions: dict[str, "DuckDBEngine"] = {}

    @classmethod
    def get_or_create(cls, session_id: str) -> "DuckDBEngine":
        if session_id not in cls._sessions:
            cls._sessions[session_id] = cls(session_id)
        return cls._sessions[session_id]

    @classmethod
    def destroy(cls, session_id: str) -> None:
        engine = cls._sessions.pop(session_id, None)
        if engine:
            try:
                engine._conn.close()
            except Exception:
                pass

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._conn = duckdb.connect()
        self._tables: dict[str, dict] = {}  # table_name -> meta
        self._staged_files: list[str] = []  # temp files to clean up

    # ── 表注册 ──────────────────────────────────────────────────────────────

    def register_file(
        self,
        filename: str,
        content: bytes,
        table_name: str | None = None,
    ) -> str:
        """将文件内容注册为 DuckDB 内存表，返回表名."""
        import re
        from pathlib import PurePosixPath

        suffix = PurePosixPath(filename).suffix.lower()
        if table_name is None:
            # 清理表名：去掉扩展名，替换非字母数字字符
            base = PurePosixPath(filename).stem
            table_name = re.sub(r"[^\w]", "_", base)[:40] or "data"

        try:
            if suffix in (".xlsx", ".xls", ".xlsb"):
                df = self._read_excel(content, suffix)
                self._conn.register(table_name, df)
            elif suffix in (".csv", ".tsv"):
                sep = "\t" if suffix == ".tsv" else ","
                df = self._read_csv(content, sep)
                self._conn.register(table_name, df)
            elif suffix == ".parquet":
                tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
                tmp.write(content)
                tmp.close()
                self._staged_files.append(tmp.name)
                self._conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{tmp.name}')")
            elif suffix == ".json":
                data = json.loads(content.decode("utf-8", errors="replace"))
                if isinstance(data, list):
                    import pandas as pd
                    df = pd.DataFrame(data)
                    self._conn.register(table_name, df)
                else:
                    import pandas as pd
                    df = pd.json_normalize(data)
                    self._conn.register(table_name, df)
            else:
                raise ValueError(f"Unsupported file type for DuckDB: {suffix}")

            # 获取 schema 信息
            schema_rows = self._conn.execute(f"DESCRIBE {table_name}").fetchall()
            row_count = self._conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            self._tables[table_name] = {
                "filename": filename,
                "schema": [(r[0], r[1]) for r in schema_rows],
                "row_count": row_count,
            }
            logger.info("DuckDB registered table '%s': %d rows", table_name, row_count)
            return table_name

        except Exception as exc:
            logger.error("DuckDB register_file failed for %s: %s", filename, exc)
            raise

    def table_schema_text(self) -> str:
        """返回所有已注册表的 schema 文本，供 LLM 生成 SQL 使用."""
        if not self._tables:
            return "（尚未注册任何表）"
        lines = []
        for tbl, meta in self._tables.items():
            lines.append(f"表名: {tbl}  (文件: {meta['filename']}, 行数: {meta['row_count']})")
            for col_name, col_type in meta["schema"]:
                lines.append(f"  {col_name}: {col_type}")
        return "\n".join(lines)

    # ── SQL 执行 ─────────────────────────────────────────────────────────────

    def execute(self, sql: str) -> QueryResult:
        import time
        t0 = time.monotonic()
        try:
            result = self._conn.execute(sql)
            columns = [d[0] for d in result.description] if result.description else []
            rows = result.fetchall()
            exec_ms = (time.monotonic() - t0) * 1000
            return QueryResult(
                sql=sql, columns=columns,
                rows=[list(r) for r in rows],
                row_count=len(rows), exec_ms=exec_ms,
            )
        except Exception as exc:
            exec_ms = (time.monotonic() - t0) * 1000
            return QueryResult(sql=sql, error=str(exc), exec_ms=exec_ms)

    # ── SQL-Agent (自然语言 → SQL → 执行) ────────────────────────────────────

    async def nl_query(self, question: str, *, max_retries: int = 2) -> QueryResult:
        """接受自然语言问题，LLM 生成 SQL，执行后返回结果."""
        from app.pipeline.llm_helpers import call_llm_json

        schema_text = self.table_schema_text()
        system_prompt = f"""你是专业的 SQL 分析师。根据用户问题和数据库 Schema 生成 DuckDB SQL 查询。
仅输出 JSON: {{"sql": "SELECT ..."}}
不要添加任何解释。
SQL 方言为 DuckDB，支持 PIVOT/UNPIVOT、窗口函数、正则、日期函数。

可用数据表 Schema:
{schema_text}"""

        user_msg = f"问题: {question}"
        last_error: str | None = None

        for attempt in range(max_retries + 1):
            if attempt > 0 and last_error:
                user_msg = f"上次 SQL 报错: {last_error}\n请修正 SQL 并重新生成。\n问题: {question}"

            try:
                resp = await call_llm_json(system_prompt, user_msg)
                sql = resp.get("sql", "").strip()
                if not sql:
                    last_error = "LLM 返回空 SQL"
                    continue
                result = self.execute(sql)
                if result.error:
                    last_error = result.error
                    continue
                return result
            except Exception as exc:
                last_error = str(exc)
                logger.warning("DuckDB nl_query attempt %d failed: %s", attempt, exc)

        return QueryResult(sql="", error=f"SQL 生成失败: {last_error}")

    # ── 工具方法 ──────────────────────────────────────────────────────────────

    def sample(self, table_name: str, n: int = 5) -> QueryResult:
        return self.execute(f"SELECT * FROM {table_name} LIMIT {n}")

    def profile(self, table_name: str) -> str:
        """返回表的列统计摘要（min/max/avg/null_count 等）."""
        try:
            result = self._conn.execute(f"SUMMARIZE {table_name}").fetchall()
            cols = ["column", "min", "max", "approx_unique", "avg", "std", "null_pct", "dtype"]
            lines = ["\t".join(cols)]
            for row in result:
                lines.append("\t".join(str(v) for v in row[:len(cols)]))
            return "\n".join(lines)
        except Exception as exc:
            return f"PROFILE 失败: {exc}"

    def __del__(self):
        for f in self._staged_files:
            try:
                os.unlink(f)
            except Exception:
                pass
        try:
            self._conn.close()
        except Exception:
            pass

    # ── 内部辅助 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _read_excel(content: bytes, suffix: str):
        import pandas as pd
        engine_map = {".xlsx": "openpyxl", ".xls": "xlrd", ".xlsb": "pyxlsb"}
        engine = engine_map.get(suffix, "openpyxl")
        try:
            return pd.read_excel(io.BytesIO(content), engine=engine)
        except Exception:
            return pd.read_excel(io.BytesIO(content))

    @staticmethod
    def _read_csv(content: bytes, sep: str = ","):
        import pandas as pd
        from app.services.file_parser import detect_encoding
        encoding = detect_encoding(content)
        return pd.read_csv(io.BytesIO(content), sep=sep, encoding=encoding, on_bad_lines="skip")
