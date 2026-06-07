"""Professional offline chart specification and rendering helpers.

Rendering priority:
  1. Plotly / Kaleido  (PNG, high fidelity, always tried first)
  2. Matplotlib + Seaborn  (fallback, CJK font-aware)
  3. PIL  (compositor for small-multiples and post-processing)

Supported chart_type values:
  bar, stacked_bar, line, area, stacked_area, pie, donut,
  combo, waterfall, heatmap, radar, scatter, small_multiples,
  funnel, gauge, treemap, sankey, boxplot,
  stock_performance, valuation_band, scenario_waterfall
"""
from __future__ import annotations

import io
import logging
import math
import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Professional colour palettes
# ---------------------------------------------------------------------------
# Business: evenly spaced across the hue wheel, professional saturation
PALETTE_VIBRANT  = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#6C63FF", "#FFB347", "#EC4899", "#22C55E", "#F97316"]
PALETTE_BUSINESS = ["#2563EB", "#F59E0B", "#22C55E", "#EF4444", "#8B5CF6", "#0EA5E9", "#F97316", "#84CC16"]
PALETTE_COOL     = ["#1E3A5F", "#2E86AB", "#4ECDC4", "#44CF6C", "#6C63FF", "#0D9488", "#7C3AED", "#0369A1"]
PALETTE_WARM     = ["#DC2626", "#EA580C", "#D97706", "#CA8A04", "#65A30D", "#B45309", "#9F1239", "#7C2D12"]

DEFAULT_PALETTE  = PALETTE_BUSINESS

# Gradient pairs (top → bottom) — end color is ~55% lightened, not near-white
GRADIENT_PAIRS = [
    ("#2563EB", "#6EA8FE"), ("#F59E0B", "#FDE68A"), ("#22C55E", "#86EFAC"),
    ("#EF4444", "#FCA5A5"), ("#8B5CF6", "#C4B5FD"), ("#0EA5E9", "#7DD3FC"),
    ("#F97316", "#FDBA74"), ("#84CC16", "#BEF264"),
]

CHART_FONT_CANDIDATES = [
    "Noto Sans CJK SC",
    "Noto Sans CJK",
    "Source Han Sans SC",
    "Source Han Sans CN",
    "PingFang SC",
    "Hiragino Sans GB",
    "Microsoft YaHei",
    "SimHei",
    "WenQuanYi Micro Hei",
    "Arial Unicode MS",
    "DejaVu Sans",
]


def _pick_chart_font() -> str:
    """Pick an installed CJK-capable font so chart exports do not show tofu boxes."""
    latin_only_fallbacks = {"verdana", "arial", "helvetica", "times new roman", "dejavu sans"}
    try:
        if shutil.which("fc-match"):
            query = ":lang=zh"
            matched = subprocess.check_output(
                ["fc-match", "-f", "%{family}", query],
                stderr=subprocess.DEVNULL,
                timeout=1.5,
            ).decode("utf-8", "ignore")
            family = matched.split(",")[0].strip()
            if family and family.lower() not in latin_only_fallbacks:
                return family
        if shutil.which("fc-list"):
            output = subprocess.check_output(
                ["fc-list", ":lang=zh", "family"],
                stderr=subprocess.DEVNULL,
                timeout=1.5,
            ).decode("utf-8", "ignore")
            for candidate in CHART_FONT_CANDIDATES:
                if candidate.lower() in output.lower():
                    return candidate
            for line in output.splitlines():
                family = line.split(",")[0].strip()
                if family and family.lower() not in latin_only_fallbacks:
                    return family
    except Exception:
        pass
    return "Noto Sans CJK SC"


CHART_FONT_FAMILY = _pick_chart_font()
CHART_FONT_STACK = ", ".join(dict.fromkeys([CHART_FONT_FAMILY, *CHART_FONT_CANDIDATES, "Arial", "sans-serif"]))


def _configure_matplotlib_fonts() -> None:
    try:
        from matplotlib import rcParams

        rcParams["font.family"] = "sans-serif"
        rcParams["font.sans-serif"] = list(dict.fromkeys([CHART_FONT_FAMILY, *CHART_FONT_CANDIDATES]))
        rcParams["axes.unicode_minus"] = False
        rcParams["pdf.fonttype"] = 42
        rcParams["ps.fonttype"] = 42
    except Exception:
        pass


def _hex_to_rgba(color: str, alpha: float) -> str:
    color = (color or "#2563EB").strip()
    if not re.match(r"^#[0-9a-fA-F]{6}$", color):
        return f"rgba(37,99,235,{alpha})"
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ChartSeries:
    name: str
    values: list[float]
    stack: str = ""          # non-empty → participate in stacking
    series_type: str = "bar" # bar | line | area | scatter


@dataclass
class ChartSpec:
    chart_type: str
    title: str
    labels: list[str]
    series: list[ChartSeries]
    unit: str = ""
    secondary_unit: str = ""
    orientation: str = "vertical"
    source_note: str = ""
    palette: list[str] = field(default_factory=list)
    # Type-specific extra config:
    # funnel              — no extra needed (uses labels + series[0].values)
    # gauge               — {"min": 0, "max": 100}; value = series[0].values[0]
    # treemap             — {"tree": [{"name":..., "value":..., "children":[...]}]}
    # sankey              — {"nodes": [{"name":...}], "links": [{"source":..., "target":..., "value":...}]}
    # boxplot             — series[i].values = [min, Q1, median, Q3, max] per group
    # stock_performance   — series[0]=stock, series[1]=benchmark(normalized); {"benchmark_name": "上证指数"}
    # valuation_band      — series[0]=metric history; {"bands":[min,p25,mean,p75,max],"current":float,"metric":"PE"}
    # scenario_waterfall  — series[0].values=[悲观净利, 基准净利, 乐观净利]; {"scenarios":[...],"probabilities":[...]}
    extra: dict = field(default_factory=dict)

    @property
    def primary_values(self) -> list[float]:
        return self.series[0].values if self.series else []

    def effective_palette(self) -> list[str]:
        return self.palette if self.palette else DEFAULT_PALETTE


@dataclass
class ChartRenderResult:
    png: bytes
    backend: str
    spec: ChartSpec


# ---------------------------------------------------------------------------
# ECharts option builder (frontend rendering path)
# ---------------------------------------------------------------------------

def chart_spec_to_echarts_option(spec: ChartSpec) -> dict:
    """Convert ChartSpec to an Apache ECharts 5.x option with gradient fills,
    rich tooltips, markLine annotations, and professional styling."""
    palette = spec.effective_palette()

    def _gradient(idx: int) -> dict:
        top, bot = GRADIENT_PAIRS[idx % len(GRADIENT_PAIRS)]
        return {
            "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
            "colorStops": [{"offset": 0, "color": top}, {"offset": 1, "color": bot}],
        }

    def _area_gradient(idx: int) -> dict:
        top = GRADIENT_PAIRS[idx % len(GRADIENT_PAIRS)][0]
        return {
            "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
            "colorStops": [
                {"offset": 0, "color": _hex_to_rgba(top, 0.35)},
                {"offset": 1, "color": "rgba(255,255,255,0)"},
            ],
        }

    _font = CHART_FONT_STACK
    _grid_color = "#F3F4F6"
    _axis_color = "#9CA3AF"

    base: dict = {
        "color": palette[:8],
        "animation": True,
        "animationDuration": 800,
        "animationEasing": "cubicOut",
        "title": {
            "text": spec.title,
            "left": "2%",
            "textStyle": {"fontFamily": _font, "fontSize": 18, "fontWeight": "bold", "color": "#111827"},
        },
        "tooltip": {
            "trigger": "axis" if spec.chart_type not in {"pie", "donut", "radar"} else "item",
            "backgroundColor": "rgba(255,255,255,0.96)",
            "borderColor": "#E5E7EB",
            "borderWidth": 1,
            "textStyle": {"color": "#111827", "fontFamily": _font},
            "extraCssText": "box-shadow:0 4px 16px rgba(0,0,0,0.12);border-radius:8px",
        },
        "legend": {
            "top": 42,
            "left": "center",
            "itemGap": 16,
            "icon": "roundRect",
            "textStyle": {"fontSize": 13, "color": "#374151", "fontFamily": _font},
        },
    }

    # ── Pie / Donut ──────────────────────────────────────────────────────────
    if spec.chart_type in {"pie", "donut"}:
        radius = ["48%", "72%"] if spec.chart_type == "donut" else ["0%", "68%"]
        n_items = len(spec.primary_values)
        # Color each slice distinctly; when >8 items cycle the palette
        slice_colors = [palette[i % len(palette)] for i in range(n_items)]
        series_item: dict = {
            "type": "pie",
            "radius": radius,
            "center": ["50%", "55%"],
            "startAngle": 90,      # top-first layout, labels spread more evenly
            "data": [
                {"value": v, "name": lbl,
                 "itemStyle": {"color": slice_colors[i], "borderColor": "#fff", "borderWidth": 2}}
                for i, (v, lbl) in enumerate(zip(spec.primary_values, spec.labels))
            ],
            "label": {
                "formatter": "{b}  {d}%",
                "fontFamily": _font, "fontSize": 12, "color": "#374151",
            },
            "labelLine": {"length": 12, "length2": 8, "smooth": True},
            "emphasis": {"scale": True, "scaleSize": 6,
                         "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.2)"}},
        }
        if spec.chart_type == "donut":
            total = sum(v for v in spec.primary_values if not math.isnan(v))
            unit_str = f" {spec.unit}" if spec.unit else ""
            base["graphic"] = [{
                "type": "text",
                "left": "center", "top": "center",
                "style": {
                    "text": f"合计\n{total:,.0f}{unit_str}",
                    "textAlign": "center",
                    "fontSize": 15, "fontWeight": "bold",
                    "fill": "#111827", "fontFamily": _font,
                },
            }]
        base["series"] = [series_item]
        return base

    # ── Radar ────────────────────────────────────────────────────────────────
    if spec.chart_type == "radar":
        max_val = max((max(s.values) for s in spec.series if s.values), default=100) * 1.2
        base["radar"] = {
            "indicator": [{"name": lbl, "max": max_val} for lbl in spec.labels],
            "shape": "polygon",
            "splitNumber": 4,
            "axisName": {"color": _axis_color, "fontSize": 12, "fontFamily": _font},
            "splitLine": {"lineStyle": {"color": _grid_color}},
            "splitArea": {"areaStyle": {"color": ["rgba(255,255,255,0)", "rgba(0,0,0,0.02)"]}},
        }
        base["series"] = [{
            "type": "radar",
            "data": [{
                "value": s.values,
                "name": s.name,
                "symbol": "circle",
                "symbolSize": 5,
                "areaStyle": {"opacity": 0.18, "color": palette[i % len(palette)]},
                "lineStyle": {"width": 2.5, "color": palette[i % len(palette)]},
                "itemStyle": {"color": palette[i % len(palette)]},
            } for i, s in enumerate(spec.series)],
        }]
        return base

    # ── Heatmap ──────────────────────────────────────────────────────────────
    if spec.chart_type == "heatmap":
        base.pop("legend", None)
        all_vals = [v for s in spec.series for v in s.values if not math.isnan(v)]
        vmin, vmax = (min(all_vals), max(all_vals)) if all_vals else (0, 100)
        data_points = []
        for yi, s in enumerate(spec.series):
            for xi, v in enumerate(s.values):
                data_points.append([xi, yi, round(v, 2) if not math.isnan(v) else None])
        base["xAxis"] = {
            "type": "category", "data": spec.labels,
            "axisLabel": {"fontSize": 12, "color": _axis_color},
            "splitArea": {"show": True},
        }
        base["yAxis"] = {
            "type": "category", "data": [s.name for s in spec.series],
            "axisLabel": {"fontSize": 12, "color": _axis_color},
            "splitArea": {"show": True},
        }
        base["visualMap"] = {
            "min": vmin, "max": vmax,
            "calculable": True,
            "orient": "horizontal",
            "left": "center", "bottom": 8,
            "inRange": {"color": ["#EFF6FF", "#DBEAFE", "#93C5FD", "#3B82F6", "#1D4ED8"]},
        }
        base["grid"] = {"left": "12%", "right": "8%", "top": "18%", "bottom": "18%", "containLabel": True}
        base["series"] = [{
            "type": "heatmap",
            "data": data_points,
            "label": {"show": True, "fontSize": 11, "fontFamily": _font},
            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}},
        }]
        return base

    # ── Shared axes setup for cartesian charts ────────────────────────────
    base["grid"] = {"left": "12%", "right": "8%", "top": "18%", "bottom": "14%", "containLabel": True}
    base["xAxis"] = {
        "type": "category" if spec.orientation != "horizontal" else "value",
        "data": spec.labels if spec.orientation != "horizontal" else None,
        "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
        "axisTick": {"show": False},
        "axisLabel": {"fontSize": 12, "color": _axis_color, "fontFamily": _font},
    }
    if spec.orientation == "horizontal":
        del base["xAxis"]["data"]
    base["yAxis"] = [{
        "type": "value" if spec.orientation != "horizontal" else "category",
        "name": spec.unit,
        "nameTextStyle": {"color": _axis_color, "fontFamily": _font},
        "axisLine": {"show": False},
        "axisTick": {"show": False},
        "axisLabel": {"fontSize": 12, "color": _axis_color},
        "splitLine": {"lineStyle": {"color": _grid_color, "type": "dashed"}},
        **({"data": spec.labels} if spec.orientation == "horizontal" else {}),
    }]

    # ── Waterfall ────────────────────────────────────────────────────────────
    if spec.chart_type == "waterfall":
        values = spec.primary_values
        placeholder, pos_vals, neg_vals = [], [], []
        cumulative = 0.0
        for v in values:
            if v >= 0:
                placeholder.append(cumulative)
                pos_vals.append(round(v, 2))
                neg_vals.append(0)
            else:
                placeholder.append(cumulative + v)
                pos_vals.append(0)
                neg_vals.append(round(-v, 2))
            cumulative += v
        base["series"] = [
            {
                "name": "_base",
                "type": "bar", "stack": "waterfall",
                "itemStyle": {"color": "transparent"},
                "data": placeholder,
                "tooltip": {"show": False},
            },
            {
                "name": "增加",
                "type": "bar", "stack": "waterfall",
                "data": pos_vals,
                "itemStyle": {"color": _gradient(1), "borderRadius": [4, 4, 0, 0]},
                "label": {"show": True, "position": "top", "formatter": "{c}", "fontFamily": _font},
            },
            {
                "name": "减少",
                "type": "bar", "stack": "waterfall",
                "data": neg_vals,
                "itemStyle": {"color": _gradient(3), "borderRadius": [0, 0, 4, 4]},
                "label": {"show": True, "position": "bottom", "formatter": "-{c}", "fontFamily": _font},
            },
        ]
        return base

    # ── Combo (bar + line dual-axis) ─────────────────────────────────────────
    if spec.chart_type == "combo":
        base["yAxis"].append({
            "type": "value",
            "name": spec.secondary_unit or "%",
            "nameTextStyle": {"color": _axis_color, "fontFamily": _font},
            "position": "right",
            "axisLine": {"show": False},
            "axisTick": {"show": False},
            "axisLabel": {"fontSize": 12, "color": _axis_color},
            "splitLine": {"show": False},
        })
        combo_series = []
        for idx, s in enumerate(spec.series[:6]):
            is_rate = _looks_like_rate(s.name) and idx > 0
            if idx == 0 or not is_rate:
                combo_series.append({
                    "name": s.name, "type": "bar",
                    "data": s.values,
                    "yAxisIndex": 0,
                    "barMaxWidth": 48,
                    "itemStyle": {"color": _gradient(idx), "borderRadius": [4, 4, 0, 0]},
                    "label": {"show": True, "position": "top", "fontSize": 11, "fontFamily": _font},
                    "emphasis": {"focus": "series"},
                })
            else:
                combo_series.append({
                    "name": s.name, "type": "line",
                    "data": s.values,
                    "yAxisIndex": 1,
                    "smooth": True,
                    "lineStyle": {"width": 3, "color": palette[idx % len(palette)]},
                    "symbol": "circle", "symbolSize": 8,
                    "itemStyle": {"color": palette[idx % len(palette)]},
                    "label": {"show": True, "position": "top", "fontSize": 11, "fontFamily": _font},
                    "markPoint": {
                        "data": [{"type": "max", "name": "最大"}, {"type": "min", "name": "最小"}],
                        "symbol": "pin", "symbolSize": 40,
                        "label": {"fontFamily": _font, "fontSize": 11},
                    },
                })
        base["series"] = combo_series
        return base

    # ── Stacked bar / bar ────────────────────────────────────────────────────
    if spec.chart_type in {"bar", "stacked_bar"}:
        is_stacked = spec.chart_type == "stacked_bar"
        is_single_series = len(spec.series) == 1
        bar_series = []
        for idx, s in enumerate(spec.series[:8]):
            if is_single_series and not is_stacked:
                # Each category gets a distinct colour for visual clarity
                cat_data = [
                    {"value": v, "itemStyle": {"color": _gradient(ci), "borderRadius": [4, 4, 0, 0]}}
                    for ci, v in enumerate(s.values)
                ]
                if spec.orientation == "horizontal":
                    cat_data = [
                        {"value": v, "itemStyle": {"color": _gradient(ci), "borderRadius": [0, 4, 4, 0]}}
                        for ci, v in enumerate(s.values)
                    ]
                item: dict = {
                    "name": s.name, "type": "bar",
                    "data": cat_data,
                    "barMaxWidth": 52,
                    "emphasis": {"focus": "series", "itemStyle": {"shadowBlur": 8, "shadowColor": "rgba(0,0,0,0.2)"}},
                    "label": {"show": True, "position": "top" if spec.orientation != "horizontal" else "right", "fontFamily": _font, "fontSize": 11},
                    "markLine": {
                        "data": [{"type": "average", "name": "均值"}],
                        "lineStyle": {"type": "dashed", "color": "#9CA3AF"},
                        "label": {"formatter": "avg: {c}", "fontFamily": _font},
                    },
                }
            else:
                item = {
                    "name": s.name, "type": "bar",
                    "data": s.values if spec.orientation != "horizontal" else None,
                    "barMaxWidth": 52,
                    "itemStyle": {"color": _gradient(idx), "borderRadius": [4, 4, 0, 0]},
                    "emphasis": {"focus": "series", "itemStyle": {"shadowBlur": 8, "shadowColor": "rgba(0,0,0,0.2)"}},
                }
                if spec.orientation == "horizontal":
                    item["data"] = s.values
                    item["itemStyle"]["borderRadius"] = [0, 4, 4, 0]
                if is_stacked:
                    item["stack"] = "total"
                    item["label"] = {"show": idx == len(spec.series) - 1, "position": "right" if spec.orientation == "horizontal" else "top", "fontFamily": _font}
                else:
                    item["label"] = {"show": True, "position": "top" if spec.orientation != "horizontal" else "right", "fontFamily": _font, "fontSize": 11}
                    item["markLine"] = {
                        "data": [{"type": "average", "name": "均值"}],
                        "lineStyle": {"type": "dashed", "color": palette[idx % len(palette)]},
                        "label": {"formatter": "avg: {c}", "fontFamily": _font},
                    }
            bar_series.append(item)
        base["series"] = bar_series
        return base

    # ── Line / Area / Stacked area ───────────────────────────────────────────
    if spec.chart_type in {"line", "area", "stacked_area"}:
        is_area = spec.chart_type in {"area", "stacked_area"}
        is_stacked = spec.chart_type == "stacked_area"
        line_series = []
        symbols = ["circle", "rect", "diamond", "triangle", "roundRect", "arrow"]
        for idx, s in enumerate(spec.series[:8]):
            item = {
                "name": s.name, "type": "line",
                "data": s.values,
                "smooth": True,
                "lineStyle": {"width": 3, "color": palette[idx % len(palette)]},
                "symbol": symbols[idx % len(symbols)], "symbolSize": 8,
                "itemStyle": {"color": palette[idx % len(palette)]},
                "label": {"show": len(s.values) <= 12, "position": "top", "fontSize": 11, "fontFamily": _font},
                "emphasis": {"focus": "series"},
            }
            if is_area:
                item["areaStyle"] = {"color": _area_gradient(idx), "opacity": 1}
            if is_stacked:
                item["stack"] = "total"
            if not is_stacked:
                item["markPoint"] = {
                    "data": [{"type": "max", "name": "峰值"}, {"type": "min", "name": "谷值"}],
                    "symbolSize": 36,
                    "label": {"fontFamily": _font, "fontSize": 10},
                }
            line_series.append(item)
        base["series"] = line_series
        return base

    # ── Scatter ──────────────────────────────────────────────────────────────
    if spec.chart_type == "scatter":
        base["series"] = [{
            "name": s.name, "type": "scatter",
            "data": list(zip(spec.labels, s.values)),
            "symbolSize": 12,
            "itemStyle": {"color": palette[i % len(palette)], "opacity": 0.8},
            "emphasis": {"focus": "series", "itemStyle": {"shadowBlur": 8}},
        } for i, s in enumerate(spec.series)]
        return base

    # ── Funnel ───────────────────────────────────────────────────────────────
    if spec.chart_type == "funnel":
        max_val = max(spec.primary_values) if spec.primary_values else 100
        funnel_data = [
            {"value": v, "name": lbl,
             "itemStyle": {"color": palette[i % len(palette)],
                           "borderColor": "#fff", "borderWidth": 1}}
            for i, (lbl, v) in enumerate(zip(spec.labels, spec.primary_values))
        ]
        base.pop("grid", None)
        base.pop("xAxis", None)
        base.pop("yAxis", None)
        base["series"] = [{
            "type": "funnel",
            "left": "8%", "right": "8%", "top": "18%", "bottom": "5%",
            "width": "84%",
            "min": 0, "max": max_val,
            "minSize": "0%", "maxSize": "100%",
            "sort": "descending", "gap": 3,
            "label": {
                "show": True, "position": "inside",
                "formatter": "{b}: {c}" + (f" {spec.unit}" if spec.unit else ""),
                "fontFamily": _font, "fontSize": 13, "color": "#fff", "fontWeight": "bold",
            },
            "labelLine": {"length": 10, "lineStyle": {"width": 1, "type": "solid"}},
            "emphasis": {"label": {"fontSize": 15}, "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.2)"}},
            "data": funnel_data,
        }]
        return base

    # ── Gauge ────────────────────────────────────────────────────────────────
    if spec.chart_type == "gauge":
        value = spec.primary_values[0] if spec.primary_values else 0
        min_val = spec.extra.get("min", 0)
        max_val = spec.extra.get("max", 100)
        ratio = (value - min_val) / max(max_val - min_val, 1)
        base.pop("grid", None)
        base.pop("xAxis", None)
        base.pop("yAxis", None)
        base.pop("legend", None)
        base["series"] = [{
            "type": "gauge",
            "center": ["50%", "62%"],
            "radius": "72%",
            "min": min_val, "max": max_val,
            "splitNumber": 5,
            "axisLine": {
                "roundCap": True,
                "lineStyle": {
                    "width": 22,
                    "color": [
                        [min(ratio * 0.6, 0.6), palette[2] if len(palette) > 2 else "#10B981"],
                        [min(ratio, 0.999), palette[0]],
                        [1, "#E5E7EB"],
                    ],
                },
            },
            "pointer": {
                "icon": "path://M12.8,0.7l12,40.1H0.7L12.8,0.7z",
                "length": "55%", "width": 12,
                "offsetCenter": [0, "-10%"],
                "itemStyle": {"color": "auto"},
            },
            "axisTick": {"length": 10, "lineStyle": {"color": "auto", "width": 2}},
            "splitLine": {"length": 20, "lineStyle": {"color": "auto", "width": 4}},
            "axisLabel": {"color": _axis_color, "distance": 40, "fontSize": 12, "fontFamily": _font},
            "title": {"offsetCenter": [0, "88%"], "fontSize": 14, "color": "#374151", "fontFamily": _font},
            "detail": {
                "valueAnimation": True,
                "formatter": "{value}" + (f" {spec.unit}" if spec.unit else ""),
                "color": "inherit", "fontSize": 30, "fontWeight": "bold",
                "offsetCenter": [0, "62%"], "fontFamily": _font,
            },
            "data": [{"value": value, "name": spec.series[0].name if spec.series else spec.title}],
        }]
        return base

    # ── Treemap ──────────────────────────────────────────────────────────────
    if spec.chart_type == "treemap":
        tree_data = spec.extra.get("tree")
        if not tree_data:
            tree_data = [
                {"name": lbl, "value": v,
                 "itemStyle": {"color": palette[i % len(palette)]}}
                for i, (lbl, v) in enumerate(zip(spec.labels, spec.primary_values))
            ]
        base.pop("grid", None)
        base.pop("xAxis", None)
        base.pop("yAxis", None)
        base["series"] = [{
            "type": "treemap",
            "width": "96%", "height": "80%", "top": "15%",
            "roam": False, "nodeClick": False,
            "data": tree_data,
            "label": {
                "show": True,
                "formatter": "{b}\n{c}" + (f" {spec.unit}" if spec.unit else ""),
                "fontFamily": _font, "fontSize": 13,
            },
            "upperLabel": {
                "show": True, "height": 28,
                "fontFamily": _font, "fontSize": 13, "fontWeight": "bold",
            },
            "itemStyle": {"borderColor": "#fff", "borderWidth": 2, "gapWidth": 2},
            "breadcrumb": {"show": False},
            "levels": [
                {"itemStyle": {"borderWidth": 3, "borderColor": "#F9FAFB", "gapWidth": 3}},
                {"colorSaturation": [0.4, 0.6],
                 "itemStyle": {"borderColorSaturation": 0.7, "gapWidth": 2, "borderWidth": 2}},
            ],
            "color": palette[:8],
            "emphasis": {"label": {"fontSize": 15}, "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.15)"}},
        }]
        return base

    # ── Sankey ───────────────────────────────────────────────────────────────
    if spec.chart_type == "sankey":
        nodes = spec.extra.get("nodes", [{"name": lbl} for lbl in spec.labels])
        links = spec.extra.get("links", [])
        base.pop("grid", None)
        base.pop("xAxis", None)
        base.pop("yAxis", None)
        base.pop("legend", None)
        base["series"] = [{
            "type": "sankey",
            "left": "5%", "right": "20%", "top": "18%", "bottom": "5%",
            "data": nodes,
            "links": links,
            "emphasis": {"focus": "adjacency"},
            "lineStyle": {"color": "gradient", "opacity": 0.4, "curveness": 0.5},
            "itemStyle": {"borderWidth": 1, "borderColor": "#aaa"},
            "label": {"fontFamily": _font, "fontSize": 12, "color": "#374151"},
            "nodeWidth": 20, "nodeGap": 10,
            "layoutIterations": 32,
        }]
        return base

    # ── Boxplot ──────────────────────────────────────────────────────────────
    if spec.chart_type == "boxplot":
        box_data: list[list[float]] = []
        outliers: list[list] = []
        for si, s in enumerate(spec.series):
            if len(s.values) >= 5:
                # Already pre-computed [min, Q1, median, Q3, max]
                box_data.append([round(v, 2) for v in s.values[:5]])
            elif len(s.values) >= 3:
                sv = sorted(v for v in s.values if not math.isnan(v))
                n = len(sv)
                q1 = sv[n // 4]
                med = sv[n // 2]
                q3 = sv[3 * n // 4]
                box_data.append([round(sv[0], 2), round(q1, 2), round(med, 2), round(q3, 2), round(sv[-1], 2)])
        base["xAxis"] = {
            "type": "category",
            "data": [s.name for s in spec.series[:len(box_data)]],
            "axisLine": {"lineStyle": {"color": "#E5E7EB"}},
            "axisLabel": {"fontFamily": _font, "fontSize": 12, "color": _axis_color},
        }
        base["series"] = [
            {
                "name": "boxplot", "type": "boxplot",
                "data": box_data,
                "itemStyle": {"color": palette[0] + "40", "borderColor": palette[0], "borderWidth": 2},
                "emphasis": {"itemStyle": {"borderColor": "#111827", "shadowBlur": 8}},
                "tooltip": {"formatter": (
                    "function(p){var v=p.data;return p.name+'<br/>"
                    "最大值: '+v[5]+'<br/>Q3: '+v[4]+'<br/>中位数: '+v[3]+'<br/>Q1: '+v[2]+'<br/>最小值: '+v[1];}"
                )},
            },
            *([{
                "name": "异常值", "type": "scatter",
                "data": outliers,
                "symbolSize": 8,
                "itemStyle": {"color": palette[3] if len(palette) > 3 else "#EF4444", "opacity": 0.7},
            }] if outliers else []),
        ]
        return base

    # Generic fallback
    base["series"] = [{
        "name": s.name, "type": "bar",
        "data": s.values,
        "itemStyle": {"color": _gradient(idx)},
    } for idx, s in enumerate(spec.series)]
    return base


# ---------------------------------------------------------------------------
# Markdown table → ChartSpec inference
# ---------------------------------------------------------------------------

def _parse_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_number(value: str) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "N/A", "NA"}:
        return None
    text = re.sub(r"[,\s，]", "", text)
    multiplier = 1.0
    if "亿" in text:
        multiplier = 100_000_000.0
    elif "万" in text:
        multiplier = 10_000.0
    text = re.sub(r"(万元|亿元|万|亿|元|%|％|人次|人|项|个|次|倍)", "", text)
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0)) * multiplier
    except ValueError:
        return None


def _unit_from_header(header: str) -> str:
    match = re.search(r"[（(]([^）)]+)[）)]", header or "")
    if match:
        return match.group(1)
    if re.search(r"(%|％|占比|比例|率|增速|同比|环比|rate|ratio|share)", header or "", re.I):
        return "%"
    return ""


def _looks_like_rate(header: str) -> bool:
    return bool(re.search(r"(%|％|率|占比|比例|增速|增长|同比|环比|margin|rate|ratio|share)", header or "", re.I))


def _is_temporal_label(label: str) -> bool:
    return bool(re.search(r"(\d{4}年|\d{1,2}月|Q[1-4]|[一二三四]季度|周|日|date|year|month|quarter)", label or "", re.I))


def infer_chart_spec_from_markdown_table(
    table_lines: list[str],
    *,
    title_hint: str = "",
    max_categories: int = 12,
) -> Optional[ChartSpec]:
    """Convert a markdown table into a ChartSpec with automatic type inference."""
    cleaned = [
        line for line in table_lines
        if line.strip().startswith("|") and not re.match(r"^\|[-:| ]+\|$", line.strip())
    ]
    if len(cleaned) < 3:
        return None

    header = _parse_row(cleaned[0])
    rows = [_parse_row(line) for line in cleaned[1:]]
    if len(header) < 2 or not rows:
        return None

    max_cols = max(len(header), *(len(row) for row in rows))
    header = header + [""] * (max_cols - len(header))
    rows = [row + [""] * (max_cols - len(row)) for row in rows]

    numeric_cols: list[tuple[int, list[float]]] = []
    for col_idx in range(1, max_cols):
        values: list[float] = []
        valid_rows = 0
        for row in rows:
            parsed = _parse_number(row[col_idx])
            if parsed is not None:
                values.append(parsed)
                valid_rows += 1
            else:
                values.append(math.nan)
        if valid_rows >= 2 and valid_rows / max(len(rows), 1) >= 0.6:
            numeric_cols.append((col_idx, values))
    if not numeric_cols:
        return None

    labels = [str(row[0]).strip()[:18] or f"项{i + 1}" for i, row in enumerate(rows)]
    keep_count = min(len(labels), max_categories)
    labels = labels[:keep_count]
    series: list[ChartSeries] = []
    for col_idx, raw_values in numeric_cols[:6]:
        values = [0 if math.isnan(v) else v for v in raw_values[:keep_count]]
        name = header[col_idx] or f"指标{len(series) + 1}"
        series.append(ChartSeries(name=name, values=values))

    combined = " ".join([title_hint, *header, *labels]).lower()
    primary_name = series[0].name
    unit = _unit_from_header(primary_name)
    secondary_unit = _unit_from_header(series[1].name) if len(series) > 1 else ""
    all_positive = all(v >= 0 for v in series[0].values)
    total = sum(series[0].values)
    is_share = bool(re.search(r"(占比|比例|份额|结构|构成|分布|pie|donut|share)", combined))
    is_temporal = bool(re.search(r"(趋势|走势|时间|年度|月份|季度|date|year|month|trend)", combined)) or \
                  sum(_is_temporal_label(lbl) for lbl in labels) >= 2
    has_rate_col = len(series) >= 2 and any(_looks_like_rate(s.name) for s in series[1:])
    # Funnel: single numeric series, monotonically decreasing, and funnel keywords
    is_funnel_shape = (
        len(series) == 1 and all_positive and len(series[0].values) >= 3
        and all(series[0].values[i] >= series[0].values[i + 1]
                for i in range(len(series[0].values) - 1))
    )
    is_funnel_keyword = bool(re.search(
        r"(漏斗|转化|转化率|pipeline|funnel|步骤|stage|环节|流失|进入|通过)", combined
    ))

    if is_share and all_positive and 2 <= len(labels) <= 8 and total > 0:
        chart_type = "donut" if len(labels) >= 4 else "pie"
        title = f"{primary_name}结构占比"
    elif is_funnel_keyword or (is_funnel_shape and len(labels) >= 3 and not is_share):
        chart_type = "funnel"
        title = f"{primary_name}转化漏斗"
    elif has_rate_col and not _looks_like_rate(primary_name):
        chart_type = "combo"
        title = f"{primary_name}与{series[1].name}组合"
    elif is_temporal:
        chart_type = "line"
        title = f"{primary_name}趋势"
    elif len(series) > 1:
        chart_type = "stacked_bar" if all_positive else "bar"
        title = f"{primary_name}多维对比"
    else:
        chart_type = "bar"
        title = f"{primary_name}对比"

    orientation = "horizontal" if chart_type == "bar" and (len(labels) > 6 or any(len(lbl) > 6 for lbl in labels)) else "vertical"
    if title_hint and title_hint not in title:
        title = f"{title_hint}｜{title}"

    return ChartSpec(
        chart_type=chart_type,
        title=title[:52],
        labels=labels,
        series=series,
        unit=unit,
        secondary_unit=secondary_unit,
        orientation=orientation,
        palette=list(PALETTE_BUSINESS),
    )


# ---------------------------------------------------------------------------
# PNG rendering
# ---------------------------------------------------------------------------

def render_chart_png(
    spec: ChartSpec,
    *,
    width: int = 1400,
    height: int = 820,
    accent_color: str = "#2563eb",
    palette: list[str] | None = None,
) -> Optional[ChartRenderResult]:
    """Render chart as PNG, trying Plotly then Matplotlib."""
    if palette:
        spec = ChartSpec(
            chart_type=spec.chart_type, title=spec.title, labels=spec.labels,
            series=spec.series, unit=spec.unit, secondary_unit=spec.secondary_unit,
            orientation=spec.orientation, source_note=spec.source_note, palette=palette,
            extra=spec.extra,
        )
    for renderer in (_render_with_plotly, _render_with_matplotlib):
        try:
            png = renderer(spec, width=width, height=height)
            if png:
                backend = renderer.__name__.replace("_render_with_", "")
                return ChartRenderResult(png=png, backend=backend, spec=spec)
        except Exception as exc:
            logger.debug("Chart renderer %s skipped: %s", renderer.__name__, exc)
    return None


def render_chart_composite(
    specs: list[ChartSpec],
    *,
    cols: int = 2,
    cell_width: int = 800,
    cell_height: int = 480,
) -> Optional[bytes]:
    """Render multiple ChartSpecs into a side-by-side small-multiples PNG using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed; cannot composite charts")
        return None

    renders = []
    for spec in specs:
        result = render_chart_png(spec, width=cell_width, height=cell_height)
        if result:
            renders.append(result.png)
        else:
            renders.append(None)

    rows = math.ceil(len(renders) / cols)
    canvas_w = cols * cell_width
    canvas_h = rows * cell_height
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#F8FAFC")
    draw = ImageDraw.Draw(canvas)

    for i, png_bytes in enumerate(renders):
        col = i % cols
        row = i // cols
        x_off = col * cell_width
        y_off = row * cell_height
        if png_bytes:
            cell_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            cell_img = cell_img.resize((cell_width, cell_height), Image.LANCZOS)
            canvas.paste(cell_img, (x_off, y_off))
        # Subtle separator lines
        draw.line([(x_off, y_off), (x_off + cell_width, y_off)], fill="#E5E7EB", width=1)
        draw.line([(x_off, y_off), (x_off, y_off + cell_height)], fill="#E5E7EB", width=1)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


def render_multi_panel_chart(
    specs: list[ChartSpec],
    *,
    figure_title: str = "",
    figure_caption: str = "",
    cols: int = 2,
    fig_width_inches: float = 14.0,
    dpi: int = 150,
    style: str = "academic",
) -> Optional[bytes]:
    """Render multiple ChartSpecs as a publication-quality multi-panel figure.

    Produces a matplotlib figure with shared academic styling:
    clean white background, light gray grid, bold value labels,
    reference/mean lines, distinct markers, and panel letter labels (A, B, …).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    if not specs:
        return None

    n = len(specs)
    rows = math.ceil(n / cols)
    panel_h = 4.2
    fig_h = rows * panel_h + (0.6 if figure_title else 0.2) + (0.5 if figure_caption else 0.0)

    PALETTE = ["#2563EB", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", "#06B6D4", "#F97316", "#84CC16"]
    GRID_COLOR = "#E5E7EB"
    AXIS_COLOR = "#374151"
    LABEL_FONTSIZE = 8
    TITLE_FONTSIZE = 10
    CAPTION_FONTSIZE = 9
    PANEL_LABEL_FONTSIZE = 11

    fig, axes_grid = plt.subplots(rows, cols, figsize=(fig_width_inches, fig_h), dpi=dpi)
    fig.patch.set_facecolor("white")

    if figure_title:
        fig.suptitle(figure_title, fontsize=13, fontweight="bold", color=AXIS_COLOR, y=0.98)

    # Flatten axes into a list
    if rows == 1 and cols == 1:
        axes_list = [axes_grid]
    elif rows == 1 or cols == 1:
        axes_list = list(axes_grid.flatten() if hasattr(axes_grid, 'flatten') else [axes_grid])
    else:
        axes_list = list(axes_grid.flatten())

    def _style_ax(ax):
        ax.set_facecolor("white")
        ax.grid(axis="y", color=GRID_COLOR, linewidth=0.7, linestyle="--", alpha=0.8)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)
            spine.set_linewidth(0.8)
        ax.tick_params(labelsize=LABEL_FONTSIZE, colors=AXIS_COLOR, length=3)

    def _add_value_labels(ax, bars, fmt="{:.1f}", fontsize=7):
        for bar in bars:
            h = bar.get_height()
            if h == 0:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2, h,
                fmt.format(h), ha="center", va="bottom",
                fontsize=fontsize, color=AXIS_COLOR, fontweight="bold",
            )

    def _draw_mean_line(ax, values, color="#EF4444", label="Mean"):
        if not values:
            return
        mean_val = float(np.mean(values))
        ax.axhline(mean_val, color=color, linewidth=1.2, linestyle="--", alpha=0.8)
        ax.text(
            ax.get_xlim()[1] if ax.get_xlim()[1] != 1.0 else len(values),
            mean_val, f" {label}={mean_val:.2f}",
            va="center", ha="left", fontsize=7, color=color, fontweight="bold",
        )

    MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]

    for idx, spec in enumerate(specs):
        if idx >= len(axes_list):
            break
        ax = axes_list[idx]
        _style_ax(ax)

        # Panel label (A, B, C, …)
        panel_letter = chr(65 + idx)
        ax.text(
            -0.08, 1.05, panel_letter, transform=ax.transAxes,
            fontsize=PANEL_LABEL_FONTSIZE, fontweight="bold", color=AXIS_COLOR,
            va="top", ha="left",
        )

        ct = spec.chart_type
        labels = spec.labels or []
        x = np.arange(len(labels))

        if ct in ("bar", "column"):
            n_series = len(spec.series)
            bar_w = 0.7 / max(n_series, 1)
            offsets = np.linspace(-(n_series - 1) * bar_w / 2, (n_series - 1) * bar_w / 2, n_series)
            all_vals = []
            for si, series in enumerate(spec.series):
                vals = list(series.values)[:len(labels)]
                color = PALETTE[si % len(PALETTE)]
                bars = ax.bar(x + offsets[si], vals, width=bar_w * 0.9, color=color, alpha=0.85, label=series.name)
                _add_value_labels(ax, bars)
                all_vals.extend(vals)
            if len(spec.series) == 1 and all_vals:
                _draw_mean_line(ax, all_vals)
            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=LABEL_FONTSIZE, rotation=20 if len(labels) > 5 else 0, ha="right")

        elif ct == "line":
            for si, series in enumerate(spec.series):
                vals = list(series.values)[:len(labels)]
                color = PALETTE[si % len(PALETTE)]
                marker = MARKERS[si % len(MARKERS)]
                ax.plot(x, vals, color=color, linewidth=2.0, marker=marker, markersize=5,
                        label=series.name, markerfacecolor="white", markeredgewidth=1.5)
                # Annotate last point
                if vals:
                    ax.annotate(
                        f"{vals[-1]:.2f}", xy=(x[-1], vals[-1]),
                        xytext=(4, 2), textcoords="offset points",
                        fontsize=6.5, color=color, fontweight="bold",
                    )
            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=LABEL_FONTSIZE, rotation=20 if len(labels) > 5 else 0, ha="right")

        elif ct in ("pie", "donut"):
            vals = spec.primary_values
            wedge_props = {"linewidth": 1.5, "edgecolor": "white"}
            if ct == "donut":
                wedge_props["width"] = 0.5
            ax.pie(vals, labels=labels, colors=PALETTE[:len(vals)],
                   autopct="%1.1f%%", startangle=90, wedgeprops=wedge_props,
                   textprops={"fontsize": LABEL_FONTSIZE})

        elif ct == "scatter":
            vals_x = spec.primary_values
            vals_y = list(spec.series[1].values) if len(spec.series) > 1 else vals_x
            ax.scatter(vals_x, vals_y, c=PALETTE[0], alpha=0.7, s=40, edgecolors="white", linewidths=0.5)
            # Trend line
            try:
                z = np.polyfit(vals_x, vals_y, 1)
                p = np.poly1d(z)
                sorted_x = sorted(vals_x)
                ax.plot(sorted_x, p(sorted_x), "--", color=PALETTE[1], linewidth=1.2, alpha=0.8)
            except Exception:
                pass

        elif ct == "funnel":
            vals = spec.primary_values
            bar_colors = PALETTE[:len(vals)]
            bars = ax.barh(range(len(labels)), vals, color=bar_colors, alpha=0.85)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=LABEL_FONTSIZE)
            ax.invert_yaxis()
            for bar, val in zip(bars, vals):
                ax.text(val + max(vals) * 0.01, bar.get_y() + bar.get_height() / 2,
                        str(val), va="center", fontsize=7, fontweight="bold", color=AXIS_COLOR)

        elif ct == "boxplot":
            box_data = [list(s.values) for s in spec.series if s.values]
            bp = ax.boxplot(box_data, patch_artist=True, notch=False,
                            medianprops={"color": "white", "linewidth": 2})
            for patch, color in zip(bp["boxes"], PALETTE):
                patch.set_facecolor(color)
                patch.set_alpha(0.8)
            ax.set_xticks(range(1, len(spec.series) + 1))
            ax.set_xticklabels([s.name for s in spec.series], fontsize=LABEL_FONTSIZE, rotation=20)

        else:
            # Fallback: bar chart
            vals = spec.primary_values
            bars = ax.bar(x, vals, color=PALETTE[0], alpha=0.85)
            _add_value_labels(ax, bars)
            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=LABEL_FONTSIZE, rotation=20 if len(labels) > 5 else 0)

        ax.set_title(spec.title, fontsize=TITLE_FONTSIZE, fontweight="bold", color=AXIS_COLOR, pad=6)
        if spec.unit:
            ax.set_ylabel(spec.unit, fontsize=LABEL_FONTSIZE, color=AXIS_COLOR)
        if len(spec.series) > 1:
            ax.legend(fontsize=7, loc="upper right", framealpha=0.8, edgecolor=GRID_COLOR)

    # Hide unused axes
    for idx in range(len(specs), len(axes_list)):
        axes_list[idx].set_visible(False)

    if figure_caption:
        fig.text(
            0.5, 0.01, figure_caption,
            ha="center", va="bottom", fontsize=CAPTION_FONTSIZE,
            color="#6B7280", style="italic",
            wrap=True,
        )

    plt.tight_layout(rect=[0, 0.04 if figure_caption else 0, 1, 0.96 if figure_title else 1])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _pack_split(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，;/]+", raw or "") if item.strip()]


def _pack_numbers(raw: str) -> list[float]:
    values: list[float] = []
    for token in re.split(r"[,，;/\s]+", raw or ""):
        match = re.search(r"-?\d+(?:\.\d+)?", token.strip().replace("%", "").replace("％", ""))
        if match:
            values.append(float(match.group(0)))
    return values


def _pack_series(raw: str) -> list[ChartSeries]:
    series: list[ChartSeries] = []
    for item in re.split(r"\s*;\s*", raw or ""):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            name, _, values_raw = item.partition(":")
        elif "=" in item:
            name, _, values_raw = item.partition("=")
        else:
            continue
        values = _pack_numbers(values_raw)
        if values:
            series.append(ChartSeries(name=name.strip(), values=values))
    return series


def _wrap_labels(labels: list[str], width: int = 12) -> list[str]:
    wrapped: list[str] = []
    for label in labels:
        parts = textwrap.wrap(str(label), width=width, break_long_words=False) or [str(label)]
        wrapped.append("\n".join(parts[:3]))
    return wrapped


def render_academic_figure_pack(
    figure_type: str,
    payload: dict[str, str],
    *,
    dpi: int = 220,
) -> Optional[bytes]:
    """Render publication-style multi-panel figures for empirical papers.

    The function intentionally requires explicit numeric data in ``payload``.
    It will return None instead of inventing benchmark values.
    """
    kind = (figure_type or "").lower().strip().replace("-", "_")
    title = payload.get("title", "")
    caption = payload.get("caption", "")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ModuleNotFoundError:
        return _render_academic_figure_pack_plotly(kind, payload)

    BLUE = "#2F91CF"
    BLUE_DARK = "#0072B2"
    RED = "#FF4D5A"
    PURPLE = "#A64DB3"
    GREEN = "#22B14C"
    ORANGE = "#F28E2B"
    GRAY = "#9CA3AF"
    GRID = "#E5E7EB"
    TEXT = "#202124"
    PALETTE = [GRAY, "#A3D5EC", "#76C6E8", "#8CCB5E", BLUE_DARK, PURPLE, ORANGE, GREEN]

    def style_ax(ax):
        ax.set_facecolor("white")
        ax.grid(True, color=GRID, linewidth=0.55, alpha=0.45)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#D0D0D0")
        ax.spines["bottom"].set_color("#D0D0D0")
        ax.tick_params(labelsize=8, colors=TEXT)

    def finish(fig):
        if title:
            fig.suptitle(title, fontsize=12, fontweight="bold", color=TEXT, y=0.985)
        if caption:
            fig.text(0.5, 0.012, caption, ha="center", va="bottom", fontsize=8, color="#4B5563", wrap=True)
        rect_bottom = 0.06 if caption else 0.035
        rect_top = 0.94 if title else 0.99
        fig.tight_layout(rect=[0.02, rect_bottom, 0.98, rect_top])
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    if kind in {"training_dynamics", "training_validation"}:
        epochs = _pack_numbers(payload.get("epochs") or payload.get("x") or "")
        loss_series = _pack_series(payload.get("loss_series", ""))
        acc_series = _pack_series(payload.get("acc_series", ""))
        if not loss_series:
            lb = _pack_numbers(payload.get("loss_baseline", ""))
            lo = _pack_numbers(payload.get("loss_ours", ""))
            if lb and lo:
                loss_series = [ChartSeries("CNN Baseline", lb), ChartSeries("Ours (ResNet-EEG)", lo)]
        if not acc_series:
            ab = _pack_numbers(payload.get("acc_baseline", ""))
            ao = _pack_numbers(payload.get("acc_ours", ""))
            if ab and ao:
                acc_series = [ChartSeries("CNN Baseline", ab), ChartSeries("Ours (ResNet-EEG)", ao)]
        if not epochs or len(loss_series) < 2 or len(acc_series) < 2:
            return None
        n = min(len(epochs), *(len(s.values) for s in loss_series + acc_series))
        epochs = epochs[:n]
        fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.3))
        for ax in axes:
            style_ax(ax)
        axes[0].set_title(payload.get("left_title", "Training Loss"), fontsize=10, fontweight="bold")
        axes[1].set_title(payload.get("right_title", "Validation Accuracy"), fontsize=10, fontweight="bold")
        styles = [(RED, "--"), (BLUE, "-"), (GREEN, "-."), (PURPLE, ":")]
        for idx, s in enumerate(loss_series[:4]):
            color, ls = styles[idx % len(styles)]
            axes[0].plot(epochs, s.values[:n], color=color, linestyle=ls, linewidth=1.7, label=s.name)
        for idx, s in enumerate(acc_series[:4]):
            color, ls = styles[idx % len(styles)]
            axes[1].plot(epochs, s.values[:n], color=color, linestyle=ls, linewidth=1.9, label=s.name)
        axes[0].set_xlabel("Epoch", fontsize=8)
        axes[0].set_ylabel(payload.get("loss_unit", "Cross-Entropy Loss"), fontsize=8)
        axes[1].set_xlabel("Epoch", fontsize=8)
        axes[1].set_ylabel(payload.get("acc_unit", "Validation Accuracy (%)"), fontsize=8)
        axes[0].legend(fontsize=7, frameon=True, edgecolor="#DADCE0")
        axes[1].legend(fontsize=7, frameon=True, edgecolor="#DADCE0", loc="lower right")
        try:
            ours_final = acc_series[1].values[n - 1]
            base_final = acc_series[0].values[n - 1]
            axes[1].axhline(ours_final, color=BLUE, linestyle=":", linewidth=1.0, alpha=0.45)
            axes[1].axhline(base_final, color=RED, linestyle=":", linewidth=1.0, alpha=0.45)
            axes[1].annotate(f"Ours: {ours_final:.1f}%", xy=(epochs[-1], ours_final), xytext=(-8, 6),
                             textcoords="offset points", ha="right", fontsize=8, color=BLUE, fontweight="bold")
            axes[1].annotate(f"Baseline: {base_final:.1f}%", xy=(epochs[-1], base_final), xytext=(-8, 6),
                             textcoords="offset points", ha="right", fontsize=8, color=RED, fontweight="bold")
        except Exception:
            pass
        return finish(fig)

    if kind in {"benchmark_comparison", "cross_dataset"}:
        labels = _pack_split(payload.get("datasets") or payload.get("labels") or "")
        series = _pack_series(payload.get("series", ""))
        if not labels or len(series) < 2:
            return None
        n = min(len(labels), *(len(s.values) for s in series))
        labels = labels[:n]
        x = np.arange(n)
        fig, ax = plt.subplots(1, 1, figsize=(10.8, 4.8))
        style_ax(ax)
        bar_w = min(0.78 / max(len(series), 1), 0.16)
        offsets = np.linspace(-(len(series) - 1) * bar_w / 2, (len(series) - 1) * bar_w / 2, len(series))
        for idx, s in enumerate(series):
            is_ours = bool(re.search(r"(ours|resnet|proposed)", s.name, re.I))
            color = BLUE_DARK if is_ours else PALETTE[idx % len(PALETTE)]
            bars = ax.bar(x + offsets[idx], s.values[:n], width=bar_w * 0.92, label=s.name, color=color, alpha=0.96 if is_ours else 0.72)
            if is_ours:
                for bar, value in zip(bars, s.values[:n]):
                    ax.text(bar.get_x() + bar.get_width() / 2, value + 0.7, f"{value:.1f}", ha="center",
                            va="bottom", fontsize=7, color=BLUE_DARK, fontweight="bold")
        ax.set_title(payload.get("panel_title", "Cross-Dataset Performance Comparison"), fontsize=11, fontweight="bold")
        ax.set_ylabel(payload.get("unit", "Classification Accuracy (%)"), fontsize=9, fontweight="bold")
        ax.set_xlabel(payload.get("x_label", "Dataset"), fontsize=9, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(_wrap_labels(labels, 12), fontsize=8)
        ax.legend(fontsize=7, ncol=min(3, len(series)), loc="upper left", frameon=True, edgecolor="#DADCE0")
        return finish(fig)

    if kind in {"ablation", "ablation_bar"}:
        variants = _pack_split(payload.get("variants", ""))
        values = _pack_numbers(payload.get("ablation_values") or payload.get("values") or "")
        if not variants or not values:
            return None
        n = min(len(variants), len(values))
        variants, values = variants[:n], values[:n]
        fig, ax = plt.subplots(1, 1, figsize=(8.8, 4.5))
        style_ax(ax)
        colors = [BLUE_DARK] + [PURPLE] * max(0, n - 2) + ([RED] if n > 1 else [])
        bars = ax.bar(np.arange(n), values, color=colors[:n], alpha=0.96)
        ax.axhline(values[0], color=BLUE, linestyle="--", linewidth=1.0, alpha=0.55)
        if n > 1:
            ax.axhline(values[-1], color=RED, linestyle="--", linewidth=1.0, alpha=0.55)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.45, f"{value:.1f}", ha="center",
                    fontsize=8, fontweight="bold", color=TEXT)
        ax.set_title(payload.get("left_title", payload.get("title", "Ablation Study")), fontsize=10, fontweight="bold")
        ax.set_ylabel(payload.get("unit", "Accuracy (%)"), fontsize=8)
        ax.set_xticks(np.arange(n))
        ax.set_xticklabels(_wrap_labels(variants, 11), fontsize=7)
        return finish(fig)

    if kind in {"ablation_subject", "ablation_subjectwise"}:
        variants = _pack_split(payload.get("variants", ""))
        ablation_values = _pack_numbers(payload.get("ablation_values", ""))
        subjects = _pack_split(payload.get("subjects", ""))
        baseline_values = _pack_numbers(payload.get("baseline_values", ""))
        ours_values = _pack_numbers(payload.get("ours_values", ""))
        if not variants or not ablation_values or not subjects or not baseline_values or not ours_values:
            return None
        n_left = min(len(variants), len(ablation_values))
        n_right = min(len(subjects), len(baseline_values), len(ours_values))
        variants, ablation_values = variants[:n_left], ablation_values[:n_left]
        subjects, baseline_values, ours_values = subjects[:n_right], baseline_values[:n_right], ours_values[:n_right]
        fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.4))
        for ax in axes:
            style_ax(ax)
        colors = [BLUE_DARK] + [PURPLE] * max(0, n_left - 2) + ([RED] if n_left > 1 else [])
        bars = axes[0].bar(np.arange(n_left), ablation_values, color=colors[:n_left], alpha=0.96)
        full_val = ablation_values[0]
        baseline_ref = ablation_values[-1]
        axes[0].axhline(full_val, color=BLUE, linestyle="--", linewidth=1.0, alpha=0.55)
        axes[0].axhline(baseline_ref, color=RED, linestyle="--", linewidth=1.0, alpha=0.55)
        for bar, value in zip(bars, ablation_values):
            axes[0].text(bar.get_x() + bar.get_width() / 2, value + 0.45, f"{value:.1f}", ha="center",
                         fontsize=8, fontweight="bold", color=TEXT)
        axes[0].set_title(payload.get("left_title", "Ablation Study"), fontsize=10, fontweight="bold")
        axes[0].set_ylabel(payload.get("unit", "Accuracy (%)"), fontsize=8)
        axes[0].set_xticks(np.arange(n_left))
        axes[0].set_xticklabels(_wrap_labels(variants, 11), fontsize=7)

        x = np.arange(n_right)
        width = 0.34
        axes[1].bar(x - width / 2, baseline_values, width=width, color=RED, label=payload.get("baseline_name", "CNN Baseline"), alpha=0.92)
        axes[1].bar(x + width / 2, ours_values, width=width, color=BLUE, label=payload.get("ours_name", "Ours"), alpha=0.92)
        mean_base = float(np.mean(baseline_values))
        mean_ours = float(np.mean(ours_values))
        axes[1].axhline(mean_ours, color=BLUE, linestyle="--", linewidth=1.0, alpha=0.65)
        axes[1].axhline(mean_base, color=RED, linestyle="--", linewidth=1.0, alpha=0.65)
        axes[1].text(n_right - 0.15, mean_ours + 0.3, f"Mean: {mean_ours:.1f}%", fontsize=8, color=BLUE, fontweight="bold")
        axes[1].text(n_right - 0.15, mean_base - 0.8, f"Mean: {mean_base:.1f}%", fontsize=8, color=RED)
        axes[1].set_title(payload.get("right_title", "Subject-wise Accuracy"), fontsize=10, fontweight="bold")
        axes[1].set_ylabel(payload.get("unit", "Accuracy (%)"), fontsize=8)
        axes[1].set_xlabel("Subject", fontsize=8)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(subjects, fontsize=7)
        axes[1].legend(fontsize=7, frameon=True, edgecolor="#DADCE0")
        return finish(fig)

    if kind in {"temporal_frequency", "temporal_band"}:
        times = _pack_numbers(payload.get("times") or payload.get("x") or "")
        series = _pack_series(payload.get("series", ""))
        bands = _pack_split(payload.get("bands", ""))
        importance = _pack_numbers(payload.get("importance", ""))
        if not times or len(series) < 2 or not bands or not importance:
            return None
        n_time = min(len(times), *(len(s.values) for s in series))
        times = times[:n_time]
        fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.4))
        for ax in axes:
            style_ax(ax)
        markers = ["o", "s", "^", "D", "P", "X"]
        for idx, s in enumerate(series[:6]):
            axes[0].plot(times, s.values[:n_time], color=[BLUE_DARK, GREEN, ORANGE, PURPLE, RED, GRAY][idx % 6],
                         marker=markers[idx % len(markers)], linewidth=1.8, markersize=4.5, label=s.name)
        if "window" in payload:
            window = _pack_numbers(payload["window"])
            if len(window) >= 2:
                axes[0].axvspan(window[0], window[1], color="#D1D5DB", alpha=0.18)
                axes[0].text((window[0] + window[1]) / 2, axes[0].get_ylim()[1] * 0.96, "Optimal\nwindow",
                             ha="center", va="top", fontsize=7, color="#6B7280")
        axes[0].set_title(payload.get("left_title", "Temporal Decoding Profile"), fontsize=10, fontweight="bold")
        axes[0].set_xlabel("Time after cue (s)", fontsize=8)
        axes[0].set_ylabel(payload.get("unit", "Decoding Accuracy (%)"), fontsize=8)
        axes[0].legend(fontsize=7, frameon=True, edgecolor="#DADCE0", loc="lower right")

        n_band = min(len(bands), len(importance))
        bands, importance = bands[:n_band], importance[:n_band]
        y = np.arange(n_band)
        bar_colors = ["#FFB04D", "#6BB7D9", "#A8E052", "#FFC1E2", "#D1D5DB", "#C779C6"][:n_band]
        axes[1].barh(y, importance, color=bar_colors, alpha=0.96)
        axes[1].set_yticks(y)
        axes[1].set_yticklabels(_wrap_labels(bands, 12), fontsize=8)
        axes[1].set_xlabel(payload.get("importance_unit", "Relative Feature Importance"), fontsize=8)
        axes[1].set_title(payload.get("right_title", "Frequency Band Importance"), fontsize=10, fontweight="bold")
        for yi, value in zip(y, importance):
            axes[1].text(value + max(importance) * 0.015, yi, f"{value:.2f}", va="center",
                         fontsize=8, color=TEXT, fontweight="bold")
        return finish(fig)

    if kind in {"business_overview", "executive_dashboard", "performance_dashboard"}:
        periods = _pack_split(payload.get("periods") or payload.get("labels") or "")
        revenue = _pack_numbers(payload.get("revenue_values") or payload.get("sales_values") or payload.get("values") or "")
        rate_values = _pack_numbers(payload.get("growth_values") or payload.get("margin_values") or payload.get("rate_values") or "")
        categories = _pack_split(payload.get("categories") or payload.get("segments") or "")
        category_values = _pack_numbers(payload.get("category_values") or payload.get("segment_values") or "")
        kpi_series = _pack_series(payload.get("kpis", ""))
        if not periods or not revenue:
            return None
        n = min(len(periods), len(revenue))
        periods, revenue = periods[:n], revenue[:n]
        if rate_values:
            rate_values = rate_values[:n]
        fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.2))
        ax1, ax2, ax3, ax4 = axes.flatten()
        for ax in (ax1, ax2, ax3):
            style_ax(ax)
        ax4.axis("off")

        x = np.arange(n)
        bars = ax1.bar(x, revenue, color=BLUE_DARK, alpha=0.88, label=payload.get("primary_name", "Revenue"))
        ax1.set_title(payload.get("left_title", "Revenue Trend"), fontsize=10, fontweight="bold")
        ax1.set_xticks(x)
        ax1.set_xticklabels(_wrap_labels(periods, 10), fontsize=7)
        ax1.set_ylabel(payload.get("unit", "Value"), fontsize=8)
        for bar, value in zip(bars, revenue):
            ax1.text(bar.get_x() + bar.get_width() / 2, value, f"{value:g}", ha="center", va="bottom", fontsize=7, fontweight="bold")
        if rate_values:
            ax1b = ax1.twinx()
            ax1b.plot(x, rate_values, color=ORANGE, linewidth=2.0, marker="o", label=payload.get("rate_name", "Rate"))
            ax1b.set_ylabel(payload.get("rate_unit", "%"), fontsize=8, color=ORANGE)
            ax1b.tick_params(axis="y", labelsize=8, colors=ORANGE)

        if categories and category_values:
            n_cat = min(len(categories), len(category_values))
            cats, vals = categories[:n_cat], category_values[:n_cat]
            order = np.argsort(vals)
            y = np.arange(n_cat)
            ax2.barh(y, [vals[i] for i in order], color=[PALETTE[i % len(PALETTE)] for i in range(n_cat)], alpha=0.92)
            ax2.set_yticks(y)
            ax2.set_yticklabels(_wrap_labels([cats[i] for i in order], 12), fontsize=7)
            ax2.set_title(payload.get("right_title", "Segment Contribution"), fontsize=10, fontweight="bold")
            for yi, value in enumerate([vals[i] for i in order]):
                ax2.text(value, yi, f" {value:g}", va="center", fontsize=7, fontweight="bold")
        else:
            deltas = [revenue[i] - revenue[i - 1] for i in range(1, len(revenue))]
            ax2.bar(np.arange(len(deltas)), deltas, color=[GREEN if v >= 0 else RED for v in deltas], alpha=0.9)
            ax2.set_xticks(np.arange(len(deltas)))
            ax2.set_xticklabels(_wrap_labels(periods[1:], 10), fontsize=7)
            ax2.set_title("Period-over-period Change", fontsize=10, fontweight="bold")

        if rate_values:
            ax3.plot(x, rate_values, color=GREEN, linewidth=2.0, marker="s")
            ax3.axhline(float(np.mean(rate_values)), color=RED, linestyle="--", linewidth=1.0, alpha=0.55)
            ax3.set_xticks(x)
            ax3.set_xticklabels(_wrap_labels(periods, 10), fontsize=7)
            ax3.set_title(payload.get("bottom_left_title", "Rate / Margin Trend"), fontsize=10, fontweight="bold")
            ax3.set_ylabel(payload.get("rate_unit", "%"), fontsize=8)
        else:
            cum = np.cumsum(revenue)
            ax3.plot(x, cum, color=GREEN, linewidth=2.0, marker="s")
            ax3.set_xticks(x)
            ax3.set_xticklabels(_wrap_labels(periods, 10), fontsize=7)
            ax3.set_title("Cumulative Performance", fontsize=10, fontweight="bold")

        kpi_items = kpi_series[:4]
        if not kpi_items:
            kpi_items = [ChartSeries("Total", [sum(revenue)]), ChartSeries("Latest", [revenue[-1]])]
        ax4.set_title(payload.get("bottom_right_title", "KPI Snapshot"), fontsize=10, fontweight="bold", color=TEXT, loc="left")
        for idx, item in enumerate(kpi_items[:4]):
            col = idx % 2
            row = idx // 2
            x0 = 0.04 + col * 0.48
            y0 = 0.62 - row * 0.36
            ax4.add_patch(plt.Rectangle((x0, y0), 0.42, 0.24, transform=ax4.transAxes, facecolor="#F8FAFC", edgecolor="#D1D5DB", linewidth=0.8))
            value = item.values[0] if item.values else 0
            ax4.text(x0 + 0.04, y0 + 0.14, f"{value:g}", transform=ax4.transAxes, fontsize=15, fontweight="bold", color=BLUE_DARK)
            ax4.text(x0 + 0.04, y0 + 0.055, item.name[:28], transform=ax4.transAxes, fontsize=8, color="#4B5563")
        return finish(fig)

    if kind in {"financial_bridge", "profit_bridge", "waterfall_bridge"}:
        labels = _pack_split(payload.get("labels") or payload.get("drivers") or "")
        values = _pack_numbers(payload.get("values") or payload.get("driver_values") or "")
        scenarios = _pack_split(payload.get("scenarios") or "")
        scenario_values = _pack_numbers(payload.get("scenario_values") or payload.get("scenario_profits") or "")
        if not labels or not values:
            return None
        n = min(len(labels), len(values))
        labels, values = labels[:n], values[:n]
        fig, axes = plt.subplots(1, 2 if scenarios and scenario_values else 1, figsize=(12.0, 4.8))
        if not isinstance(axes, np.ndarray):
            axes = np.array([axes])
        ax = axes[0]
        style_ax(ax)
        cumulative = np.cumsum([0] + values[:-1])
        colors = [GREEN if v >= 0 else RED for v in values]
        for idx, (base, value) in enumerate(zip(cumulative, values)):
            bottom = base if value >= 0 else base + value
            ax.bar(idx, abs(value), bottom=bottom, color=colors[idx], alpha=0.9)
            ax.text(idx, bottom + abs(value) + max(abs(v) for v in values) * 0.03, f"{value:+g}", ha="center", fontsize=8, fontweight="bold", color=TEXT)
            if idx > 0:
                ax.plot([idx - 1 + 0.35, idx - 0.35], [base, base], color="#9CA3AF", linewidth=0.8)
        ax.axhline(0, color="#6B7280", linewidth=0.8)
        ax.set_xticks(np.arange(n))
        ax.set_xticklabels(_wrap_labels(labels, 10), fontsize=7, rotation=15, ha="right")
        ax.set_title(payload.get("left_title", "Driver Bridge"), fontsize=10, fontweight="bold")
        ax.set_ylabel(payload.get("unit", "Value"), fontsize=8)
        if len(axes) > 1:
            ax2 = axes[1]
            style_ax(ax2)
            n2 = min(len(scenarios), len(scenario_values))
            bars = ax2.bar(np.arange(n2), scenario_values[:n2], color=[RED, ORANGE, GREEN, BLUE_DARK][:n2], alpha=0.9)
            ax2.set_xticks(np.arange(n2))
            ax2.set_xticklabels(_wrap_labels(scenarios[:n2], 10), fontsize=8)
            ax2.set_title(payload.get("right_title", "Scenario Range"), fontsize=10, fontweight="bold")
            for bar, value in zip(bars, scenario_values[:n2]):
                ax2.text(bar.get_x() + bar.get_width() / 2, value, f"{value:g}", ha="center", va="bottom", fontsize=8, fontweight="bold")
        return finish(fig)

    if kind in {"conversion_funnel", "growth_funnel", "pipeline_funnel"}:
        stages = _pack_split(payload.get("stages") or payload.get("labels") or "")
        values = _pack_numbers(payload.get("values") or payload.get("stage_values") or "")
        series = _pack_series(payload.get("series", ""))
        if not stages or not values:
            return None
        n = min(len(stages), len(values))
        stages, values = stages[:n], values[:n]
        fig, axes = plt.subplots(1, 2 if series else 1, figsize=(12.0, 4.8))
        if not isinstance(axes, np.ndarray):
            axes = np.array([axes])
        ax = axes[0]
        style_ax(ax)
        y = np.arange(n)
        max_val = max(values) if values else 1
        bars = ax.barh(y, values, color=[PALETTE[i % len(PALETTE)] for i in range(n)], alpha=0.9)
        ax.set_yticks(y)
        ax.set_yticklabels(_wrap_labels(stages, 13), fontsize=8)
        ax.invert_yaxis()
        ax.set_title(payload.get("left_title", "Conversion Funnel"), fontsize=10, fontweight="bold")
        ax.set_xlabel(payload.get("unit", "Users"), fontsize=8)
        for idx, (bar, value) in enumerate(zip(bars, values)):
            rate = value / values[idx - 1] * 100 if idx > 0 and values[idx - 1] else 100
            ax.text(value + max_val * 0.015, bar.get_y() + bar.get_height() / 2, f"{value:g} ({rate:.1f}%)", va="center", fontsize=8, fontweight="bold")
        if series and len(axes) > 1:
            ax2 = axes[1]
            style_ax(ax2)
            x = np.arange(n)
            width = min(0.72 / len(series), 0.28)
            offsets = np.linspace(-(len(series) - 1) * width / 2, (len(series) - 1) * width / 2, len(series))
            for idx, s in enumerate(series[:5]):
                vals = s.values[:n]
                ax2.bar(x + offsets[idx], vals, width=width, label=s.name, color=PALETTE[idx % len(PALETTE)], alpha=0.9)
            ax2.set_xticks(x)
            ax2.set_xticklabels(_wrap_labels(stages, 10), fontsize=7, rotation=15, ha="right")
            ax2.set_title(payload.get("right_title", "Segment Funnel Comparison"), fontsize=10, fontweight="bold")
            ax2.legend(fontsize=7, frameon=True, edgecolor="#DADCE0")
        return finish(fig)

    if kind in {"risk_matrix", "risk_control", "risk_assessment"}:
        risks = _pack_split(payload.get("risks") or payload.get("labels") or "")
        probability = _pack_numbers(payload.get("probability") or payload.get("likelihood") or "")
        impact = _pack_numbers(payload.get("impact") or payload.get("severity") or "")
        categories = _pack_split(payload.get("categories") or "")
        category_values = _pack_numbers(payload.get("category_values") or "")
        if not risks or not probability or not impact:
            return None
        n = min(len(risks), len(probability), len(impact))
        risks, probability, impact = risks[:n], probability[:n], impact[:n]
        fig, axes = plt.subplots(1, 2 if categories and category_values else 1, figsize=(12.0, 4.8))
        if not isinstance(axes, np.ndarray):
            axes = np.array([axes])
        ax = axes[0]
        style_ax(ax)
        exposure = [p * i for p, i in zip(probability, impact)]
        sizes = [max(90, e * 55) for e in exposure]
        scatter = ax.scatter(probability, impact, s=sizes, c=exposure, cmap="YlOrRd", alpha=0.78, edgecolors="white", linewidths=1.0)
        for risk, p_val, i_val in zip(risks, probability, impact):
            ax.text(p_val + 0.04, i_val + 0.04, risk[:18], fontsize=7, color=TEXT)
        ax.set_xlim(0, max(5, max(probability) + 0.8))
        ax.set_ylim(0, max(5, max(impact) + 0.8))
        ax.set_xlabel(payload.get("x_label", "Likelihood"), fontsize=8)
        ax.set_ylabel(payload.get("y_label", "Impact"), fontsize=8)
        ax.set_title(payload.get("left_title", "Risk Matrix"), fontsize=10, fontweight="bold")
        fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04, label=payload.get("color_label", "Exposure"))
        if categories and category_values and len(axes) > 1:
            ax2 = axes[1]
            style_ax(ax2)
            n2 = min(len(categories), len(category_values))
            bars = ax2.barh(np.arange(n2), category_values[:n2], color=[RED, ORANGE, BLUE_DARK, GREEN, PURPLE][:n2], alpha=0.9)
            ax2.set_yticks(np.arange(n2))
            ax2.set_yticklabels(_wrap_labels(categories[:n2], 12), fontsize=8)
            ax2.set_title(payload.get("right_title", "Risk Exposure by Category"), fontsize=10, fontweight="bold")
            for bar, value in zip(bars, category_values[:n2]):
                ax2.text(value, bar.get_y() + bar.get_height() / 2, f" {value:g}", va="center", fontsize=8, fontweight="bold")
        return finish(fig)

    if kind in {"branch_dashboard", "branch_kpi_grid", "multi_branch_kpi", "branch_comparison"}:
        branches = _pack_split(payload.get("branches") or payload.get("labels") or "")
        values = _pack_numbers(payload.get("values") or payload.get("kpi_values") or "")
        kpi_name = payload.get("kpi_name", "KPI")
        try:
            avg_value = float(payload.get("avg_value") or 0)
        except (TypeError, ValueError):
            avg_value = 0.0
        periods = _pack_split(payload.get("periods") or "")
        trend_series = _pack_series(payload.get("trend_series", ""))
        kpi_series = _pack_series(payload.get("kpis", ""))
        if not branches or not values:
            return None
        n = min(len(branches), len(values), 20)
        branches, values = branches[:n], values[:n]
        if not avg_value and values:
            avg_value = float(np.mean(values))

        fig, axes = plt.subplots(2, 2, figsize=(12.8, 7.6))
        ax1, ax2, ax3, ax4 = axes.flatten()
        for ax in (ax1, ax2, ax3):
            style_ax(ax)
        ax4.axis("off")

        # Panel 1: Branch ranking (horizontal bar, sorted ascending so highest is on top)
        order = np.argsort(values)
        y_r = np.arange(n)
        rank_colors = [GREEN if values[i] >= avg_value else BLUE_DARK for i in order]
        bars1 = ax1.barh(y_r, [values[i] for i in order], color=rank_colors, alpha=0.88, height=0.65)
        ax1.set_yticks(y_r)
        ax1.set_yticklabels(_wrap_labels([branches[i] for i in order], 10), fontsize=7)
        ax1.set_title(f"{kpi_name} 分行排名", fontsize=10, fontweight="bold", color=TEXT)
        if avg_value:
            ax1.axvline(avg_value, color=RED, linestyle="--", linewidth=1.2, alpha=0.7, label=f"均值 {avg_value:g}")
            ax1.legend(fontsize=7, frameon=False)
        for bar, val in zip(bars1, [values[i] for i in order]):
            ax1.text(
                val + max(values) * 0.012, bar.get_y() + bar.get_height() / 2,
                f"{val:g}", va="center", fontsize=7, fontweight="bold", color=TEXT,
            )

        # Panel 2: Deviation from average (positive = green, negative = red)
        deviations = [v - avg_value for v in values]
        max_abs = max(abs(d) for d in deviations) if deviations else 1
        dev_colors = [GREEN if d >= 0 else RED for d in deviations]
        ax2.bar(np.arange(n), deviations, color=dev_colors, alpha=0.88, width=0.7)
        ax2.axhline(0, color="#6B7280", linewidth=0.9)
        ax2.set_xticks(np.arange(n))
        ax2.set_xticklabels(_wrap_labels(branches, 8), fontsize=6, rotation=35, ha="right")
        ax2.set_title(f"{kpi_name} 偏差（分行 vs 均值）", fontsize=10, fontweight="bold", color=TEXT)
        for idx, (d, col) in enumerate(zip(deviations, dev_colors)):
            offset = max_abs * 0.04 * (1 if d >= 0 else -1)
            ax2.text(idx, d + offset, f"{d:+.1f}", ha="center", fontsize=6, fontweight="bold", color=col)

        # Panel 3: Trend lines (if time-series provided) OR Top vs Bottom comparison
        if trend_series and periods:
            np_ = len(periods)
            x3 = np.arange(np_)
            for idx, s in enumerate(trend_series[:6]):
                vals = s.values[:np_]
                ax3.plot(
                    x3[:len(vals)], vals,
                    color=PALETTE[idx % len(PALETTE)], linewidth=1.8,
                    marker="o", markersize=3.5, label=s.name[:12],
                )
            ax3.set_xticks(x3)
            ax3.set_xticklabels(_wrap_labels(periods, 10), fontsize=7)
            ax3.set_title(payload.get("trend_title", "分行趋势对比"), fontsize=10, fontweight="bold", color=TEXT)
            ax3.legend(fontsize=6, frameon=True, edgecolor="#DADCE0", ncol=2)
        else:
            top3_idx = sorted(range(n), key=lambda i: values[i], reverse=True)[:3]
            bot3_idx = sorted(range(n), key=lambda i: values[i])[:min(3, n)]
            sel_idx = list(dict.fromkeys(top3_idx + bot3_idx))
            sel_vals = [values[i] for i in sel_idx]
            sel_names = [branches[i] for i in sel_idx]
            sel_colors = [GREEN if values[i] >= avg_value else RED for i in sel_idx]
            bars3 = ax3.bar(np.arange(len(sel_idx)), sel_vals, color=sel_colors, alpha=0.88, width=0.65)
            ax3.set_xticks(np.arange(len(sel_idx)))
            ax3.set_xticklabels(_wrap_labels(sel_names, 9), fontsize=7, rotation=20, ha="right")
            ax3.set_title("头部 vs 尾部分行对比", fontsize=10, fontweight="bold", color=TEXT)
            if avg_value:
                ax3.axhline(avg_value, color=ORANGE, linestyle="--", linewidth=1.0, alpha=0.7)
            for bar, val in zip(bars3, sel_vals):
                ax3.text(
                    bar.get_x() + bar.get_width() / 2, val + max(sel_vals) * 0.015,
                    f"{val:g}", ha="center", fontsize=7.5, fontweight="bold",
                )

        # Panel 4: KPI snapshot cards
        kpi_items = kpi_series[:4]
        if not kpi_items:
            total_val = sum(values)
            kpi_items = [
                ChartSeries(f"合计 {kpi_name}", [total_val]),
                ChartSeries(f"均值 {kpi_name}", [avg_value]),
                ChartSeries("分行数量", [float(n)]),
                ChartSeries(f"最高 {kpi_name}", [max(values)]),
            ]
        ax4.set_title("关键指标快览", fontsize=10, fontweight="bold", color=TEXT, loc="left")
        for idx, item in enumerate(kpi_items[:4]):
            col = idx % 2
            row = idx // 2
            x0 = 0.04 + col * 0.48
            y0 = 0.62 - row * 0.38
            ax4.add_patch(plt.Rectangle(
                (x0, y0), 0.43, 0.25,
                transform=ax4.transAxes, facecolor="#F0F6FF", edgecolor="#C7D8F0", linewidth=0.9,
            ))
            value = item.values[0] if item.values else 0
            ax4.text(x0 + 0.04, y0 + 0.15, f"{value:,.0f}" if abs(value) >= 10 else f"{value:g}",
                     transform=ax4.transAxes, fontsize=14, fontweight="bold", color=BLUE_DARK)
            ax4.text(x0 + 0.04, y0 + 0.055, item.name[:26],
                     transform=ax4.transAxes, fontsize=8, color="#4B5563")
        return finish(fig)

    return None


def _render_academic_figure_pack_plotly(kind: str, payload: dict[str, str]) -> Optional[bytes]:
    """Plotly/Kaleido fallback for academic multi-panel figures."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception:
        return None

    BLUE = "#2F91CF"
    BLUE_DARK = "#0072B2"
    RED = "#FF4D5A"
    PURPLE = "#A64DB3"
    GREEN = "#22B14C"
    ORANGE = "#F28E2B"
    GRAY = "#9CA3AF"
    PALETTE = [GRAY, "#A3D5EC", "#76C6E8", "#8CCB5E", BLUE_DARK, PURPLE, ORANGE, GREEN]

    title = payload.get("title", "")
    layout_common = dict(
        template="plotly_white",
        title=dict(text=title, x=0.5, xanchor="center", font=dict(size=24, color="#202124")),
        font=dict(family="Arial, Helvetica, sans-serif", size=15, color="#202124"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=70, r=40, t=95 if title else 45, b=70),
        legend=dict(bgcolor="rgba(255,255,255,0.82)", bordercolor="#DADCE0", borderwidth=1),
    )

    def finish(fig, width=2600, height=1050):
        fig.update_layout(**layout_common)
        fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB", gridwidth=0.6, zeroline=False, linecolor="#D0D0D0")
        fig.update_yaxes(showgrid=True, gridcolor="#E5E7EB", gridwidth=0.6, zeroline=False, linecolor="#D0D0D0")
        try:
            return fig.to_image(format="png", width=width, height=height, scale=1)
        except Exception as exc:
            logger.debug("Academic Plotly figure render skipped: %s", exc)
            return None

    if kind in {"training_dynamics", "training_validation"}:
        epochs = _pack_numbers(payload.get("epochs") or payload.get("x") or "")
        loss_series = _pack_series(payload.get("loss_series", ""))
        acc_series = _pack_series(payload.get("acc_series", ""))
        if not loss_series:
            lb = _pack_numbers(payload.get("loss_baseline", ""))
            lo = _pack_numbers(payload.get("loss_ours", ""))
            if lb and lo:
                loss_series = [ChartSeries("CNN Baseline", lb), ChartSeries("Ours (ResNet-EEG)", lo)]
        if not acc_series:
            ab = _pack_numbers(payload.get("acc_baseline", ""))
            ao = _pack_numbers(payload.get("acc_ours", ""))
            if ab and ao:
                acc_series = [ChartSeries("CNN Baseline", ab), ChartSeries("Ours (ResNet-EEG)", ao)]
        if not epochs or len(loss_series) < 2 or len(acc_series) < 2:
            return None
        n = min(len(epochs), *(len(s.values) for s in loss_series + acc_series))
        fig = make_subplots(rows=1, cols=2, subplot_titles=(
            payload.get("left_title", "Training Loss"),
            payload.get("right_title", "Validation Accuracy"),
        ))
        styles = [(RED, "dash"), (BLUE, "solid"), (GREEN, "dashdot"), (PURPLE, "dot")]
        for idx, s in enumerate(loss_series[:4]):
            color, dash = styles[idx % len(styles)]
            fig.add_trace(go.Scatter(x=epochs[:n], y=s.values[:n], mode="lines", name=s.name,
                                     line=dict(color=color, dash=dash, width=3)), row=1, col=1)
        for idx, s in enumerate(acc_series[:4]):
            color, dash = styles[idx % len(styles)]
            fig.add_trace(go.Scatter(x=epochs[:n], y=s.values[:n], mode="lines", name=s.name,
                                     line=dict(color=color, dash=dash, width=3)), row=1, col=2)
        if acc_series and n:
            fig.add_hline(y=acc_series[1].values[n - 1], line_dash="dot", line_color=BLUE, opacity=0.45, row=1, col=2)
            fig.add_hline(y=acc_series[0].values[n - 1], line_dash="dot", line_color=RED, opacity=0.45, row=1, col=2)
        fig.update_xaxes(title_text="Epoch", row=1, col=1)
        fig.update_yaxes(title_text=payload.get("loss_unit", "Cross-Entropy Loss"), row=1, col=1)
        fig.update_xaxes(title_text="Epoch", row=1, col=2)
        fig.update_yaxes(title_text=payload.get("acc_unit", "Validation Accuracy (%)"), row=1, col=2)
        return finish(fig, 2600, 1050)

    if kind in {"benchmark_comparison", "cross_dataset"}:
        labels = _pack_split(payload.get("datasets") or payload.get("labels") or "")
        series = _pack_series(payload.get("series", ""))
        if not labels or len(series) < 2:
            return None
        n = min(len(labels), *(len(s.values) for s in series))
        fig = go.Figure()
        for idx, s in enumerate(series):
            is_ours = bool(re.search(r"(ours|resnet|proposed)", s.name, re.I))
            color = BLUE_DARK if is_ours else PALETTE[idx % len(PALETTE)]
            fig.add_trace(go.Bar(
                x=labels[:n],
                y=s.values[:n],
                name=s.name,
                marker_color=color,
                opacity=1.0 if is_ours else 0.72,
                text=[f"{v:.1f}" if is_ours else "" for v in s.values[:n]],
                textposition="outside",
            ))
        fig.update_layout(barmode="group")
        fig.update_xaxes(title_text=payload.get("x_label", "Dataset"))
        fig.update_yaxes(title_text=payload.get("unit", "Classification Accuracy (%)"))
        return finish(fig, 2500, 1100)

    if kind in {"ablation", "ablation_bar"}:
        variants = _pack_split(payload.get("variants", ""))
        values = _pack_numbers(payload.get("ablation_values") or payload.get("values") or "")
        if not variants or not values:
            return None
        n = min(len(variants), len(values))
        colors = [BLUE_DARK] + [PURPLE] * max(0, n - 2) + ([RED] if n > 1 else [])
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=_wrap_labels(variants[:n], 13),
            y=values[:n],
            marker_color=colors[:n],
            text=[f"{v:.1f}" for v in values[:n]],
            textposition="outside",
            showlegend=False,
        ))
        fig.add_hline(y=values[0], line_dash="dash", line_color=BLUE, opacity=0.5)
        if n > 1:
            fig.add_hline(y=values[-1], line_dash="dash", line_color=RED, opacity=0.5)
        fig.update_xaxes(title_text="Variant")
        fig.update_yaxes(title_text=payload.get("unit", "Accuracy (%)"))
        return finish(fig, 2100, 1050)

    if kind in {"ablation_subject", "ablation_subjectwise"}:
        variants = _pack_split(payload.get("variants", ""))
        ablation_values = _pack_numbers(payload.get("ablation_values", ""))
        subjects = _pack_split(payload.get("subjects", ""))
        baseline_values = _pack_numbers(payload.get("baseline_values", ""))
        ours_values = _pack_numbers(payload.get("ours_values", ""))
        if not variants or not ablation_values or not subjects or not baseline_values or not ours_values:
            return None
        n_left = min(len(variants), len(ablation_values))
        n_right = min(len(subjects), len(baseline_values), len(ours_values))
        fig = make_subplots(rows=1, cols=2, subplot_titles=(
            payload.get("left_title", "Ablation Study"),
            payload.get("right_title", "Subject-wise Accuracy"),
        ))
        colors = [BLUE_DARK] + [PURPLE] * max(0, n_left - 2) + ([RED] if n_left > 1 else [])
        fig.add_trace(go.Bar(x=_wrap_labels(variants[:n_left], 13), y=ablation_values[:n_left],
                             marker_color=colors[:n_left], text=[f"{v:.1f}" for v in ablation_values[:n_left]],
                             textposition="outside", showlegend=False), row=1, col=1)
        x = subjects[:n_right]
        fig.add_trace(go.Bar(x=x, y=baseline_values[:n_right], name=payload.get("baseline_name", "CNN Baseline"),
                             marker_color=RED, opacity=0.92), row=1, col=2)
        fig.add_trace(go.Bar(x=x, y=ours_values[:n_right], name=payload.get("ours_name", "Ours"),
                             marker_color=BLUE, opacity=0.92), row=1, col=2)
        fig.add_hline(y=ablation_values[0], line_dash="dash", line_color=BLUE, opacity=0.5, row=1, col=1)
        fig.add_hline(y=ablation_values[n_left - 1], line_dash="dash", line_color=RED, opacity=0.5, row=1, col=1)
        fig.add_hline(y=sum(ours_values[:n_right]) / n_right, line_dash="dash", line_color=BLUE, opacity=0.55, row=1, col=2)
        fig.add_hline(y=sum(baseline_values[:n_right]) / n_right, line_dash="dash", line_color=RED, opacity=0.55, row=1, col=2)
        fig.update_layout(barmode="group")
        fig.update_yaxes(title_text=payload.get("unit", "Accuracy (%)"), row=1, col=1)
        fig.update_yaxes(title_text=payload.get("unit", "Accuracy (%)"), row=1, col=2)
        fig.update_xaxes(title_text="Subject", row=1, col=2)
        return finish(fig, 2600, 1050)

    if kind in {"temporal_frequency", "temporal_band"}:
        times = _pack_numbers(payload.get("times") or payload.get("x") or "")
        series = _pack_series(payload.get("series", ""))
        bands = _pack_split(payload.get("bands", ""))
        importance = _pack_numbers(payload.get("importance", ""))
        if not times or len(series) < 2 or not bands or not importance:
            return None
        n_time = min(len(times), *(len(s.values) for s in series))
        n_band = min(len(bands), len(importance))
        fig = make_subplots(rows=1, cols=2, subplot_titles=(
            payload.get("left_title", "Temporal Decoding Profile"),
            payload.get("right_title", "Frequency Band Importance"),
        ))
        colors = [BLUE_DARK, GREEN, ORANGE, PURPLE, RED, GRAY]
        for idx, s in enumerate(series[:6]):
            fig.add_trace(go.Scatter(x=times[:n_time], y=s.values[:n_time], mode="lines+markers",
                                     name=s.name, line=dict(color=colors[idx % len(colors)], width=3)),
                          row=1, col=1)
        fig.add_trace(go.Bar(x=importance[:n_band], y=bands[:n_band], orientation="h", showlegend=False,
                             marker_color=["#FFB04D", "#6BB7D9", "#A8E052", "#FFC1E2", "#D1D5DB", "#C779C6"][:n_band],
                             text=[f"{v:.2f}" for v in importance[:n_band]], textposition="outside"),
                      row=1, col=2)
        fig.update_xaxes(title_text="Time after cue (s)", row=1, col=1)
        fig.update_yaxes(title_text=payload.get("unit", "Decoding Accuracy (%)"), row=1, col=1)
        fig.update_xaxes(title_text=payload.get("importance_unit", "Relative Feature Importance"), row=1, col=2)
        return finish(fig, 2600, 1050)

    if kind in {"business_overview", "executive_dashboard", "performance_dashboard"}:
        periods = _pack_split(payload.get("periods") or payload.get("labels") or "")
        revenue = _pack_numbers(payload.get("revenue_values") or payload.get("sales_values") or payload.get("values") or "")
        rate_values = _pack_numbers(payload.get("growth_values") or payload.get("margin_values") or payload.get("rate_values") or "")
        categories = _pack_split(payload.get("categories") or payload.get("segments") or "")
        category_values = _pack_numbers(payload.get("category_values") or payload.get("segment_values") or "")
        kpi_series = _pack_series(payload.get("kpis", ""))
        if not periods or not revenue:
            return None
        n = min(len(periods), len(revenue))
        periods, revenue = periods[:n], revenue[:n]
        rate_values = rate_values[:n] if rate_values else []
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                payload.get("left_title", "Revenue Trend"),
                payload.get("right_title", "Segment Contribution"),
                payload.get("bottom_left_title", "Rate / Margin Trend"),
                payload.get("bottom_right_title", "KPI Snapshot"),
            ),
            specs=[[{"secondary_y": bool(rate_values)}, {}], [{}, {}]],
        )
        fig.add_trace(go.Bar(x=periods, y=revenue, name=payload.get("primary_name", "Revenue"),
                             marker_color=BLUE_DARK, text=[f"{v:g}" for v in revenue], textposition="outside"),
                      row=1, col=1, secondary_y=False)
        if rate_values:
            fig.add_trace(go.Scatter(x=periods, y=rate_values, mode="lines+markers",
                                     name=payload.get("rate_name", "Rate"), line=dict(color=ORANGE, width=3)),
                          row=1, col=1, secondary_y=True)
        if categories and category_values:
            n_cat = min(len(categories), len(category_values))
            fig.add_trace(go.Bar(x=category_values[:n_cat], y=categories[:n_cat], orientation="h",
                                 showlegend=False, marker_color=PALETTE[:n_cat],
                                 text=[f"{v:g}" for v in category_values[:n_cat]], textposition="outside"),
                          row=1, col=2)
        if rate_values:
            fig.add_trace(go.Scatter(x=periods, y=rate_values, mode="lines+markers", showlegend=False,
                                     line=dict(color=GREEN, width=3)),
                          row=2, col=1)
        else:
            cumulative = []
            running = 0
            for value in revenue:
                running += value
                cumulative.append(running)
            fig.add_trace(go.Scatter(x=periods, y=cumulative, mode="lines+markers", showlegend=False,
                                     line=dict(color=GREEN, width=3)),
                          row=2, col=1)
        kpis = kpi_series[:4] or [ChartSeries("Total", [sum(revenue)]), ChartSeries("Latest", [revenue[-1]])]
        fig.update_xaxes(visible=False, row=2, col=2)
        fig.update_yaxes(visible=False, row=2, col=2)
        for idx, item in enumerate(kpis[:4]):
            x = 0.58 + (idx % 2) * 0.205
            y = 0.29 - (idx // 2) * 0.18
            fig.add_annotation(
                x=x, y=y, xref="paper", yref="paper", showarrow=False,
                text=f"<b>{item.values[0]:g}</b><br><span style='font-size:12px'>{item.name}</span>",
                align="left",
                bgcolor="#F8FAFC", bordercolor="#D1D5DB", borderwidth=1, borderpad=8,
                font=dict(color="#111827", size=18),
            )
        fig.update_yaxes(title_text=payload.get("unit", "Value"), row=1, col=1)
        if rate_values:
            fig.update_yaxes(title_text=payload.get("rate_unit", "%"), row=1, col=1, secondary_y=True)
            fig.update_yaxes(title_text=payload.get("rate_unit", "%"), row=2, col=1)
        return finish(fig, 2600, 1500)

    if kind in {"financial_bridge", "profit_bridge", "waterfall_bridge"}:
        labels = _pack_split(payload.get("labels") or payload.get("drivers") or "")
        values = _pack_numbers(payload.get("values") or payload.get("driver_values") or "")
        scenarios = _pack_split(payload.get("scenarios") or "")
        scenario_values = _pack_numbers(payload.get("scenario_values") or payload.get("scenario_profits") or "")
        if not labels or not values:
            return None
        n = min(len(labels), len(values))
        labels, values = labels[:n], values[:n]
        two_panel = bool(scenarios and scenario_values)
        fig = make_subplots(rows=1, cols=2 if two_panel else 1, subplot_titles=(
            payload.get("left_title", "Driver Bridge"),
            payload.get("right_title", "Scenario Range"),
        ) if two_panel else (payload.get("left_title", "Driver Bridge"),))
        measure = ["relative"] * n
        if n >= 2:
            measure[0] = "absolute"
            measure[-1] = "total"
        fig.add_trace(go.Waterfall(
            x=labels,
            y=values,
            measure=measure,
            connector={"line": {"color": "#9CA3AF"}},
            increasing={"marker": {"color": GREEN}},
            decreasing={"marker": {"color": RED}},
            totals={"marker": {"color": BLUE_DARK}},
            text=[f"{v:+g}" for v in values],
            textposition="outside",
            name="Bridge",
        ), row=1, col=1)
        if two_panel:
            n2 = min(len(scenarios), len(scenario_values))
            fig.add_trace(go.Bar(
                x=scenarios[:n2],
                y=scenario_values[:n2],
                marker_color=[RED, ORANGE, GREEN, BLUE_DARK][:n2],
                text=[f"{v:g}" for v in scenario_values[:n2]],
                textposition="outside",
                showlegend=False,
            ), row=1, col=2)
        fig.update_yaxes(title_text=payload.get("unit", "Value"), row=1, col=1)
        return finish(fig, 2600 if two_panel else 1800, 1050)

    if kind in {"conversion_funnel", "growth_funnel", "pipeline_funnel"}:
        stages = _pack_split(payload.get("stages") or payload.get("labels") or "")
        values = _pack_numbers(payload.get("values") or payload.get("stage_values") or "")
        series = _pack_series(payload.get("series", ""))
        if not stages or not values:
            return None
        n = min(len(stages), len(values))
        stages, values = stages[:n], values[:n]
        fig = make_subplots(rows=1, cols=2 if series else 1, subplot_titles=(
            payload.get("left_title", "Conversion Funnel"),
            payload.get("right_title", "Segment Funnel Comparison"),
        ) if series else (payload.get("left_title", "Conversion Funnel"),))
        fig.add_trace(go.Funnel(
            y=stages,
            x=values,
            textinfo="value+percent previous",
            marker={"color": PALETTE[:n]},
            name="Funnel",
        ), row=1, col=1)
        if series:
            for idx, s in enumerate(series[:5]):
                fig.add_trace(go.Bar(x=stages, y=s.values[:n], name=s.name,
                                     marker_color=PALETTE[idx % len(PALETTE)], opacity=0.88),
                              row=1, col=2)
            fig.update_layout(barmode="group")
        return finish(fig, 2600 if series else 1600, 1050)

    if kind in {"risk_matrix", "risk_control", "risk_assessment"}:
        risks = _pack_split(payload.get("risks") or payload.get("labels") or "")
        probability = _pack_numbers(payload.get("probability") or payload.get("likelihood") or "")
        impact = _pack_numbers(payload.get("impact") or payload.get("severity") or "")
        categories = _pack_split(payload.get("categories") or "")
        category_values = _pack_numbers(payload.get("category_values") or "")
        if not risks or not probability or not impact:
            return None
        n = min(len(risks), len(probability), len(impact))
        risks, probability, impact = risks[:n], probability[:n], impact[:n]
        two_panel = bool(categories and category_values)
        fig = make_subplots(rows=1, cols=2 if two_panel else 1, subplot_titles=(
            payload.get("left_title", "Risk Matrix"),
            payload.get("right_title", "Risk Exposure by Category"),
        ) if two_panel else (payload.get("left_title", "Risk Matrix"),))
        exposure = [p * i for p, i in zip(probability, impact)]
        fig.add_trace(go.Scatter(
            x=probability,
            y=impact,
            mode="markers+text",
            text=risks,
            textposition="top center",
            marker=dict(size=[max(18, e * 4) for e in exposure], color=exposure, colorscale="YlOrRd", showscale=True),
            name="Risk exposure",
        ), row=1, col=1)
        if two_panel:
            n2 = min(len(categories), len(category_values))
            fig.add_trace(go.Bar(x=category_values[:n2], y=categories[:n2], orientation="h",
                                 marker_color=[RED, ORANGE, BLUE_DARK, GREEN, PURPLE][:n2],
                                 text=[f"{v:g}" for v in category_values[:n2]], textposition="outside",
                                 showlegend=False),
                          row=1, col=2)
        fig.update_xaxes(title_text=payload.get("x_label", "Likelihood"), row=1, col=1)
        fig.update_yaxes(title_text=payload.get("y_label", "Impact"), row=1, col=1)
        return finish(fig, 2600 if two_panel else 1600, 1050)

    if kind in {"branch_dashboard", "branch_kpi_grid", "multi_branch_kpi", "branch_comparison"}:
        branches = _pack_split(payload.get("branches") or payload.get("labels") or "")
        values = _pack_numbers(payload.get("values") or payload.get("kpi_values") or "")
        kpi_name = payload.get("kpi_name", "KPI")
        try:
            avg_value = float(payload.get("avg_value") or 0)
        except (TypeError, ValueError):
            avg_value = 0.0
        trend_series = _pack_series(payload.get("trend_series", ""))
        periods = _pack_split(payload.get("periods") or "")
        kpi_series = _pack_series(payload.get("kpis", ""))
        if not branches or not values:
            return None
        import statistics
        n = min(len(branches), len(values), 20)
        branches, values = branches[:n], values[:n]
        if not avg_value and values:
            avg_value = statistics.mean(values)

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                f"{kpi_name} 分行排名",
                f"{kpi_name} 偏差（分行 vs 均值）",
                payload.get("trend_title", "头部 vs 尾部分行对比"),
                "关键指标快览",
            ),
            specs=[[{}, {}], [{}, {"type": "domain"}]],
        )

        # Panel 1: Horizontal ranking bar (sorted ascending → highest on top in go.Bar horizontal)
        sorted_order = sorted(range(n), key=lambda i: values[i])
        sorted_branches = [branches[i] for i in sorted_order]
        sorted_values = [values[i] for i in sorted_order]
        bar_colors = [GREEN if v >= avg_value else BLUE_DARK for v in sorted_values]
        fig.add_trace(go.Bar(
            x=sorted_values, y=sorted_branches, orientation="h",
            marker_color=bar_colors, name=kpi_name,
            text=[f"{v:g}" for v in sorted_values], textposition="outside",
        ), row=1, col=1)
        fig.add_vline(x=avg_value, line_dash="dash", line_color=RED, line_width=1.5,
                      annotation_text=f"均值 {avg_value:g}", annotation_position="top right",
                      row=1, col=1)

        # Panel 2: Deviation bar
        deviations = [v - avg_value for v in values]
        dev_colors = [GREEN if d >= 0 else RED for d in deviations]
        fig.add_trace(go.Bar(
            x=branches, y=deviations,
            marker_color=dev_colors, name="偏差",
            text=[f"{d:+.1f}" for d in deviations], textposition="outside",
        ), row=1, col=2)
        fig.add_hline(y=0, line_color="#6B7280", line_width=0.8, row=1, col=2)

        # Panel 3: Top/bottom comparison or trend lines
        if trend_series and periods:
            for idx, s in enumerate(trend_series[:5]):
                fig.add_trace(go.Scatter(
                    x=periods[:len(s.values)], y=s.values[:len(periods)],
                    mode="lines+markers", name=s.name,
                    line=dict(color=PALETTE[idx % len(PALETTE)], width=2),
                ), row=2, col=1)
        else:
            top3 = sorted(range(n), key=lambda i: values[i], reverse=True)[:3]
            bot3 = sorted(range(n), key=lambda i: values[i])[:min(3, n)]
            sel_idx = list(dict.fromkeys(top3 + bot3))
            sel_vals = [values[i] for i in sel_idx]
            sel_names = [branches[i] for i in sel_idx]
            sel_colors = [GREEN if values[i] >= avg_value else RED for i in sel_idx]
            fig.add_trace(go.Bar(
                x=sel_names, y=sel_vals,
                marker_color=sel_colors, name="分行对比",
                text=[f"{v:g}" for v in sel_vals], textposition="outside",
            ), row=2, col=1)
            fig.add_hline(y=avg_value, line_dash="dash", line_color=ORANGE, line_width=1.0, row=2, col=1)

        # Panel 4: KPI cards via annotations (domain subplot is blank)
        kpi_items = kpi_series[:4]
        if not kpi_items:
            total_val = sum(values)
            kpi_items = [
                ChartSeries(f"合计 {kpi_name}", [total_val]),
                ChartSeries(f"均值 {kpi_name}", [avg_value]),
                ChartSeries("分行数量", [float(n)]),
                ChartSeries(f"最高 {kpi_name}", [max(values)]),
            ]
        card_positions = [(0.575, 0.24), (0.785, 0.24), (0.575, 0.06), (0.785, 0.06)]
        for idx, (item, (xp, yp)) in enumerate(zip(kpi_items[:4], card_positions)):
            value = item.values[0] if item.values else 0
            fig.add_annotation(
                x=xp, y=yp, xref="paper", yref="paper", showarrow=False,
                text=(
                    f"<b style='font-size:20px'>{value:,.0f}</b><br>"
                    f"<span style='font-size:11px;color:#4B5563'>{item.name[:22]}</span>"
                ),
                align="left", bgcolor="#F0F6FF", bordercolor="#C7D8F0",
                borderwidth=1, borderpad=10, font=dict(color=BLUE_DARK, size=14),
            )

        return finish(fig, 2600, 1500)

    return None


def _apply_pil_polish(png_bytes: bytes, *, shadow: bool = True) -> bytes:
    """Post-process a chart PNG with drop-shadow and subtle rounded border via PIL."""
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError:
        return png_bytes

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    if not shadow:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    # Add padding for shadow
    pad = 16
    w, h = img.size
    shadowed = Image.new("RGBA", (w + pad * 2, h + pad * 2), (248, 250, 252, 255))
    # Shadow layer
    shadow_layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    shadow_base = Image.new("RGBA", (w, h), (0, 0, 0, 60))
    shadow_layer.paste(shadow_base, (pad + 4, pad + 4))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=8))
    shadowed = Image.alpha_composite(shadowed, shadow_layer)
    shadowed.paste(img, (pad, pad))
    buf = io.BytesIO()
    shadowed.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Plotly renderer
# ---------------------------------------------------------------------------

def _render_with_plotly(spec: ChartSpec, *, width: int, height: int) -> bytes:
    import plotly.graph_objects as go

    palette = spec.effective_palette()
    _font_family = CHART_FONT_STACK

    fig = go.Figure()

    # ── Pie / Donut ──
    if spec.chart_type in {"pie", "donut"}:
        fig.add_trace(go.Pie(
            labels=spec.labels,
            values=spec.primary_values,
            hole=0.48 if spec.chart_type == "donut" else 0,
            textinfo="label+percent",
            texttemplate="%{label}<br>%{percent:.1%}",
            marker={"colors": palette[:len(spec.labels)], "line": {"color": "#fff", "width": 2}},
            sort=False,
            pull=[0.04 if i == 0 else 0 for i in range(len(spec.labels))],
        ))

    # ── Waterfall ──
    elif spec.chart_type == "waterfall":
        vals = spec.primary_values
        measures = ["relative"] * len(vals)
        fig.add_trace(go.Waterfall(
            x=spec.labels, y=vals, measure=measures,
            connector={"line": {"color": "#E5E7EB", "width": 1}},
            increasing={"marker": {"color": palette[1]}},
            decreasing={"marker": {"color": palette[3] if len(palette) > 3 else "#EF4444"}},
            totals={"marker": {"color": palette[0]}},
            text=[f"{v:+.1f}" for v in vals],
            textposition="outside",
        ))

    # ── Heatmap ──
    elif spec.chart_type == "heatmap":
        z = [s.values for s in spec.series]
        fig.add_trace(go.Heatmap(
            z=z,
            x=spec.labels,
            y=[s.name for s in spec.series],
            colorscale="Blues",
            text=[[f"{v:.1f}" for v in row] for row in z],
            texttemplate="%{text}",
            showscale=True,
        ))

    # ── Radar ──
    elif spec.chart_type == "radar":
        for idx, s in enumerate(spec.series[:6]):
            vals_closed = s.values + [s.values[0]]
            labels_closed = spec.labels + [spec.labels[0]]
            fig.add_trace(go.Scatterpolar(
                r=vals_closed, theta=labels_closed, fill="toself",
                name=s.name,
                line={"color": palette[idx % len(palette)], "width": 2.5},
                fillcolor=_hex_to_rgba(palette[idx % len(palette)], 0.15),
            ))
        fig.update_layout(polar={"radialaxis": {"visible": True, "gridcolor": "#E5E7EB"}})

    # ── Combo (bar + line) ──
    elif spec.chart_type == "combo":
        for idx, s in enumerate(spec.series[:6]):
            is_rate = _looks_like_rate(s.name) and idx > 0
            if idx == 0 or not is_rate:
                fig.add_trace(go.Bar(
                    x=spec.labels, y=s.values, name=s.name,
                    text=[f"{v:g}" for v in s.values], textposition="outside",
                    marker_color=palette[idx % len(palette)],
                    yaxis="y",
                ))
            else:
                fig.add_trace(go.Scatter(
                    x=spec.labels, y=s.values, name=s.name,
                    mode="lines+markers+text",
                    text=[f"{v:g}" for v in s.values], textposition="top center",
                    line={"width": 3, "color": palette[idx % len(palette)]},
                    marker={"size": 8},
                    yaxis="y2",
                ))
        fig.update_layout(
            yaxis={"title": spec.unit, "showgrid": True, "gridcolor": "#F3F4F6"},
            yaxis2={"title": spec.secondary_unit or "%", "overlaying": "y", "side": "right", "showgrid": False},
        )

    # ── Stacked bar ──
    elif spec.chart_type == "stacked_bar":
        horiz = spec.orientation == "horizontal"
        for idx, s in enumerate(spec.series[:8]):
            fig.add_trace(go.Bar(
                x=s.values if horiz else spec.labels,
                y=spec.labels if horiz else s.values,
                name=s.name,
                orientation="h" if horiz else "v",
                marker_color=palette[idx % len(palette)],
            ))
        fig.update_layout(barmode="stack")

    # ── Line / Area ──
    elif spec.chart_type in {"line", "area", "stacked_area"}:
        for idx, s in enumerate(spec.series[:8]):
            fill_mode = "tonexty" if spec.chart_type == "stacked_area" and idx > 0 else \
                        ("tozeroy" if spec.chart_type in {"area", "stacked_area"} else "none")
            fig.add_trace(go.Scatter(
                x=spec.labels, y=s.values, name=s.name,
                mode="lines+markers",
                line={"width": 3, "color": palette[idx % len(palette)]},
                marker={"size": 8, "symbol": ["circle", "square", "diamond", "triangle-up"][idx % 4]},
                fill=fill_mode,
                fillcolor=_hex_to_rgba(palette[idx % len(palette)], 0.18),
            ))

    # ── Scatter ──
    elif spec.chart_type == "scatter":
        for idx, s in enumerate(spec.series[:6]):
            fig.add_trace(go.Scatter(
                x=list(range(len(s.values))), y=s.values, name=s.name,
                mode="markers",
                marker={"size": 12, "color": palette[idx % len(palette)], "opacity": 0.8,
                        "line": {"width": 1, "color": "#fff"}},
            ))

    # ── Funnel ──
    elif spec.chart_type == "funnel":
        fig.add_trace(go.Funnel(
            y=spec.labels,
            x=spec.primary_values,
            textinfo="value+percent initial",
            textfont={"family": _font_family, "size": 13},
            marker={"color": palette[:len(spec.labels)],
                    "line": {"width": 2, "color": "white"}},
            connector={"line": {"color": "#E5E7EB", "width": 2, "dash": "dot"}},
        ))
        fig.update_layout(showlegend=False)

    # ── Gauge ──
    elif spec.chart_type == "gauge":
        value = spec.primary_values[0] if spec.primary_values else 0
        min_val = spec.extra.get("min", 0)
        max_val = spec.extra.get("max", 100)
        fig.add_trace(go.Indicator(
            mode="gauge+number+delta",
            value=value,
            number={"suffix": f" {spec.unit}" if spec.unit else "", "font": {"size": 40, "family": _font_family}},
            title={"text": spec.series[0].name if spec.series else spec.title, "font": {"size": 16, "family": _font_family}},
            gauge={
                "axis": {"range": [min_val, max_val], "tickwidth": 1, "tickcolor": "#374151"},
                "bar": {"color": palette[0], "thickness": 0.3},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "#E5E7EB",
                "steps": [
                    {"range": [min_val, (max_val - min_val) * 0.5 + min_val], "color": "#EFF6FF"},
                    {"range": [(max_val - min_val) * 0.5 + min_val, (max_val - min_val) * 0.8 + min_val], "color": "#DBEAFE"},
                    {"range": [(max_val - min_val) * 0.8 + min_val, max_val], "color": "#BFDBFE"},
                ],
                "threshold": {"line": {"color": "#EF4444", "width": 4}, "thickness": 0.75, "value": max_val * 0.9},
            },
            domain={"x": [0.1, 0.9], "y": [0.1, 0.9]},
        ))
        fig.update_layout(paper_bgcolor="white", margin={"l": 40, "r": 40, "t": 100, "b": 40})

    # ── Treemap ──
    elif spec.chart_type == "treemap":
        tree_data = spec.extra.get("tree")
        if tree_data:
            # Flatten tree for Plotly
            labels_flat, parents_flat, values_flat = [], [], []
            def _flatten(nodes, parent=""):
                for node in nodes:
                    labels_flat.append(node["name"])
                    parents_flat.append(parent)
                    values_flat.append(node.get("value", 0))
                    if node.get("children"):
                        _flatten(node["children"], node["name"])
            _flatten(tree_data)
            fig.add_trace(go.Treemap(
                labels=labels_flat, parents=parents_flat, values=values_flat,
                texttemplate="<b>%{label}</b><br>%{value}",
                marker={"colorscale": "Blues"},
            ))
        else:
            fig.add_trace(go.Treemap(
                labels=spec.labels, parents=[""] * len(spec.labels),
                values=spec.primary_values,
                texttemplate="<b>%{label}</b><br>%{value}" + (f" {spec.unit}" if spec.unit else ""),
                marker={"colors": palette[:len(spec.labels)]},
            ))
        fig.update_layout(margin={"l": 10, "r": 10, "t": 80, "b": 10})

    # ── Sankey ──
    elif spec.chart_type == "sankey":
        nodes = spec.extra.get("nodes", [{"name": lbl} for lbl in spec.labels])
        links = spec.extra.get("links", [])
        node_labels = [n["name"] for n in nodes]
        name_to_idx = {n: i for i, n in enumerate(node_labels)}
        fig.add_trace(go.Sankey(
            node={"pad": 15, "thickness": 20, "line": {"color": "#E5E7EB", "width": 0.5},
                  "label": node_labels, "color": palette[:len(node_labels)]},
            link={
                "source": [name_to_idx.get(str(lk.get("source", "")), 0) for lk in links],
                "target": [name_to_idx.get(str(lk.get("target", "")), 0) for lk in links],
                "value":  [lk.get("value", 1) for lk in links],
                "color": ["rgba(37,99,235,0.3)"] * len(links),
            },
            textfont={"family": _font_family, "size": 12},
        ))
        fig.update_layout(margin={"l": 20, "r": 20, "t": 80, "b": 20})

    # ── Boxplot ──
    elif spec.chart_type == "boxplot":
        for idx, s in enumerate(spec.series[:8]):
            if len(s.values) >= 5:
                q_min, q1, med, q3, q_max = s.values[:5]
                fig.add_trace(go.Box(
                    name=s.name,
                    q1=[q1], median=[med], q3=[q3],
                    lowerfence=[q_min], upperfence=[q_max],
                    marker_color=palette[idx % len(palette)],
                    boxmean=True,
                ))
            elif len(s.values) >= 3:
                fig.add_trace(go.Box(
                    y=s.values, name=s.name,
                    marker_color=palette[idx % len(palette)],
                    boxmean=True, boxpoints="outliers",
                ))
        fig.update_layout(boxmode="group")

    # ── Stock performance (normalized dual-line) ──────────────────────────────
    elif spec.chart_type == "stock_performance":
        # extra: {"benchmark_name": "上证指数"} optional
        benchmark_name = spec.extra.get("benchmark_name", "指数")
        for idx, s in enumerate(spec.series[:2]):
            color = palette[idx % len(palette)]
            dash = "solid" if idx == 0 else "dot"
            fig.add_trace(go.Scatter(
                x=spec.labels, y=s.values, name=s.name,
                mode="lines",
                line={"color": color, "width": 2.5 if idx == 0 else 1.8, "dash": dash},
                fill="tozeroy" if idx == 0 else None,
                fillcolor=f"rgba({int(color[1:3], 16)},{int(color[3:5], 16)},{int(color[5:7], 16)},0.07)" if idx == 0 else None,
            ))
        # Zero reference line
        fig.add_hline(y=100, line_width=1, line_dash="dash", line_color="#9CA3AF",
                      annotation_text="基准（100）", annotation_position="right")
        fig.update_yaxes(title_text="归一化价格（基准=100）")
        fig.update_xaxes(title_text="日期")

    # ── Valuation band (PE/PB historical range) ───────────────────────────────
    elif spec.chart_type == "valuation_band":
        # extra: {"bands": [min, p25, mean, p75, max], "current": float, "metric": "PE"}
        metric = spec.extra.get("metric", "PE")
        bands = spec.extra.get("bands")
        current_val = spec.extra.get("current")
        if bands and len(bands) >= 5 and spec.series:
            # Plot historical metric line
            for idx, s in enumerate(spec.series[:1]):
                fig.add_trace(go.Scatter(
                    x=spec.labels, y=s.values, name=metric,
                    mode="lines", line={"color": palette[0], "width": 2},
                ))
            # Add band fills
            band_colors = ["rgba(239,68,68,0.08)", "rgba(234,179,8,0.08)",
                           "rgba(34,197,94,0.08)", "rgba(234,179,8,0.08)"]
            band_names = ["最低值", "25%分位", "均值", "75%分位", "最高值"]
            for i in range(min(4, len(bands) - 1)):
                fig.add_hrect(y0=bands[i], y1=bands[i + 1],
                              fillcolor=band_colors[i % len(band_colors)],
                              line_width=0, opacity=1)
            for i, (bval, bname) in enumerate(zip(bands, band_names)):
                fig.add_hline(y=bval, line_width=1, line_dash="dash",
                              line_color="#D1D5DB",
                              annotation_text=f"{bname}: {bval:.1f}x",
                              annotation_position="right")
            if current_val is not None:
                fig.add_hline(y=current_val, line_width=2, line_color="#EF4444",
                              annotation_text=f"当前: {current_val:.1f}x",
                              annotation_position="right",
                              annotation_font_color="#EF4444")
        elif spec.series:
            # Fallback: simple line chart
            for idx, s in enumerate(spec.series[:3]):
                fig.add_trace(go.Scatter(x=spec.labels, y=s.values, name=s.name,
                                         mode="lines", line={"color": palette[idx]}))
        fig.update_yaxes(title_text=f"{metric} (x)")

    # ── Scenario waterfall (probability-weighted target price) ────────────────
    elif spec.chart_type == "scenario_waterfall":
        # extra: {"scenarios": [...], "probabilities": [...]}
        # series[0].values = net profits per scenario
        scenarios = spec.extra.get("scenarios", spec.labels or ["悲观", "基准", "乐观"])
        probs = spec.extra.get("probabilities", [0.25, 0.50, 0.25])
        values = spec.series[0].values if spec.series else []
        scenario_colors = ["#EF4444", "#F59E0B", "#10B981"]  # red, amber, green
        if values:
            bar_colors = [scenario_colors[i % 3] for i in range(len(values))]
            fig.add_trace(go.Bar(
                x=scenarios[:len(values)], y=values,
                text=[f"{v:,.0f}亿<br>({p*100:.0f}%概率)" for v, p in
                      zip(values, probs[:len(values)])],
                textposition="outside",
                marker_color=bar_colors,
            ))
            # Weighted average line
            if len(values) == len(probs):
                weighted = sum(v * p for v, p in zip(values, probs))
                fig.add_hline(y=weighted, line_width=2, line_dash="dash",
                              line_color="#6B7280",
                              annotation_text=f"概率加权均值: {weighted:,.0f}亿",
                              annotation_position="right")
        fig.update_yaxes(title_text=spec.unit or "净利润（亿元）")

    # ── Default bar ──
    else:
        is_single = len(spec.series) == 1
        for idx, s in enumerate(spec.series[:8]):
            # Single-series: distinct colour per category for visual clarity
            bar_colors = [palette[ci % len(palette)] for ci in range(len(s.values))] if is_single else palette[idx % len(palette)]
            if spec.orientation == "horizontal":
                fig.add_trace(go.Bar(
                    y=spec.labels, x=s.values, name=s.name,
                    orientation="h",
                    text=[f"{v:g}" for v in s.values], textposition="outside",
                    marker_color=bar_colors,
                ))
            else:
                fig.add_trace(go.Bar(
                    x=spec.labels, y=s.values, name=s.name,
                    text=[f"{v:g}" for v in s.values], textposition="outside",
                    marker_color=bar_colors,
                ))

    fig.update_layout(
        title={"text": spec.title, "x": 0.02, "xanchor": "left",
               "font": {"size": 22, "color": "#111827", "family": _font_family}},
        width=width, height=height,
        paper_bgcolor="white", plot_bgcolor="white",
        margin={"l": 80, "r": 60, "t": 90, "b": 100},
        font={"family": _font_family, "size": 13, "color": "#374151"},
        legend={"orientation": "h", "y": -0.20, "x": 0.5, "xanchor": "center",
                "title_text": "", "bgcolor": "rgba(255,255,255,0.9)",
                "bordercolor": "#E5E7EB", "borderwidth": 1},
        bargap=0.30,
        colorway=palette,
    )
    fig.update_xaxes(showgrid=False, zeroline=False,
                     linecolor="#E5E7EB", tickfont={"size": 12, "family": _font_family})
    fig.update_yaxes(showgrid=True, gridcolor="#F3F4F6", gridwidth=1, zeroline=False,
                     linecolor="#E5E7EB", tickfont={"size": 12, "family": _font_family})
    png_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    return _apply_pil_polish(png_bytes)


# ---------------------------------------------------------------------------
# Matplotlib renderer (fallback)
# ---------------------------------------------------------------------------

def _render_with_matplotlib(spec: ChartSpec, *, width: int, height: int) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    _configure_matplotlib_fonts()
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    palette = spec.effective_palette()
    fig_w, fig_h = width / 150, height / 150
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FAFAFA")

    ct = spec.chart_type

    # ── Heatmap ──
    if ct == "heatmap":
        z = np.array([[v for v in s.values] for s in spec.series], dtype=float)
        im = ax.imshow(z, cmap="Blues", aspect="auto")
        ax.set_xticks(range(len(spec.labels)))
        ax.set_xticklabels(spec.labels, rotation=30, ha="right", fontsize=10)
        ax.set_yticks(range(len(spec.series)))
        ax.set_yticklabels([s.name for s in spec.series], fontsize=10)
        for yi in range(z.shape[0]):
            for xi in range(z.shape[1]):
                ax.text(xi, yi, f"{z[yi, xi]:.1f}", ha="center", va="center", fontsize=9, color="#111827")
        fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)

    # ── Radar ──
    elif ct == "radar":
        n = len(spec.labels)
        angles = [n_i / float(n) * 2 * 3.14159 for n_i in range(n)]
        angles += angles[:1]
        ax.remove()
        ax = fig.add_subplot(111, polar=True)
        ax.set_facecolor("#FAFAFA")
        for idx, s in enumerate(spec.series[:6]):
            vals = s.values + [s.values[0]] if s.values else []
            color = palette[idx % len(palette)]
            ax.plot(angles, vals, color=color, linewidth=2.5, label=s.name)
            ax.fill(angles, vals, color=color, alpha=0.12)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(spec.labels, fontsize=10)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), frameon=False, fontsize=10)

    # ── Waterfall ──
    elif ct == "waterfall":
        vals = spec.primary_values
        cumulative, bottoms = 0.0, []
        bar_colors = []
        for v in vals:
            bottoms.append(cumulative if v >= 0 else cumulative + v)
            bar_colors.append(palette[1] if v >= 0 else (palette[3] if len(palette) > 3 else "#EF4444"))
            cumulative += v
        x = range(len(vals))
        ax.bar(x, [abs(v) for v in vals], bottom=bottoms, color=bar_colors, width=0.55, edgecolor="white")
        ax.set_xticks(list(x))
        ax.set_xticklabels(spec.labels, rotation=20, ha="right", fontsize=10)
        for xi, (v, bot) in enumerate(zip(vals, bottoms)):
            ax.text(xi, bot + abs(v) + 0.5, f"{v:+.1f}", ha="center", va="bottom", fontsize=9)

    # ── Stacked bar ──
    elif ct == "stacked_bar":
        x = range(len(spec.labels))
        bottoms_arr = [0.0] * len(spec.labels)
        for idx, s in enumerate(spec.series[:8]):
            ax.bar(x, s.values, bottom=bottoms_arr, label=s.name,
                   color=palette[idx % len(palette)], width=0.55, edgecolor="white")
            bottoms_arr = [b + v for b, v in zip(bottoms_arr, s.values)]
        ax.set_xticks(list(x))
        ax.set_xticklabels(spec.labels, rotation=20, ha="right", fontsize=10)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=min(len(spec.series), 4), frameon=False, fontsize=10)

    # ── Area / Stacked area ──
    elif ct in {"area", "stacked_area"}:
        is_stacked = ct == "stacked_area"
        base_arr = [0.0] * len(spec.labels)
        x_idx = range(len(spec.labels))
        for idx, s in enumerate(spec.series[:8]):
            color = palette[idx % len(palette)]
            top_arr = [b + v for b, v in zip(base_arr, s.values)] if is_stacked else s.values
            ax.fill_between(list(x_idx), base_arr if is_stacked else [0]*len(s.values),
                            top_arr, alpha=0.35, color=color, label=s.name)
            ax.plot(list(x_idx), top_arr, color=color, linewidth=2.5)
            if is_stacked:
                base_arr = top_arr
        ax.set_xticks(list(x_idx))
        ax.set_xticklabels(spec.labels, rotation=20, ha="right", fontsize=10)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=min(len(spec.series), 4), frameon=False, fontsize=10)

    # ── Combo ──
    elif ct == "combo":
        x = list(range(len(spec.labels)))
        ax.bar(x, spec.series[0].values, width=0.52, color=palette[0], label=spec.series[0].name)
        for xi, v in zip(x, spec.series[0].values):
            ax.text(xi, v, f"{v:g}", ha="center", va="bottom", fontsize=9)
        ax2 = ax.twinx()
        for idx, s in enumerate(spec.series[1:5], start=1):
            target = ax2 if _looks_like_rate(s.name) else ax
            target.plot(x, s.values, marker="o", linewidth=2.5, label=s.name, color=palette[idx % len(palette)])
            for xi, v in zip(x, s.values):
                target.text(xi, v, f"{v:g}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(spec.labels, rotation=18, ha="right", fontsize=10)
        ax2.set_ylabel(spec.secondary_unit or "%", fontsize=11)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.18),
                  ncol=min(len(spec.series), 3), frameon=False, fontsize=10)

    # ── Line ──
    elif ct == "line":
        symbols = ["o", "s", "D", "^", "v", "P"]
        for idx, s in enumerate(spec.series[:8]):
            ax.plot(spec.labels, s.values, marker=symbols[idx % len(symbols)],
                    linewidth=2.5, label=s.name, color=palette[idx % len(palette)])
            for x, y in zip(spec.labels, s.values):
                ax.text(x, y, f"{y:g}", ha="center", va="bottom", fontsize=8.5)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16),
                  ncol=min(len(spec.series), 3), frameon=False, fontsize=10)

    # ── Pie / Donut ──
    elif ct in {"pie", "donut"}:
        wedge_kwargs = {"linewidth": 1.5, "edgecolor": "white"}
        wedges, _, autotexts = ax.pie(
            spec.primary_values, labels=spec.labels, autopct="%1.0f%%",
            startangle=90, colors=palette[:len(spec.labels)],
            wedgeprops=wedge_kwargs,
            textprops={"fontsize": 10, "color": "#374151"},
            pctdistance=0.82 if ct == "donut" else 0.75,
            explode=[0.04] + [0] * (len(spec.primary_values) - 1),
        )
        if ct == "donut":
            ax.add_artist(plt.Circle((0, 0), 0.54, fc="white"))
        for t in autotexts:
            t.set_color("#111827")
            t.set_fontweight("bold")
        ax.axis("equal")

    # ── Horizontal bar ──
    elif spec.orientation == "horizontal":
        y_pos = range(len(spec.labels))
        vals = spec.primary_values
        bar_colors = [palette[i % len(palette)] for i in range(len(vals))]
        ax.barh(y_pos, vals, color=bar_colors, height=0.58)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(spec.labels, fontsize=10)
        ax.invert_yaxis()
        limit = max(vals) if vals else 1
        ax.set_xlim(0, limit * 1.22)
        for yi, v in zip(y_pos, vals):
            ax.text(v + limit * 0.01, yi, f"{v:g}", va="center", fontsize=9)

    # ── Funnel (Matplotlib) ──
    elif ct == "funnel":
        vals = spec.primary_values
        max_v = max(vals) if vals else 1
        for yi, (lbl, v) in enumerate(zip(reversed(spec.labels), reversed(vals))):
            width = v / max_v
            color = palette[yi % len(palette)]
            rect = plt.Rectangle((0.5 - width / 2, yi - 0.28), width, 0.56,
                                  color=color, ec="white", lw=1.5, zorder=2)
            ax.add_patch(rect)
            ax.text(0.5, yi, f"{lbl}: {v:g}" + (f" {spec.unit}" if spec.unit else ""),
                    ha="center", va="center", fontsize=10, color="white", fontweight="bold", zorder=3)
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.5, len(vals) - 0.5)
        ax.axis("off")

    # ── Gauge (Matplotlib — arc gauge) ──
    elif ct == "gauge":
        import numpy as _np
        value = spec.primary_values[0] if spec.primary_values else 0
        min_val = spec.extra.get("min", 0)
        max_val = spec.extra.get("max", 100)
        ax.remove()
        ax = fig.add_subplot(111)
        ax.set_facecolor("white")
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-0.2, 1.1)
        ax.axis("off")
        theta = _np.linspace(_np.pi, 0, 200)
        r_out, r_in = 1.0, 0.7
        ax.fill_between(_np.cos(theta), r_in * _np.sin(theta), r_out * _np.sin(theta),
                        color="#E5E7EB", alpha=0.8)
        ratio = min(max((value - min_val) / max(max_val - min_val, 1), 0), 1)
        theta_val = _np.linspace(_np.pi, _np.pi * (1 - ratio), 200)
        ax.fill_between(_np.cos(theta_val), r_in * _np.sin(theta_val), r_out * _np.sin(theta_val),
                        color=palette[0], alpha=0.9)
        angle = _np.pi * (1 - ratio)
        ax.annotate("", xy=(0.75 * _np.cos(angle), 0.75 * _np.sin(angle)), xytext=(0, 0),
                    arrowprops={"arrowstyle": "->", "color": "#111827", "lw": 2.5})
        ax.text(0, -0.12, f"{value:g}{' ' + spec.unit if spec.unit else ''}",
                ha="center", va="center", fontsize=22, fontweight="bold", color="#111827")
        ax.text(0, -0.22, spec.series[0].name if spec.series else spec.title,
                ha="center", fontsize=11, color="#6B7280")

    # ── Treemap (Matplotlib) ──
    elif ct == "treemap":
        try:
            import squarify
            vals = spec.primary_values
            normed = squarify.normalize_sizes(vals, fig_w * 150, fig_h * 150)
            rects = squarify.squarify(normed, 0, 0, fig_w * 150, fig_h * 150)
            ax.set_xlim(0, fig_w * 150)
            ax.set_ylim(0, fig_h * 150)
            ax.axis("off")
            for i, (rect, lbl, v) in enumerate(zip(rects, spec.labels, vals)):
                color = palette[i % len(palette)]
                patch = plt.Rectangle((rect["x"], rect["y"]), rect["dx"], rect["dy"],
                                      color=color, ec="white", lw=2)
                ax.add_patch(patch)
                cx, cy = rect["x"] + rect["dx"] / 2, rect["y"] + rect["dy"] / 2
                ax.text(cx, cy, f"{lbl}\n{v:g}", ha="center", va="center",
                        fontsize=9, color="white", fontweight="bold")
        except ImportError:
            ax.barh(range(len(spec.labels)), spec.primary_values,
                    color=[palette[i % len(palette)] for i in range(len(spec.labels))])
            ax.set_yticks(range(len(spec.labels)))
            ax.set_yticklabels(spec.labels, fontsize=10)

    # ── Sankey (Matplotlib) ──
    elif ct == "sankey":
        from matplotlib.sankey import Sankey as _Sankey
        links = spec.extra.get("links", [])
        if links:
            sankey_obj = _Sankey(ax=ax, scale=0.01, offset=0.2, head_angle=180,
                                  unit=spec.unit or None)
            flows = [lk.get("value", 1) for lk in links[:8]]
            sankey_obj.add(flows=flows, labels=[lk.get("source", "") for lk in links[:8]],
                           orientations=[0] * len(flows))
            sankey_obj.finish()
        else:
            ax.text(0.5, 0.5, "Sankey 图需要 nodes/links 数据", ha="center", va="center",
                    fontsize=12, color="#6B7280", transform=ax.transAxes)
        ax.axis("off")

    # ── Boxplot (Matplotlib) ──
    elif ct == "boxplot":
        box_data_mpl: list = []
        tick_labels: list[str] = []
        for s in spec.series[:8]:
            if len(s.values) >= 5:
                q_min, q1, med, q3, q_max = s.values[:5]
                box_data_mpl.append({"med": med, "q1": q1, "q3": q3,
                                     "whislo": q_min, "whishi": q_max, "fliers": []})
                tick_labels.append(s.name)
            elif len(s.values) >= 3:
                box_data_mpl.append(list(s.values))
                tick_labels.append(s.name)
        if box_data_mpl:
            if isinstance(box_data_mpl[0], dict):
                ax.bxp(box_data_mpl, showfliers=False, patch_artist=True,
                       boxprops={"facecolor": palette[0] + "60", "edgecolor": palette[0]},
                       medianprops={"color": palette[0], "linewidth": 2.5},
                       whiskerprops={"color": palette[0]}, capprops={"color": palette[0]})
            else:
                ax.boxplot(box_data_mpl, patch_artist=True, labels=tick_labels,
                           boxprops={"facecolor": palette[0] + "60"},
                           medianprops={"color": "#EF4444", "linewidth": 2})
            ax.set_xticklabels(tick_labels, fontsize=10)

    # ── Default bar ──
    else:
        x = list(range(len(spec.labels)))
        n_series = max(len(spec.series), 1)
        is_single_mpl = n_series == 1
        bar_w = min(0.72 / n_series, 0.32)
        for idx, s in enumerate(spec.series[:8]):
            offset = (idx - (n_series - 1) / 2) * bar_w
            # Single series: each category gets a distinct colour
            if is_single_mpl:
                bar_color = [palette[ci % len(palette)] for ci in range(len(s.values))]
            else:
                bar_color = palette[idx % len(palette)]
            bars = ax.bar([n + offset for n in x], s.values, width=bar_w,
                          color=bar_color, label=s.name, edgecolor="white")
            for bar, v in zip(bars, s.values):
                ax.text(bar.get_x() + bar.get_width() / 2, v, f"{v:g}",
                        ha="center", va="bottom", fontsize=8.5)
        ax.set_xticks(x)
        ax.set_xticklabels(spec.labels, rotation=18, ha="right", fontsize=10)
        if n_series > 1:
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18),
                      ncol=min(n_series, 3), frameon=False, fontsize=10)

    # ── Common styling for non-polar axes ──
    if ct not in {"pie", "donut", "radar", "funnel", "gauge", "treemap", "sankey"}:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#E5E7EB")
        ax.spines["bottom"].set_color("#E5E7EB")
        ax.grid(axis="y" if spec.orientation != "horizontal" else "x",
                color="#E5E7EB", linewidth=0.7, linestyle="--")
        ax.set_axisbelow(True)
        if spec.unit:
            ax.set_ylabel(spec.unit, fontsize=11)

    ax.set_title(spec.title, fontsize=14, fontweight="bold", color="#111827", loc="left", pad=14)
    plt.tight_layout(pad=1.0)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return _apply_pil_polish(buf.read())
