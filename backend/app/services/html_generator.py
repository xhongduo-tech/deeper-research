"""
HTML Generator — produces standalone, self-contained HTML report files.

Generates professional, responsive HTML pages from research content.
No external dependencies — all CSS/JS is inlined so files work offline.
"""
import json
import logging
import re
import html as html_lib
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Color palettes per template style ─────────────────────────────────────────

PALETTES = {
    "dashboard": {
        "bg": "#0f172a", "bg2": "#1e293b", "accent": "#38bdf8",
        "accent2": "#818cf8", "text": "#f1f5f9", "text2": "#94a3b8",
        "card": "#1e293b", "border": "#334155", "surface": "#162032",
        "accent_rgb": "56,189,248", "accent2_rgb": "129,140,248",
    },
    "report": {
        "bg": "#ffffff", "bg2": "#f8fafc", "accent": "#2563eb",
        "accent2": "#7c3aed", "text": "#0f172a", "text2": "#64748b",
        "card": "#f1f5f9", "border": "#e2e8f0", "surface": "#f8fafc",
        "accent_rgb": "37,99,235", "accent2_rgb": "124,58,237",
    },
    "minimal": {
        "bg": "#fafafa", "bg2": "#ffffff", "accent": "#18181b",
        "accent2": "#71717a", "text": "#18181b", "text2": "#71717a",
        "card": "#ffffff", "border": "#e4e4e7", "surface": "#f4f4f5",
        "accent_rgb": "24,24,27", "accent2_rgb": "113,113,122",
    },
    "vivid": {
        "bg": "#0d0d0d", "bg2": "#1a1a1a", "accent": "#ff6b35",
        "accent2": "#ffd166", "text": "#ffffff", "text2": "#a1a1aa",
        "card": "#1a1a1a", "border": "#2a2a2a", "surface": "#141414",
        "accent_rgb": "255,107,53", "accent2_rgb": "255,209,102",
    },
    "pm-gantt": {
        "bg": "#f8fafc", "bg2": "#ffffff", "accent": "#2563eb",
        "accent2": "#10b981", "text": "#0f172a", "text2": "#475569",
        "card": "#ffffff", "border": "#dbe3ef", "surface": "#f1f5f9",
        "accent_rgb": "37,99,235", "accent2_rgb": "16,185,129",
    },
    "pm-kanban": {
        "bg": "#f8fafc", "bg2": "#ffffff", "accent": "#10b981",
        "accent2": "#2563eb", "text": "#0f172a", "text2": "#475569",
        "card": "#ffffff", "border": "#dbe3ef", "surface": "#f1f5f9",
        "accent_rgb": "16,185,129", "accent2_rgb": "37,99,235",
    },
    "pm-timeline": {
        "bg": "#ffffff", "bg2": "#f8fafc", "accent": "#7c3aed",
        "accent2": "#f59e0b", "text": "#111827", "text2": "#4b5563",
        "card": "#f8fafc", "border": "#e5e7eb", "surface": "#f3f4f6",
        "accent_rgb": "124,58,237", "accent2_rgb": "245,158,11",
    },
    "pm-resource": {
        "bg": "#f8fafc", "bg2": "#ffffff", "accent": "#0f766e",
        "accent2": "#f59e0b", "text": "#0f172a", "text2": "#475569",
        "card": "#ffffff", "border": "#dbe3ef", "surface": "#f1f5f9",
        "accent_rgb": "15,118,110", "accent2_rgb": "245,158,11",
    },
    "pm-risk": {
        "bg": "#ffffff", "bg2": "#f8fafc", "accent": "#dc2626",
        "accent2": "#f59e0b", "text": "#111827", "text2": "#4b5563",
        "card": "#f8fafc", "border": "#e5e7eb", "surface": "#fef2f2",
        "accent_rgb": "220,38,38", "accent2_rgb": "245,158,11",
    },
    "pm-mindmap": {
        "bg": "#fffaf0", "bg2": "#ffffff", "accent": "#f59e0b",
        "accent2": "#2563eb", "text": "#111827", "text2": "#57534e",
        "card": "#ffffff", "border": "#fde68a", "surface": "#fef9f0",
        "accent_rgb": "245,158,11", "accent2_rgb": "37,99,235",
    },
    "pm-fishbone": {
        "bg": "#f8fafc", "bg2": "#ffffff", "accent": "#0891b2",
        "accent2": "#7c3aed", "text": "#0f172a", "text2": "#475569",
        "card": "#ffffff", "border": "#dbe3ef", "surface": "#f0f9ff",
        "accent_rgb": "8,145,178", "accent2_rgb": "124,58,237",
    },
}

BASE_CSS = """
/* ── Reset & Base ─────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; font-size: 16px; }
body {
  font-family: -apple-system, 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ── Layout ───────────────────────────────────────────────────────────────── */
.page-wrap {
  max-width: 980px;
  margin: 0 auto;
  padding: 0 24px 80px;
}

/* ── Hero Section ─────────────────────────────────────────────────────────── */
.hero {
  padding: 56px 0 40px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 60% 50% at 50% 0%, rgba(var(--accent_rgb), 0.07) 0%, transparent 70%);
  pointer-events: none;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  border-radius: 100px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: rgba(var(--accent_rgb), 0.1);
  color: var(--accent);
  border: 1px solid rgba(var(--accent_rgb), 0.2);
  margin-bottom: 18px;
}
.hero h1 {
  font-size: clamp(1.9rem, 4.5vw, 3rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 14px;
}
.hero-subtitle {
  font-size: 1.05rem;
  color: var(--text2);
  max-width: 640px;
  margin: 0 auto 24px;
  line-height: 1.65;
}
.hero-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border), transparent);
  margin-top: 40px;
}

/* ── Meta row ─────────────────────────────────────────────────────────────── */
.meta {
  display: flex;
  gap: 24px;
  justify-content: center;
  margin-top: 20px;
  flex-wrap: wrap;
}
.meta-item {
  font-size: 0.82rem;
  color: var(--text2);
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ── Tags ─────────────────────────────────────────────────────────────────── */
.tags-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 20px 0 28px; justify-content: center; }
.tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 11px;
  border-radius: 100px;
  font-size: 0.75rem;
  font-weight: 600;
  background: rgba(var(--accent_rgb), 0.1);
  color: var(--accent);
  border: 1px solid rgba(var(--accent_rgb), 0.2);
  transition: all .2s ease;
}
.tag:hover { background: rgba(var(--accent_rgb), 0.18); }

/* ── Metric Cards ─────────────────────────────────────────────────────────── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin: 28px 0;
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px 20px 18px;
  position: relative;
  overflow: hidden;
  transition: transform .2s ease, box-shadow .2s ease;
}
.card::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  border-radius: 14px 14px 0 0;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(var(--accent_rgb), 0.12); }
.card-num {
  font-size: 2.2rem;
  font-weight: 800;
  color: var(--accent);
  letter-spacing: -0.03em;
  line-height: 1;
  margin-bottom: 6px;
}
.card-label {
  font-size: 0.8rem;
  color: var(--text2);
  font-weight: 500;
}
.card-trend {
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 100px;
}
.card-trend.up { background: rgba(16,185,129,0.12); color: #10b981; }
.card-trend.down { background: rgba(239,68,68,0.12); color: #ef4444; }

/* ── Content Sections ─────────────────────────────────────────────────────── */
.section { margin-bottom: 44px; }

.section-title {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 16px;
  margin-bottom: 20px;
  position: relative;
}
.section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 2px;
  bottom: 2px;
  width: 4px;
  background: linear-gradient(to bottom, var(--accent), var(--accent2));
  border-radius: 4px;
}

.section-title-sm {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
  padding-left: 14px;
  margin: 24px 0 12px;
  position: relative;
}
.section-title-sm::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  bottom: 3px;
  width: 3px;
  background: rgba(var(--accent_rgb), 0.5);
  border-radius: 3px;
}

/* ── Body text ────────────────────────────────────────────────────────────── */
.section-body { color: var(--text2); font-size: 0.95rem; }
.section-body p { margin-bottom: 14px; line-height: 1.8; }
.section-body strong { color: var(--text); font-weight: 650; }
.section-body em { font-style: italic; color: var(--text); }

/* ── Lists ────────────────────────────────────────────────────────────────── */
.section-body ul, .section-body ol {
  padding-left: 0;
  margin: 12px 0 16px;
  list-style: none;
  counter-reset: list-counter;
}
.section-body ul li, .section-body ol li {
  position: relative;
  padding: 7px 14px 7px 32px;
  margin-bottom: 4px;
  border-radius: 8px;
  background: rgba(var(--accent_rgb), 0.03);
  border: 1px solid rgba(var(--accent_rgb), 0.06);
  line-height: 1.65;
  transition: background .15s;
}
.section-body ul li:hover, .section-body ol li:hover {
  background: rgba(var(--accent_rgb), 0.07);
}
.section-body ul li::before {
  content: '';
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}
.section-body ol li {
  counter-increment: list-counter;
}
.section-body ol li::before {
  content: counter(list-counter);
  position: absolute;
  left: 10px;
  top: 7px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(var(--accent_rgb), 0.15);
  color: var(--accent);
  font-size: 0.72rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* Nested ul/ol inside card-style lists */
.section-body ul ul, .section-body ul ol,
.section-body ol ul, .section-body ol ol {
  margin: 8px 0 4px;
}
.section-body ul ul li, .section-body ol ul li {
  background: none;
  border: none;
  padding-left: 20px;
}
.section-body ul ul li::before { width: 4px; height: 4px; background: var(--text2); }

/* ── Tables ───────────────────────────────────────────────────────────────── */
.table-wrap { overflow-x: auto; margin: 16px 0; border-radius: 12px; border: 1px solid var(--border); }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
thead tr { background: rgba(var(--accent_rgb), 0.06); }
th {
  padding: 11px 15px;
  text-align: left;
  font-weight: 700;
  color: var(--text);
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 2px solid rgba(var(--accent_rgb), 0.15);
  white-space: nowrap;
}
td {
  padding: 10px 15px;
  border-bottom: 1px solid var(--border);
  color: var(--text2);
  line-height: 1.5;
}
tr:last-child td { border-bottom: none; }
tbody tr:hover { background: rgba(var(--accent_rgb), 0.03); }
tbody tr:nth-child(even) { background: rgba(var(--accent_rgb), 0.02); }

/* ── Blockquotes ──────────────────────────────────────────────────────────── */
blockquote {
  margin: 20px 0;
  padding: 16px 20px 16px 24px;
  background: rgba(var(--accent2_rgb), 0.06);
  border-left: 4px solid var(--accent2);
  border-radius: 0 10px 10px 0;
  color: var(--text2);
  font-style: italic;
  position: relative;
}
blockquote::before {
  content: '\201C';
  position: absolute;
  top: -8px;
  left: 14px;
  font-size: 3rem;
  color: rgba(var(--accent2_rgb), 0.25);
  font-style: normal;
  line-height: 1;
  font-family: Georgia, serif;
}

/* ── Inline text styles ───────────────────────────────────────────────────── */
del { text-decoration: line-through; color: var(--text2); opacity: 0.6; }
mark { background: rgba(var(--accent_rgb), 0.18); color: var(--text); padding: 1px 4px; border-radius: 3px; }
a { color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(var(--accent_rgb), 0.3); transition: border-color .15s; }
a:hover { border-bottom-color: var(--accent); }

/* ── Code blocks ──────────────────────────────────────────────────────────── */
pre {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
  overflow-x: auto;
  margin: 16px 0;
  font-size: 0.85rem;
  line-height: 1.6;
  position: relative;
}
pre::before {
  content: attr(data-lang);
  position: absolute;
  top: 8px;
  right: 12px;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text2);
  opacity: 0.6;
}
code {
  font-family: 'SF Mono', 'Cascadia Code', 'JetBrains Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 0.875em;
  background: rgba(var(--accent_rgb), 0.08);
  color: var(--accent);
  padding: 2px 6px;
  border-radius: 5px;
}
pre code {
  background: none;
  color: var(--text);
  padding: 0;
  font-size: inherit;
}

/* ── Alert / Callout boxes ────────────────────────────────────────────────── */
.callout {
  padding: 14px 18px;
  border-radius: 10px;
  margin: 16px 0;
  font-size: 0.9rem;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.callout-icon { font-size: 1.1rem; flex-shrink: 0; margin-top: 1px; }
.callout-info { background: rgba(37,99,235,0.07); border: 1px solid rgba(37,99,235,0.15); color: var(--text); }
.callout-warn { background: rgba(245,158,11,0.07); border: 1px solid rgba(245,158,11,0.2); color: var(--text); }
.callout-danger { background: rgba(220,38,38,0.07); border: 1px solid rgba(220,38,38,0.15); color: var(--text); }
.callout-success { background: rgba(16,185,129,0.07); border: 1px solid rgba(16,185,129,0.15); color: var(--text); }

/* ── Horizontal rule ──────────────────────────────────────────────────────── */
hr {
  border: none;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border), transparent);
  margin: 36px 0;
}

/* ── TOC Navigation ───────────────────────────────────────────────────────── */
.toc-wrap {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 22px;
  margin: 28px 0 36px;
}
.toc-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 7px;
}
.toc-list { list-style: none; padding: 0; }
.toc-list li {
  margin-bottom: 3px;
  background: none !important;
  border: none !important;
  padding: 3px 4px 3px 0 !important;
}
.toc-list li::before { display: none !important; }
.toc-list a {
  color: var(--text2);
  text-decoration: none;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 7px;
  transition: all .15s;
}
.toc-list a:hover {
  background: rgba(var(--accent_rgb), 0.08);
  color: var(--accent);
}
.toc-list a::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(var(--accent_rgb), 0.4);
  flex-shrink: 0;
}
.toc-num {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--accent);
  background: rgba(var(--accent_rgb), 0.1);
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: auto;
  flex-shrink: 0;
  display: none;
}

/* ── Progress bar (used in metric cards) ─────────────────────────────────── */
.progress-wrap { margin-top: 10px; }
.progress-bar {
  height: 4px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  border-radius: 4px;
  transition: width 1s cubic-bezier(.4,0,.2,1);
}

/* ── Footer ───────────────────────────────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 36px 0 20px;
  border-top: 1px solid var(--border);
  margin-top: 60px;
  font-size: 0.8rem;
  color: var(--text2);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.footer-logo {
  font-weight: 700;
  font-size: 0.88rem;
  color: var(--text);
  letter-spacing: -0.01em;
}
.footer-logo span {
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ── Back to top ──────────────────────────────────────────────────────────── */
#back-to-top {
  position: fixed;
  bottom: 28px;
  right: 28px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  border: none;
  cursor: pointer;
  font-size: 16px;
  display: none;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(var(--accent_rgb), 0.4);
  transition: all .25s ease;
  z-index: 100;
  text-decoration: none;
  line-height: 1;
}
#back-to-top:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(var(--accent_rgb), 0.5); }
#back-to-top.visible { display: flex; }

/* ── Scroll reveal animation ──────────────────────────────────────────────── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
.reveal { opacity: 0; }
.reveal.visible { animation: fadeInUp .5s cubic-bezier(.22,1,.36,1) forwards; }

/* ── Print styles ─────────────────────────────────────────────────────────── */
@media print {
  #back-to-top { display: none !important; }
  .hero::before { display: none; }
  .card { break-inside: avoid; }
  .section { break-inside: avoid; }
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  pre { white-space: pre-wrap; }
}

/* ── Responsive ───────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .page-wrap { padding: 0 16px 60px; }
  .hero { padding: 36px 0 28px; }
  .hero h1 { font-size: 1.7rem; }
  .card-grid { grid-template-columns: 1fr 1fr; }
  .toc-wrap { display: none; }
  #back-to-top { bottom: 16px; right: 16px; width: 36px; height: 36px; font-size: 14px; }
}
"""

PROJECT_VIEW_CSS = """
/* ── Deterministic project view renderer ──────────────────────────────────── */
.pv-shell {
  margin: 30px 0 38px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: linear-gradient(180deg, var(--bg2), var(--card));
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
  overflow: hidden;
}
.pv-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
  border-bottom: 1px solid var(--border);
  background: rgba(var(--accent_rgb), 0.05);
}
.pv-kicker {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 4px;
}
.pv-title { font-size: 1.25rem; font-weight: 800; color: var(--text); line-height: 1.25; }
.pv-sub { color: var(--text2); font-size: 0.86rem; margin-top: 6px; max-width: 620px; }
.pv-badge {
  flex-shrink: 0;
  border: 1px solid rgba(var(--accent_rgb), 0.2);
  background: rgba(var(--accent_rgb), 0.09);
  color: var(--accent);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 0.74rem;
  font-weight: 750;
}
.pv-body { padding: 22px; }
.pv-grid { display: grid; gap: 14px; }
.pv-grid-2 { grid-template-columns: 1.15fr 0.85fr; }
.pv-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.pv-card {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg2);
  padding: 14px;
  min-width: 0;
}
.pv-card-title {
  color: var(--text);
  font-size: 0.88rem;
  font-weight: 800;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 7px;
}
.pv-muted { color: var(--text2); font-size: 0.78rem; }
.pv-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(var(--accent_rgb), 0.09);
  color: var(--accent);
  font-size: 0.72rem;
  font-weight: 750;
}
.pv-metric-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.pv-metric {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 11px 12px;
  background: var(--bg2);
}
.pv-metric strong { display: block; color: var(--accent); font-size: 1.25rem; line-height: 1; }
.pv-metric span { display: block; margin-top: 5px; color: var(--text2); font-size: 0.74rem; }
.pv-timeline {
  position: relative;
  padding: 10px 6px 4px 92px;
  min-height: 238px;
}
.pv-time-axis {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0;
  position: absolute;
  left: 92px;
  right: 8px;
  top: 8px;
  bottom: 6px;
}
.pv-time-axis span { border-left: 1px solid var(--border); color: var(--text2); font-size: 0.66rem; padding-left: 4px; }
.pv-gantt-row {
  position: relative;
  height: 34px;
  margin: 12px 0;
}
.pv-gantt-label {
  position: absolute;
  left: -86px;
  top: 7px;
  width: 78px;
  color: var(--text2);
  font-size: 0.76rem;
  font-weight: 650;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.pv-gantt-bar {
  position: absolute;
  top: 4px;
  height: 24px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  color: #fff;
  display: flex;
  align-items: center;
  padding: 0 9px;
  font-size: 0.7rem;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(var(--accent_rgb), 0.18);
}
.pv-milestone {
  position: absolute;
  top: 2px;
  width: 18px;
  height: 18px;
  transform: rotate(45deg);
  background: #f59e0b;
  border: 2px solid #fff;
  box-shadow: 0 4px 12px rgba(245,158,11,.35);
}
.pv-pert svg, .pv-fishbone svg, .pv-chart svg { width: 100%; height: auto; display: block; }
.pv-kanban {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 12px;
  overflow-x: auto;
}
.pv-lane {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  padding: 10px;
}
.pv-lane-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--text);
  font-size: 0.8rem;
  font-weight: 800;
  margin-bottom: 8px;
}
.pv-task-card {
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  padding: 9px;
  background: var(--bg2);
  margin-bottom: 8px;
}
.pv-task-card strong { display: block; color: var(--text); font-size: 0.78rem; line-height: 1.35; }
.pv-task-card span { display: block; color: var(--text2); font-size: 0.7rem; margin-top: 4px; }
.pv-burndown {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px;
  background: var(--bg2);
}
.pv-risk-matrix {
  display: grid;
  grid-template-columns: 28px repeat(3, minmax(0, 1fr));
  grid-template-rows: repeat(3, 88px) 24px;
  gap: 6px;
  align-items: stretch;
}
.pv-risk-axis-y {
  grid-row: 1 / span 3;
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text2);
  font-size: 0.72rem;
  font-weight: 800;
}
.pv-risk-axis-x {
  grid-column: 2 / span 3;
  color: var(--text2);
  font-size: 0.72rem;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pv-risk-cell {
  border-radius: 12px;
  padding: 8px;
  border: 1px solid rgba(255,255,255,.8);
  display: flex;
  flex-direction: column;
  gap: 5px;
  overflow: hidden;
}
.pv-risk-chip {
  border-radius: 7px;
  padding: 3px 6px;
  background: rgba(255,255,255,.78);
  color: #111827;
  font-size: 0.68rem;
  font-weight: 750;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pv-actions {
  display: grid;
  gap: 8px;
}
.pv-action {
  display: grid;
  grid-template-columns: minmax(0,1fr) auto;
  gap: 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 9px 10px;
  background: var(--bg2);
}
.pv-action strong { color: var(--text); font-size: 0.78rem; }
.pv-action span { color: var(--text2); font-size: 0.72rem; }
.pv-resource-heat {
  display: grid;
  grid-template-columns: 86px repeat(6, minmax(0, 1fr));
  gap: 5px;
  align-items: center;
}
.pv-resource-heat span {
  min-height: 28px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-weight: 750;
}
.pv-resource-name { color: var(--text2); justify-content: flex-start !important; background: transparent !important; }
.pv-mm {
  position: relative;
  min-height: 320px;
}
.pv-mm-node {
  position: absolute;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  border: 1px solid rgba(var(--accent_rgb), .22);
  background: var(--bg2);
  color: var(--text);
  padding: 9px 13px;
  font-size: 0.78rem;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(15,23,42,.08);
}
.pv-mm-node.center {
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
  min-width: 120px;
  text-align: center;
}
.pv-dashboard {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.pv-dashboard-chart {
  grid-column: span 2;
  min-height: 230px;
}
@media (max-width: 820px) {
  .pv-grid-2, .pv-grid-3, .pv-metric-strip, .pv-dashboard { grid-template-columns: 1fr; }
  .pv-kanban { grid-template-columns: repeat(4, 210px); }
  .pv-dashboard-chart { grid-column: span 1; }
  .pv-head { flex-direction: column; }
  .pv-timeline { padding-left: 76px; }
  .pv-time-axis { left: 76px; }
  .pv-gantt-label { left: -72px; width: 66px; }
}
"""

# ── Inline JS for interactive behaviours ──────────────────────────────────────

INLINE_JS = """
(function(){
  // Back-to-top button
  var btn = document.getElementById('back-to-top');
  if (btn) {
    window.addEventListener('scroll', function(){
      if (window.scrollY > 300) btn.classList.add('visible');
      else btn.classList.remove('visible');
    });
    btn.addEventListener('click', function(){ window.scrollTo({top:0,behavior:'smooth'}); });
  }

  // Scroll reveal
  var reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && reveals.length) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){ if(e.isIntersecting){ e.target.classList.add('visible'); io.unobserve(e.target); } });
    }, {threshold: 0.12});
    reveals.forEach(function(el){ io.observe(el); });
  } else {
    reveals.forEach(function(el){ el.classList.add('visible'); });
  }
})();
"""


def _make_css_vars(palette: dict) -> str:
    return ":root{" + "".join(f"--{k}:{v};" for k, v in palette.items()) + "}"


def _markdown_to_html(md: str) -> str:
    """Enhanced markdown → HTML conversion supporting most common elements."""
    lines = md.split("\n")
    out: list[str] = []
    in_ul = False
    in_ol = False
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    in_table = False
    table_lines: list[str] = []

    def close_list():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def flush_table():
        nonlocal in_table, table_lines
        if not table_lines:
            return
        rows = []
        for r in table_lines:
            stripped = r.strip().strip("|")
            cells = [c.strip() for c in stripped.split("|")]
            # skip separator rows (---:---:---)
            if all(re.match(r'^[-: ]+$', c) for c in cells if c):
                continue
            rows.append(cells)
        if rows:
            html = '<div class="table-wrap"><table><thead><tr>'
            for cell in rows[0]:
                html += f"<th>{_inline(cell)}</th>"
            html += "</tr></thead><tbody>"
            for row in rows[1:]:
                html += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>"
            html += "</tbody></table></div>"
            out.append(html)
        table_lines.clear()
        in_table = False

    def _inline(text: str) -> str:
        """Apply inline formatting: bold, italic, code, strikethrough, links."""
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
        text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
        return text

    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Fenced code block ────────────────────────────────────────────────
        if line.strip().startswith("```"):
            if not in_code:
                close_list()
                if in_table:
                    flush_table()
                in_code = True
                code_lang = line.strip()[3:].strip() or "text"
                code_buf = []
            else:
                in_code = False
                escaped = "\n".join(
                    line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    for line in code_buf
                )
                out.append(f'<pre data-lang="{code_lang}"><code>{escaped}</code></pre>')
                code_buf = []
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # ── Table rows ───────────────────────────────────────────────────────
        if line.startswith("|"):
            close_list()
            in_table = True
            table_lines.append(line)
            i += 1
            continue
        if in_table:
            flush_table()

        # ── Horizontal rule ──────────────────────────────────────────────────
        if re.match(r'^---+$|^\*\*\*+$', line.strip()):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        # ── Headings ─────────────────────────────────────────────────────────
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            close_list()
            level = len(m.group(1))
            text = _inline(m.group(2).strip())
            slug = re.sub(r'[^\w一-鿿-]', '-', text.lower()).strip('-')
            if level == 1:
                out.append(f'<h2 class="section-title reveal" id="{slug}">{text}</h2>')
            elif level == 2:
                out.append(f'<h2 class="section-title reveal" id="{slug}">{text}</h2>')
            elif level == 3:
                out.append(f'<h3 class="section-title-sm" id="{slug}">{text}</h3>')
            else:
                out.append(f'<h4 style="font-size:.95rem;font-weight:700;color:var(--text);margin:16px 0 8px">{text}</h4>')
            i += 1
            continue

        # ── Blockquote ───────────────────────────────────────────────────────
        if line.startswith("> ") or line.strip() == ">":
            close_list()
            content = _inline(line[2:].strip() if line.startswith("> ") else "")
            out.append(f"<blockquote><p>{content}</p></blockquote>")
            i += 1
            continue

        # ── Unordered list ───────────────────────────────────────────────────
        ul_m = re.match(r'^(\s*)[-*+]\s+(.*)', line)
        if ul_m:
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = _inline(ul_m.group(2))
            out.append(f"<li>{item}</li>")
            i += 1
            continue

        # ── Ordered list ─────────────────────────────────────────────────────
        ol_m = re.match(r'^(\s*)\d+[.)]\s+(.*)', line)
        if ol_m:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            item = _inline(ol_m.group(2))
            out.append(f"<li>{item}</li>")
            i += 1
            continue

        # ── Empty line closes lists ──────────────────────────────────────────
        if not line.strip():
            close_list()
            i += 1
            continue

        # ── Regular paragraph ────────────────────────────────────────────────
        close_list()
        txt = _inline(line)
        out.append(f"<p>{txt}</p>")
        i += 1

    close_list()
    if in_code and code_buf:
        escaped = "\n".join(l.replace("<","&lt;") for l in code_buf)
        out.append(f'<pre data-lang="{code_lang}"><code>{escaped}</code></pre>')
    if in_table:
        flush_table()

    return "\n".join(out)


def _build_toc(headings: list[tuple[str, str]]) -> str:
    """Build a Table of Contents from (slug, title) pairs."""
    if not headings:
        return ""
    items = "".join(
        f'<li><a href="#{slug}">{title}</a></li>'
        for slug, title in headings[:12]
    )
    return f"""<nav class="toc-wrap reveal">
  <div class="toc-title">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="15" y2="12"/><line x1="3" y1="18" x2="9" y2="18"/></svg>
    目录
  </div>
  <ul class="toc-list">{items}</ul>
</nav>"""


def _extract_headings(md: str) -> list[tuple[str, str]]:
    """Extract (slug, title) pairs from markdown headings."""
    headings = []
    for line in md.split("\n"):
        m = re.match(r'^#{1,4}\s+(.*)', line)
        if m:
            title = re.sub(r'\*+', '', m.group(1)).strip()
            slug = re.sub(r'[^\w一-鿿-]', '-', title.lower()).strip('-')
            headings.append((slug, title))
    return headings


PROJECT_VIEW_STYLES = {
    "pm-gantt",
    "pm-kanban",
    "pm-timeline",
    "pm-resource",
    "pm-risk",
    "pm-mindmap",
    "pm-fishbone",
    "dashboard",
}


def _esc(value: object) -> str:
    return html_lib.escape(str(value or ""), quote=True)


def _compact_text(md: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", md or "")
    text = re.sub(r"[#>*`|_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sentences(md: str, limit: int = 12) -> list[str]:
    text = _compact_text(md)
    parts = re.split(r"[。！？!?；;\n]+", text)
    cleaned = [p.strip(" ：:，,.-") for p in parts if len(p.strip()) >= 6]
    return cleaned[:limit]


def _extract_json_spec(content: str) -> dict | None:
    """Extract a project_view_spec JSON object when the model provides one."""
    candidates: list[str] = []
    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content or "", re.IGNORECASE):
        candidates.append(match.group(1).strip())
    candidates.append(content or "")
    for raw in candidates:
        if "project_view_spec" in raw:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                raw = raw[start : end + 1]
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict):
            spec = obj.get("project_view_spec") if isinstance(obj.get("project_view_spec"), dict) else obj
            if isinstance(spec, dict) and (spec.get("type") or spec.get("view_type")):
                return spec
    return None


def _style_to_view_type(template_style: str) -> str:
    return {
        "pm-gantt": "gantt_pert",
        "pm-kanban": "kanban_burndown",
        "pm-timeline": "timeline",
        "pm-resource": "resource_gantt",
        "pm-risk": "risk_matrix",
        "pm-mindmap": "mind_map",
        "pm-fishbone": "fishbone",
        "dashboard": "dashboard",
    }.get(template_style, "summary")


def _first_match(text: str, keywords: list[str], fallback: str) -> str:
    for sentence in _sentences(text, 16):
        if any(kw.lower() in sentence.lower() for kw in keywords):
            return sentence[:56]
    return fallback


def _fallback_project_view_spec(title: str, content: str, template_style: str) -> dict:
    view_type = _style_to_view_type(template_style)
    sentences = _sentences(content, 16)
    generic_tasks = [
        {"name": "需求澄清", "owner": "产品/PMO", "status": "进行中", "start": 3, "duration": 18, "progress": 62, "risk": "需求范围变化"},
        {"name": "方案设计", "owner": "架构/业务", "status": "待确认", "start": 18, "duration": 22, "progress": 48, "risk": "关键方案待拍板"},
        {"name": "开发实施", "owner": "研发团队", "status": "进行中", "start": 38, "duration": 30, "progress": 41, "risk": "资源冲突"},
        {"name": "联调验收", "owner": "测试/业务", "status": "未开始", "start": 66, "duration": 20, "progress": 10, "risk": "上线窗口紧张"},
        {"name": "复盘交付", "owner": "项目经理", "status": "未开始", "start": 83, "duration": 12, "progress": 0, "risk": "文档沉淀不足"},
    ]
    if sentences:
        for idx, sentence in enumerate(sentences[:5]):
            generic_tasks[idx]["name"] = sentence[:18]
    risks = [
        {"id": "R1", "name": _first_match(content, ["风险", "延期", "阻塞"], "需求变更导致关键路径延期"), "probability": 3, "impact": 3, "owner": "项目经理", "action": "冻结范围并建立升级机制"},
        {"id": "R2", "name": _first_match(content, ["资源", "人力", "冲突"], "核心人员资源冲突"), "probability": 2, "impact": 3, "owner": "资源负责人", "action": "调整排期并准备替代人选"},
        {"id": "R3", "name": _first_match(content, ["数据", "质量", "口径"], "数据口径不一致"), "probability": 2, "impact": 2, "owner": "数据负责人", "action": "统一指标口径并复核"},
        {"id": "R4", "name": _first_match(content, ["验收", "上线", "客户"], "验收标准不清晰"), "probability": 1, "impact": 2, "owner": "业务负责人", "action": "补齐验收清单"},
    ]
    metrics = [
        {"label": "整体进度", "value": "62%", "trend": "+8%", "progress": 62},
        {"label": "高风险项", "value": "3", "trend": "-1", "progress": 42},
        {"label": "阻塞任务", "value": "2", "trend": "-"},
        {"label": "本周动作", "value": "7", "trend": "+3"},
    ]
    return {
        "type": view_type,
        "title": title,
        "summary": (sentences[0] if sentences else "围绕项目目标、进度、风险和行动闭环生成可执行项目视图。")[:120],
        "metrics": metrics,
        "tasks": generic_tasks,
        "risks": risks,
        "actions": [
            {"name": "确认关键路径与里程碑", "owner": "项目经理", "due": "本周", "status": "高优先级"},
            {"name": "补齐数据口径与验收标准", "owner": "业务/数据负责人", "due": "下次评审前", "status": "进行中"},
            {"name": "同步资源冲突与调配方案", "owner": "资源负责人", "due": "48小时内", "status": "待决策"},
        ],
        "lanes": [
            {"name": "待办", "wip": 5, "cards": generic_tasks[:2]},
            {"name": "进行中", "wip": 3, "cards": generic_tasks[2:4]},
            {"name": "验收", "wip": 2, "cards": generic_tasks[3:5]},
            {"name": "阻塞", "wip": 1, "cards": [{"name": risks[0]["name"], "owner": risks[0]["owner"], "risk": risks[0]["action"]}]},
        ],
        "causes": [
            {"category": "人员", "items": ["关键角色投入不足", "责任边界不清"]},
            {"category": "流程", "items": ["需求变更未冻结", "验收口径后置"]},
            {"category": "技术", "items": ["接口依赖复杂", "数据质量需复核"]},
            {"category": "外部", "items": ["协同方响应慢", "上线窗口受限"]},
        ],
        "branches": [
            {"name": "目标", "items": ["范围", "收益"]},
            {"name": "进度", "items": ["里程碑", "关键路径"]},
            {"name": "风险", "items": ["概率", "影响"]},
            {"name": "行动", "items": ["责任人", "截止时间"]},
        ],
        "resources": [
            {"name": "产品", "loads": [60, 76, 84, 58, 42, 35]},
            {"name": "研发", "loads": [72, 88, 95, 91, 76, 52]},
            {"name": "测试", "loads": [20, 35, 55, 78, 86, 64]},
            {"name": "业务", "loads": [42, 55, 61, 48, 65, 70]},
        ],
    }


def _normalize_spec(spec: dict | None, title: str, content: str, template_style: str) -> dict:
    fallback = _fallback_project_view_spec(title, content, template_style)
    if not spec:
        return fallback
    merged = {**fallback, **spec}
    merged["type"] = str(merged.get("type") or merged.get("view_type") or fallback["type"]).replace("-", "_")
    for key in ("metrics", "tasks", "risks", "actions", "lanes", "causes", "branches", "resources"):
        if not isinstance(merged.get(key), list) or not merged[key]:
            merged[key] = fallback[key]
    merged["title"] = str(merged.get("title") or title)
    merged["summary"] = str(merged.get("summary") or fallback["summary"])
    return merged


def _render_project_metrics(spec: dict) -> str:
    cards = []
    for metric in spec.get("metrics", [])[:4]:
        cards.append(
            f'<div class="pv-metric"><strong>{_esc(metric.get("value"))}</strong>'
            f'<span>{_esc(metric.get("label"))} {_esc(metric.get("trend"))}</span></div>'
        )
    return f'<div class="pv-metric-strip">{"".join(cards)}</div>' if cards else ""


def _render_actions(spec: dict) -> str:
    items = []
    for action in spec.get("actions", [])[:5]:
        items.append(
            f'<div class="pv-action"><div><strong>{_esc(action.get("name"))}</strong><br>'
            f'<span>{_esc(action.get("owner"))} · {_esc(action.get("due"))}</span></div>'
            f'<span class="pv-pill">{_esc(action.get("status") or "待推进")}</span></div>'
        )
    return f'<div class="pv-actions">{"".join(items)}</div>'


def _render_gantt(spec: dict) -> str:
    rows = []
    for task in spec.get("tasks", [])[:7]:
        left = max(0, min(92, int(task.get("start") or 0)))
        width = max(8, min(96 - left, int(task.get("duration") or 18)))
        progress = max(0, min(100, int(task.get("progress") or 0)))
        rows.append(
            f'<div class="pv-gantt-row"><span class="pv-gantt-label">{_esc(task.get("name"))}</span>'
            f'<div class="pv-gantt-bar" style="left:{left}%;width:{width}%">{progress}% · {_esc(task.get("owner"))}</div></div>'
        )
    axis = "".join(f"<span>W{i + 1}</span>" for i in range(6))
    pert = _render_pert(spec)
    return f"""<div class="pv-grid pv-grid-2">
  <div class="pv-card"><div class="pv-card-title">甘特进度与关键路径</div>
    <div class="pv-timeline"><div class="pv-time-axis">{axis}</div>{''.join(rows)}
      <span class="pv-milestone" style="left:76%;top:196px" title="关键里程碑"></span>
    </div>
  </div>
  <div class="pv-card pv-pert"><div class="pv-card-title">PERT 依赖网络</div>{pert}</div>
</div>"""


def _render_pert(spec: dict) -> str:
    tasks = spec.get("tasks", [])[:5]
    labels = [_esc(t.get("name") or f"任务{i+1}")[:18] for i, t in enumerate(tasks)]
    while len(labels) < 5:
        labels.append(f"任务{len(labels)+1}")
    return f"""<svg viewBox="0 0 420 260" role="img" aria-label="PERT dependency network">
  <defs><marker id="pv-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--accent)"/></marker></defs>
  <g stroke="var(--accent)" stroke-width="2.2" marker-end="url(#pv-arrow)" opacity=".72">
    <line x1="78" y1="130" x2="160" y2="74"/><line x1="78" y1="130" x2="160" y2="184"/>
    <line x1="214" y1="74" x2="294" y2="130"/><line x1="214" y1="184" x2="294" y2="130"/><line x1="330" y1="130" x2="374" y2="130"/>
  </g>
  {''.join(_svg_node(x, y, label, i == 0 or i == 4) for i, (x, y, label) in enumerate([(54,130,labels[0]),(188,74,labels[1]),(188,184,labels[2]),(318,130,labels[3]),(386,130,labels[4])]))}
</svg>"""


def _svg_node(x: int, y: int, label: str, strong: bool = False) -> str:
    fill = "var(--accent)" if strong else "var(--bg2)"
    text = "#fff" if strong else "var(--text)"
    return (
        f'<g><circle cx="{x}" cy="{y}" r="33" fill="{fill}" stroke="var(--accent)" stroke-width="2"/>'
        f'<text x="{x}" y="{y-3}" text-anchor="middle" font-size="11" font-weight="800" fill="{text}">{label[:8]}</text>'
        f'<text x="{x}" y="{y+12}" text-anchor="middle" font-size="9" fill="{text}" opacity=".75">节点</text></g>'
    )


def _render_kanban(spec: dict) -> str:
    lanes_html = []
    for lane in spec.get("lanes", [])[:4]:
        cards = ""
        for card in (lane.get("cards") or [])[:4]:
            cards += (
                f'<div class="pv-task-card"><strong>{_esc(card.get("name"))}</strong>'
                f'<span>{_esc(card.get("owner"))} · {_esc(card.get("risk") or card.get("status") or "待处理")}</span></div>'
            )
        lanes_html.append(
            f'<div class="pv-lane"><div class="pv-lane-head"><span>{_esc(lane.get("name"))}</span>'
            f'<span class="pv-pill">WIP {int(lane.get("wip") or 0)}</span></div>{cards}</div>'
        )
    burndown = _render_burndown()
    return f"""<div class="pv-grid">
  <div class="pv-kanban">{''.join(lanes_html)}</div>
  <div class="pv-burndown"><div class="pv-card-title">燃尽趋势</div>{burndown}</div>
</div>"""


def _render_burndown() -> str:
    return """<svg viewBox="0 0 720 180" role="img" aria-label="burndown chart">
      <g stroke="var(--border)" stroke-width="1"><line x1="36" y1="20" x2="36" y2="150"/><line x1="36" y1="150" x2="690" y2="150"/></g>
      <polyline points="44,42 150,60 260,82 370,96 480,120 610,136 684,146" fill="none" stroke="var(--accent)" stroke-width="4" stroke-linecap="round"/>
      <polyline points="44,34 684,150" fill="none" stroke="var(--accent2)" stroke-width="2" stroke-dasharray="7 7"/>
      <g fill="var(--accent)"><circle cx="44" cy="42" r="5"/><circle cx="150" cy="60" r="5"/><circle cx="260" cy="82" r="5"/><circle cx="370" cy="96" r="5"/><circle cx="480" cy="120" r="5"/><circle cx="610" cy="136" r="5"/><circle cx="684" cy="146" r="5"/></g>
    </svg>"""


def _render_risk_matrix(spec: dict) -> str:
    cells: dict[tuple[int, int], list[dict]] = {}
    for risk in spec.get("risks", [])[:8]:
        p = max(1, min(3, int(risk.get("probability") or 2)))
        i = max(1, min(3, int(risk.get("impact") or 2)))
        cells.setdefault((p, i), []).append(risk)
    colors = {(1, 1): "#dcfce7", (2, 1): "#dcfce7", (3, 1): "#fef3c7", (1, 2): "#dcfce7", (2, 2): "#fef3c7", (3, 2): "#fed7aa", (1, 3): "#fef3c7", (2, 3): "#fed7aa", (3, 3): "#fecaca"}
    grid = ['<div class="pv-risk-axis-y">影响 Impact</div>']
    for impact in (3, 2, 1):
        for prob in (1, 2, 3):
            risks = cells.get((prob, impact), [])
            chips = "".join(f'<span class="pv-risk-chip">{_esc(r.get("id"))} {_esc(r.get("name"))}</span>' for r in risks)
            grid.append(f'<div class="pv-risk-cell" style="background:{colors[(prob, impact)]}">{chips}</div>')
    grid.append('<div></div><div class="pv-risk-axis-x">概率 Probability</div>')
    return f"""<div class="pv-grid pv-grid-2">
      <div class="pv-card"><div class="pv-card-title">影响 / 概率风险矩阵</div><div class="pv-risk-matrix">{''.join(grid)}</div></div>
      <div class="pv-card"><div class="pv-card-title">TOP 风险与应对动作</div>{_render_risk_actions(spec)}</div>
    </div>"""


def _render_risk_actions(spec: dict) -> str:
    items = []
    for risk in spec.get("risks", [])[:5]:
        items.append(
            f'<div class="pv-action"><div><strong>{_esc(risk.get("id"))} · {_esc(risk.get("name"))}</strong><br>'
            f'<span>{_esc(risk.get("owner"))} · {_esc(risk.get("action"))}</span></div>'
            f'<span class="pv-pill">P{_esc(risk.get("probability"))}/I{_esc(risk.get("impact"))}</span></div>'
        )
    return f'<div class="pv-actions">{"".join(items)}</div>'


def _render_fishbone(spec: dict) -> str:
    causes = spec.get("causes", [])[:6]
    positions = [(120, 78, -28), (260, 78, -28), (400, 78, -28), (120, 222, 28), (260, 222, 28), (400, 222, 28)]
    bones = []
    for idx, cause in enumerate(causes):
        x, y, rot = positions[idx]
        cat = _esc(cause.get("category") or f"原因{idx+1}")
        item = _esc((cause.get("items") or ["待验证原因"])[0])
        bones.append(
            f'<g transform="translate({x},{y}) rotate({rot})"><line x1="0" y1="0" x2="135" y2="0" stroke="var(--accent)" stroke-width="4" stroke-linecap="round"/></g>'
            f'<rect x="{x-42}" y="{y + (-48 if y < 150 else 22)}" width="96" height="34" rx="9" fill="var(--bg2)" stroke="var(--border)"/>'
            f'<text x="{x+6}" y="{y + (-28 if y < 150 else 42)}" text-anchor="middle" font-size="12" font-weight="800" fill="var(--accent)">{cat}</text>'
            f'<text x="{x+6}" y="{y + (-13 if y < 150 else 57)}" text-anchor="middle" font-size="9" fill="var(--text2)">{item[:12]}</text>'
        )
    return f"""<div class="pv-card pv-fishbone"><div class="pv-card-title">鱼骨图 / 根因结构</div>
      <svg viewBox="0 0 620 300" role="img" aria-label="fishbone root cause diagram">
        <defs><marker id="fish-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="var(--accent)"/></marker></defs>
        <line x1="58" y1="150" x2="518" y2="150" stroke="var(--accent)" stroke-width="5" stroke-linecap="round" marker-end="url(#fish-arrow)"/>
        {''.join(bones)}
        <rect x="510" y="126" width="86" height="48" rx="14" fill="var(--accent)"/>
        <text x="553" y="146" text-anchor="middle" font-size="12" font-weight="800" fill="#fff">核心问题</text>
        <text x="553" y="162" text-anchor="middle" font-size="10" fill="#fff" opacity=".85">根因闭环</text>
      </svg>
    </div>"""


def _render_timeline(spec: dict) -> str:
    tasks = spec.get("tasks", [])[:5]
    nodes = []
    for idx, task in enumerate(tasks):
        x = 8 + idx * 21
        nodes.append(
            f'<div style="position:absolute;left:{x}%;top:50%;transform:translate(-50%,-50%);">'
            f'<div style="width:18px;height:18px;border-radius:50%;background:var(--bg2);border:4px solid var(--accent);"></div>'
            f'<div class="pv-card" style="width:148px;margin-top:16px;padding:10px"><strong style="font-size:.78rem;color:var(--text)">{_esc(task.get("name"))}</strong><br><span class="pv-muted">{_esc(task.get("owner"))} · {_esc(task.get("status"))}</span></div>'
            f'</div>'
        )
    return f'<div class="pv-card" style="min-height:280px;position:relative"><div class="pv-card-title">路线图与关键里程碑</div><div style="position:absolute;left:42px;right:42px;top:126px;height:4px;border-radius:4px;background:linear-gradient(90deg,var(--accent),var(--accent2));"></div>{"".join(nodes)}</div>'


def _render_resource(spec: dict) -> str:
    heat = []
    for label in ["资源", "W1", "W2", "W3", "W4", "W5", "W6"]:
        heat.append(f'<span class="pv-resource-name" style="font-weight:800">{_esc(label)}</span>')
    for resource in spec.get("resources", [])[:5]:
        heat.append(f'<span class="pv-resource-name">{_esc(resource.get("name"))}</span>')
        for load in (resource.get("loads") or [])[:6]:
            val = max(0, min(100, int(load or 0)))
            if val >= 85:
                color = "#fecaca"
            elif val >= 70:
                color = "#fed7aa"
            elif val >= 50:
                color = "#fef3c7"
            else:
                color = "#dcfce7"
            heat.append(f'<span style="background:{color};color:#334155">{val}%</span>')
    return f"""<div class="pv-grid pv-grid-2">
      <div class="pv-card">{_render_gantt(spec)}</div>
      <div class="pv-card"><div class="pv-card-title">资源负载热力</div><div class="pv-resource-heat">{''.join(heat)}</div></div>
    </div>"""


def _render_mind_map(spec: dict) -> str:
    branches = spec.get("branches", [])[:6]
    pos = [(20, 24), (80, 24), (16, 72), (84, 72), (50, 14), (50, 86)]
    lines = []
    nodes = ['<div class="pv-mm-node center" style="left:50%;top:50%;">中心主题</div>']
    for idx, branch in enumerate(branches):
        x, y = pos[idx]
        lines.append(f'<line x1="50" y1="50" x2="{x}" y2="{y}" stroke="var(--accent)" stroke-width="1.8" opacity=".45"/>')
        nodes.append(f'<div class="pv-mm-node" style="left:{x}%;top:{y}%;">{_esc(branch.get("name"))}</div>')
    return f'<div class="pv-card"><div class="pv-card-title">思维导图结构</div><div class="pv-mm"><svg viewBox="0 0 100 100" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%;height:100%;">{"".join(lines)}</svg>{"".join(nodes)}</div></div>'


def _render_dashboard(spec: dict) -> str:
    bars = [62, 48, 75, 38, 82, 56, 68]
    chart = "".join(f'<rect x="{30+i*54}" y="{160-h}" width="28" height="{h}" rx="6" fill="var(--accent)" opacity="{0.52+i*0.06}"/>' for i, h in enumerate(bars))
    heat = "".join(f'<rect x="{30+c*42}" y="{36+r*36}" width="30" height="25" rx="5" fill="{["#dbeafe","#bfdbfe","#38bdf8","#10b981","#f59e0b","#fecaca"][(r+c)%6]}"/>' for r in range(4) for c in range(6))
    return f"""<div class="pv-dashboard">
      {_render_project_metrics(spec)}
      <div class="pv-card pv-dashboard-chart pv-chart"><div class="pv-card-title">趋势与目标达成</div><svg viewBox="0 0 440 210">{chart}<polyline points="38,114 92,98 146,122 200,72 254,92 308,66 362,54" fill="none" stroke="var(--accent2)" stroke-width="4" stroke-linecap="round"/></svg></div>
      <div class="pv-card pv-dashboard-chart pv-chart"><div class="pv-card-title">维度热力矩阵</div><svg viewBox="0 0 330 210">{heat}</svg></div>
      <div class="pv-card"><div class="pv-card-title">行动建议</div>{_render_actions(spec)}</div>
    </div>"""


def _render_project_view(spec: dict, template_style: str) -> str:
    view_type = spec.get("type") or _style_to_view_type(template_style)
    if view_type in ("gantt_pert", "gantt", "pert"):
        visual = _render_gantt(spec)
    elif view_type in ("kanban_burndown", "kanban"):
        visual = _render_kanban(spec)
    elif view_type in ("risk_matrix", "risk"):
        visual = _render_risk_matrix(spec)
    elif view_type in ("fishbone", "root_cause"):
        visual = _render_fishbone(spec)
    elif view_type in ("timeline", "roadmap"):
        visual = _render_timeline(spec)
    elif view_type in ("resource_gantt", "resource"):
        visual = _render_resource(spec)
    elif view_type in ("mind_map", "mindmap"):
        visual = _render_mind_map(spec)
    elif view_type == "dashboard":
        visual = _render_dashboard(spec)
    else:
        visual = _render_dashboard(spec)
    return f"""<section class="pv-shell reveal">
      <div class="pv-head">
        <div><div class="pv-kicker">Project View Spec</div><div class="pv-title">{_esc(spec.get("title"))}</div><div class="pv-sub">{_esc(spec.get("summary"))}</div></div>
        <div class="pv-badge">{_esc(str(view_type).replace("_", " ").title())}</div>
      </div>
      <div class="pv-body">
        {_render_project_metrics(spec) if view_type != "dashboard" else ""}
        {visual}
      </div>
    </section>"""


def _strip_project_view_spec_blocks(content: str) -> str:
    def repl(match: re.Match) -> str:
        body = match.group(1)
        return "" if "project_view_spec" in body or '"type"' in body and '"tasks"' in body else match.group(0)

    stripped = re.sub(r"```(?:json)?\s*([\s\S]*?)```", repl, content or "", flags=re.IGNORECASE)
    stripped = re.sub(r"(?is)\{\s*\"project_view_spec\"\s*:\s*\{[\s\S]*?\}\s*\}", "", stripped)
    return stripped.strip() or content


def generate_html_report(
    title: str,
    content: str,
    template_style: str = "report",
    subtitle: str = "",
    created_at: str = "",
    author: str = "DataAgent Studio",
    kv_metrics: Optional[list[dict]] = None,
    tags: Optional[list[str]] = None,
    show_toc: bool = True,
) -> str:
    """
    Produce a self-contained HTML file from research content (Markdown).
    Returns the complete HTML string.
    """
    palette = PALETTES.get(template_style, PALETTES["report"])
    css_vars = _make_css_vars(palette)
    project_view_html = ""
    render_content = content
    if template_style in PROJECT_VIEW_STYLES:
        spec = _normalize_spec(_extract_json_spec(content), title, content, template_style)
        project_view_html = _render_project_view(spec, template_style)
        render_content = _strip_project_view_spec_blocks(content)
    body_html = _markdown_to_html(render_content)

    # Build TOC from headings
    headings = _extract_headings(render_content)
    toc_html = _build_toc(headings) if show_toc and len(headings) >= 3 else ""

    # KV metric cards
    metric_html = ""
    if kv_metrics:
        cards = ""
        for m in kv_metrics[:6]:
            trend = m.get("trend", "")
            trend_html = f'<span class="card-trend {"up" if trend and "+" in str(trend) else "down"}">{trend}</span>' if trend else ""
            prog = m.get("progress")
            prog_html = f'<div class="progress-wrap"><div class="progress-bar"><div class="progress-fill" style="width:{prog}%"></div></div></div>' if prog else ""
            cards += (
                f'<div class="card">'
                f'{trend_html}'
                f'<div class="card-num">{m["value"]}</div>'
                f'<div class="card-label">{m["label"]}</div>'
                f'{prog_html}'
                f'</div>'
            )
        metric_html = f'<div class="card-grid reveal">{cards}</div>'

    # Tags
    tag_html = ""
    if tags:
        tag_html = '<div class="tags-row">' + "".join(f'<span class="tag">{t}</span>' for t in tags[:12]) + "</div>"

    # Meta
    meta_items = []
    if created_at:
        meta_items.append(f'<span class="meta-item"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> {created_at}</span>')
    if author:
        meta_items.append(f'<span class="meta-item"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> {author}</span>')
    meta_html = f'<div class="meta">{"".join(meta_items)}</div>' if meta_items else ""

    # Word count badge
    word_count = len(re.findall(r'[一-鿿]|[a-zA-Z]+', content))
    badge_html = f'<div class="hero-badge"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> DataAgent Studio</div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="generator" content="DataAgent Studio">
<title>{title}</title>
<style>
{css_vars}
{BASE_CSS}
{PROJECT_VIEW_CSS if template_style in PROJECT_VIEW_STYLES else ""}
</style>
</head>
<body>
<div class="page-wrap">

  <div class="hero">
    {badge_html}
    <h1>{title}</h1>
    {f'<p class="hero-subtitle">{subtitle}</p>' if subtitle else ''}
    {meta_html}
    {tag_html}
    <div class="hero-divider"></div>
  </div>

  {metric_html}
  {toc_html}
  {project_view_html}

  <div class="section">
    <div class="section-body">{body_html}</div>
  </div>

  <div class="footer">
    <div class="footer-logo">Data<span>Agent</span> Studio</div>
    <div>{created_at or ''} · {word_count:,} 字</div>
    <div>本报告由 AI 生成，仅供参考，请结合实际情况判断</div>
  </div>
</div>

<button id="back-to-top" title="返回顶部" aria-label="返回顶部">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>
</button>

<script>{INLINE_JS}</script>
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
