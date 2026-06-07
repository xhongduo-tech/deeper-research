"""
Excel/CSV grounding service — upgraded to full async + precision computing.

For tabular uploads (xlsx, xls, xlsb, ods, csv, tsv), the LLM generates a
pandas/numpy/scipy/Decimal analysis script that runs in the full-library sandbox.
The stdout + return value become the grounded text that replaces the naive
text-extraction snippet in uploaded_texts, ensuring the report uses actual
data values rather than approximate text renderings.

Improvements over v1:
- Reads multi-sheet Excel (up to 6 sheets), picks the largest/most numeric
- Switches from sync execute_sandbox → async execute_python (full lib stack)
- Code generation prompt allows Decimal, mpmath, scipy, statsmodels, numpy
- Larger sample in prompt (30 rows instead of 5)
- Generates chart figures as base64 PNGs alongside text
- Handles .xlsb (pyxlsb) and .ods (odfpy) formats
- Better encoding detection for GBK/UTF-8 CSVs
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from app.services.llm_service import chat
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)

_TABULAR_EXTS = {".xlsx", ".xls", ".xlsb", ".xlsm", ".ods", ".csv", ".tsv"}

# Keywords that suggest a column is a dimension (entity) rather than a KPI
_DIM_KEYWORDS = [
    "分行", "机构", "部门", "地区", "城市", "区域", "产品", "渠道",
    "客户", "团队", "支行", "网点", "公司", "子公司", "业务线",
    "类别", "类型", "品类", "门店", "项目", "合同", "人员",
]


def _detect_branch_structure(df: pd.DataFrame) -> dict | None:
    """Detect if the DataFrame follows a multi-entity pattern (rows=entities, cols=KPIs).

    Returns a structured dict when detected, None otherwise.
    """
    if df.shape[0] < 2 or df.shape[1] < 2:
        return None

    # Look for a dimension column by keyword match first
    dim_col = None
    for col in df.columns:
        col_str = str(col)
        if any(kw in col_str for kw in _DIM_KEYWORDS):
            # Confirm it's categorical (string or low-cardinality)
            is_str = pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object
            if is_str or df[col].nunique() <= max(df.shape[0], 2):
                dim_col = col
                break

    # Fallback: first column is string-typed and remaining columns are numeric
    if dim_col is None:
        first_col = df.columns[0]
        numeric_cols_all = df.select_dtypes(include="number").columns.tolist()
        is_first_string = pd.api.types.is_string_dtype(df[first_col]) or df[first_col].dtype == object
        if is_first_string and len(numeric_cols_all) >= 2 and df.shape[0] >= 3:
            dim_col = first_col

    if dim_col is None:
        return None

    kpi_cols = df.select_dtypes(include="number").columns.tolist()
    if not kpi_cols:
        return None

    branches = df[dim_col].dropna().astype(str).tolist()

    return {
        "is_branch_data": True,
        "dimension_col": str(dim_col),
        "kpi_cols": [str(c) for c in kpi_cols[:10]],
        "branch_count": len(branches),
        "branch_names": branches[:25],
    }


def is_tabular(file_type: str) -> bool:
    ext = file_type.lower().strip()
    if not ext.startswith("."):
        ext = "." + ext
    return ext in _TABULAR_EXTS


def _load_dataframe(file_path: str, file_type: str) -> tuple[pd.DataFrame | None, dict]:
    """Load a tabular file into a DataFrame.

    Returns:
        (df, meta) where meta contains:
            sheet_name, all_sheets, n_rows, n_cols, file_type, encoding
    """
    ext = file_type.lower().strip()
    if not ext.startswith("."):
        ext = "." + ext
    meta: dict = {"file_type": ext, "all_sheets": [], "sheet_name": "Sheet1", "encoding": "utf-8"}

    try:
        if ext in (".xlsx", ".xlsm"):
            return _load_excel_xlsx(file_path, meta)
        if ext == ".xlsb":
            return _load_excel_xlsb(file_path, meta)
        if ext == ".xls":
            return _load_excel_xls(file_path, meta)
        if ext == ".ods":
            return _load_ods(file_path, meta)
        if ext in (".csv", ".tsv"):
            return _load_csv(file_path, ext, meta)
    except Exception as e:
        logger.warning(f"excel_grounding: failed to load {file_path}: {e}")
    return None, meta


def _load_excel_xlsx(path: str, meta: dict) -> tuple[pd.DataFrame | None, dict]:
    """Load .xlsx / .xlsm — pick the most data-rich sheet."""
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        sheet_names = xl.sheet_names
        meta["all_sheets"] = sheet_names

        # Pick the sheet with the most numeric data
        best_df: pd.DataFrame | None = None
        best_score = -1
        for sname in sheet_names[:8]:
            try:
                df = xl.parse(sname, header=0)
                # Score: total numeric cells
                score = df.select_dtypes(include="number").size + df.shape[0]
                if score > best_score:
                    best_score = score
                    best_df = df
                    meta["sheet_name"] = sname
            except Exception:
                continue
        return best_df, meta
    except Exception as e:
        logger.warning(f"xlsx load failed: {e}")
        return None, meta


def _load_excel_xls(path: str, meta: dict) -> tuple[pd.DataFrame | None, dict]:
    """Load legacy .xls with xlrd."""
    try:
        df = pd.read_excel(path, engine="xlrd")
        meta["sheet_name"] = "Sheet1"
        return df, meta
    except Exception as e:
        logger.warning(f"xls load failed: {e}")
        return None, meta


def _load_excel_xlsb(path: str, meta: dict) -> tuple[pd.DataFrame | None, dict]:
    """Load Excel Binary (.xlsb) with pyxlsb."""
    try:
        df = pd.read_excel(path, engine="pyxlsb")
        meta["sheet_name"] = "Sheet1"
        return df, meta
    except Exception as e:
        logger.warning(f"xlsb load failed: {e}")
        return None, meta


def _load_ods(path: str, meta: dict) -> tuple[pd.DataFrame | None, dict]:
    """Load OpenDocument Spreadsheet (.ods) with odfpy."""
    try:
        df = pd.read_excel(path, engine="odf")
        meta["sheet_name"] = "Sheet1"
        return df, meta
    except Exception as e:
        logger.warning(f"ods load failed: {e}")
        return None, meta


def _load_csv(path: str, ext: str, meta: dict) -> tuple[pd.DataFrame | None, dict]:
    """Load CSV/TSV with smart encoding detection."""
    sep = "\t" if ext == ".tsv" else ","
    # Try multiple encodings in order of likelihood
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "gb18030", "big5", "latin-1"]
    for enc in encodings:
        try:
            df = pd.read_csv(path, sep=sep, encoding=enc, engine="python",
                             on_bad_lines="skip", dtype_backend="numpy_nullable")
            meta["encoding"] = enc
            meta["sheet_name"] = Path(path).stem
            return df, meta
        except (UnicodeDecodeError, Exception):
            continue
    return None, meta


def _build_visualization_grounding(df: pd.DataFrame, filename: str) -> str:
    """Create deterministic chart-ready hints from uploaded tabular data."""
    numeric_cols = [str(c) for c in df.select_dtypes(include="number").columns.tolist()]
    if not numeric_cols:
        return ""

    cols = df.columns.tolist()
    dim_col = None
    for col in cols:
        if str(col) not in numeric_cols:
            nunique = df[col].nunique(dropna=True)
            if 2 <= nunique <= min(max(len(df), 2), 30):
                dim_col = col
                break

    time_col = None
    for col in cols:
        name = str(col)
        if any(k in name.lower() for k in ("date", "time", "year", "month")) or any(k in name for k in ("日期", "时间", "年份", "月份", "季度")):
            time_col = col
            break

    lines = ["【图表数据建议】", f"数据源文件：{filename}", f"可用于图表的数值列：{', '.join(numeric_cols[:12])}"]
    if dim_col is not None:
        labels = df[dim_col].dropna().astype(str).head(8).tolist()
        lines.append(f"推荐对比维度：{dim_col}（示例标签：{'、'.join(labels)}）")
        for metric in numeric_cols[:4]:
            sample = df[[dim_col, metric]].dropna().head(8)
            if not sample.empty:
                pairs = "；".join(f"{r[dim_col]}={float(r[metric]):.2f}" for _, r in sample.iterrows())
                lines.append(f"- 可生成柱状/条形图：按「{dim_col}」比较「{metric}」；样本数据：{pairs}")
    if time_col is not None:
        for metric in numeric_cols[:3]:
            sample = df[[time_col, metric]].dropna().head(8)
            if not sample.empty:
                pairs = "；".join(f"{r[time_col]}={float(r[metric]):.2f}" for _, r in sample.iterrows())
                lines.append(f"- 可生成折线/面积图：按「{time_col}」展示「{metric}」趋势；样本数据：{pairs}")
    if len(numeric_cols) >= 2:
        lines.append(f"- 可生成组合图/复合图：主轴展示「{numeric_cols[0]}」，副叙事展示「{numeric_cols[1]}」或其增速/占比。")
    if len(numeric_cols) >= 3:
        lines.append(f"- 可生成热力图/雷达图：比较 {', '.join(numeric_cols[:5])} 等多指标表现。")
    return "\n".join(lines)


async def _generate_grounding_code(
    df: pd.DataFrame,
    brief: str,
    filename: str,
    meta: dict | None = None,
    branch_ctx: dict | None = None,
) -> str:
    """Generate comprehensive analysis code with precision computing support."""
    meta = meta or {}
    columns = df.columns.tolist()
    dtypes = {str(k): str(v) for k, v in df.dtypes.items()}
    # Show 30-row sample so LLM sees more patterns
    sample_rows = min(30, len(df))
    sample = df.head(sample_rows).to_dict(orient="records")
    shape = df.shape
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    all_sheets = meta.get("all_sheets", [])
    sheet_name = meta.get("sheet_name", "Sheet1")

    sheets_note = ""
    if len(all_sheets) > 1:
        sheets_note = f"\n文件含多个工作表：{', '.join(all_sheets[:8])}（已选用 {sheet_name}）"

    branch_instruction = ""
    if branch_ctx and branch_ctx.get("is_branch_data"):
        dim_col = branch_ctx["dimension_col"]
        kpi_cols = branch_ctx["kpi_cols"]
        branch_instruction = f"""
【检测到分行/机构维度数据】
维度列（实体名称）: {dim_col}
KPI指标列: {', '.join(kpi_cols)}

请在 analyze(df) 内务必包含：
1. 以 `{dim_col}` 分组，对每个KPI计算 sum/mean/max/min
2. 主要KPI（前3个）排名：Top5 和 Bottom5
3. 计算偏差：各分行值 − 全均值，标注高于/低于均值的
4. 输出分行×KPI透视表
5. 返回字符串摘要：共X个{dim_col}，{kpi_cols[0]}最高/最低/均值
"""

    prompt = f"""你是精确数据分析专家。用户正在撰写报告，请对上传数据进行严格精确的分析。

【报告主题】{brief or '（未指定）'}
【文件名】{filename}{sheets_note}
【数据规模】{shape[0]}行 × {shape[1]}列
【列名与类型】{dtypes}
【数值列】{numeric_cols[:20]}
【前{sample_rows}行样本】{sample}
{branch_instruction}

## 可用的预注入库（直接使用，无需 import）
- df          — 已注入的 pandas DataFrame（即上传的数据）
- pd          — pandas
- np          — numpy
- scipy_stats — scipy.stats（分布检验、pearsonr、spearmanr、ttest_ind 等）
- sm          — statsmodels.api（OLS、时间序列、ARIMA）
- Decimal     — decimal.Decimal（高精度十进制运算）
- ROUND_HALF_UP — decimal 舍入模式
- decimal_getcontext — 设置精度上下文
- math        — math 模块
- statistics  — statistics 模块（mean/median/stdev/variance）
- Fraction    — fractions.Fraction（精确分数运算）
- mpmath      — 任意精度数学（若需要极高精度）
- tabulate    — tabulate(data, headers, tablefmt='pipe')（Markdown表格）

## 分析代码要求
生成 `analyze(df)` 函数，函数内部：

**A. 基础统计（必须）**
1. 精确计算每个数值列的 sum / mean / median / std / min / max（用 round(x,4) 保留4位）
2. 对非数值列（维度列）输出 value_counts() 前10项
3. 输出空值率、数据类型异常情况

**B. 业务分析（按数据特征选择）**
4. 若有时序列（年/月/季/日期列）：计算增长率、累计值、期间对比
5. 若有分类维度列：groupby 汇总，排名前5和后5，计算各组占比
6. 若数值列≥2：计算相关系数矩阵，标注强相关对（|r|>0.7）
7. 若有明显的总计列/行（如含"合计"、"总计"的行）：单独提取并验证加总准确性

**C. 精确计算（重要）**
8. 对关键指标用 Decimal 重新计算：
   ```python
   from decimal import Decimal, ROUND_HALF_UP, getcontext
   getcontext().prec = 28
   precise_sum = sum(Decimal(str(v)) for v in df['列名'].dropna())
   ```
9. 计算同比/环比增长率（如有时序数据）

**D. 输出格式**
- 用 print() 输出 Markdown 格式表格（用 tabulate(data, headers, tablefmt='pipe')）
- 函数返回字符串摘要（不少于200字），包含：行列规模、关键数值、核心发现
- 在函数末尾调用：result = analyze(df)

## 代码规范
- 不读写文件，数据已通过 df 变量注入
- 所有除法加防零：/ (x if x != 0 else 1)
- 浮点数格式化：f"{{v:,.4f}}" 或 f"{{v:.2f}}%"
- 处理空值：.fillna(0) 或 .dropna()
- 尽量使用 vectorized 操作而非循环

只输出可直接执行的 Python 代码，不含 Markdown 标记或任何解释文字。"""

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是高精度数据分析代码专家。生成可直接运行的 Python 代码，"
                    "使用 pandas/numpy/scipy/Decimal 进行精准计算。只输出代码，无需解释。"
                ),
            },
            {"role": "user", "content": prompt},
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(
            agent_type="quinn",
            messages=messages,
        )
        code = await chat(
            messages=messages,
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0.15,      # lower temp for precise code
            max_tokens=2000,        # more room for comprehensive code
        )
        code = code.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()
        return code
    except Exception as e:
        logger.warning(f"excel_grounding: code generation failed: {e}")
        return _fallback_grounding_code()


async def _run_grounding_code_async(code: str, df: pd.DataFrame) -> tuple[str, str, list[dict]]:
    """Execute grounding code in the full-library async sandbox.

    Returns: (stdout_text, result_str, figures)
    """
    from app.services.sandbox import execute_python
    from app.agents.data_analyst import _build_df_preamble

    preamble = _build_df_preamble(df)
    full_code = preamble + "\n\n" + code

    try:
        exec_result = await execute_python(full_code, timeout=90, capture_figures=True)
        stdout_text = (exec_result.get("stdout") or "").strip()
        result_val = exec_result.get("variables", {}).get("result", "")
        result_str = str(result_val).strip() if result_val else ""
        figures = exec_result.get("figures") or []
        error = exec_result.get("error")
        if error and not result_str and not stdout_text:
            logger.warning(f"excel_grounding: sandbox error: {error[:300]}")
            # Try once more with a fallback
            fallback_code = preamble + "\n\n" + _fallback_grounding_code()
            retry = await execute_python(fallback_code, timeout=30, capture_figures=False)
            stdout_text = (retry.get("stdout") or "").strip()
            result_val = retry.get("variables", {}).get("result", "")
            result_str = str(result_val).strip() if result_val else ""
        return stdout_text, result_str, figures
    except Exception as e:
        logger.warning(f"excel_grounding: async execution failed: {e}")
        return "", "", []


def _fallback_grounding_code() -> str:
    """Minimal analysis code when LLM generation fails."""
    return """\
def analyze(df):
    import pandas as _pd
    lines = []
    lines.append(f"数据规模：{df.shape[0]}行 × {df.shape[1]}列")
    lines.append(f"列名：{', '.join(str(c) for c in df.columns.tolist())}")
    num_df = df.select_dtypes(include='number')
    if not num_df.empty:
        desc = num_df.describe().round(4)
        lines.append("数值统计：")
        lines.append(desc.to_string())
        sums = num_df.sum().round(4)
        lines.append("列合计：" + " | ".join(f"{c}={v:,.4f}" for c, v in sums.items()))
    return "\\n".join(lines)

result = analyze(df)
"""


async def ground_excel_file(
    file_path: str,
    file_type: str,
    filename: str,
    brief: str,
) -> Optional[str]:
    """Load a tabular file, run LLM-generated precision analysis, return grounded text.

    The returned string is inserted into uploaded_texts so the report pipeline
    has access to precise, calculated values rather than raw text extractions.
    """
    df, meta = _load_dataframe(file_path, file_type)
    if df is None or df.empty:
        return None

    logger.info(
        f"excel_grounding: grounding {filename} "
        f"({df.shape[0]}×{df.shape[1]}, sheet={meta.get('sheet_name', '?')})"
    )

    branch_ctx = _detect_branch_structure(df)
    if branch_ctx:
        logger.info(
            f"excel_grounding: branch structure detected — "
            f"dim={branch_ctx['dimension_col']}, "
            f"branches={branch_ctx['branch_count']}"
        )

    code = await _generate_grounding_code(df, brief, filename, meta=meta, branch_ctx=branch_ctx)
    stdout_text, result_str, figures = await _run_grounding_code_async(code, df)

    parts: list[str] = []

    # ── Reliable baseline (always included) ─────────────────────────────────
    all_sheets = meta.get("all_sheets", [])
    if len(all_sheets) > 1:
        parts.append(f"文件工作表：{', '.join(all_sheets[:8])}（分析工作表：{meta.get('sheet_name', '?')}）")
    parts.append(f"数据规模：{df.shape[0]} 行 × {df.shape[1]} 列")
    parts.append(f"数据列：{', '.join(str(c) for c in df.columns.tolist())}")

    # ── Branch structure metadata ────────────────────────────────────────────
    if branch_ctx and branch_ctx.get("is_branch_data"):
        branch_names_preview = "、".join(branch_ctx["branch_names"][:10])
        if branch_ctx["branch_count"] > 10:
            branch_names_preview += f"...（共{branch_ctx['branch_count']}个）"
        parts.append(
            f"\n【分行结构】dimension_col={branch_ctx['dimension_col']} | "
            f"kpi_cols={','.join(branch_ctx['kpi_cols'])} | "
            f"branch_count={branch_ctx['branch_count']} | "
            f"branches={branch_names_preview}"
        )

    # ── LLM-generated analysis (stdout + return value) ──────────────────────
    if stdout_text:
        parts.append("\n【计算分析输出】\n" + stdout_text[:8000])
    if result_str and result_str not in ("None", ""):
        parts.append("\n【数据摘要】\n" + result_str[:3000])

    # ── Hard ground-truth numeric stats ─────────────────────────────────────
    try:
        numeric_df = df.select_dtypes(include="number")
        if not numeric_df.empty:
            desc_str = numeric_df.describe().round(4).to_string()
            parts.append("\n【数值统计（精确参考）】\n" + desc_str)
            sums = numeric_df.sum(numeric_only=True).round(4)
            sums_str = " | ".join(f"{c}={v:,.4f}" for c, v in sums.items())
            parts.append(f"【列合计】{sums_str}")
    except Exception:
        pass

    # ── Visualization grounding ──────────────────────────────────────────────
    visual_grounding = _build_visualization_grounding(df, filename)
    if visual_grounding:
        parts.append("\n" + visual_grounding)

    # ── Chart figures note ───────────────────────────────────────────────────
    if figures:
        parts.append(f"\n【已生成 {len(figures)} 张分析图表（base64 PNG）】")

    result_text = "\n".join(parts)

    # Store figures on the result so callers can broadcast them
    # (attribute injection — callers check hasattr(result_text, '_figures'))
    # We use a wrapper instead to keep the return type str
    return result_text
