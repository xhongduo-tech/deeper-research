"""
HTML Generator — produces standalone, self-contained HTML report files.

Generates professional, responsive HTML pages from research content.
No external dependencies — all CSS/JS is inlined so files work offline.
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Color palettes per template style ─────────────────────────────────────────

PALETTES = {
    "dashboard": {
        "bg": "#0f172a", "bg2": "#1e293b", "accent": "#38bdf8",
        "accent2": "#818cf8", "text": "#f1f5f9", "text2": "#94a3b8",
        "card": "#1e293b", "border": "#334155",
    },
    "report": {
        "bg": "#ffffff", "bg2": "#f8fafc", "accent": "#2563eb",
        "accent2": "#7c3aed", "text": "#0f172a", "text2": "#64748b",
        "card": "#f1f5f9", "border": "#e2e8f0",
    },
    "minimal": {
        "bg": "#fafafa", "bg2": "#ffffff", "accent": "#18181b",
        "accent2": "#71717a", "text": "#18181b", "text2": "#71717a",
        "card": "#ffffff", "border": "#e4e4e7",
    },
    "vivid": {
        "bg": "#0d0d0d", "bg2": "#1a1a1a", "accent": "#ff6b35",
        "accent2": "#ffd166", "text": "#ffffff", "text2": "#a1a1aa",
        "card": "#1a1a1a", "border": "#2a2a2a",
    },
}

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
       background: var(--bg); color: var(--text); min-height: 100vh; line-height: 1.7; }
.page-wrap { max-width: 960px; margin: 0 auto; padding: 48px 24px; }
.hero { padding: 48px 0 36px; text-align: center; border-bottom: 1px solid var(--border); margin-bottom: 40px; }
.hero h1 { font-size: clamp(1.8rem, 4vw, 2.8rem); font-weight: 800;
           background: linear-gradient(135deg, var(--accent), var(--accent2));
           -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 12px; }
.hero p { font-size: 1.05rem; color: var(--text2); max-width: 600px; margin: 0 auto; }
.meta { display: flex; gap: 20px; justify-content: center; margin-top: 20px; flex-wrap: wrap; }
.meta-item { font-size: 0.82rem; color: var(--text2); display: flex; align-items: center; gap: 6px; }
.section { margin-bottom: 40px; }
.section-title { font-size: 1.2rem; font-weight: 700; color: var(--text);
                 border-left: 3px solid var(--accent); padding-left: 14px; margin-bottom: 20px; }
.section-body { color: var(--text2); font-size: 0.95rem; }
.section-body p { margin-bottom: 12px; }
.section-body h3 { font-size: 1rem; font-weight: 600; color: var(--text); margin: 20px 0 8px; }
.section-body ul { padding-left: 20px; }
.section-body ul li { margin-bottom: 6px; }
.section-body strong { color: var(--text); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 20px 0; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.card-num { font-size: 2rem; font-weight: 800; color: var(--accent); }
.card-label { font-size: 0.82rem; color: var(--text2); margin-top: 4px; }
.tag { display: inline-block; padding: 3px 10px; border-radius: 100px; font-size: 0.75rem;
       font-weight: 600; background: color-mix(in srgb, var(--accent) 15%, transparent);
       color: var(--accent); margin: 3px; }
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
thead tr { background: color-mix(in srgb, var(--accent) 12%, transparent); }
th { padding: 10px 14px; text-align: left; font-weight: 600; color: var(--text); font-size: 0.82rem; letter-spacing: .04em; }
td { padding: 9px 14px; border-bottom: 1px solid var(--border); color: var(--text2); }
tr:last-child td { border-bottom: none; }
blockquote { border-left: 3px solid var(--accent2); padding: 12px 16px; margin: 16px 0;
             background: color-mix(in srgb, var(--accent2) 8%, transparent); border-radius: 0 8px 8px 0; }
.footer { text-align: center; padding: 32px 0 16px; border-top: 1px solid var(--border);
          margin-top: 48px; font-size: 0.8rem; color: var(--text2); }
@media (max-width: 600px) { .page-wrap { padding: 24px 16px; } .card-grid { grid-template-columns: 1fr 1fr; } }
"""


def _make_css_vars(palette: dict) -> str:
    return ":root{" + "".join(f"--{k}:{v};" for k, v in palette.items()) + "}"


def _markdown_to_html(md: str) -> str:
    """Minimal markdown → HTML conversion."""
    lines = md.split("\n")
    out = []
    in_ul = False
    in_table = False
    table_lines: list[str] = []

    def flush_table():
        nonlocal in_table, table_lines
        if not table_lines:
            return
        rows = [r.strip().strip("|").split("|") for r in table_lines if r.strip() and not set(r.replace("|","").replace("-","").replace(":","").strip()) == set()]
        if not rows:
            table_lines = []
            in_table = False
            return
        html = "<div style='overflow-x:auto'><table><thead><tr>"
        for cell in rows[0]:
            html += f"<th>{cell.strip()}</th>"
        html += "</tr></thead><tbody>"
        for row in rows[1:]:
            html += "<tr>" + "".join(f"<td>{c.strip()}</td>" for c in row) + "</tr>"
        html += "</tbody></table></div>"
        out.append(html)
        table_lines = []
        in_table = False

    for line in lines:
        if line.startswith("|"):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            in_table = True
            table_lines.append(line)
            continue
        if in_table:
            flush_table()

        if in_ul and not line.strip().startswith("- "):
            out.append("</ul>")
            in_ul = False

        if line.startswith("# "):
            out.append(f'<h2 class="section-title">{line[2:].strip()}</h2>')
        elif line.startswith("## "):
            out.append(f'<h2 class="section-title">{line[3:].strip()}</h2>')
        elif line.startswith("### "):
            out.append(f'<h3 class="section-title" style="font-size:1.05rem">{line[4:].strip()}</h3>')
        elif line.strip().startswith("- "):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = line.strip()[2:]
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", item)
            out.append(f"<li>{item}</li>")
        elif line.strip().startswith("> "):
            out.append(f'<blockquote>{line.strip()[2:]}</blockquote>')
        elif line.strip():
            txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            txt = re.sub(r"\*(.+?)\*", r"<em>\1</em>", txt)
            out.append(f"<p>{txt}</p>")
        else:
            if in_ul:
                out.append("</ul>")
                in_ul = False

    if in_ul:
        out.append("</ul>")
    if in_table:
        flush_table()

    return "\n".join(out)


def generate_html_report(
    title: str,
    content: str,
    template_style: str = "report",
    subtitle: str = "",
    created_at: str = "",
    author: str = "DataAgent Studio",
    kv_metrics: Optional[list[dict]] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """
    Produce a self-contained HTML file from research content (Markdown).
    Returns the complete HTML string.
    """
    palette = PALETTES.get(template_style, PALETTES["report"])
    css_vars = _make_css_vars(palette)
    body_html = _markdown_to_html(content)

    # KV metric cards
    metric_html = ""
    if kv_metrics:
        cards = "".join(
            f'<div class="card"><div class="card-num">{m["value"]}</div>'
            f'<div class="card-label">{m["label"]}</div></div>'
            for m in kv_metrics[:6]
        )
        metric_html = f'<div class="card-grid">{cards}</div>'

    # Tags
    tag_html = ""
    if tags:
        tag_html = '<div style="margin:16px 0">' + "".join(f'<span class="tag">{t}</span>' for t in tags[:10]) + "</div>"

    meta_items = []
    if created_at:
        meta_items.append(f'<span class="meta-item">📅 {created_at}</span>')
    if author:
        meta_items.append(f'<span class="meta-item">✍️ {author}</span>')
    meta_html = f'<div class="meta">{"".join(meta_items)}</div>' if meta_items else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
{css_vars}
{BASE_CSS}
</style>
</head>
<body>
<div class="page-wrap">
  <div class="hero">
    <h1>{title}</h1>
    {f'<p>{subtitle}</p>' if subtitle else ''}
    {meta_html}
  </div>
  {tag_html}
  {metric_html}
  <div class="section">
    <div class="section-body">{body_html}</div>
  </div>
  <div class="footer">Generated by DataAgent Studio · {created_at or ''}</div>
</div>
</body>
</html>"""


async def generate_html_from_report(
    report_title: str,
    sections: list[dict],
    template_style: str = "report",
    output_path: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Build HTML from a structured report (list of {title, content} sections).
    Writes to output_path if given, always returns the HTML string.
    """
    md_parts = []
    for sec in sections:
        if sec.get("title"):
            md_parts.append(f"## {sec['title']}\n")
        if sec.get("content"):
            md_parts.append(sec["content"])
        md_parts.append("")

    html = generate_html_report(
        title=report_title,
        content="\n".join(md_parts),
        template_style=template_style,
        **kwargs,
    )

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")
        logger.info(f"[html_gen] Written {len(html)} chars to {output_path}")

    return html
