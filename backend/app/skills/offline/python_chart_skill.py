"""Python Chart Skill — LLM-driven Python visualization via PythonChartEngine.

Generates publication-quality charts using matplotlib/seaborn/plotly/squarify/
wordcloud/networkx/mplfinance/pywaffle/calplot/joypy and more.

Returns base64 PNG figure(s) that the frontend renders directly.
Supports: bar, line, pie, scatter, heatmap, boxplot, violin, histogram,
          treemap, wordcloud, network, candlestick, waffle, calendar,
          ridgeline, venn, sankey, sunburst, bubble, funnel, waterfall, area.
"""
from __future__ import annotations

import logging

from app.skills.base import Skill

logger = logging.getLogger(__name__)


class PythonChartSkill(Skill):
    name = "generate_python_chart"
    description = (
        "用 Python (matplotlib/seaborn/plotly/squarify/wordcloud/networkx 等) "
        "生成专业可视化图表，返回 base64 PNG 图像。"
        "支持：柱状/折线/饼图/散点/热力图/箱线/小提琴/直方/矩形树图/"
        "词云/网络图/K线/华夫/日历热力/山脊线/韦恩/桑基/旭日/气泡/漏斗/瀑布/面积图。"
    )
    category = "data"
    parameters = {
        "data": {
            "type": "string",
            "description": "CSV 或 JSON 格式的数据（最多 20000 字符）",
        },
        "question": {
            "type": "string",
            "description": "可视化需求描述，如：'展示各月销售额趋势及同比增长'",
        },
        "chart_type": {
            "type": "string",
            "description": (
                "可选图表类型: bar|line|pie|scatter|heatmap|boxplot|violin|"
                "histogram|treemap|wordcloud|network|candlestick|waffle|"
                "calendar|ridgeline|venn|sankey|sunburst|bubble|funnel|"
                "waterfall|area|auto（默认auto，LLM自动选择）"
            ),
            "default": "auto",
        },
        "color_theme": {
            "type": "string",
            "description": "配色主题: business|vibrant|cool|warm（默认business）",
            "default": "business",
        },
        "context": {
            "type": "string",
            "description": "业务背景，帮助生成更贴切的图表标题和标注",
            "default": "",
        },
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        data = (params.get("data") or "").strip()
        question = (params.get("question") or "").strip()
        chart_type = params.get("chart_type", "auto")
        color_theme = params.get("color_theme", "business")
        biz_context = params.get("context", "")

        if not data and not question:
            return {"result": "", "error": "data 或 question 参数不能同时为空"}

        # Build the full question with business context
        full_question = question
        if biz_context:
            full_question = f"{question}（业务背景：{biz_context}）"

        try:
            from app.services.python_chart_engine import get_python_chart_engine
            engine = get_python_chart_engine()

            # Convert data string to DataFrame
            import pandas as pd
            from io import StringIO
            import json as _json

            df = None
            if data:
                try:
                    df = pd.read_csv(StringIO(data), sep=None, engine="python")
                except Exception:
                    try:
                        df = pd.DataFrame(_json.loads(data))
                    except Exception:
                        df = pd.DataFrame()

            result = await engine.render(
                data=df if df is not None and not df.empty else pd.DataFrame(),
                question=full_question,
                chart_hint="" if chart_type == "auto" else chart_type,
                style=color_theme,
            )

            out: dict = {
                "result": result.insight or f"已生成 {len(result.figures)} 张图表",
                "code": result.code,
                "chart_type": result.chart_type,
                "exec_ms": result.exec_ms,
            }
            if result.figures:
                out["figures"] = result.figures
            if result.error:
                out["error"] = result.error[:400]
            if result.stdout:
                out["stdout"] = result.stdout[:500]
            return out

        except ImportError:
            logger.warning("PythonChartEngine not available, falling back to basic sandbox")
            return await self._fallback(data, question)
        except Exception as e:
            logger.warning(f"PythonChartSkill failed: {e}")
            return {"result": f"图表生成失败: {e}", "error": str(e)}

    async def _fallback(self, data: str, question: str) -> dict:
        """Minimal fallback: run the data through execute_python directly."""
        from app.services.sandbox import execute_python
        import json as _json

        code = f"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import StringIO

try:
    df = pd.read_csv(StringIO({_json.dumps(data)}), sep=None, engine='python')
except Exception:
    df = pd.DataFrame()

if not df.empty:
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    if numeric_cols:
        fig, ax = plt.subplots(figsize=(10, 6))
        df[numeric_cols[:4]].mean().plot(kind='bar', ax=ax, color=['#2563EB','#F59E0B','#22C55E','#EF4444'])
        ax.set_title('数据概览', fontsize=14, fontweight='bold')
        ax.set_ylabel('均值', fontsize=12)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        for bar in ax.patches:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()*1.01,
                    f'{{bar.get_height():.1f}}', ha='center', fontsize=10)
        plt.tight_layout()
result = df.describe().to_string() if not df.empty else "数据为空"
"""
        exec_result = await execute_python(code, timeout=30, capture_figures=True)
        out = {"result": exec_result.get("variables", {}).get("result", "图表已生成")}
        if exec_result.get("figures"):
            out["figures"] = exec_result["figures"]
        return out
