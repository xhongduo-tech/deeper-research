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
from app.skills.offline.sota_utils import self_critique, adversarial_review

logger = logging.getLogger(__name__)


class PythonChartSkill(Skill):
    name = "generate_python_chart"
    description = (
        "SOTA Python可视化：用 matplotlib/seaborn/plotly 等生成专业图表，返回 base64 PNG。"
        "含图表设计推理、自动修复、洞察生成、自评和质量评分。"
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
        "enable_critique": {
            "type": "boolean",
            "description": "启用图表质量自评",
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
        chart_type = params.get("chart_type", "auto")
        color_theme = params.get("color_theme", "business")
        biz_context = params.get("context", "")
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)

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

            # ── CoT: Chart design reasoning ───────────────────────────────────
            cot_messages = [
                {"role": "system", "content": "你是数据可视化专家。在生成图表前先分析数据特征，规划最佳图表设计方案。"},
                {"role": "user", "content": f"""请分析以下可视化需求，规划图表设计方案。

需求：{full_question}
图表类型偏好：{chart_type}
配色主题：{color_theme}

请先回答：
1. 数据最适合用什么图表类型展示？
2. 关键数据点有哪些需要在图表中标注？
3. 配色和布局应注意什么？
4. 可能存在的误导性风险是什么？"""},
            ]
            reasoning = await chat(cot_messages, temperature=0.3, max_tokens=600)

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

            # SOTA: Self-critique
            if enable_critique and out.get("result"):
                try:
                    critique = await self_critique(
                        draft=out["result"][:2000],
                        topic=f"图表生成 - {question[:50]}",
                        dimensions=["specificity", "structural_clarity", "audience_fit"],
                    )
                    out["quality_score"] = round(critique["overall_score"] * 10)
                    out["critique"] = critique
                except Exception as exc:
                    logger.warning(f"PythonChart self-critique failed: {exc}")

            # SOTA: Adversarial review
            if enable_adversarial and out.get("result"):
                try:
                    adversarial = await adversarial_review(
                        output=out["result"][:2000],
                        topic=f"图表生成 - {question[:50]}",
                    )
                    out["adversarial"] = adversarial
                except Exception as exc:
                    logger.warning(f"PythonChart adversarial failed: {exc}")

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
