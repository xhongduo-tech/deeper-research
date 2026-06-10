"""ExcelAnalyzerSkill — precision analysis of Excel/CSV files.

Unlike DataAnalyzerSkill (which works on CSV string snippets), this skill:
- Reads the full file directly (xlsx/xlsb/xls/ods/csv/tsv)
- Handles multi-sheet workbooks — analyses each sheet separately
- Uses Decimal + mpmath for exact numeric computation
- Generates publication-quality charts with seaborn/plotly
- Returns structured: {result, figures, sheets_summary, precision_values}

Called by Quinn persona when a tabular file path is in the research context.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.skills.base import Skill
from app.services.llm_service import chat_json, chat
from app.services.model_router import get_model_router
from app.skills.offline.sota_utils import self_critique, adversarial_review

logger = logging.getLogger(__name__)

_PRECISION_SYSTEM = """\
你是高精度数据分析工程师。生成可直接执行的 Python 代码，
使用 pandas / numpy / scipy / Decimal / mpmath 进行精确计算。
只输出代码，不输出任何解释。
"""

# ── What the sandbox pre-injects (for the LLM's reference) ─────────────────
_INJECTED_LIBS_DOC = """\
## 沙盒预注入变量（直接使用，无需 import）
- df          — 已加载的 pandas DataFrame（上传的主数据）
- all_sheets  — dict[str, pd.DataFrame]（所有工作表，Excel 时有值）
- pd, np      — pandas / numpy
- scipy_stats — scipy.stats
- sm          — statsmodels.api
- Decimal, ROUND_HALF_UP, decimal_getcontext — 高精度十进制
- math, statistics, Fraction — 内置精度模块
- mpmath, mp  — 任意精度浮点
- sp          — sympy（符号数学）
- tabulate    — tabulate(rows, headers, tablefmt='pipe')
- plt, sns, px, go — matplotlib/seaborn/plotly 可视化
- squarify, nx, WordCloud — 专用图表
- json, StringIO — 数据工具
- duckdb, pl  — 嵌入式SQL / polars
- openpyxl, xlrd, pyxlsb — Excel 读写（已注入，可在代码中再次导入）
"""


class ExcelAnalyzerSkill(Skill):
    name = "analyze_excel"
    description = (
        "SOTA Excel高精度分析：对上传的 Excel/CSV/ODS 文件执行多表读取、精确数值计算、"
        "排名/透视/趋势/相关性分析，生成专业可视化图表。"
        "含代码自动生成、沙箱执行、自动修复、洞察生成、自评和质量评分。"
        "返回 Markdown 分析报告 + 精确数值 + 质量评分"
    )
    category = "data"
    parameters = {
        "file_path": {
            "type": "string",
            "description": "上传文件的绝对路径（.xlsx / .xlsb / .xls / .csv / .tsv / .ods）",
        },
        "question": {
            "type": "string",
            "description": "分析问题，如：'计算各季度销售额合计及同比增长率'",
        },
        "sheet_name": {
            "type": "string",
            "description": "可选：指定工作表名称（默认自动选取数据最多的表）",
            "default": "",
        },
        "context": {
            "type": "string",
            "description": "业务背景，帮助生成更准确的解读",
            "default": "",
        },
        "precision_mode": {
            "type": "boolean",
            "description": "启用高精度模式：所有数值用 Decimal(28位) 重算（默认 true）",
            "default": True,
        },
        "enable_critique": {
            "type": "boolean",
            "description": "启用分析结果质量自评",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队挑战",
            "default": True,
        },
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        file_path = (params.get("file_path") or "").strip()
        question = (params.get("question") or "").strip()
        sheet_name = (params.get("sheet_name") or "").strip()
        biz_context = params.get("context", "")
        precision_mode = params.get("precision_mode", True)
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)

        if not file_path:
            return {"result": "", "error": "file_path 不能为空"}
        if not Path(file_path).exists():
            return {"result": "", "error": f"文件不存在: {file_path}"}

        # 1. Load the file
        df, meta = self._load_file(file_path, sheet_name)
        if df is None or df.empty:
            return {"result": "文件读取失败或数据为空", "error": "empty_dataframe"}

        # 1.5 CoT: Analyze data characteristics and plan analysis strategy
        reasoning = await self._cot_plan(df, meta, question, biz_context)

        # 2. Generate analysis code
        code = await self._generate_code(df, meta, question, biz_context, precision_mode, reasoning)

        # 3. Execute in full-library sandbox
        exec_result = await self._execute(df, meta, code, file_path)

        # 4. Auto-repair on error
        if exec_result.get("error") and not exec_result.get("variables", {}).get("result"):
            logger.info("ExcelAnalyzer: first execution failed, attempting repair")
            repair_code = await self._repair_code(code, exec_result["error"], df, question)
            if repair_code:
                exec_result = await self._execute(df, meta, repair_code, file_path)
                code = repair_code

        # 5. Generate insight
        insight = await self._generate_insight(exec_result, question, df)

        # 6. Build output
        out = self._build_output(exec_result, code, insight, meta, df)

        # SOTA: Self-critique
        if enable_critique and out.get("result"):
            try:
                critique = await self_critique(
                    draft=out["result"][:3000],
                    topic=f"Excel分析 - {question[:50]}",
                    dimensions=["data_grounding", "logical_rigor", "specificity"],
                )
                out["quality_score"] = round(critique["overall_score"] * 10)
                out["critique"] = critique
            except Exception as exc:
                logger.warning(f"ExcelAnalyzer self-critique failed: {exc}")

        # SOTA: Adversarial review
        if enable_adversarial and out.get("result"):
            try:
                adv = await adversarial_review(
                    output=out["result"][:3000],
                    topic=f"Excel分析 - {question[:50]}",
                )
                out["adversarial"] = adv
            except Exception as exc:
                logger.warning(f"ExcelAnalyzer adversarial failed: {exc}")

        return out

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_file(self, file_path: str, sheet_name: str) -> tuple:
        """Load file into (primary_df, meta_dict)."""
        from app.services.excel_grounding import _load_dataframe
        ext = Path(file_path).suffix.lower()
        try:
            df, meta = _load_dataframe(file_path, ext)
            if df is None:
                return None, {}
            # If caller specified a sheet, reload with that sheet
            if sheet_name and sheet_name in meta.get("all_sheets", []):
                try:
                    import pandas as pd
                    df2 = pd.ExcelFile(file_path, engine="openpyxl").parse(sheet_name)
                    meta["sheet_name"] = sheet_name
                    return df2, meta
                except Exception:
                    pass
            return df, meta
        except Exception as e:
            logger.warning(f"ExcelAnalyzer: load failed {file_path}: {e}")
            return None, {}

    async def _cot_plan(self, df, meta: dict, question: str, biz_context: str) -> str:
        """CoT: Analyze data characteristics and plan analysis strategy before code generation."""
        shape = df.shape
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
        sample = df.head(5).to_dict(orient="records")

        prompt = f"""你是数据分析策略专家。请根据数据特征和用户需求，规划最佳分析策略。

数据规模：{shape[0]}行 × {shape[1]}列
数值列：{numeric_cols[:10]}
分类列：{cat_cols[:10]}
时间列：{date_cols[:5]}
样本：{sample}

用户问题：{question}
业务背景：{biz_context or '无'}

请回答：
1. 数据有哪些关键特征？
2. 最适合的分析方法是什么？
3. 应该生成什么类型的图表？
4. 需要注意的数据质量问题？"""

        try:
            messages = [
                {"role": "system", "content": "你是数据分析策略专家，擅长根据数据特征规划分析方案。"},
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(agent_type="quinn", messages=messages)
            return await chat(messages=messages, model=model, base_url=base_url, api_key=api_key,
                              temperature=0.3, max_tokens=600)
        except Exception as e:
            logger.debug(f"ExcelAnalyzer CoT failed: {e}")
            return ""

    async def _generate_code(
        self,
        df,
        meta: dict,
        question: str,
        biz_context: str,
        precision_mode: bool,
        reasoning: str = "",
    ) -> str:
        import pandas as pd
        shape = df.shape
        dtypes = {str(k): str(v) for k, v in df.dtypes.items()}
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        sample = df.head(15).to_dict(orient="records")
        all_sheets = meta.get("all_sheets", [])
        sheet_name = meta.get("sheet_name", "Sheet1")

        sheets_note = ""
        if len(all_sheets) > 1:
            sheets_note = (
                f"\n文件含 {len(all_sheets)} 个工作表：{', '.join(all_sheets[:8])}，"
                f"当前分析工作表：{sheet_name}\n"
                "（all_sheets 变量已注入，格式为 dict[sheet_name, DataFrame]）"
            )

        precision_note = ""
        if precision_mode:
            precision_note = """
## 精确计算要求（必须）
对所有金额/比率/累计值，用 Decimal 重算并存入 precision_result 变量：
```python
decimal_getcontext().prec = 28
precision_result = {}
for col in numeric_cols:
    vals = [Decimal(str(v)) for v in df[col].dropna() if str(v) not in ('nan','inf')]
    if vals:
        precision_result[col] = {
            'sum': str(sum(vals)),
            'mean': str(sum(vals)/len(vals)),
            'count': len(vals)
        }
```
"""

        reasoning_block = f"\n\n## 分析策略规划\n{reasoning[:500]}" if reasoning else ""

        prompt = f"""你是精确数据分析专家。请为以下 Excel/CSV 数据生成完整的 Python 分析和可视化代码。

## 数据信息
- 文件：{meta.get("sheet_name", "Sheet1")}
- 规模：{shape[0]}行 × {shape[1]}列{sheets_note}
- 列名与类型：{dtypes}
- 数值列：{numeric_cols[:20]}
- 前15行样本：{sample}

## 分析问题
{question}
{f"业务背景：{biz_context}" if biz_context else ""}{reasoning_block}

{_INJECTED_LIBS_DOC}
{precision_note}

## 分析代码要求

**1. 数值计算（必须精确）**
- 所有数值列：计算 sum/mean/median/std/min/max，保留4位小数
- 若有维度列（分类/机构/名称）：groupby 汇总，Top5/Bottom5 排名
- 若有时序列（年/月/日期）：计算增长率、趋势、累计值
- 若数值列≥2：计算相关系数矩阵
- 检测并报告异常值（IQR法）

**2. 精确计算（重要）**
- 用 Decimal 重算关键数值（避免浮点误差）
- 验证加总：若有总计行/列，检查加总是否准确

**3. 可视化（必须生成图表）**
- 根据数据特征选择最合适的图表类型
- 使用预注入的 plt/sns/px，figsize≥(10,6)，中文标题
- 数值标注，专业配色，plt.tight_layout() 结尾

**4. 输出变量（必须赋值）**
- result = "Markdown 格式分析报告（不少于 200 字，含表格）"
- chart_labels = [...], chart_series = [...]
- precision_result = {{}} （精确计算结果）

只输出 Python 代码，不加任何解释或代码块标记。"""

        try:
            messages = [
                {"role": "system", "content": _PRECISION_SYSTEM},
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(
                agent_type="quinn", messages=messages
            )
            code = await chat(
                messages=messages, model=model, base_url=base_url, api_key=api_key,
                temperature=0.15, max_tokens=2500,
            )
            return (
                code.strip()
                .removeprefix("```python").removeprefix("```")
                .removesuffix("```").strip()
            )
        except Exception as e:
            logger.warning(f"ExcelAnalyzer: code gen failed: {e}")
            return self._fallback_code(df)

    async def _execute(self, df, meta: dict, code: str, file_path: str) -> dict:
        """Execute in sandbox with df + all_sheets injected."""
        from app.services.sandbox import execute_python
        from app.agents.data_analyst import _build_df_preamble

        # Build all_sheets dict preamble for multi-sheet Excel
        all_sheets = meta.get("all_sheets", [])
        sheets_preamble = ""
        if len(all_sheets) > 1:
            ext = Path(file_path).suffix.lower()
            if ext in (".xlsx", ".xlsm", ".xls", ".xlsb"):
                sheets_preamble = (
                    "# Load all sheets\n"
                    "_all_sheets = {}\n"
                    "try:\n"
                    f"    _xl = pd.ExcelFile({repr(file_path)}, engine='openpyxl')\n"
                    "    for _sn in _xl.sheet_names[:6]:\n"
                    "        try:\n"
                    "            _all_sheets[_sn] = _xl.parse(_sn)\n"
                    "        except Exception:\n"
                    "            pass\n"
                    "except Exception:\n"
                    "    pass\n"
                    "all_sheets = _all_sheets\n"
                )

        preamble = _build_df_preamble(df) + "\n" + sheets_preamble
        full_code = preamble + "\n\n" + code

        try:
            return await execute_python(full_code, timeout=120, capture_figures=True)
        except Exception as e:
            return {"error": str(e), "figures": [], "stdout": "", "variables": {}}

    async def _repair_code(self, original_code: str, error: str, df, question: str) -> str:
        """Ask LLM to fix the broken code."""
        dtypes = {str(k): str(v) for k, v in df.dtypes.items()}
        prompt = (
            f"以下 Python 代码执行报错，请修复并重新生成：\n\n"
            f"原始问题: {question}\n"
            f"数据列类型: {dtypes}\n\n"
            f"报错信息:\n{error[:600]}\n\n"
            f"原始代码:\n{original_code[:2000]}\n\n"
            "请输出修复后的完整代码，不含任何解释。"
        )
        try:
            messages = [
                {"role": "system", "content": _PRECISION_SYSTEM},
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(
                agent_type="quinn", messages=messages
            )
            code = await chat(
                messages=messages, model=model, base_url=base_url, api_key=api_key,
                temperature=0.1, max_tokens=2000,
            )
            return (
                code.strip()
                .removeprefix("```python").removeprefix("```")
                .removesuffix("```").strip()
            )
        except Exception:
            return ""

    async def _generate_insight(self, exec_result: dict, question: str, df) -> str:
        stdout = (exec_result.get("stdout") or "")[:600]
        variables = exec_result.get("variables") or {}
        result_val = str(variables.get("result", ""))[:600]
        precision = variables.get("precision_result", {})
        n_figures = len(exec_result.get("figures") or [])
        error = (exec_result.get("error") or "")[:200]

        ctx_parts = []
        if stdout:
            ctx_parts.append(f"计算输出：\n{stdout}")
        if result_val:
            ctx_parts.append(f"分析结果：\n{result_val}")
        if precision:
            ctx_parts.append(f"精确计算值：{json.dumps(precision, ensure_ascii=False)[:400]}")
        if n_figures:
            ctx_parts.append(f"已生成 {n_figures} 张图表")
        if error:
            ctx_parts.append(f"执行异常：{error}")

        context = "\n\n".join(ctx_parts) or "分析完成"

        prompt = (
            f"请基于以下分析结果，用中文回答用户问题并总结核心发现。\n\n"
            f"用户问题：{question}\n\n"
            f"分析结果：\n{context}\n\n"
            "要求：3-5句话，包含精确数字，语言专业简洁，不重复问题。"
        )
        try:
            messages = [
                {"role": "system", "content": "你是数据洞察专家，提供精确、专业的中文分析结论。"},
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(
                agent_type="quinn", messages=messages
            )
            return await chat(
                messages=messages, model=model, base_url=base_url, api_key=api_key,
                temperature=0.3, max_tokens=400,
            )
        except Exception as e:
            return f"分析完成，共生成 {n_figures} 张图表。"

    def _build_output(self, exec_result: dict, code: str, insight: str, meta: dict, df) -> dict:
        variables = exec_result.get("variables") or {}
        stdout = (exec_result.get("stdout") or "")
        result_text = variables.get("result") or stdout or ""
        figures = exec_result.get("figures") or []

        out: dict = {
            "result": f"{insight}\n\n{result_text}"[:6000] if result_text else insight,
            "insight": insight,
            "code": code,
            "sheet_name": meta.get("sheet_name", ""),
            "all_sheets": meta.get("all_sheets", []),
            "exec_ms": exec_result.get("exec_ms", 0),
        }
        if figures:
            out["figures"] = figures
        if variables.get("precision_result"):
            out["precision_result"] = variables["precision_result"]
        if variables.get("chart_series"):
            out["chart_series"] = variables["chart_series"]
        if variables.get("chart_labels"):
            out["chart_labels"] = variables["chart_labels"]
        if exec_result.get("error") and not result_text:
            out["error"] = exec_result["error"][:400]
        return out

    def _fallback_code(self, df) -> str:
        """Minimal analysis when code gen fails."""
        return """\
# Fallback analysis
numeric_cols = df.select_dtypes(include='number').columns.tolist()
lines = [f"数据规模：{df.shape[0]}行 × {df.shape[1]}列"]
lines.append(f"数值列：{', '.join(numeric_cols)}")
if numeric_cols:
    desc = df[numeric_cols].describe().round(4)
    lines.append(desc.to_string())
    sums = df[numeric_cols].sum().round(4)
    lines.append("列合计：" + " | ".join(f"{c}={v:,.4f}" for c,v in sums.items()))
    # Precision check
    decimal_getcontext().prec = 28
    for col in numeric_cols[:3]:
        precise = sum(Decimal(str(v)) for v in df[col].dropna())
        lines.append(f"精确合计 {col} = {precise}")
result = "\\n".join(lines)
chart_labels = []
chart_series = []

# Generate overview chart
if numeric_cols:
    from matplotlib import rcParams
    rcParams['font.family'] = 'sans-serif'
    rcParams['font.sans-serif'] = ['Noto Sans CJK SC','PingFang SC','Microsoft YaHei','SimHei','Arial','sans-serif']
    rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(10, 6))
    means = df[numeric_cols[:6]].mean()
    ax.bar(means.index, means.values,
           color=['#2563EB','#F59E0B','#22C55E','#EF4444','#8B5CF6','#0EA5E9'][:len(means)])
    ax.set_title('数值列均值概览', fontsize=14, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
"""
