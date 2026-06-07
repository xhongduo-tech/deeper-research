"""
PythonChartEngine — LLM-driven Python code generation for complex charts.

Unlike the ECharts JSON path (chart_spec_generator → frontend renders),
this engine generates Python code that runs server-side and returns rendered
PNG figures.  Result quality is much higher for:
  - Complex multi-panel layouts
  - Statistical charts (distribution, regression, ANOVA)
  - Specialized types: wordcloud, network, candlestick, waffle, calendar, ridge
  - Custom annotation and styling not possible in ECharts JSON

Pipeline:
  1. classify_intent()  — detect chart family from question + data
  2. build_prompt()     — construct a rich code-gen prompt with data + library guide
  3. generate_code()    — LLM call → Python code
  4. execute_code()     — sandbox execution → figures + stdout
  5. build_result()     — assemble PythonChartResult

Usage:
    engine = PythonChartEngine()
    result = await engine.render(
        data=df,                 # pandas DataFrame
        question="分析各城市销售额分布",
        chart_hint="violin",     # optional: bar|line|pie|scatter|heatmap|
                                 #  violin|boxplot|wordcloud|network|candlestick|
                                 #  waffle|calendar|ridge|treemap|venn|sankey
        title="城市销售额分布图",
        style="business",        # business|vibrant|cool|warm
        context="2024年Q1-Q3报告",
    )
    # result.figures: list of {"format":"png","base64":"...","size_kb":N}
    # result.code:    the generated Python code
    # result.insight: LLM-generated natural language summary
"""
from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from app.services.llm_service import chat
from app.services.model_router import get_model_router
from app.services.sandbox import execute_python

logger = logging.getLogger(__name__)

# ── Palette library ──────────────────────────────────────────────────────────
PALETTES = {
    "business": ["#2563EB", "#F59E0B", "#22C55E", "#EF4444", "#8B5CF6", "#0EA5E9", "#F97316", "#84CC16"],
    "vibrant":  ["#FF6B6B", "#4ECDC4", "#45B7D1", "#6C63FF", "#FFB347", "#EC4899", "#22C55E", "#F97316"],
    "cool":     ["#1E3A5F", "#2E86AB", "#4ECDC4", "#44CF6C", "#6C63FF", "#0D9488", "#7C3AED", "#0369A1"],
    "warm":     ["#DC2626", "#EA580C", "#D97706", "#CA8A04", "#65A30D", "#B45309", "#9F1239", "#7C2D12"],
}

# ── Chart type → family mapping ──────────────────────────────────────────────
CHART_FAMILIES: dict[str, str] = {
    # Standard
    "bar": "standard",       "stacked_bar": "standard",
    "line": "standard",      "area": "standard",
    "scatter": "standard",   "pie": "standard",
    "donut": "standard",     "combo": "standard",
    # Statistical
    "violin": "statistical", "boxplot": "statistical",
    "heatmap": "statistical","histogram": "statistical",
    "kde": "statistical",    "regression": "statistical",
    "ridge": "statistical",  "correlation": "statistical",
    # Specialized
    "wordcloud": "specialized",  "network": "specialized",
    "candlestick": "specialized","waffle": "specialized",
    "calendar": "specialized",   "treemap": "specialized",
    "venn": "specialized",       "sankey": "specialized",
    "funnel": "specialized",     "gauge": "specialized",
    "sunburst": "specialized",
}

# ── Per-family code-generation guides ────────────────────────────────────────
FAMILY_GUIDES: dict[str, str] = {
    "standard": textwrap.dedent("""\
        标准图表指南：
        - bar/line: plt.figure(figsize=(12,7))；seaborn 或 matplotlib；渐变色 + 数值标注
        - pie/donut: plt.pie 或 px.pie；显示百分比 + 图例
        - scatter: sns.scatterplot 或 plt.scatter；添加回归线 (sns.regplot)
        - combo: ax1/ax2 双 Y 轴；bar + line 组合
        - 所有图表：中文标题 + 轴标签，字体 14-16pt；网格线 alpha=0.3
    """),
    "statistical": textwrap.dedent("""\
        统计图表指南：
        - violin: sns.violinplot(data=df, x='分类', y='数值')；内嵌箱线 inner='box'
        - boxplot: sns.boxplot + sns.stripplot（数据点叠加）
        - heatmap: sns.heatmap(pivot, annot=True, fmt='.2f', cmap='Blues')
        - histogram: sns.histplot(data=df, bins=30, kde=True)
        - kde: sns.kdeplot，多组用 hue 参数区分
        - regression: sns.regplot 或 statsmodels OLS；显示置信区间
        - ridge/joyplot: joypy.joyplot(df, column='数值', by='分组')
        - correlation: sns.heatmap(df.corr(), annot=True, cmap='RdYlGn', center=0)
        注意：figsize 至少 (12,8)；seaborn 主题 set_theme(style='whitegrid')
    """),
    "specialized": textwrap.dedent("""\
        专用图表指南：
        - wordcloud:
            text = ' '.join(df['文本列'].astype(str))
            wc = WordCloud(width=1200, height=600, background_color='white',
                           colormap='viridis', max_words=200).generate(text)
            plt.figure(figsize=(14,7)); plt.imshow(wc, interpolation='bilinear')
            plt.axis('off'); plt.title('词云图', fontsize=16)
        - network:
            G = nx.DiGraph()  # 或 nx.Graph()
            G.add_edges_from([(src, tgt, {'weight': w}) for src, tgt, w in data])
            pos = nx.spring_layout(G, seed=42, k=2)
            nx.draw_networkx(G, pos, with_labels=True, node_color='#2563EB',
                             edge_color='#9CA3AF', node_size=800, font_color='white')
        - candlestick (K线):
            # df 需有 Open, High, Low, Close (大写) 列，index 为日期
            mpf.plot(df, type='candle', style='charles', volume=True,
                     title='K线图', savefig=dict(fname=None))
            # 注意：mpf 直接输出图，用 plt.gcf() 获取
        - waffle:
            plt.figure(FigureClass=Waffle, rows=10,
                       values={'类别A': 40, '类别B': 35, '类别C': 25},
                       colors=['#2563EB','#F59E0B','#22C55E'],
                       title={'label': '占比分布', 'loc': 'left'},
                       legend={'loc': 'lower left', 'bbox_to_anchor': (0,-0.4)})
        - calendar (日历热力图):
            # series: DatetimeIndex, float values
            series = pd.Series(values, index=pd.DatetimeIndex(dates))
            calplot.calplot(series, cmap='YlOrRd', figsize=(14,3))
        - treemap (squarify):
            fig, ax = plt.subplots(figsize=(12,8))
            squarify.plot(sizes=values, label=labels, color=colors,
                          alpha=0.8, text_kwargs={'fontsize':11}, ax=ax)
            ax.axis('off')
        - venn:
            venn2(subsets=(A_only, B_only, AB), set_labels=('A', 'B'))
            # 或三组: venn3(subsets=(A,B,C,AB,AC,BC,ABC), ...)
        - sankey: go.Sankey — 节点 + 链接结构，存入 _plotly_fig = fig
        - sunburst: px.sunburst(df, path=['分类1','分类2'], values='数值')，存入 _plotly_fig = fig
        注意：plotly 图形存入变量 `_plotly_fig = fig`（自动被捕获）
    """),
}

# ── Inline data serialization limit ─────────────────────────────────────────
_MAX_INLINE_ROWS = 500
_MAX_INLINE_COLS = 25


@dataclass
class PythonChartResult:
    figures: list[dict] = field(default_factory=list)
    code: str = ""
    insight: str = ""
    error: str = ""
    exec_ms: int = 0
    chart_type: str = ""
    stdout: str = ""


class PythonChartEngine:
    """LLM-driven Python chart generator with full library access."""

    async def render(
        self,
        data: pd.DataFrame | dict | str,
        question: str,
        chart_hint: str = "",
        title: str = "",
        style: str = "business",
        context: str = "",
        timeout: int = 90,
    ) -> PythonChartResult:
        """Generate and execute a Python chart based on natural language question.

        Args:
            data:       pandas DataFrame, dict of {col: [values]}, or CSV/JSON string
            question:   natural language description of what to visualize
            chart_hint: optional chart type hint (bar, violin, wordcloud, etc.)
            title:      chart title override
            style:      color palette: business|vibrant|cool|warm
            context:    additional business context for the LLM
            timeout:    sandbox execution timeout in seconds

        Returns:
            PythonChartResult with figures, code, insight
        """
        df = self._to_dataframe(data)
        chart_type = self._classify(question, chart_hint, df)
        family = CHART_FAMILIES.get(chart_type, "standard")
        palette = PALETTES.get(style, PALETTES["business"])

        code = await self._generate_code(df, question, chart_type, family, palette, title, context)
        exec_result = await self._execute(df, code, timeout)
        insight = await self._summarize(exec_result, question, chart_type)

        return PythonChartResult(
            figures=exec_result.get("figures", []),
            code=code,
            insight=insight,
            error=exec_result.get("error") or "",
            exec_ms=exec_result.get("exec_ms", 0),
            chart_type=chart_type,
            stdout=exec_result.get("stdout", ""),
        )

    # ── Intent classification ────────────────────────────────────────────────

    def _classify(self, question: str, hint: str, df: pd.DataFrame) -> str:
        if hint and hint in CHART_FAMILIES:
            return hint

        q = question.lower()
        # Specialized types
        if any(kw in q for kw in ["词云", "词频", "关键词", "word"]):
            return "wordcloud"
        if any(kw in q for kw in ["网络", "关系图", "图谱", "network"]):
            return "network"
        if any(kw in q for kw in ["k线", "蜡烛", "股票", "ohlc", "candlestick"]):
            return "candlestick"
        if any(kw in q for kw in ["华夫", "单位图", "waffle"]):
            return "waffle"
        if any(kw in q for kw in ["日历", "calendar", "活跃度"]):
            return "calendar"
        if any(kw in q for kw in ["矩形树图", "treemap", "层级占比"]):
            return "treemap"
        if any(kw in q for kw in ["韦恩", "venn", "集合"]):
            return "venn"
        if any(kw in q for kw in ["桑基", "sankey", "流向"]):
            return "sankey"
        if any(kw in q for kw in ["旭日", "sunburst"]):
            return "sunburst"
        # Statistical
        if any(kw in q for kw in ["小提琴", "violin", "分布"]):
            return "violin"
        if any(kw in q for kw in ["箱线", "boxplot", "四分位"]):
            return "boxplot"
        if any(kw in q for kw in ["热力", "heatmap", "相关性", "correlation"]):
            return "heatmap"
        if any(kw in q for kw in ["山脊", "ridge", "密度叠加"]):
            return "ridge"
        if any(kw in q for kw in ["回归", "regression", "拟合"]):
            return "regression"
        if any(kw in q for kw in ["直方图", "histogram", "频率分布"]):
            return "histogram"
        # Standard
        if any(kw in q for kw in ["趋势", "时间", "折线"]):
            return "line"
        if any(kw in q for kw in ["占比", "比例", "饼图", "pie"]):
            return "pie"
        if any(kw in q for kw in ["散点", "scatter", "相关"]):
            return "scatter"
        if any(kw in q for kw in ["堆叠", "stacked"]):
            return "stacked_bar"
        # Default
        numeric_cols = df.select_dtypes(include="number").columns
        return "line" if len(numeric_cols) >= 2 else "bar"

    # ── Code generation ──────────────────────────────────────────────────────

    async def _generate_code(
        self,
        df: pd.DataFrame,
        question: str,
        chart_type: str,
        family: str,
        palette: list[str],
        title: str,
        context: str,
    ) -> str:
        guide = FAMILY_GUIDES.get(family, FAMILY_GUIDES["standard"])
        cols_info = {col: str(df[col].dtype) for col in df.columns}
        sample = df.head(5).to_dict(orient="records")
        palette_str = str(palette[:8])

        prompt = f"""你是专业数据可视化工程师，请为以下数据生成高质量的 Python 可视化代码。

## 任务
- 用户问题：{question}
- 图表类型：{chart_type}
- 图表标题：{title or question}
- 业务背景：{context or '通用'}
- 主题配色：{palette_str}

## 数据结构
列信息：{cols_info}
样本：{sample}
总行数：{len(df)}

## 图表指南
{guide}

## 可用库（已预导入）
- plt, matplotlib, GridSpec, mpatches, mticker
- np (numpy), pd (pandas)
- sns (seaborn)
- px (plotly.express), go (plotly.graph_objects), make_subplots
- scipy_stats, sm (statsmodels)
- squarify, WordCloud, STOPWORDS
- nx (networkx), mpf (mplfinance)
- Waffle (pywaffle), calplot, joypy
- venn2, venn3 (matplotlib_venn)
- adjust_text

## 约束
1. 数据已注入为 `df`（pandas DataFrame），直接使用
2. 如使用 matplotlib，不要调用 plt.show() 或 plt.savefig()，用 plt.tight_layout() 结尾
3. 如使用 plotly，将 fig 存入 `_plotly_fig = fig`
4. figsize 至少 (11, 7)，dpi 不需要设置（沙箱自动 150dpi）
5. 中文标题、标签直接写，字体已预配置
6. 只输出 Python 代码，不加任何解释、注释或代码块标记
7. 代码必须可直接运行（不依赖外部文件）

## 高质量要求
- 专业配色（使用提供的 palette 或 seaborn/plotly 内置主题）
- 数值标注（bar 顶部，pie 百分比）
- 添加参考线/均值线（如适合）
- 图例位置合理
- 去掉多余边框 spines['top']/['right'].set_visible(False)
- 主副标题（plt.suptitle + ax.set_title 或 title+subtitle 方式）
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是数据可视化代码专家，专精 Python matplotlib/seaborn/plotly/专用图表库。"
                        "生成可直接运行的高质量代码。只输出代码，不附任何说明。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(
                agent_type="visual", messages=messages
            )
            code = await chat(
                messages=messages,
                model=model, base_url=base_url, api_key=api_key,
                temperature=0.2, max_tokens=2500,
            )
            code = (
                code.strip()
                .removeprefix("```python")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return code
        except Exception as e:
            logger.warning(f"[PythonChartEngine] Code generation failed: {e}")
            return _minimal_chart_code(chart_type, palette)

    # ── Execution ────────────────────────────────────────────────────────────

    async def _execute(self, df: pd.DataFrame, code: str, timeout: int) -> dict:
        """Serialize df and execute code in sandbox."""
        try:
            preamble = _df_preamble(df)
            full_code = preamble + "\n\n" + code
            return await execute_python(full_code, timeout=timeout, capture_figures=True)
        except Exception as e:
            return {"error": str(e), "figures": [], "stdout": "", "exec_ms": 0}

    # ── Insight generation ───────────────────────────────────────────────────

    async def _summarize(
        self, exec_result: dict, question: str, chart_type: str
    ) -> str:
        stdout = (exec_result.get("stdout") or "").strip()[:800]
        n_figs = len(exec_result.get("figures", []))
        err = (exec_result.get("error") or "").strip()[:300]

        context = f"图表类型：{chart_type}，已生成 {n_figs} 张图。"
        if stdout:
            context += f"\n程序输出：{stdout}"
        if err:
            context += f"\n执行错误：{err}"

        prompt = (
            f"用户问题：{question}\n"
            f"可视化结果：{context}\n\n"
            "请用 2-3 句话描述图表展示的核心规律和关键洞察，语言专业简洁。"
        )
        try:
            messages = [
                {"role": "system", "content": "你是数据洞察专家。"},
                {"role": "user", "content": prompt},
            ]
            router = get_model_router()
            model, base_url, api_key = router.route_for_chat(
                agent_type="quinn", messages=messages
            )
            return await chat(
                messages=messages,
                model=model, base_url=base_url, api_key=api_key,
                temperature=0.4, max_tokens=300,
            )
        except Exception as e:
            return f"图表已生成（{n_figs} 张）。洞察生成失败：{e}"

    # ── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_dataframe(data: Any) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data
        if isinstance(data, dict):
            return pd.DataFrame(data)
        if isinstance(data, str):
            import io
            try:
                return pd.read_csv(io.StringIO(data))
            except Exception:
                pass
            try:
                import json
                return pd.DataFrame(json.loads(data))
            except Exception:
                pass
        return pd.DataFrame()


# ── Module-level helpers ─────────────────────────────────────────────────────

def _df_preamble(df: pd.DataFrame) -> str:
    """Serialize DataFrame to inline Python for sandbox injection."""
    import json

    try:
        if len(df) <= _MAX_INLINE_ROWS and len(df.columns) <= _MAX_INLINE_COLS:
            records = df.to_dict(orient="records")
            json_str = json.dumps(records, ensure_ascii=False, default=str)
            cols = json.dumps(df.columns.tolist(), ensure_ascii=False)
            return (
                "import pandas as _pd_\nimport json as _js_\n"
                f"_recs = {json_str}\n"
                f"df = _pd_.DataFrame(_recs, columns={cols})\n"
                "for _c in df.columns:\n"
                "    try: df[_c] = _pd_.to_numeric(df[_c], errors='ignore')\n"
                "    except: pass\n"
            )
        from app.services.sandbox import stage_dataframe
        path = stage_dataframe(df)
        return f"import pandas as _pd_\ndf = _pd_.read_parquet({repr(path)})\n"
    except Exception:
        return "import pandas as _pd_\ndf = _pd_.DataFrame()\n"


def _minimal_chart_code(chart_type: str, palette: list[str]) -> str:
    """Ultra-minimal fallback chart when code generation fails."""
    return textwrap.dedent(f"""
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 7))
        try:
            numeric = df.select_dtypes('number')
            if len(numeric.columns) and len(df):
                col = numeric.columns[0]
                vals = df[col].dropna().values[:20]
                labels = df.iloc[:len(vals), 0].astype(str).tolist() if len(df.columns) > 1 else list(range(len(vals)))
                ax.bar(labels, vals, color={palette[:6]!r})
                ax.set_title(col, fontsize=15, fontweight='bold')
        except Exception as _e:
            ax.text(0.5, 0.5, str(_e), transform=ax.transAxes, ha='center')
        plt.tight_layout()
    """).strip()


# ── Convenience wrapper ──────────────────────────────────────────────────────
_engine: Optional[PythonChartEngine] = None


def get_python_chart_engine() -> PythonChartEngine:
    """Singleton accessor."""
    global _engine
    if _engine is None:
        _engine = PythonChartEngine()
    return _engine
