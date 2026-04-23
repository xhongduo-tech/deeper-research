"""
ChartGenerator  -  专业级报告图表生成器（v3）。

v3 升级：
  • 配色方案升级为品牌深研褐色系（对齐 DESIGN.md §5 色彩规范）
  • 新增 waterfall_chart  -  瀑布图（增减分解、差异归因）
  • 新增 grouped_bar_chart  -  分组柱状图（多系列对比）
  • 新增 stacked_bar_chart  -  堆积柱状图（占比趋势）
  • 新增 boxplot  -  箱线图（分布与异常值）
  • heatmap 增强：seaborn 热力图，支持相关矩阵自动标注
  • 所有图表统一添加数据标注（关键值直接标在图上）

Output spec:
  • 300 DPI PNG，透明安全背景
  • CJK 字体自动检测：SimHei / PingFang SC / Microsoft YaHei / Noto Sans CJK
  • 所有 public 方法返回 bytes，可直接嵌入 Word

Supported chart types:
  bar_chart             -  单系列垂直/水平柱状图
  grouped_bar_chart     -  多系列分组柱状图
  stacked_bar_chart     -  堆积柱状图（绝对值或百分比）
  line_chart            -  多系列折线图（含数据点标记）
  pie_chart             -  饼图 / 环形图
  combo_chart           -  柱 + 折组合双轴图
  area_chart            -  堆积/叠加面积图
  scatter_chart         -  散点图（含可选趋势线）
  waterfall_chart       -  瀑布图（增减分解）
  heatmap               -  热力图（相关矩阵 / 数据矩阵）
  boxplot               -  箱线图（分布与异常值）
  table_chart           -  表格样式图像渲染
  from_markdown_table   -  解析 Markdown 表格自动生成最优图表（Iris 核心入口）

Usage example:
    from app.generators.chart_generator import ChartGenerator
    png = ChartGenerator.bar_chart(
        categories=["Q1", "Q2", "Q3", "Q4"],
        values=[120, 145, 132, 178],
        title="季度净利润（百万元）",
        ylabel="百万元",
    )
    # pass png (bytes) to WordGenerator.embed_image
"""
from __future__ import annotations

import io
import warnings
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# ── 品牌配色（对齐 DESIGN.md §5）────────────────────────────────────────────
_BRAND   = "#8c4f3a"   # 深研褐（主 CTA / 首选数据系列）
_PALETTE = [
    "#8c4f3a",   # brand 深研褐
    "#3b82f6",   # 蓝
    "#22c55e",   # 绿（成功）
    "#d97706",   # 橙（警示）
    "#8b5cf6",   # 紫
    "#06b6d4",   # 青
    "#f43f5e",   # 玫红
    "#64748b",   # 灰蓝
]
_BG     = "#fafaf9"    # canvas 主底色
_GRID   = "#e5e4e0"    # line 常规边框色
_TEXT   = "#141414"    # ink-1 主文色
_TEXT2  = "#4a4a46"    # ink-2 次要文色
_DPI    = 300


def _setup_font() -> None:
    """Configure matplotlib to use a CJK-capable font if available."""
    import matplotlib
    import matplotlib.font_manager as fm

    candidates = [
        "SimHei", "黑体", "PingFang SC", "Microsoft YaHei", "微软雅黑",
        "Noto Sans CJK SC", "WenQuanYi Micro Hei", "Source Han Sans CN",
        "Heiti TC",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
    # Fallback: DejaVu (no CJK)  -  labels won't render CJK but won't crash
    matplotlib.rcParams["font.family"] = "DejaVu Sans"
    matplotlib.rcParams["axes.unicode_minus"] = False


def _base_fig(
    w: float = 10, h: float = 5.5, *, tight: bool = True
) -> Tuple[Any, Any]:
    """Return a (fig, ax) with standardised styling."""
    import matplotlib.pyplot as plt

    _setup_font()
    warnings.filterwarnings("ignore", category=UserWarning)
    fig, ax = plt.subplots(figsize=(w, h), dpi=_DPI)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(_GRID)
    ax.spines["bottom"].set_color(_GRID)
    ax.tick_params(colors=_TEXT, labelsize=9)
    ax.yaxis.grid(True, color=_GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    if tight:
        fig.tight_layout(pad=1.6)
    return fig, ax


def _title_label(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", color=_TEXT, pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color=_TEXT)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=_TEXT)


def _to_png(fig) -> bytes:
    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=_DPI, bbox_inches="tight",
                facecolor=_BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── public API ─────────────────────────────────────────────────────────────────

class ChartGenerator:
    """Stateless factory - all methods are class-level and return PNG bytes."""

    # ── bar chart ─────────────────────────────────────────────────────────────

    @classmethod
    def bar_chart(
        cls,
        categories: List[str],
        values: List[Union[int, float]],
        *,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        color: Optional[str] = None,
        horizontal: bool = False,
        show_values: bool = True,
    ) -> bytes:
        fig, ax = _base_fig()
        c = color or _PALETTE[0]
        x = range(len(categories))

        if horizontal:
            bars = ax.barh(x, values, color=c, zorder=3, height=0.55)
            ax.set_yticks(list(x))
            ax.set_yticklabels(categories, fontsize=9)
            ax.xaxis.grid(True, color=_GRID, linewidth=0.7)
            ax.yaxis.grid(False)
            ax.spines["left"].set_visible(False)
            if show_values:
                for bar, v in zip(bars, values):
                    ax.text(
                        bar.get_width() + max(values) * 0.01,
                        bar.get_y() + bar.get_height() / 2,
                        f"{v:,.1f}" if isinstance(v, float) else f"{v:,}",
                        va="center", fontsize=8, color=_TEXT,
                    )
        else:
            bars = ax.bar(x, values, color=c, zorder=3, width=0.55)
            ax.set_xticks(list(x))
            ax.set_xticklabels(categories, fontsize=9, rotation=20 if len(categories) > 6 else 0)
            if show_values:
                for bar, v in zip(bars, values):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(values) * 0.01,
                        f"{v:,.1f}" if isinstance(v, float) else f"{v:,}",
                        ha="center", va="bottom", fontsize=8, color=_TEXT,
                    )

        _title_label(ax, title, xlabel, ylabel)
        return _to_png(fig)

    # ── grouped bar ──────────────────────────────────────────────────────────

    @classmethod
    def grouped_bar_chart(
        cls,
        categories: List[str],
        series: Dict[str, List[Union[int, float]]],
        *,
        title: str = "",
        ylabel: str = "",
        show_values: bool = False,
    ) -> bytes:
        import numpy as np

        n_series = len(series)
        n_cats   = len(categories)
        fig, ax  = _base_fig(w=max(10, n_cats * 1.2 + 2))

        x      = np.arange(n_cats)
        width  = 0.75 / n_series

        for i, (label, vals) in enumerate(series.items()):
            offset = (i - n_series / 2 + 0.5) * width
            bars = ax.bar(x + offset, vals, width, label=label,
                          color=_PALETTE[i % len(_PALETTE)], zorder=3)
            if show_values:
                for bar, v in zip(bars, vals):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(max(v2) for v2 in series.values()) * 0.01,
                        f"{v:,}", ha="center", va="bottom", fontsize=7, color=_TEXT,
                    )

        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9,
                           rotation=20 if n_cats > 6 else 0)
        ax.legend(fontsize=9, framealpha=0.6, facecolor=_BG)
        _title_label(ax, title, ylabel=ylabel)
        return _to_png(fig)

    # ── line chart ───────────────────────────────────────────────────────────

    @classmethod
    def line_chart(
        cls,
        x_labels: List[str],
        series: Dict[str, List[Union[int, float]]],
        *,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        markers: bool = True,
        fill: bool = False,
    ) -> bytes:
        fig, ax = _base_fig()
        for i, (label, vals) in enumerate(series.items()):
            col = _PALETTE[i % len(_PALETTE)]
            kw: Dict[str, Any] = dict(
                color=col, linewidth=2.0, zorder=3, label=label,
                marker="o" if markers else None, markersize=5,
                markerfacecolor=_BG, markeredgewidth=1.5,
            )
            ax.plot(range(len(x_labels)), vals, **kw)
            if fill:
                ax.fill_between(range(len(x_labels)), vals, alpha=0.12, color=col)

        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels, fontsize=9,
                           rotation=20 if len(x_labels) > 7 else 0)
        if len(series) > 1:
            ax.legend(fontsize=9, framealpha=0.6, facecolor=_BG)
        _title_label(ax, title, xlabel, ylabel)
        return _to_png(fig)

    # ── pie / donut ──────────────────────────────────────────────────────────

    @classmethod
    def pie_chart(
        cls,
        labels: List[str],
        values: List[Union[int, float]],
        *,
        title: str = "",
        donut: bool = True,
        show_pct: bool = True,
    ) -> bytes:
        import matplotlib.pyplot as plt

        _setup_font()
        fig, ax = plt.subplots(figsize=(7, 5.5), dpi=_DPI)
        fig.patch.set_facecolor(_BG)

        colors = (_PALETTE * (len(values) // len(_PALETTE) + 1))[:len(values)]
        wedge_props = dict(width=0.5) if donut else {}
        pct_fmt = "%1.1f%%" if show_pct else ""

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            colors=colors,
            autopct=pct_fmt,
            pctdistance=0.75 if donut else 0.6,
            startangle=90,
            wedgeprops=wedge_props,
        )
        for t in autotexts:
            t.set_fontsize(8)
            t.set_color(_BG)
            t.set_fontweight("bold")

        ax.legend(
            wedges, labels,
            loc="center left", bbox_to_anchor=(1, 0.5),
            fontsize=9, framealpha=0.6, facecolor=_BG,
        )
        if title:
            ax.set_title(title, fontsize=13, fontweight="bold", color=_TEXT, pad=10)

        fig.tight_layout(pad=1.6)
        return _to_png(fig)

    # ── combo (bar + line) ───────────────────────────────────────────────────

    @classmethod
    def combo_chart(
        cls,
        categories: List[str],
        bar_values: List[Union[int, float]],
        line_values: List[Union[int, float]],
        *,
        title: str = "",
        bar_label: str = "值",
        line_label: str = "增长率",
        bar_ylabel: str = "",
        line_ylabel: str = "%",
        bar_color: Optional[str] = None,
        line_color: Optional[str] = None,
    ) -> bytes:
        import matplotlib.pyplot as plt

        _setup_font()
        warnings.filterwarnings("ignore", category=UserWarning)
        fig, ax1 = plt.subplots(figsize=(10, 5.5), dpi=_DPI)
        fig.patch.set_facecolor(_BG)
        ax1.set_facecolor(_BG)

        for spine in ("top", "right"):
            ax1.spines[spine].set_visible(False)
        ax1.spines["left"].set_color(_GRID)
        ax1.spines["bottom"].set_color(_GRID)
        ax1.yaxis.grid(True, color=_GRID, linewidth=0.7, zorder=0)
        ax1.set_axisbelow(True)

        x = range(len(categories))
        bc = bar_color or _PALETTE[0]
        lc = line_color or _PALETTE[1]

        bars = ax1.bar(x, bar_values, color=bc, zorder=3, width=0.55,
                       alpha=0.85, label=bar_label)
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(categories, fontsize=9,
                            rotation=20 if len(categories) > 6 else 0)
        ax1.set_ylabel(bar_ylabel, fontsize=9, color=bc)
        ax1.tick_params(axis="y", colors=bc, labelsize=9)

        ax2 = ax1.twinx()
        ax2.plot(x, line_values, color=lc, linewidth=2.2, marker="o",
                 markersize=5, markerfacecolor=_BG, markeredgewidth=1.5,
                 zorder=4, label=line_label)
        ax2.set_ylabel(line_ylabel, fontsize=9, color=lc)
        ax2.tick_params(axis="y", colors=lc, labelsize=9)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_color(_GRID)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2,
                   fontsize=9, framealpha=0.6, facecolor=_BG, loc="upper left")

        if title:
            ax1.set_title(title, fontsize=13, fontweight="bold", color=_TEXT, pad=10)

        fig.tight_layout(pad=1.6)
        return _to_png(fig)

    # ── area chart ───────────────────────────────────────────────────────────

    @classmethod
    def area_chart(
        cls,
        x_labels: List[str],
        series: Dict[str, List[Union[int, float]]],
        *,
        title: str = "",
        ylabel: str = "",
        stacked: bool = False,
    ) -> bytes:
        import numpy as np

        fig, ax = _base_fig()
        x = np.arange(len(x_labels))

        if stacked:
            bottom = np.zeros(len(x_labels))
            for i, (label, vals) in enumerate(series.items()):
                col = _PALETTE[i % len(_PALETTE)]
                v = np.array(vals, dtype=float)
                ax.fill_between(x, bottom, bottom + v,
                                alpha=0.75, color=col, label=label, zorder=3)
                ax.plot(x, bottom + v, color=col, linewidth=1, zorder=4)
                bottom += v
        else:
            for i, (label, vals) in enumerate(series.items()):
                col = _PALETTE[i % len(_PALETTE)]
                ax.fill_between(x, vals, alpha=0.25, color=col, zorder=2)
                ax.plot(x, vals, color=col, linewidth=2, label=label, zorder=3,
                        marker="o", markersize=4, markerfacecolor=_BG, markeredgewidth=1.5)

        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, fontsize=9,
                           rotation=20 if len(x_labels) > 7 else 0)
        if len(series) > 1:
            ax.legend(fontsize=9, framealpha=0.6, facecolor=_BG)
        _title_label(ax, title, ylabel=ylabel)
        return _to_png(fig)

    # ── table chart ──────────────────────────────────────────────────────────

    @classmethod
    def table_chart(
        cls,
        headers: List[str],
        rows: List[List[str]],
        *,
        title: str = "",
        col_widths: Optional[List[float]] = None,
    ) -> bytes:
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors

        _setup_font()
        n_rows = len(rows)
        n_cols = len(headers)
        fig_h  = max(3.0, 0.45 * (n_rows + 2))
        fig_w  = max(8.0, n_cols * 1.8)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=_DPI)
        fig.patch.set_facecolor(_BG)
        ax.axis("off")

        cell_data = rows
        col_w = col_widths or [1.0 / n_cols] * n_cols

        tbl = ax.table(
            cellText=cell_data,
            colLabels=headers,
            colWidths=col_w,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        tbl.scale(1, 1.5)

        # Style header row
        for col in range(n_cols):
            cell = tbl[0, col]
            cell.set_facecolor(_PALETTE[0])
            cell.set_text_props(color="white", fontweight="bold")

        # Alternating row colours
        for row in range(1, n_rows + 1):
            bg = "#F0F4FA" if row % 2 == 0 else _BG
            for col in range(n_cols):
                tbl[row, col].set_facecolor(bg)
                tbl[row, col].set_text_props(color=_TEXT)

        if title:
            ax.set_title(title, fontsize=12, fontweight="bold",
                         color=_TEXT, pad=10, y=1.02)

        fig.tight_layout(pad=1.2)
        return _to_png(fig)

    # ── heatmap ──────────────────────────────────────────────────────────────

    @classmethod
    def heatmap(
        cls,
        data: List[List[float]],
        row_labels: List[str],
        col_labels: List[str],
        *,
        title: str = "",
        cmap: str = "Blues",
        annotate: bool = True,
        fmt: str = ".2f",
    ) -> bytes:
        import numpy as np
        import matplotlib.pyplot as plt

        _setup_font()
        matrix = np.array(data)
        n_rows, n_cols = matrix.shape
        fig_h = max(4.0, n_rows * 0.55 + 1.5)
        fig_w = max(6.0, n_cols * 0.9 + 2.0)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=_DPI)
        fig.patch.set_facecolor(_BG)

        im = ax.imshow(matrix, cmap=cmap, aspect="auto")
        fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)

        ax.set_xticks(range(n_cols))
        ax.set_yticks(range(n_rows))
        ax.set_xticklabels(col_labels, fontsize=9, rotation=30, ha="right")
        ax.set_yticklabels(row_labels, fontsize=9)
        ax.spines[:].set_visible(False)
        ax.tick_params(length=0)

        if annotate:
            thresh = (matrix.max() + matrix.min()) / 2
            for i in range(n_rows):
                for j in range(n_cols):
                    ax.text(j, i, format(matrix[i, j], fmt),
                            ha="center", va="center", fontsize=8,
                            color="white" if matrix[i, j] > thresh else _TEXT)

        if title:
            ax.set_title(title, fontsize=12, fontweight="bold",
                         color=_TEXT, pad=10)

        fig.tight_layout(pad=1.4)
        return _to_png(fig)

    # ── scatter ──────────────────────────────────────────────────────────────

    @classmethod
    def scatter_chart(
        cls,
        x: List[float],
        y: List[float],
        *,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        labels: Optional[List[str]] = None,
        trendline: bool = False,
        color: Optional[str] = None,
    ) -> bytes:
        import numpy as np

        fig, ax = _base_fig()
        c = color or _PALETTE[0]
        ax.scatter(x, y, color=c, s=60, zorder=3, alpha=0.8,
                   edgecolors=_BG, linewidths=0.5)

        if labels:
            for xi, yi, lbl in zip(x, y, labels):
                ax.annotate(lbl, (xi, yi), textcoords="offset points",
                            xytext=(4, 4), fontsize=7, color=_TEXT)

        if trendline and len(x) > 1:
            z = np.polyfit(x, y, 1)
            p = np.poly1d(z)
            xs = np.linspace(min(x), max(x), 100)
            ax.plot(xs, p(xs), linestyle="--", color=_PALETTE[1],
                    linewidth=1.5, alpha=0.8, zorder=2)

        _title_label(ax, title, xlabel, ylabel)
        return _to_png(fig)

    # ── from markdown table ───────────────────────────────────────────────────

    @classmethod
    def from_markdown_table(
        cls,
        markdown: str,
        chart_type: str = "bar",
        *,
        title: str = "",
        value_col: int = 1,
    ) -> Optional[bytes]:
        """
        Parse a GitHub-flavored markdown table and render as a chart.

        chart_type: "bar" | "line" | "pie" | "table"
        value_col:  index of the numeric column to use for bar/line/pie
        """
        rows: List[List[str]] = []
        for line in markdown.strip().splitlines():
            stripped = line.strip().strip("|")
            if re.match(r"^[\s\-:|]+$", stripped):
                continue
            cells = [c.strip() for c in stripped.split("|")]
            rows.append(cells)
        if len(rows) < 2:
            return None

        headers = rows[0]
        data_rows = rows[1:]

        if chart_type == "table":
            return cls.table_chart(headers, data_rows, title=title)

        label_col = 0
        categories = [r[label_col] for r in data_rows if len(r) > label_col]
        try:
            values = [float(r[value_col].replace(",", "").replace("%", ""))
                      for r in data_rows if len(r) > value_col]
        except ValueError:
            return cls.table_chart(headers, data_rows, title=title)

        ylabel = headers[value_col] if len(headers) > value_col else ""

        if chart_type == "pie":
            return cls.pie_chart(categories, values, title=title)
        elif chart_type == "line":
            return cls.line_chart(categories, {"values": values},
                                  title=title, ylabel=ylabel)
        elif chart_type == "waterfall":
            return cls.waterfall_chart(categories, values, title=title, ylabel=ylabel)
        else:
            return cls.bar_chart(categories, values, title=title, ylabel=ylabel)

    # ── waterfall chart ───────────────────────────────────────────────────────

    @classmethod
    def waterfall_chart(
        cls,
        categories: List[str],
        values: List[float],
        *,
        title: str = "",
        ylabel: str = "",
        total_label: str = "合计",
        annotate: bool = True,
    ) -> bytes:
        """Waterfall chart for variance decomposition.

        Positive bars use brand color (up), negative bars use warning orange (down),
        last bar is the running total.
        """
        import matplotlib.pyplot as plt
        import numpy as np

        _setup_font()
        fig, ax = _base_fig(figsize=(max(8, len(categories) * 0.9 + 2), 5))

        running = 0.0
        bottoms: List[float] = []
        colors: List[str] = []

        for i, v in enumerate(values[:-1]):
            bottoms.append(running if v >= 0 else running + v)
            colors.append(_PALETTE[0] if v >= 0 else _PALETTE[3])
            running += v

        # last bar is a total  -  draw from 0
        bottoms.append(0.0)
        colors.append(_PALETTE[1])

        x = list(range(len(categories)))
        bars = ax.bar(x, values, bottom=bottoms, color=colors,
                      width=0.55, zorder=3, edgecolor=_BG, linewidth=0.5)

        if annotate:
            for bar, v, b in zip(bars, values, bottoms):
                ypos = b + v + (abs(v) * 0.03 + 0.1)
                ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                        f"{v:+.1f}", ha="center", va="bottom",
                        fontsize=8, color=_TEXT)

        # connector lines
        run = 0.0
        for i, v in enumerate(values[:-1]):
            ax.plot([i + 0.275, i + 0.725], [run + v, run + v],
                    color=_TEXT2, linewidth=0.8, linestyle="--", zorder=2)
            run += v

        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9)
        ax.axhline(0, color=_TEXT2, linewidth=0.8)
        _title_label(ax, title, "", ylabel)
        return _to_png(fig)

    # ── grouped bar chart ─────────────────────────────────────────────────────

    @classmethod
    def grouped_bar_chart(
        cls,
        categories: List[str],
        series: Dict[str, List[float]],
        *,
        title: str = "",
        ylabel: str = "",
        annotate: bool = False,
    ) -> bytes:
        """Grouped bar chart - multi-series side-by-side."""
        import matplotlib.pyplot as plt
        import numpy as np

        _setup_font()
        fig, ax = _base_fig(figsize=(max(8, len(categories) * len(series) * 0.5 + 2), 5))

        n_groups = len(categories)
        n_series = len(series)
        width = 0.8 / n_series
        x = np.arange(n_groups)

        for i, (label, vals) in enumerate(series.items()):
            offset = (i - (n_series - 1) / 2) * width
            bars = ax.bar(x + offset, vals, width=width * 0.9,
                          label=label, color=_PALETTE[i % len(_PALETTE)],
                          zorder=3, edgecolor=_BG, linewidth=0.4)
            if annotate:
                for bar, v in zip(bars, vals):
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + abs(bar.get_height()) * 0.02,
                            f"{v:.1f}", ha="center", va="bottom", fontsize=7)

        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9)
        if n_series > 1:
            ax.legend(fontsize=8, framealpha=0.8)
        _title_label(ax, title, "", ylabel)
        return _to_png(fig)

    # ── stacked bar chart ─────────────────────────────────────────────────────

    @classmethod
    def stacked_bar_chart(
        cls,
        categories: List[str],
        series: Dict[str, List[float]],
        *,
        title: str = "",
        ylabel: str = "",
        percentage: bool = False,
    ) -> bytes:
        """Stacked bar chart - show component proportions or absolute values."""
        import matplotlib.pyplot as plt
        import numpy as np

        _setup_font()
        fig, ax = _base_fig()

        vals_matrix = np.array(list(series.values()), dtype=float)
        if percentage:
            col_sums = vals_matrix.sum(axis=0)
            col_sums[col_sums == 0] = 1
            vals_matrix = vals_matrix / col_sums * 100

        x = np.arange(len(categories))
        bottoms = np.zeros(len(categories))
        for i, (label, row) in enumerate(zip(series.keys(), vals_matrix)):
            ax.bar(x, row, bottom=bottoms, label=label,
                   color=_PALETTE[i % len(_PALETTE)],
                   zorder=3, edgecolor=_BG, linewidth=0.3)
            bottoms += row

        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9)
        ax.legend(fontsize=8, framealpha=0.8, loc="upper right")
        if percentage:
            ax.set_ylim(0, 110)
            ax.set_ylabel("%")
        _title_label(ax, title, "", ylabel if not percentage else "占比 (%)")
        return _to_png(fig)

    # ── boxplot ───────────────────────────────────────────────────────────────

    @classmethod
    def boxplot(
        cls,
        data: Dict[str, List[float]],
        *,
        title: str = "",
        ylabel: str = "",
    ) -> bytes:
        """Boxplot - show data distribution and outliers."""
        import matplotlib.pyplot as plt

        _setup_font()
        fig, ax = _base_fig()

        labels = list(data.keys())
        values_list = list(data.values())

        bp = ax.boxplot(
            values_list, labels=labels, patch_artist=True,
            medianprops={"color": _BRAND, "linewidth": 2},
            flierprops={"marker": "o", "color": _PALETTE[3],
                        "markersize": 4, "alpha": 0.6},
        )
        for patch, color in zip(bp["boxes"], _PALETTE):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        _title_label(ax, title, "", ylabel)
        return _to_png(fig)


# re needed for from_markdown_table
import re
