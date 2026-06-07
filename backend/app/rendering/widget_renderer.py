"""动态直出引擎 — 将数据与洞察渲染为可交互 HTML/ECharts Widget.

支持图表类型:
  line / bar / pie / scatter / radar / heatmap / treemap / candlestick / funnel / gauge

Widget 通过 <iframe srcdoc="..."> 嵌入前端页面，无需服务端渲染。
LLM 只需提供数据 + 图表类型，渲染逻辑在前端 ECharts 执行。
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"

# 离线部署时使用本地静态资源
_ECHARTS_LOCAL = "/static/echarts.min.js"


def _echarts_script_src() -> str:
    """优先使用本地 ECharts（离线环境），回退到 CDN."""
    import os
    static_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "static"
    )
    local_js = os.path.join(static_dir, "echarts.min.js")
    if os.path.exists(local_js):
        return _ECHARTS_LOCAL
    return _ECHARTS_CDN


class WidgetRenderer:
    """生成自包含的 HTML ECharts Widget."""

    @classmethod
    def render(
        cls,
        chart_type: str,
        title: str,
        data: dict | list,
        *,
        width: str = "100%",
        height: str = "400px",
        theme: str = "light",
        extra_option: dict | None = None,
    ) -> str:
        """
        Args:
            chart_type:   图表类型 (line/bar/pie/scatter/radar/heatmap/...)
            title:        图表标题
            data:         图表数据（格式见各 _build_* 方法）
            width/height: 容器尺寸
            theme:        ECharts 主题 (light/dark/macarons)
            extra_option: 额外的 ECharts option 覆盖

        Returns:
            可直接嵌入 iframe srcdoc 的完整 HTML 字符串
        """
        option = cls._build_option(chart_type, title, data)
        if extra_option:
            option.update(extra_option)

        option_json = json.dumps(option, ensure_ascii=False, indent=None)
        script_src = _echarts_script_src()
        theme_arg = f'"{theme}"' if theme != "light" else ""

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; }}
  #chart {{ width: {width}; height: {height}; }}
</style>
</head>
<body>
<div id="chart"></div>
<script src="{script_src}"></script>
<script>
  var chart = echarts.init(document.getElementById('chart'), {theme_arg});
  var option = {option_json};
  chart.setOption(option);
  window.addEventListener('resize', function() {{ chart.resize(); }});
</script>
</body>
</html>"""
        return html

    @classmethod
    def render_as_iframe(
        cls,
        chart_type: str,
        title: str,
        data: dict | list,
        **kwargs,
    ) -> str:
        """返回 <iframe srcdoc="..."> 标签（已转义），可直接嵌入 HTML 报告."""
        html = cls.render(chart_type, title, data, **kwargs)
        # 转义 srcdoc 属性中的双引号
        escaped = html.replace("&", "&amp;").replace('"', "&quot;")
        width = kwargs.get("width", "100%")
        height = kwargs.get("height", "420px")
        return (
            f'<iframe srcdoc="{escaped}" '
            f'style="width:{width};height:{height};border:none;overflow:hidden;" '
            f'sandbox="allow-scripts" scrolling="no"></iframe>'
        )

    # ── Option 构建 ──────────────────────────────────────────────────────────

    @classmethod
    def _build_option(cls, chart_type: str, title: str, data: Any) -> dict:
        builders = {
            "line":        cls._line_option,
            "bar":         cls._bar_option,
            "pie":         cls._pie_option,
            "scatter":     cls._scatter_option,
            "radar":       cls._radar_option,
            "heatmap":     cls._heatmap_option,
            "treemap":     cls._treemap_option,
            "candlestick": cls._candlestick_option,
            "funnel":      cls._funnel_option,
            "gauge":       cls._gauge_option,
        }
        builder = builders.get(chart_type, cls._bar_option)
        option = builder(data)
        option.setdefault("title", {})
        option["title"]["text"] = title
        option.setdefault("toolbox", {"feature": {"saveAsImage": {}}})
        return option

    @staticmethod
    def _line_option(data: dict) -> dict:
        """data: {xAxis: [...], series: [{name, data: [...]}]}"""
        series = []
        for s in data.get("series", []):
            series.append({
                "name": s.get("name", ""),
                "type": "line",
                "data": s.get("data", []),
                "smooth": s.get("smooth", True),
            })
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [s["name"] for s in series]},
            "xAxis": {"type": "category", "data": data.get("xAxis", [])},
            "yAxis": {"type": "value"},
            "series": series,
        }

    @staticmethod
    def _bar_option(data: dict) -> dict:
        """data: {xAxis: [...], series: [{name, data: [...]}]}"""
        series = []
        for s in data.get("series", []):
            series.append({
                "name": s.get("name", ""),
                "type": "bar",
                "data": s.get("data", []),
            })
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [s["name"] for s in series]},
            "xAxis": {"type": "category", "data": data.get("xAxis", [])},
            "yAxis": {"type": "value"},
            "series": series,
        }

    @staticmethod
    def _pie_option(data: list | dict) -> dict:
        """data: [{name, value}, ...] 或 {series: [{name, value}]}"""
        if isinstance(data, dict):
            items = data.get("series", data.get("data", []))
        else:
            items = data
        return {
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "left": "left"},
            "series": [{
                "type": "pie",
                "radius": "60%",
                "data": items,
                "label": {"formatter": "{b}\n{d}%"},
            }],
        }

    @staticmethod
    def _scatter_option(data: dict) -> dict:
        """data: {series: [{name, data: [[x,y], ...]}]}"""
        series = [
            {"name": s.get("name", ""), "type": "scatter", "data": s.get("data", [])}
            for s in data.get("series", [])
        ]
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "value"},
            "series": series,
        }

    @staticmethod
    def _radar_option(data: dict) -> dict:
        """data: {indicators: [{name, max}], series: [{name, data: [...]}]}"""
        return {
            "tooltip": {},
            "radar": {"indicator": data.get("indicators", [])},
            "series": [{
                "type": "radar",
                "data": [{"name": s["name"], "value": s["data"]}
                         for s in data.get("series", [])],
            }],
        }

    @staticmethod
    def _heatmap_option(data: dict) -> dict:
        """data: {xAxis: [...], yAxis: [...], data: [[x,y,value], ...]}"""
        raw = data.get("data", [])
        values = [d[2] for d in raw if len(d) >= 3] or [0]
        return {
            "tooltip": {"position": "top"},
            "xAxis": {"type": "category", "data": data.get("xAxis", [])},
            "yAxis": {"type": "category", "data": data.get("yAxis", [])},
            "visualMap": {
                "min": min(values), "max": max(values),
                "calculable": True, "orient": "horizontal", "left": "center",
            },
            "series": [{"type": "heatmap", "data": raw, "label": {"show": True}}],
        }

    @staticmethod
    def _treemap_option(data: list | dict) -> dict:
        """data: [{name, value, children?}, ...]"""
        items = data if isinstance(data, list) else data.get("data", [])
        return {
            "tooltip": {"formatter": "{b}: {c}"},
            "series": [{"type": "treemap", "data": items}],
        }

    @staticmethod
    def _candlestick_option(data: dict) -> dict:
        """data: {xAxis: [...], data: [[open,close,low,high], ...]}"""
        return {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
            "xAxis": {"data": data.get("xAxis", [])},
            "yAxis": {"scale": True},
            "series": [{"type": "candlestick", "data": data.get("data", [])}],
        }

    @staticmethod
    def _funnel_option(data: list | dict) -> dict:
        """data: [{name, value}, ...]"""
        items = data if isinstance(data, list) else data.get("data", [])
        return {
            "tooltip": {"trigger": "item"},
            "series": [{
                "type": "funnel",
                "data": sorted(items, key=lambda x: x.get("value", 0), reverse=True),
            }],
        }

    @staticmethod
    def _gauge_option(data: dict) -> dict:
        """data: {value: float, name: str, min?: 0, max?: 100}"""
        return {
            "series": [{
                "type": "gauge",
                "min": data.get("min", 0),
                "max": data.get("max", 100),
                "data": [{"value": data.get("value", 0), "name": data.get("name", "")}],
            }],
        }

    # ── LLM 辅助生成 ─────────────────────────────────────────────────────────

    @classmethod
    async def generate_from_nl(
        cls,
        question: str,
        records: list[dict],
        *,
        title: str = "",
    ) -> str | None:
        """从自然语言指令 + 数据记录生成 iframe widget.

        Args:
            question: 用户问题，如"画一个各类别占比的饼图"
            records:  数据记录列表（DuckDB 查询结果的 JSON 格式）
            title:    图表标题（可留空，LLM 生成）

        Returns:
            iframe HTML 字符串，或 None（失败时）
        """
        from app.pipeline.llm_helpers import call_llm_json

        sample = records[:5]
        columns = list(sample[0].keys()) if sample else []

        system = """你是可视化专家。根据用户需求和数据，生成 ECharts 图表配置。
仅输出 JSON:
{
  "chart_type": "bar|line|pie|scatter|radar|heatmap|treemap|funnel|gauge",
  "title": "图表标题",
  "data": { ... }   // 对应 chart_type 的 data 结构
}

各类型 data 结构:
- bar/line: {xAxis: [...], series: [{name, data: [...]}]}
- pie: [{name, value}, ...]
- scatter: {series: [{name, data: [[x,y],...]}]}
- radar: {indicators: [{name, max}], series: [{name, data: [...]}]}
- heatmap: {xAxis:[...], yAxis:[...], data: [[x_idx, y_idx, value],...]}
- treemap: [{name, value, children?},...]
- funnel: [{name, value},...]
- gauge: {value: 75, name: "完成率", min: 0, max: 100}"""

        user_msg = f"""问题: {question}
列名: {columns}
数据样本(前5行): {json.dumps(sample, ensure_ascii=False)}
全部数据({len(records)}行): {json.dumps(records[:50], ensure_ascii=False)}"""

        try:
            resp = await call_llm_json(system, user_msg)
            chart_type = resp.get("chart_type", "bar")
            chart_title = resp.get("title", title or question[:30])
            data = resp.get("data", {})
            return cls.render_as_iframe(chart_type, chart_title, data)
        except Exception as exc:
            logger.warning("WidgetRenderer.generate_from_nl failed: %s", exc)
            return None
