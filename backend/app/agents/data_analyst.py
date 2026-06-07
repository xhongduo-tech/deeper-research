"""
Data Analyst Agent — Natural language → pandas + visualization analysis.

Upgraded from basic pandas-only to full chart generation pipeline:
- matplotlib / seaborn / plotly / scipy / statsmodels
- squarify, wordcloud, networkx, mplfinance, pywaffle, calplot, joypy
- Figures captured as base64 PNG via execute_python()
- Chart type auto-selected based on data shape + question intent
"""

import logging
import time
from typing import Any

import pandas as pd

from app.models.research import AnalysisResult
from app.services.llm_service import chat, chat_json
from app.services.model_router import get_model_router
from app.services.sandbox import execute_python

logger = logging.getLogger(__name__)

# ── Chart library availability catalogue (injected into LLM prompt) ────────
AVAILABLE_CHART_LIBS = """
可用的可视化库（均已预导入到沙箱）：

基础：
  plt      — matplotlib.pyplot
  np       — numpy
  pd       — pandas
  sns      — seaborn（推荐用于统计图表：heatmap, violinplot, boxplot, pairplot, regplot）

交互式：
  px       — plotly.express（推荐用于快速图表：bar, line, scatter, pie, sunburst, treemap, choropleth）
  go       — plotly.graph_objects（自定义交互图表）
  make_subplots — plotly subplots

统计/科学：
  scipy_stats        — scipy.stats（分布、检验、回归）
  sm                 — statsmodels.api（时间序列、回归、ARIMA）

专用图表：
  squarify  — matplotlib 矩形树图（squarify.plot(sizes, label, color, ax=ax)）
  WordCloud — 词云（WordCloud(width=800,height=400).generate(text).to_image()）
  nx        — networkx（网络/流程图）
  mpf       — mplfinance（K线/蜡烛图：mpf.plot(ohlc_df, type='candle', ...)）
  Waffle    — pywaffle（华夫图：plt.figure(FigureClass=Waffle, ...)）
  calplot   — 日历热力图（calplot.calplot(series, ...)）
  joypy     — 山脊线图（joypy.joyplot(df, ...)）
  venn2/venn3 — 韦恩图（matplotlib_venn）
  adjust_text — 标签防重叠（scatter图）

绘图规范：
  - 保存到 plt.figure() 后 savefig / plt.show() 无效（已被 Agg backend 捕获）
  - 不要调用 plt.show()，直接 plt.tight_layout() 结尾即可
  - plotly 图形存入变量 _plotly_fig = fig（自动被捕获为 PNG）
  - 每张图单独 plt.figure()，建议 figsize=(10,6) 或 (12,7)
  - 中文字体已预配置，直接写中文标签即可
"""

# Chart type auto-selection hints
CHART_INTENT_MAP = {
    "分布": "seaborn histplot / violinplot / boxplot / kdeplot",
    "对比": "bar chart (plt/sns/px.bar) or grouped bars",
    "趋势": "line chart with area (sns.lineplot + fill_between)",
    "占比": "pie / donut (plt.pie) or squarify treemap or Waffle",
    "相关": "scatter + regression (sns.regplot / sns.pairplot)",
    "热力": "seaborn heatmap (sns.heatmap)",
    "网络": "networkx (nx.draw_networkx)",
    "词频": "WordCloud",
    "财务": "mplfinance K线图 (mpf.plot)",
    "地理": "plotly choropleth (px.choropleth)",
    "层级": "squarify treemap or plotly sunburst (px.sunburst)",
    "流程": "networkx directed graph or sankey (go.Sankey)",
    "时间序列": "sns.lineplot or statsmodels ARIMA",
    "统计检验": "scipy_stats + annotated bar/violin",
    "山脊": "joypy.joyplot",
}


class DataAnalystAgent:
    """Analyzes uploaded data + generates publication-quality charts."""

    async def analyze(self, df: pd.DataFrame, question: str) -> AnalysisResult:
        start = time.monotonic()

        # 1. Generate analysis + visualization code
        code = await self._generate_code(df, question)

        # 2. Execute in full-library sandbox
        exec_result = await self._execute(code, df)

        # 3. Generate insight
        insight = await self._generate_insight(exec_result, question)

        elapsed = int((time.monotonic() - start) * 1000)

        # 4. ECharts fallback (if no Python figures were produced)
        charts = []
        figures = exec_result.get("figures", [])
        if not figures:
            charts = self._extract_chart_configs(
                exec_result.get("variables", {}).get("result", df)
                if isinstance(exec_result.get("variables", {}).get("result"), pd.DataFrame)
                else df
            )

        return AnalysisResult(
            code=code,
            result_summary=str(exec_result.get("stdout", "") or exec_result.get("variables", {}).get("result", ""))[:2000],
            insight=insight,
            charts=charts,
            figures=figures,
            execution_time_ms=elapsed,
        )

    async def _generate_code(self, df: pd.DataFrame, question: str) -> str:
        columns = df.columns.tolist()
        dtypes = {str(k): str(v) for k, v in df.dtypes.to_dict().items()}
        sample = df.head(5).to_dict(orient="records")
        n_rows = len(df)

        # Infer likely chart intent from question
        chart_hints = [hint for kw, hint in CHART_INTENT_MAP.items() if kw in question]
        chart_hint_str = f"\n推荐图表方式：{' / '.join(chart_hints[:3])}" if chart_hints else ""

        prompt = f"""你是数据分析与可视化专家。请根据以下数据和用户问题，生成完整的 Python 分析和可视化代码。

## 数据信息
- 行数：{n_rows}
- 列名：{columns}
- 数据类型：{dtypes}
- 样本（前5行）：{sample}

## 用户问题
{question}{chart_hint_str}

## 可用库
{AVAILABLE_CHART_LIBS}

## 代码要求
1. 数据已作为 `df`（pandas DataFrame）注入，直接使用即可
2. 如果需要展示统计数据，将结果存入 `result` 变量
3. **必须生成至少一张图表**，使用上方可用库中最合适的方式
4. 图表要求：
   - 标题清晰（中文）
   - 轴标签中文
   - 图例清晰
   - 专业配色（seaborn 主题或 plotly 内置主题）
   - 如使用 plotly，将 fig 存入 `_plotly_fig = fig`
   - 如使用 matplotlib，直接绘制，不要调用 plt.show()
   - figsize 至少 (10, 6)
5. 代码末尾加 `plt.tight_layout()` 或 plotly 等效
6. 不要读写文件，不要调用 plt.savefig()
7. 只输出 Python 代码，不加任何解释或代码块标记

## 高质量图表清单（尽量满足）
- 渐变色或专业配色方案
- 数据标注（bar 顶部显示数值，pie 显示百分比）
- 网格线（淡灰色）
- 参考线（均值线、目标线）
- 标题 + 副标题
- 字体大小适中（title 14-16pt，标签 10-12pt）
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是数据可视化代码专家。生成可直接运行的 Python 代码，"
                        "利用 matplotlib/seaborn/plotly/squarify/wordcloud/networkx 等库创建专业图表。"
                        "只输出代码，不输出任何解释。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(
                agent_type="quinn", messages=messages
            )
            code = await chat(
                messages=messages, model=model, base_url=base_url, api_key=api_key,
                temperature=0.25, max_tokens=2000,
            )
            # Strip markdown fences
            code = (
                code.strip()
                .removeprefix("```python")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return code
        except Exception as e:
            logger.warning(f"Code generation failed: {e}")
            return _fallback_chart_code()

    async def _execute(self, code: str, df: pd.DataFrame) -> dict:
        """Execute code in full-library sandbox, inject df."""
        try:
            # Inject df as a staged variable via exec_globals injection trick:
            # execute_python() doesn't directly accept extra globals, but we can
            # prepend a serialisation + deserialization preamble.
            preamble = _build_df_preamble(df)
            full_code = preamble + "\n\n" + code
            result = await execute_python(full_code, timeout=60, capture_figures=True)
            return result
        except Exception as e:
            logger.warning(f"Sandbox execution failed: {e}")
            return {"error": str(e), "figures": [], "stdout": "", "variables": {}}

    def _extract_chart_configs(self, df: Any) -> list[dict]:
        """Fallback ECharts spec extraction (used only when no Python figures)."""
        configs = []
        try:
            if not isinstance(df, pd.DataFrame) or len(df) < 2:
                return configs
            numeric_cols = df.select_dtypes(include="number").columns.tolist()
            str_cols = df.select_dtypes(exclude="number").columns.tolist()
            if not numeric_cols:
                return configs
            categories_col = str_cols[0] if str_cols else None
            categories = (
                df[categories_col].astype(str).tolist()
                if categories_col
                else [str(i + 1) for i in range(len(df))]
            )
            for col in numeric_cols[:3]:
                col_lower = col.lower()
                is_time = any(
                    k in col_lower
                    for k in ["年", "月", "季", "期", "趋势", "增长", "time", "trend", "date"]
                )
                chart_type = "line" if is_time else "bar"
                configs.append({
                    "chart_type": chart_type,
                    "title": col,
                    "categories": categories,
                    "series": [{"name": col, "data": df[col].fillna(0).tolist()}],
                })
        except Exception:
            pass
        return configs

    async def _generate_insight(self, exec_result: dict, question: str) -> str:
        stdout = str(exec_result.get("stdout", "")).strip()
        variables = exec_result.get("variables", {})
        result_val = variables.get("result", "")
        error = exec_result.get("error", "")
        n_figures = len(exec_result.get("figures", []))

        context_parts = []
        if stdout:
            context_parts.append(f"程序输出：\n{stdout[:600]}")
        if result_val:
            context_parts.append(f"result 变量：\n{str(result_val)[:400]}")
        if error:
            context_parts.append(f"执行错误：{str(error)[:200]}")
        if n_figures:
            context_parts.append(f"已生成 {n_figures} 张图表")

        context = "\n\n".join(context_parts) or "分析完成，无文字输出"

        prompt = f"""请基于以下分析结果，用中文回答用户的问题，并总结关键发现。

用户问题：{question}

分析结果：
{context}

要求：
- 用 2-4 句话描述核心发现
- 如有图表，描述图表展示的关键规律
- 语言专业、简洁、有洞察力
- 不要重复用户的问题"""

        try:
            messages = [
                {"role": "system", "content": "你是数据洞察专家。用中文提供清晰、专业的分析结论。"},
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(
                agent_type="quinn", messages=messages
            )
            return await chat(
                messages=messages, model=model, base_url=base_url, api_key=api_key,
                temperature=0.4, max_tokens=400,
            )
        except Exception as e:
            return f"分析完成，共生成 {n_figures} 张图表。洞察生成失败: {e}"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_df_preamble(df: pd.DataFrame) -> str:
    """Serialize a small DataFrame as an inline literal, or use parquet staging for large ones."""
    import json
    try:
        # Small df → inline JSON (< 500 rows × 20 cols)
        if len(df) <= 500 and len(df.columns) <= 20:
            records = df.to_dict(orient="records")
            json_str = json.dumps(records, ensure_ascii=False, default=str)
            cols = json.dumps(df.columns.tolist(), ensure_ascii=False)
            return (
                "import pandas as _pd_inner\nimport json as _json_inner\n"
                f"_records = {json_str}\n"
                f"df = _pd_inner.DataFrame(_records, columns={cols})\n"
                "# Attempt type coercion\n"
                "for _col in df.columns:\n"
                "    try:\n"
                "        df[_col] = _pd_inner.to_numeric(df[_col], errors='ignore')\n"
                "    except Exception:\n"
                "        pass\n"
            )
        # Large df → stage as parquet and load inside sandbox
        from app.services.sandbox import stage_dataframe
        path = stage_dataframe(df)
        return (
            "import pandas as _pd_inner\n"
            f"df = _pd_inner.read_parquet({repr(path)})\n"
        )
    except Exception:
        # Ultimate fallback: empty df
        return "import pandas as _pd_inner\ndf = _pd_inner.DataFrame()\n"


def _fallback_chart_code() -> str:
    """A minimal chart to show when code generation itself fails."""
    return """
import matplotlib.pyplot as plt
import numpy as np
fig, ax = plt.subplots(figsize=(10, 6))
categories = df.columns.tolist()[:6] if len(df.columns) > 0 else ['A','B','C']
values = [float(df[c].mean()) if df[c].dtype.kind in 'iuf' else 0 for c in categories]
colors = ['#2563EB','#F59E0B','#22C55E','#EF4444','#8B5CF6','#0EA5E9']
bars = ax.bar(categories, values, color=colors[:len(categories)], edgecolor='white', linewidth=1.5)
for bar, val in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
            f'{val:.1f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
ax.set_title('数据概览', fontsize=16, fontweight='bold', pad=15)
ax.set_xlabel('字段', fontsize=12)
ax.set_ylabel('均值', fontsize=12)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.yaxis.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
result = df.describe().to_dict()
"""
