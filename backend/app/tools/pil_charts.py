import os
import re
import textwrap
import uuid
from typing import Any, Dict, List, Optional

from app.config import settings


class PILChartGenerator:
    """Generate report-ready bitmap charts with Pillow."""

    def __init__(self):
        self.output_dir = os.path.abspath(os.path.join(settings.UPLOAD_DIR, "outputs", "charts"))
        os.makedirs(self.output_dir, exist_ok=True)

    async def bar_chart(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            return {"success": False, "error": f"Pillow 未安装: {exc}", "path": None}

        data = self._normalize_data(spec.get("data") or spec.get("values") or [])
        if not data:
            return {"success": False, "error": "柱状图缺少有效 data/values", "path": None}

        title = str(spec.get("title") or "柱状图")
        x_label = str(spec.get("x_label") or "")
        y_label = str(spec.get("y_label") or "")
        width = int(spec.get("width") or 1280)
        height = int(spec.get("height") or 760)
        width = min(max(width, 720), 2400)
        height = min(max(height, 480), 1600)

        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)
        font_regular = self._font(ImageFont, 28)
        font_small = self._font(ImageFont, 22)
        font_title = self._font(ImageFont, 42)

        margin_left = 130
        margin_right = 60
        margin_top = 110
        margin_bottom = 135
        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom
        axis_color = "#2f3a44"
        grid_color = "#d7dde3"
        bar_color = spec.get("bar_color") or "#2E75B6"
        accent_color = spec.get("accent_color") or "#E87B35"

        max_value = max(value for _, value in data)
        min_value = min(0, min(value for _, value in data))
        value_span = max_value - min_value if max_value != min_value else max(1, abs(max_value))

        self._center_text(draw, title, font_title, width // 2, 42, fill="#17212b")
        if spec.get("subtitle"):
            self._center_text(draw, str(spec["subtitle"]), font_small, width // 2, 88, fill="#61707f")

        # Grid and y axis labels.
        tick_count = 5
        for i in range(tick_count + 1):
            ratio = i / tick_count
            y = margin_top + plot_h - ratio * plot_h
            value = min_value + ratio * value_span
            draw.line((margin_left, y, width - margin_right, y), fill=grid_color, width=1)
            draw.text((24, y - 13), self._format_number(value), font=font_small, fill="#52616f")

        draw.line((margin_left, margin_top, margin_left, margin_top + plot_h), fill=axis_color, width=3)
        draw.line(
            (margin_left, margin_top + plot_h, width - margin_right, margin_top + plot_h),
            fill=axis_color,
            width=3,
        )

        bar_gap = max(10, int(plot_w / max(len(data), 1) * 0.22))
        bar_w = max(24, int((plot_w - bar_gap * (len(data) + 1)) / len(data)))
        zero_y = margin_top + plot_h - ((0 - min_value) / value_span) * plot_h

        for idx, (label, value) in enumerate(data):
            x0 = margin_left + bar_gap + idx * (bar_w + bar_gap)
            x1 = x0 + bar_w
            value_y = margin_top + plot_h - ((value - min_value) / value_span) * plot_h
            y0, y1 = sorted((zero_y, value_y))
            fill = accent_color if value < 0 else bar_color
            draw.rounded_rectangle((x0, y0, x1, y1), radius=6, fill=fill)
            self._center_text(draw, self._format_number(value), font_small, int((x0 + x1) / 2), y0 - 28, fill="#17212b")

            wrapped = "\n".join(textwrap.wrap(str(label), width=max(4, int(bar_w / 13)))[:2])
            self._center_multiline(draw, wrapped, font_small, int((x0 + x1) / 2), margin_top + plot_h + 18)

        if x_label:
            self._center_text(draw, x_label, font_regular, width // 2, height - 46, fill="#2f3a44")
        if y_label:
            draw.text((24, 24), y_label, font=font_small, fill="#2f3a44")

        source = spec.get("source")
        if source:
            draw.text((margin_left, height - 26), f"来源: {source}", font=font_small, fill="#7a8793")

        filename = self._safe_filename(spec.get("filename") or title) + f"_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(self.output_dir, filename)
        img.save(path, "PNG", optimize=True)
        return {
            "success": True,
            "path": path,
            "filename": filename,
            "description": f"已生成 PIL 柱状图: {filename}",
        }

    def _normalize_data(self, raw: List[Any]) -> List[tuple]:
        result = []
        for item in raw:
            if isinstance(item, dict):
                label = item.get("label") or item.get("name") or item.get("x")
                value = item.get("value") if item.get("value") is not None else item.get("y")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                label, value = item[0], item[1]
            else:
                continue
            try:
                numeric = float(str(value).replace(",", "").replace("%", ""))
            except (TypeError, ValueError):
                continue
            result.append((str(label), numeric))
        return result[:40]

    def _font(self, image_font, size: int):
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return image_font.truetype(path, size)
                except Exception:
                    continue
        return image_font.load_default()

    def _center_text(self, draw, text: str, font, x: int, y: int, fill: str):
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text((x - (bbox[2] - bbox[0]) / 2, y), text, font=font, fill=fill)

    def _center_multiline(self, draw, text: str, font, x: int, y: int):
        lines = text.splitlines() or [text]
        for idx, line in enumerate(lines):
            self._center_text(draw, line, font, x, y + idx * 26, fill="#3f4c58")

    def _format_number(self, value: float) -> str:
        if abs(value) >= 100000000:
            return f"{value / 100000000:.1f}亿"
        if abs(value) >= 10000:
            return f"{value / 10000:.1f}万"
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}"

    def _safe_filename(self, name: Any) -> str:
        safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", str(name)).strip("_")
        return safe[:48] or "bar_chart"
