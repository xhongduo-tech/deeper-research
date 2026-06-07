"""DocumentSpec — structured Pydantic models that LLM generates, Python renderer applies.

The separation between DocumentSpec (what to write) and DocRenderer (how to write it)
is the core architectural fix for template adherence:
- LLM produces a validated JSON spec
- Renderer opens the template file and applies spec deterministically
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Shared primitives ────────────────────────────────────────────────────────

class TableSpec(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    caption: Optional[str] = None

    @field_validator("rows")
    @classmethod
    def rows_not_empty(cls, v: list) -> list:
        return v or []


class ChartSeriesSpec(BaseModel):
    name: str
    values: list[float]
    series_type: Literal["bar", "line", "area", "scatter"] = "bar"


class ChartSpec(BaseModel):
    chart_type: Literal[
        "bar", "column", "line", "area", "pie", "donut",
        "stacked_bar", "stacked_area", "waterfall",
        "combo", "scatter", "heatmap", "funnel",
    ] = "bar"
    title: str
    labels: list[str]
    series: list[ChartSeriesSpec]
    unit: str = ""
    source_note: str = ""
    orientation: Literal["vertical", "horizontal"] = "vertical"

    @model_validator(mode="after")
    def validate_series_label_alignment(self) -> "ChartSpec":
        """P1-1: Ensure every series has exactly len(labels) values.

        Mismatched lengths cause silent renderer failures (openpyxl/pptx drops
        the extra values or crashes with an IndexError).  We fix here rather
        than in the renderer so errors surface early with a clear message.
        """
        n_labels = len(self.labels)
        fixed_series = []
        for s in self.series:
            if len(s.values) != n_labels:
                # Pad with 0.0 or truncate to match label count
                fixed_vals = (s.values + [0.0] * n_labels)[:n_labels]
                fixed_series.append(s.model_copy(update={"values": fixed_vals}))
            else:
                fixed_series.append(s)
        if fixed_series != self.series:
            object.__setattr__(self, "series", fixed_series)
        return self

    def to_render_spec(self):
        """Convert to chart_render_service.ChartSpec dataclass."""
        from app.services.chart_render_service import ChartSpec as RenderChartSpec, ChartSeries
        return RenderChartSpec(
            chart_type=self.chart_type,
            title=self.title,
            labels=self.labels,
            series=[ChartSeries(name=s.name, values=s.values, series_type=s.series_type)
                    for s in self.series],
            unit=self.unit,
            source_note=self.source_note,
            orientation=self.orientation,
        )


# ── DOCX ─────────────────────────────────────────────────────────────────────

class DocxSectionSpec(BaseModel):
    id: str
    title: str
    template_heading_match: Optional[str] = None  # exact heading text from reference doc
    content_type: Literal["paragraphs", "bullets", "table", "mixed"] = "paragraphs"
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    table: Optional[TableSpec] = None
    chart: Optional[ChartSpec] = None
    target_chars: int = 400
    style_note: Optional[str] = None  # "narrative" | "formal" | "speech"
    evidence_ids: list[str] = Field(default_factory=list)  # P3-1: source evidence chunk IDs
    subsections: list["DocxSectionSpec"] = Field(default_factory=list)  # H2/H3 nesting

    @field_validator("paragraphs", "bullets")
    @classmethod
    def strip_empty(cls, v: list) -> list:
        return [s for s in v if s and s.strip()]

    @field_validator("subsections")
    @classmethod
    def limit_subsection_depth(cls, v: list) -> list:
        # Allow up to 3 levels of nesting; deeper subsections are flattened up
        def _flatten_deep(sections: list, depth: int) -> list:
            result = []
            for sec in sections:
                if depth >= 3 and sec.subsections:
                    sec = sec.model_copy(update={"subsections": []})
                else:
                    sec = sec.model_copy(
                        update={"subsections": _flatten_deep(sec.subsections, depth + 1)}
                    )
                result.append(sec)
            return result
        return _flatten_deep(v, depth=2)


DocxSectionSpec.model_rebuild()  # resolve forward reference for subsections


class DocxSpec(BaseModel):
    format: Literal["docx"] = "docx"
    style: Literal["speech", "report", "analysis", "table_heavy"] = "report"
    tense: Literal["past", "present"] = "present"
    title: str
    sections: list[DocxSectionSpec]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sections")
    @classmethod
    def sections_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("sections must not be empty")
        return v


# ── PPTX ──────────────────────────────────────────────────────────────────────

class PptxSlideSpec(BaseModel):
    id: str
    layout: Literal[
        "content", "comparison", "title_only",
        "section_header", "big_number", "data_table",
    ] = "content"
    template_slide_idx: Optional[int] = None  # which template slide to base this on
    assertion_title: str  # must be a full assertion, not a topic label
    bullets: list[str] = Field(default_factory=list)
    table: Optional[TableSpec] = None
    chart: Optional[ChartSpec] = None
    big_number: Optional[dict[str, str]] = None  # {"value": "23%", "label": "同比增长"}
    speaker_notes: Optional[str] = None

    @field_validator("assertion_title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("assertion_title must not be empty")
        v = v.strip()
        if len(v) > 30:
            v = v[:30]  # truncate to fit slide title area
        return v

    @field_validator("bullets")
    @classmethod
    def strip_empty_bullets(cls, v: list) -> list:
        v = [s for s in v if s and s.strip()]
        return v[:6]  # enforce max 6 bullets per slide for content density

    @field_validator("speaker_notes")
    @classmethod
    def validate_speaker_notes(cls, v: Optional[str]) -> Optional[str]:
        # P1-3: Sentence-aware truncation — avoid cutting mid-word at 220 chars.
        if not v:
            return v
        v = v.strip()
        if len(v) <= 220:
            return v
        # Find last sentence-ending punctuation before the hard limit
        window = v[:220]
        for punct in ("。", "！", "？", ".", "!", "?"):
            idx = window.rfind(punct)
            if idx > 60:  # at least 60 chars of content
                return window[: idx + 1]
        # No sentence boundary found — fall back to hard cut
        return window


class PptxSpec(BaseModel):
    format: Literal["pptx"] = "pptx"
    title: str
    slides: list[PptxSlideSpec]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slides")
    @classmethod
    def slides_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("slides must not be empty")
        return v


# ── XLSX ──────────────────────────────────────────────────────────────────────

class XlsxFormulaSpec(BaseModel):
    cell: str       # e.g. "B10"
    formula: str    # e.g. "=SUM(B2:B9)"
    label: str = "" # optional label for the cell to the left


class XlsxChartSpec(BaseModel):
    chart_type: Literal["bar", "column", "line", "pie", "area", "scatter"] = "column"
    title: str
    data_range: str     # e.g. "A1:C5" — references cells in the same sheet
    position: str = "E2"  # top-left cell anchor for chart placement


class XlsxConditionalFormat(BaseModel):
    """A conditional formatting rule applied to a cell range."""
    range: str                        # e.g. "B2:B20"
    type: Literal[
        "color_scale",   # red→yellow→green gradient
        "data_bar",      # proportional fill bar
        "above_average", # highlight cells above a threshold
    ] = "color_scale"
    threshold: float = 0.0            # used by above_average type


class XlsxPivotSpec(BaseModel):
    """Describe a PivotTable to generate from data already in the sheet."""
    name: str = "PivotTable1"
    data_range: str          # e.g. "A1:F50" — the source data range
    dest_cell: str = "H2"   # top-left anchor for the pivot output
    row_fields: list[str] = Field(default_factory=list)    # column headers for row grouping
    col_fields: list[str] = Field(default_factory=list)    # column headers for column pivot
    value_fields: list[str] = Field(default_factory=list)  # column headers to aggregate (SUM)
    filter_fields: list[str] = Field(default_factory=list) # column headers for page filters


class XlsxSheetSpec(BaseModel):
    id: str
    name: str
    description: str = ""
    table: Optional[TableSpec] = None
    key_findings: list[str] = Field(default_factory=list)
    calculation_notes: list[str] = Field(default_factory=list)
    formulas: list[XlsxFormulaSpec] = Field(default_factory=list)
    charts: list[XlsxChartSpec] = Field(default_factory=list)
    number_formats: dict[str, str] = Field(default_factory=dict)  # col letter → format string
    freeze_pane: Optional[str] = None  # e.g. "A2" freezes the header row
    conditional_formats: list[XlsxConditionalFormat] = Field(default_factory=list)
    named_ranges: dict[str, str] = Field(default_factory=dict)    # name → range (e.g. "Revenue":"B2:B13")
    pivot_table: Optional[XlsxPivotSpec] = None


class XlsxSpec(BaseModel):
    format: Literal["xlsx"] = "xlsx"
    title: str
    sheets: list[XlsxSheetSpec]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sheets")
    @classmethod
    def sheets_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("sheets must not be empty")
        return v


# ── Union type ────────────────────────────────────────────────────────────────

DocumentSpec = Union[DocxSpec, PptxSpec, XlsxSpec]


def parse_document_spec(raw: dict, output_format: str) -> DocumentSpec:
    """Parse and validate a raw dict from LLM into the correct DocumentSpec type.

    Raises pydantic.ValidationError if the dict does not conform to the schema.
    The caller (spec_gen phase) must handle this and retry with the error injected
    into the next LLM prompt.
    """
    fmt = output_format.lower().strip()
    if fmt in ("pptx", "ppt", "powerpoint"):
        return PptxSpec.model_validate(raw)
    elif fmt in ("xlsx", "excel", "xls"):
        return XlsxSpec.model_validate(raw)
    else:
        return DocxSpec.model_validate(raw)


# ── JSON schema strings for LLM prompts ──────────────────────────────────────

_DOCX_SCHEMA_EXAMPLE = {
    "format": "docx",
    "style": "report",
    "tense": "past",
    "title": "2025年度工作总结",
    "sections": [
        {
            "id": "s1",
            "title": "一、工作概述",
            "template_heading_match": "一、工作概述",
            "content_type": "paragraphs",
            "paragraphs": ["本年度完成了…", "在XX方面，实现了…"],
            "target_chars": 400,
        },
        {
            "id": "s2",
            "title": "二、主要成果",
            "template_heading_match": "二、主要成果",
            "content_type": "mixed",
            "paragraphs": ["本年度主要成果如下："],
            "bullets": ["完成项目A，实现收入XXX万元", "推进项目B，覆盖XX个客户"],
            "target_chars": 500,
        },
    ],
}

_PPTX_SCHEMA_EXAMPLE = {
    "format": "pptx",
    "title": "2025年度经营分析",
    "slides": [
        {
            "id": "slide1",
            "layout": "content",
            "assertion_title": "2025年营业收入达50亿，同比增长15%",
            "bullets": ["核心业务板块贡献80%营收", "新兴业务同比增长40%"],
            "chart": {
                "chart_type": "bar",
                "title": "各季度营收（亿元）",
                "labels": ["Q1", "Q2", "Q3", "Q4"],
                "series": [{"name": "营收", "values": [10.5, 12.0, 13.5, 14.0]}],
            },
        },
    ],
}


def get_spec_schema_hint(output_format: str) -> str:
    """Return a compact JSON schema example for injecting into LLM prompts."""
    import json
    fmt = output_format.lower()
    if fmt in ("pptx", "ppt"):
        return json.dumps(_PPTX_SCHEMA_EXAMPLE, ensure_ascii=False, indent=2)
    return json.dumps(_DOCX_SCHEMA_EXAMPLE, ensure_ascii=False, indent=2)


def infer_chart_type(labels: list[str], n_series: int) -> str:
    """P2-3: Rule-based chart type selection from data shape.

    Priority order:
    1. Time-series labels (Q1/Q2, 年/月/季) → line
    2. Single series, ≤5 labels → pie
    3. Many labels (>10) → line
    4. ≤6 labels → column
    5. >6 labels, multiple series → stacked_bar
    6. Default → column
    """
    import re as _re
    n = len(labels)
    label_sample = " ".join(str(l) for l in labels[:6]).lower()
    # P1-2: Extended time-series detection including Chinese time labels.
    # Original pattern missed 第X季度, 上/下半年, Chinese month names,
    # and relative periods like 前N年/月.
    _TIME_PAT = _re.compile(
        r"(q[1-4]"
        r"|第?[一二三四]季度"          # 第一季度 / 一季度
        r"|上半年|下半年"              # 半年报
        r"|前\d+[年月]|近\d+[年月]"   # 前3年 / 近6月
        r"|\d{4}年|\d{1,2}月"         # 2023年 / 3月
        r"|[一二三四五六七八九十百]+月" # 一月 / 十一月
        r"|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
        r"|fy\d|h[12]\d)"
    )
    is_time = bool(_TIME_PAT.search(label_sample)) or (
        n > 4 and _re.search(r"20\d{2}", label_sample)
    )
    if is_time:
        return "line"
    if n_series == 1 and 2 <= n <= 5:
        return "pie"
    if n > 10:
        return "line"
    if n <= 6:
        return "column"
    if n_series > 1:
        return "stacked_bar"
    return "column"
