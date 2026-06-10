"""Data Analyst Skill — natural language → pandas/scipy/numpy → structured results.

Capabilities:
  • Descriptive statistics (mean, median, std, percentiles, skewness, kurtosis)
  • Trend analysis (moving average, linear regression trend, seasonal decomposition)
  • Year-over-year / Month-over-month growth rates
  • Ranking & top-N analysis
  • Correlation & covariance matrices
  • Anomaly / outlier detection (IQR, Z-score)
  • Distribution analysis (histogram bins, normality test)
  • Comparative analysis across categories or time periods
  • Pivot tables and cross-tabulation
  • Chart-ready data extraction (returns ECharts-compatible data arrays)

Execution model:
  1. LLM generates pandas/numpy/scipy Python code targeting `result` variable
  2. Code runs in isolated sandbox (30 s timeout, no I/O)
  3. On error, LLM auto-repairs the code once and retries
  4. Output is structured as {summary, table_md, chart_data, code}
"""
from __future__ import annotations

import json
import logging

from app.skills.base import Skill
from app.services.llm_service import chat_json, chat
from app.services.sandbox import execute_python
from app.skills.offline.sota_utils import self_critique, adversarial_review

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Question-type classifier → selects code generation strategy
# ---------------------------------------------------------------------------

_STRATEGY_MAP = [
    (["同比", "环比", "增长率", "增速", "yoy", "mom", "growth"], "growth_rate"),
    (["排名", "排序", "top", "前", "最大", "最小", "最高", "最低", "第一", "第二"], "ranking"),
    (["相关", "关联", "相关性", "correlation", "covariance"], "correlation"),
    (["异常", "离群", "outlier", "异常值", "偏差", "z-score", "iqr"], "anomaly"),
    (["分布", "直方", "histogram", "频率", "频次", "区间"], "distribution"),
    (["趋势", "走势", "时序", "时间序列", "trend", "moving average", "均线"], "trend"),
    (["对比", "比较", "compare", "差异", "差距", "各", "分组", "group"], "comparison"),
    (["透视", "交叉", "pivot", "crosstab", "分类汇总"], "pivot"),
    (["预测", "预估", "forecast", "regression", "回归", "外推"], "forecast"),
]

_STRATEGY_GUIDES: dict[str, str] = {
    "growth_rate": """
计算增长率分析代码要求：
- 用 pandas .pct_change() 或手动 (new-old)/old 计算增长率
- 输出同比/环比两列（如有时间维度）
- 计算 CAGR = (最终值/初始值)**(1/(n-1)) - 1
- 标注增长最快/最慢的时期
- result 设为 markdown 字符串：先一段文字摘要（2-3句），再附 markdown 表格
- ★ 图表：sns.lineplot 展示原始值 + 增长率双轴图，或 plt.bar 展示各期增长率（正负不同色）
""",
    "ranking": """
计算排名分析代码要求：
- 用 .rank(ascending=False) 或 .nlargest() / .nsmallest()
- 前5名高亮标注，倒数3名标注
- 计算各项占总量的百分比
- result 设为 markdown 字符串：摘要 + 排名表格
- ★ 图表：水平条形图（sns.barplot 或 plt.barh），按值排序，顶/末端标注数值
""",
    "correlation": """
计算相关性分析代码要求：
- 用 .corr() 生成相关矩阵
- 标注绝对值>0.7 的强相关对
- 标注绝对值<0.3 的弱相关对
- 用 scipy_stats.pearsonr 计算 p 值（如样本>5）
- result 设为 markdown 字符串：强/弱相关结论 + 相关矩阵表格
- ★ 图表：sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0, fmt='.2f')
""",
    "anomaly": """
计算异常检测代码要求：
- IQR 法: Q1-1.5*IQR < x < Q3+1.5*IQR 外为异常
- Z-score 法: |z| > 2.5 为异常
- 综合两种方法，报告共识异常点
- result 设为 markdown 字符串：异常摘要 + 异常值明细表格
- ★ 图表：scatter 图，正常点蓝色，异常点红色高亮（s=80, zorder=5）
""",
    "distribution": """
计算分布分析代码要求：
- 输出均值、中位数、标准差、偏度、峰度
- 用 pd.cut 分 6-8 个区间，计算频率分布
- 用 scipy_stats.normaltest 检验正态性
- result 设为 markdown 字符串：分布特征描述 + 频率分布表格
- ★ 图表：sns.histplot(kde=True) 或 sns.violinplot，标注均值/中位数参考线
""",
    "trend": """
计算趋势分析代码要求：
- 计算 3/6/12 期移动平均（视数据长度）
- 用 numpy.polyfit(x, y, 1) 拟合线性趋势，输出斜率和 R²
- 标注趋势转折点（局部极值）
- result 设为 markdown 字符串：趋势描述 + 关键时间节点表格
- ★ 图表：sns.lineplot + fill_between 阴影，叠加移动均线（不同颜色），标注极值点
""",
    "comparison": """
计算对比分析代码要求：
- 用 groupby + agg 计算各分组的均值、总量、占比
- 计算各分组间的绝对差异和相对差异
- 标注表现最好/最差的分组
- result 设为 markdown 字符串：对比摘要 + 分组汇总表格
- ★ 图表：分组柱状图（sns.barplot）或分组小提琴图，顶部显示数值标签
""",
    "pivot": """
计算透视表代码要求：
- 用 pd.pivot_table 生成交叉汇总
- 添加行/列总计（margins=True）
- 计算各单元格占行总量/列总量的百分比
- result 设为 markdown 字符串：透视表摘要 + markdown 透视表
- ★ 图表：sns.heatmap 热力图展示透视表（annot=True, fmt=',.0f', cmap='YlOrRd'）
""",
    "forecast": """
计算预测分析代码要求：
- 用 numpy.polyfit 或 scipy_stats.linregress 线性回归
- 预测未来 3-6 个周期，附 95% 置信区间（如数据充足）
- 输出 R² 拟合度和预测准确度评估
- result 设为 markdown 字符串：预测摘要 + 预测值表格（含区间）
- ★ 图表：历史值折线（实线）+ 预测值折线（虚线）+ 置信区间阴影（fill_between）
""",
    "default": """
计算综合描述性统计代码要求：
- 输出各数值列的 count, mean, median, std, min, 25%, 75%, max
- 标注最显著的数据特征（最大值、分布特征等）
- result 设为 markdown 字符串：核心洞察摘要 + 统计汇总表格
- ★ 图表：最多选 2 个最重要的数值列，生成对比条形图或分布图
""",
}

# ---------------------------------------------------------------------------
# Skill implementation
# ---------------------------------------------------------------------------

_CODE_SYSTEM = """\
你是资深数据分析工程师兼可视化专家，专精 pandas / numpy / scipy / matplotlib / seaborn / plotly。
生成的 Python 代码在一个受限沙盒中执行，DATA_STR 变量已预先注入（str 类型）。

## 预注入的可视化库（直接使用，无需 import）
- plt      — matplotlib.pyplot（Agg 无头后端，figsize 至少 (10,6)）
- np       — numpy
- pd       — pandas
- sns      — seaborn（主题 whitegrid 已预设，支持 heatmap/boxplot/violin/kde/regplot/barplot）
- px       — plotly.express（bar/line/scatter/pie/sunburst/treemap/choropleth）
- go       — plotly.graph_objects
- squarify — matplotlib 矩形树图
- WordCloud — 词云
- nx        — networkx（网络图）
- scipy_stats — scipy.stats
- sm        — statsmodels.api

## 预注入的精度计算库（直接使用，无需 import）
- Decimal, ROUND_HALF_UP, decimal_getcontext — 高精度十进制运算
  用法：getcontext().prec=28; sum(Decimal(str(v)) for v in series)
- Fraction — fractions.Fraction（精确分数运算）
- math, statistics — Python 内置数学/统计模块
- mpmath   — 任意精度浮点数（mp.dps=50 设置精度）
- sp       — sympy（符号数学：sp.Rational, sp.nsimplify, sp.factor）
- tabulate — tabulate(rows, headers, tablefmt='pipe')（Markdown 表格输出）
- StringIO — io.StringIO（字符串读取 CSV）
- json     — json 模块
- pl       — polars（快速 DataFrame 操作）
- duckdb   — 嵌入式 SQL 分析引擎

## 变量约定（必须全部赋值）
- result       : str  — markdown 格式分析报告（摘要 + 表格，不少于 80 字）
- chart_labels : list — X 轴类别/时间列表，如 ['Q1','Q2','Q3','Q4']
- chart_data   : list — [(系列名:str, 数值列表:list), ...] 最多 6 个系列
- chart_series : list — [{"name":..., "values":[...]}] 格式（与 chart_data 同步赋值）

## 数据读取（DATA_STR 已注入，直接使用）
```python
# 自动检测 CSV / JSON（推荐）
try:
    df = pd.read_csv(StringIO(DATA_STR), sep=None, engine='python', encoding='utf-8')
except Exception:
    try:
        df = pd.DataFrame(json.loads(DATA_STR))
    except Exception:
        df = pd.DataFrame()
```

## 数值列清洗（必须执行）
```python
for col in df.columns:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(df[col])
numeric_cols = df.select_dtypes(include='number').columns.tolist()
df[numeric_cols] = df[numeric_cols].fillna(0).replace([float('inf'), float('-inf')], 0)
```

## 精确计算（推荐用 Decimal 处理金额/比率）
```python
# 高精度求和（避免浮点误差）
decimal_getcontext().prec = 28
precise_total = sum(Decimal(str(v)) for v in df['金额列'].dropna() if v == v)
# 精确百分比
pct = (Decimal(str(part)) / Decimal(str(total)) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

## ★ 图表生成要求（必须生成至少一张图）
- 根据分析类型选择最合适的图表：
  - 趋势/时序 → sns.lineplot 或 plt.plot + fill_between
  - 对比/排名 → sns.barplot 或 plt.bar，顶部显示数值标签
  - 分布 → sns.histplot / sns.violinplot / sns.boxplot
  - 占比 → plt.pie（donut：wedgeprops=dict(width=0.6)）或 squarify treemap
  - 相关 → sns.heatmap（相关矩阵）或 sns.regplot
  - 多维 → sns.pairplot 或 subplots 组合
- figsize 至少 (10,6)；标题用中文，fontsize=14；轴标签中文，fontsize=12
- 专业配色：sns.set_palette("Blues_d") 或 colors=['#2563EB','#F59E0B','#22C55E','#EF4444','#8B5CF6']
- 数值标注：bar顶端显示数值，pie显示百分比
- 去除顶部/右侧边框：ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
- 淡灰网格：ax.yaxis.grid(True, linestyle='--', alpha=0.4)
- 代码末尾 plt.tight_layout()（不要调用 plt.show() 或 plt.savefig()）
- 如使用 plotly，将 fig 存入 _plotly_fig = fig

## 代码规范
1. 不使用 print()，全部通过变量返回
2. 精度要求高时用 Decimal：
   ```python
   decimal_getcontext().prec = 28
   precise_total = sum(Decimal(str(v)) for v in df['金额'].dropna())
   ```
3. 浮点数保留 4 位（精确），展示时 2 位：round(x, 4) 计算，f"{v:,.2f}" 展示
4. 大数字格式化：f"{v:,.2f}"（千分位分隔符）
5. 空 DataFrame 检查：if df.empty: result = "数据为空"; chart_labels = []; ...
6. 所有 division 加防零保护：/ (denom if denom != 0 else 1)
7. 可以直接用 pd 读取 Excel（沙盒已注入 openpyxl/xlrd）
8. 对字符串数字列做转换：pd.to_numeric(df[col], errors='coerce')
9. 代码长度控制在 150 行以内
10. 关键数字用 tabulate 输出 Markdown 表格存入 result

## result 格式要求
```markdown
**洞察摘要**
- 结论1（含具体数字）
- 结论2
- 结论3

| 列名1 | 列名2 | 列名3 |
|---|---|---|
| 值 | 值 | 值 |
```

只输出 JSON: {"code": "完整Python代码（不含注释、不含 print）"}
"""


class DataAnalyzerSkill(Skill):
    name = "analyze_data"
    description = (
        "SOTA数据深度分析：对表格数据执行统计/趋势/排名/相关性/异常检测/分布/对比/透视/预测分析。"
        "含CoT策略选择、代码自动生成、沙箱执行、自动修复、结果验证、自评和红队挑战。"
        "输出 markdown 摘要 + 表格 + 图表数据 + 质量评分"
    )
    category = "data"
    parameters = {
        "data": {
            "type": "string",
            "description": "CSV 或 JSON 格式的数据（最多 20000 字符）",
        },
        "question": {
            "type": "string",
            "description": "分析问题，例如：'各分行贷款余额同比增长率排名？'",
        },
        "analysis_type": {
            "type": "string",
            "description": "可选：auto|growth_rate|ranking|correlation|anomaly|distribution|trend|comparison|pivot|forecast",
            "default": "auto",
        },
        "context": {
            "type": "string",
            "description": "业务背景说明，帮助生成更准确的解读",
            "default": "",
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
        data = (params.get("data") or "").strip()
        question = (params.get("question") or "").strip()
        analysis_type = params.get("analysis_type", "auto")
        biz_context = params.get("context", "")
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)

        if not data or not question:
            return {"result": "", "error": "data 和 question 参数不能为空"}

        # Detect analysis strategy
        strategy = _detect_strategy(question, analysis_type)
        strategy_guide = _STRATEGY_GUIDES.get(strategy, _STRATEGY_GUIDES["default"])

        # Truncate data to avoid context overflow
        data_preview = data[:12000]

        user_prompt = _build_code_prompt(data_preview, question, strategy_guide, biz_context)

        # First attempt: generate code
        code = await _generate_code(user_prompt)
        if not code:
            return {"result": "无法生成分析代码", "error": "code generation failed", "strategy": strategy}

        # Execute in sandbox
        exec_result = await _run_code(code, data_preview)

        # Auto-repair on error
        if exec_result.get("error") and not exec_result.get("result"):
            logger.info("DataAnalyzer: first execution failed, attempting auto-repair")
            repair_prompt = _build_repair_prompt(code, exec_result["error"], data_preview, question)
            repaired_code = await _generate_code(repair_prompt, is_repair=True)
            if repaired_code:
                exec_result = await _run_code(repaired_code, data_preview)
                code = repaired_code

        return await _build_output_sota(exec_result, code, strategy, question, enable_critique, enable_adversarial)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_strategy(question: str, requested: str) -> str:
    if requested and requested != "auto":
        return requested
    q = question.lower()
    for keywords, strategy in _STRATEGY_MAP:
        if any(kw in q for kw in keywords):
            return strategy
    return "default"


def _build_code_prompt(data: str, question: str, strategy_guide: str, biz_context: str) -> str:
    context_line = f"\n业务背景: {biz_context}" if biz_context else ""
    is_csv = "," in data[:500] or "\t" in data[:500]
    parse_hint = (
        'pd.read_csv(StringIO(DATA_STR), encoding="utf-8")'
        if is_csv
        else 'pd.DataFrame(json.loads(DATA_STR))'
    )
    return f"""数据（前12000字符）:
```
{data[:12000]}
```
{context_line}
分析问题: {question}

数据解析提示: 用 `{parse_hint}` 读取数据，变量名 DATA_STR 替换为实际字符串。

{strategy_guide}

额外要求：
- chart_labels = 类别/时间列的 list（如 ['Q1','Q2','Q3','Q4']）
- chart_data = [(系列名, 数值list), ...] 格式，最多6个系列
- result 必须是完整 markdown 字符串，不少于100字，含：
  1. **洞察摘要**（3-5句关键结论）
  2. 数据表格（markdown | 格式）
- ★★★ 必须使用 plt/sns/px 生成至少一张图表（沙盒已预注入这些库，无需 import）
  - 图表配置要求：标题中文，figsize=(10,6)，plt.tight_layout() 结尾，不调用 plt.show()/savefig()
  - 若用 plotly，将 fig 存入变量 _plotly_fig
"""


def _build_repair_prompt(failed_code: str, error: str, data: str, question: str) -> str:
    return f"""以下 Python 代码运行报错，请修复后重新生成。

原始问题: {question}

报错信息:
{error[:800]}

原始代码:
```python
{failed_code[:3000]}
```

修复要求:
1. 保持分析逻辑不变，只修复语法/运行时错误
2. 确保 result, chart_labels, chart_data 三个变量都被赋值
3. 对 NaN/Inf/空值做防御处理
4. 数值列转换：pd.to_numeric(col, errors='coerce').fillna(0)

只输出 JSON: {{"code": "修复后的完整Python代码"}}
"""


async def _generate_code(prompt: str, is_repair: bool = False) -> str:
    try:
        resp = await chat_json(
            [
                {"role": "system", "content": _CODE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.05 if is_repair else 0.1,
        )
        return (resp.get("code") or "").strip()
    except Exception as exc:
        logger.error("DataAnalyzer: code generation error: %s", exc)
        return ""


async def _run_code(code: str, data: str) -> dict:
    """Execute analysis code with safe data injection.

    For datasets >32KB, we stage the data as a temp file and inject the file
    path instead of the raw string — eliminating the JSON-blob overhead that
    capped baseline analysis at ~12k chars of input.
    """
    staged_path = None
    use_staging = len(data) > 32768  # 32KB threshold

    if use_staging:
        # Stage as CSV (works for both CSV input and JSON if pre-parsed)
        try:
            from app.services.sandbox import stage_dataframe
            # Try to parse as CSV first, fall back to JSON-list
            df = None
            try:
                from io import StringIO
                import pandas as pd
                df = pd.read_csv(StringIO(data), sep=None, engine="python")
            except Exception:
                try:
                    import pandas as pd
                    df = pd.DataFrame(json.loads(data))
                except Exception:
                    df = None
            if df is not None and not df.empty:
                staged_path = stage_dataframe(df)
        except Exception as exc:
            logger.debug("Data staging failed, falling back to inline: %s", exc)

    # ── Shared variable preamble (uses sandbox pre-injected globals) ─────────
    # pd, np, scipy_stats, Decimal, math, tabulate, etc. are all already in
    # exec_globals — no need to import them again. We only set up DATA_STR.
    shared_vars = "chart_labels = []\nchart_data = []\nchart_series = []\nresult = ''\n"

    if staged_path:
        # Staged path: code reads from DATA_PATH (Parquet/CSV file)
        injectable = (
            "# Load staged dataset\n"
            "if DATA_PATH.endswith('.parquet'):\n"
            "    _df_stage = pd.read_parquet(DATA_PATH)\n"
            "else:\n"
            "    _df_stage = pd.read_csv(DATA_PATH)\n"
            "DATA_STR = _df_stage.to_csv(index=False)\n"
            + shared_vars
            + code
        )
        try:
            exec_result = await execute_python(
                injectable,
                timeout=90,                # larger budget for staged analyses
                staged_data_path=staged_path,
                capture_figures=True,
            )
            return exec_result
        except Exception as exc:
            return {"error": str(exc), "stdout": "", "variables": {}}
        finally:
            try:
                from app.services.sandbox import cleanup_staged
                cleanup_staged(staged_path)
            except Exception:
                pass

    # Small data: inline injection
    data_json = json.dumps(data)
    injectable = (
        f"DATA_STR = {data_json}\n"
        + shared_vars
        + code
    )
    try:
        exec_result = await execute_python(injectable, timeout=60, capture_figures=True)
        return exec_result
    except Exception as exc:
        return {"error": str(exc), "stdout": "", "variables": {}}


def _build_output(exec_result: dict, code: str, strategy: str, question: str) -> dict:
    error = exec_result.get("error") or ""
    stdout = exec_result.get("stdout") or ""
    variables = exec_result.get("variables") or {}

    result_text = variables.get("result") or stdout or ""
    chart_labels = variables.get("chart_labels") or []
    chart_data_raw = variables.get("chart_data") or []

    # Normalise chart_data: accept list-of-tuples or list-of-lists
    chart_series = []
    if isinstance(chart_data_raw, list):
        for item in chart_data_raw[:6]:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                name, vals = item
                if isinstance(vals, list):
                    chart_series.append({"name": str(name), "values": [round(float(v), 2) if v is not None else 0 for v in vals]})

    out: dict = {
        "result": result_text[:8000] if result_text else f"分析完成（策略：{strategy}）。查询：{question}",
        "strategy": strategy,
        "code": code,
    }
    if chart_labels:
        out["chart_labels"] = chart_labels
    if chart_series:
        out["chart_series"] = chart_series

    # ── Post-computation sanity verification ─────────────────────────────────
    # Catches: all-NaN metrics, ±Inf values, all-zero divisions, epoch dates.
    try:
        from app.services.result_verifier import verify_scalar_metrics, auto_verify
        ver_results: list[dict] = []
        # Check metrics dict if present
        metrics = variables.get("metrics")
        if isinstance(metrics, dict):
            m_report = verify_scalar_metrics(metrics)
            if m_report.issues:
                ver_results.append(m_report.to_dict())
        # Check df_summary table if present
        df_summary = variables.get("df_summary")
        if df_summary is not None:
            d_report = auto_verify(df_summary)
            if d_report.issues:
                ver_results.append(d_report.to_dict())
        # Check chart_series for NaN/Inf
        if chart_series:
            chart_metrics = {f"series_{i}_total": sum(s.get("values") or [0]) for i, s in enumerate(chart_series)}
            c_report = verify_scalar_metrics(chart_metrics)
            if c_report.issues:
                ver_results.append(c_report.to_dict())
        if ver_results:
            out["verification"] = ver_results
    except Exception as exc:
        logger.debug("Result verification step failed: %s", exc)

    # Surface sandbox-level artifacts (figures + exec_ms)
    figures = exec_result.get("figures") or []
    if figures:
        out["figures"] = figures
    if exec_result.get("exec_ms"):
        out["exec_ms"] = exec_result["exec_ms"]

    if error and not result_text:
        out["error"] = error[:400]
    return out


async def _build_output_sota(exec_result: dict, code: str, strategy: str, question: str, enable_critique: bool, enable_adversarial: bool) -> dict:
    """SOTA-enhanced output builder with optional self-critique and adversarial review."""
    out = _build_output(exec_result, code, strategy, question)

    # SOTA: Self-critique on analysis quality
    if enable_critique and out.get("result"):
        try:
            critique = await self_critique(
                draft=out["result"][:3000],
                topic=f"数据分析 - {strategy}",
                dimensions=["data_grounding", "logical_rigor", "specificity"],
            )
            out["quality_score"] = round(critique["overall_score"] * 10)
            out["critique"] = critique
        except Exception as exc:
            logger.debug("DataAnalyzer self-critique failed: %s", exc)

    # SOTA: Adversarial review
    if enable_adversarial and out.get("result"):
        try:
            adv = await adversarial_review(
                output=out["result"][:3000],
                topic=f"数据分析 - {strategy}",
            )
            out["adversarial"] = adv
        except Exception as exc:
            logger.debug("DataAnalyzer adversarial failed: %s", exc)

    return out
