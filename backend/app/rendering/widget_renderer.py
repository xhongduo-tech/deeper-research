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

# ── Professional colour palette ──────────────────────────────────────────────
PALETTE = ["#2563EB", "#F59E0B", "#22C55E", "#EF4444", "#8B5CF6",
           "#0EA5E9", "#F97316", "#84CC16", "#EC4899", "#14B8A6"]

# Gradient pairs for bar/line area fills
GRADIENT_PAIRS = [
    ("#2563EB", "#6EA8FE"), ("#F59E0B", "#FDE68A"),
    ("#22C55E", "#86EFAC"), ("#EF4444", "#FCA5A5"),
    ("#8B5CF6", "#C4B5FD"), ("#0EA5E9", "#7DD3FC"),
]

# Shared high-quality base option
_BASE_OPTION = {
    "animation": True,
    "animationDuration": 800,
    "animationEasing": "cubicOut",
    "color": PALETTE,
    "tooltip": {
        "backgroundColor": "rgba(255,255,255,0.96)",
        "borderColor": "#E5E7EB",
        "borderWidth": 1,
        "textStyle": {"color": "#111827", "fontSize": 13},
        "extraCssText": "box-shadow:0 4px 16px rgba(0,0,0,0.12);border-radius:8px;",
    },
    "legend": {
        "top": 8, "left": "center", "itemGap": 16,
        "textStyle": {"fontSize": 12, "color": "#374151"},
        "icon": "roundRect",
    },
    "grid": {"left": "10%", "right": "8%", "top": "16%", "bottom": "14%", "containLabel": True},
    "textStyle": {"fontFamily": "PingFang SC, Microsoft YaHei, Helvetica Neue, Arial, sans-serif"},
    "toolbox": {
        "feature": {
            "saveAsImage": {"title": "保存图片", "pixelRatio": 2},
            "dataZoom": {"title": {"zoom": "区域缩放", "back": "缩放还原"}},
            "restore": {"title": "还原"},
        }
    },
}

# 离线部署时使用本地静态资源
_ECHARTS_LOCAL = "/static/echarts.min.js"


def _hex_to_rgba(color: str, alpha: float) -> str:
    """Convert hex colour to rgba string."""
    color = (color or "#2563EB").strip()
    if not color.startswith("#") or len(color) != 7:
        return f"rgba(37,99,235,{alpha})"
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"


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
        option = {**_BASE_OPTION, **builder(data)}
        option.setdefault("title", {})
        option["title"]["text"] = title
        option["title"].setdefault("textStyle", {"fontSize": 16, "fontWeight": "bold", "color": "#1F2937"})
        return option

    @staticmethod
    def _line_option(data: dict) -> dict:
        """data: {xAxis: [...], series: [{name, data: [...]}]}"""
        series = []
        for idx, s in enumerate(data.get("series", [])):
            top, bot = GRADIENT_PAIRS[idx % len(GRADIENT_PAIRS)]
            series.append({
                "name": s.get("name", ""),
                "type": "line",
                "data": s.get("data", []),
                "smooth": s.get("smooth", True),
                "symbol": "circle",
                "symbolSize": 8,
                "lineStyle": {"width": 3},
                "areaStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": f"{_hex_to_rgba(top, 0.35)}"},
                            {"offset": 1, "color": "rgba(255,255,255,0)"},
                        ],
                    }
                },
                "emphasis": {
                    "focus": "series",
                    "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"},
                },
                "markPoint": {
                    "data": [
                        {"type": "max", "name": "最大值"},
                        {"type": "min", "name": "最小值"},
                    ]
                },
            })
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [s["name"] for s in series]},
            "xAxis": {
                "type": "category", "data": data.get("xAxis", []),
                "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 12},
            },
            "yAxis": {
                "type": "value",
                "splitLine": {"lineStyle": {"color": "#F3F4F6", "type": "dashed"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 12},
            },
            "series": series,
            "dataZoom": [{"type": "inside"}, {"type": "slider", "bottom": 0}],
        }

    @staticmethod
    def _bar_option(data: dict) -> dict:
        """data: {xAxis: [...], series: [{name, data: [...]}]}"""
        series = []
        for idx, s in enumerate(data.get("series", [])):
            top, bot = GRADIENT_PAIRS[idx % len(GRADIENT_PAIRS)]
            series.append({
                "name": s.get("name", ""),
                "type": "bar",
                "data": s.get("data", []),
                "itemStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": top},
                            {"offset": 1, "color": bot},
                        ],
                    },
                    "borderRadius": [4, 4, 0, 0],
                },
                "label": {"show": True, "position": "top", "color": "#374151", "fontSize": 11},
                "emphasis": {
                    "focus": "series",
                    "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.2)"},
                },
                "markLine": {
                    "data": [{"type": "average", "name": "平均值"}],
                    "lineStyle": {"type": "dashed", "color": "#9CA3AF"},
                },
            })
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [s["name"] for s in series]},
            "xAxis": {
                "type": "category", "data": data.get("xAxis", []),
                "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 12},
            },
            "yAxis": {
                "type": "value",
                "splitLine": {"lineStyle": {"color": "#F3F4F6", "type": "dashed"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 12},
            },
            "series": series,
            "dataZoom": [{"type": "inside"}, {"type": "slider", "bottom": 0}],
        }

    @staticmethod
    def _pie_option(data: list | dict) -> dict:
        """data: [{name, value}, ...] or {series: [{name, value}]}"""
        if isinstance(data, dict):
            items = data.get("series", data.get("data", []))
        else:
            items = data
        n_items = len(items)
        slice_colors = [PALETTE[i % len(PALETTE)] for i in range(n_items)]
        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c} ({d}%)",
                "backgroundColor": "rgba(255,255,255,0.96)",
                "borderColor": "#E5E7EB",
                "borderWidth": 1,
            },
            "legend": {"orient": "vertical", "left": "left", "top": "center"},
            "series": [{
                "type": "pie",
                "radius": ["0%", "68%"],
                "data": items,
                "color": slice_colors,
                "itemStyle": {"borderColor": "#fff", "borderWidth": 2},
                "label": {"formatter": "{b}\n{d}%", "fontSize": 12, "color": "#374151"},
                "labelLine": {"length": 12, "length2": 8},
                "emphasis": {
                    "scaleSize": 8,
                    "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.2)"},
                    "label": {"fontSize": 14, "fontWeight": "bold"},
                },
            }],
        }

    @staticmethod
    def _scatter_option(data: dict) -> dict:
        """data: {series: [{name, data: [[x,y], ...]}]}"""
        symbols = ["circle", "rect", "diamond", "triangle"]
        series = []
        for idx, s in enumerate(data.get("series", [])):
            series.append({
                "name": s.get("name", ""),
                "type": "scatter",
                "data": s.get("data", []),
                "symbol": symbols[idx % len(symbols)],
                "symbolSize": 10,
                "itemStyle": {"opacity": 0.85},
                "emphasis": {
                    "focus": "series",
                    "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)", "borderColor": "#fff", "borderWidth": 2},
                },
            })
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#F3F4F6", "type": "dashed"}}},
            "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#F3F4F6", "type": "dashed"}}},
            "series": series,
        }

    @staticmethod
    def _radar_option(data: dict) -> dict:
        """data: {indicators: [{name, max}], series: [{name, data: [...]}]}"""
        series = []
        for idx, s in enumerate(data.get("series", [])):
            color = PALETTE[idx % len(PALETTE)]
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            series.append({
                "name": s["name"],
                "type": "radar",
                "data": [{"name": s["name"], "value": s["data"]}],
                "lineStyle": {"width": 2.5, "color": color},
                "areaStyle": {"color": f"rgba({r},{g},{b},0.15)"},
                "symbol": "circle",
                "symbolSize": 6,
                "emphasis": {
                    "lineStyle": {"width": 3.5},
                    "areaStyle": {"color": f"rgba({r},{g},{b},0.25)"},
                },
            })
        return {
            "tooltip": {},
            "radar": {
                "indicator": data.get("indicators", []),
                "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
                "splitLine": {"lineStyle": {"color": "#F3F4F6"}},
                "splitArea": {"areaStyle": {"color": ["rgba(255,255,255,0.9)", "rgba(248,250,252,0.9)"]}},
            },
            "series": series,
        }

    @staticmethod
    def _heatmap_option(data: dict) -> dict:
        """data: {xAxis: [...], yAxis: [...], data: [[x,y,value], ...]}"""
        raw = data.get("data", [])
        values = [d[2] for d in raw if len(d) >= 3] or [0]
        return {
            "tooltip": {
                "position": "top",
                "formatter": "{b}: {c}",
            },
            "xAxis": {
                "type": "category", "data": data.get("xAxis", []),
                "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 11},
                "splitArea": {"show": True},
            },
            "yAxis": {
                "type": "category", "data": data.get("yAxis", []),
                "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 11},
                "splitArea": {"show": True},
            },
            "visualMap": {
                "min": min(values), "max": max(values),
                "calculable": True, "orient": "horizontal", "left": "center", "bottom": 0,
                "inRange": {"color": ["#EFF6FF", "#93C5FD", "#2563EB", "#1E3A8F"]},
                "textStyle": {"color": "#6B7280"},
            },
            "series": [{
                "type": "heatmap",
                "data": raw,
                "label": {"show": True, "color": "#374151", "fontSize": 11},
                "itemStyle": {"borderColor": "#fff", "borderWidth": 1},
                "emphasis": {
                    "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"},
                },
            }],
        }

    @staticmethod
    def _treemap_option(data: list | dict) -> dict:
        """data: [{name, value, children?}, ...]"""
        items = data if isinstance(data, list) else data.get("data", [])
        return {
            "tooltip": {
                "formatter": "{b}: {c}",
                "backgroundColor": "rgba(255,255,255,0.96)",
                "borderColor": "#E5E7EB",
                "borderWidth": 1,
            },
            "series": [{
                "type": "treemap",
                "data": items,
                "itemStyle": {"borderColor": "#fff", "borderWidth": 2, "gapWidth": 2},
                "levels": [
                    {
                        "itemStyle": {"borderColor": "#fff", "borderWidth": 3, "gapWidth": 2},
                        "upperLabel": {"show": True, "height": 24, "color": "#fff", "fontWeight": "bold"},
                    },
                    {
                        "itemStyle": {"borderColor": "#fff", "borderWidth": 2, "gapWidth": 1},
                        "upperLabel": {"show": True, "height": 20},
                    },
                ],
                "breadcrumb": {"show": False},
                "emphasis": {
                    "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.2)"},
                },
            }],
        }

    @staticmethod
    def _candlestick_option(data: dict) -> dict:
        """data: {xAxis: [...], data: [[open,close,low,high], ...]}"""
        return {
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "cross"},
                "backgroundColor": "rgba(255,255,255,0.96)",
                "borderColor": "#E5E7EB",
                "borderWidth": 1,
            },
            "xAxis": {
                "data": data.get("xAxis", []),
                "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 11},
                "splitLine": {"show": False},
            },
            "yAxis": {
                "scale": True,
                "splitLine": {"lineStyle": {"color": "#F3F4F6", "type": "dashed"}},
                "axisLabel": {"color": "#6B7280", "fontSize": 11},
            },
            "grid": {"left": "10%", "right": "8%", "top": "10%", "bottom": "15%"},
            "series": [{
                "type": "candlestick",
                "data": data.get("data", []),
                "itemStyle": {
                    "color": "#EF4444",
                    "color0": "#22C55E",
                    "borderColor": "#EF4444",
                    "borderColor0": "#22C55E",
                },
                "emphasis": {
                    "itemStyle": {"shadowBlur": 8, "shadowColor": "rgba(0,0,0,0.2)"},
                },
            }],
        }

    @staticmethod
    def _funnel_option(data: list | dict) -> dict:
        """data: [{name, value}, ...]"""
        items = data if isinstance(data, list) else data.get("data", [])
        n_items = len(items)
        slice_colors = [PALETTE[i % len(PALETTE)] for i in range(n_items)]
        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c} ({d}%)",
                "backgroundColor": "rgba(255,255,255,0.96)",
                "borderColor": "#E5E7EB",
                "borderWidth": 1,
            },
            "series": [{
                "type": "funnel",
                "data": sorted(items, key=lambda x: x.get("value", 0), reverse=True),
                "color": slice_colors,
                "sort": "descending",
                "gap": 3,
                "label": {
                    "show": True,
                    "position": "inside",
                    "formatter": "{b}\n{c}",
                    "fontSize": 12,
                    "color": "#fff",
                    "fontWeight": "bold",
                },
                "itemStyle": {
                    "borderColor": "#fff",
                    "borderWidth": 2,
                },
                "emphasis": {
                    "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.2)"},
                    "label": {"fontSize": 14},
                },
            }],
        }

    @staticmethod
    def _gauge_option(data: dict) -> dict:
        """data: {value: float, name: str, min?: 0, max?: 100}"""
        value = data.get("value", 0)
        min_val = data.get("min", 0)
        max_val = data.get("max", 100)
        mid = (max_val - min_val) * 0.5 + min_val
        high = (max_val - min_val) * 0.8 + min_val
        return {
            "series": [{
                "type": "gauge",
                "min": min_val,
                "max": max_val,
                "data": [{"value": value, "name": data.get("name", "")}],
                "axisLine": {
                    "lineStyle": {
                        "width": 20,
                        "color": [
                            [0.5, "#2563EB"],
                            [0.8, "#F59E0B"],
                            [1.0, "#EF4444"],
                        ],
                    },
                },
                "pointer": {"length": "60%", "width": 6, "itemStyle": {"color": "#111827"}},
                "axisTick": {"distance": -20, "length": 6, "lineStyle": {"color": "#fff", "width": 2}},
                "splitLine": {"distance": -20, "length": 14, "lineStyle": {"color": "#fff", "width": 3}},
                "axisLabel": {"distance": -14, "color": "#6B7280", "fontSize": 12},
                "detail": {
                    "valueAnimation": True,
                    "formatter": "{value}",
                    "color": "#111827",
                    "fontSize": 32,
                    "fontWeight": "bold",
                    "offsetCenter": [0, "60%"],
                },
                "title": {"offsetCenter": [0, "80%"], "fontSize": 14, "color": "#6B7280"},
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
