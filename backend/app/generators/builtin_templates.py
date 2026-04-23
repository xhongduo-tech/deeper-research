"""
Built-in Word templates seeded at startup.

Each template is a minimal .docx with pre-configured styles so every report
produced with that template inherits its look without any extra work from
WordGenerator.  The templates themselves contain NO content — they are pure
style vessels.

Seeded records in uploaded_files with user_id=0 (system) and is_template=True.
"""
from __future__ import annotations

import io
import os
from typing import List, Tuple


# ── colour palettes ────────────────────────────────────────────────────────────

_PALETTES = {
    "formal": {
        "h1": (0x0D, 0x47, 0xA1),   # deep blue
        "h2": (0x15, 0x65, 0xC0),
        "h3": (0x19, 0x76, 0xD2),
        "title": (0x0A, 0x2D, 0x6E),
        "accent": "0D47A1",
        "body": "宋体",
        "heading": "黑体",
    },
    "elegant": {
        "h1": (0x2C, 0x3E, 0x50),   # charcoal
        "h2": (0x34, 0x49, 0x5E),
        "h3": (0x44, 0x5A, 0x6F),
        "title": (0x1A, 0x25, 0x2F),
        "accent": "2C3E50",
        "body": "宋体",
        "heading": "黑体",
    },
    "minimal": {
        "h1": (0x21, 0x21, 0x21),   # near-black
        "h2": (0x42, 0x42, 0x42),
        "h3": (0x61, 0x61, 0x61),
        "title": (0x00, 0x00, 0x00),
        "accent": "424242",
        "body": "宋体",
        "heading": "宋体",
    },
}

BUILTIN_TEMPLATES: List[Tuple[str, str, str]] = [
    # (internal_name, display_name, palette_key)
    ("builtin_formal",   "正式公文",   "formal"),
    ("builtin_elegant",  "商务雅致",   "elegant"),
    ("builtin_minimal",  "极简清晰",   "minimal"),
]


def build_template_docx(palette_key: str) -> bytes:
    """Return raw .docx bytes for one built-in template style."""
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.oxml.ns import qn

        p = _PALETTES[palette_key]
        doc = Document()

        # Page margins
        for sec in doc.sections:
            sec.top_margin    = Cm(2.54)
            sec.bottom_margin = Cm(2.54)
            sec.left_margin   = Cm(3.17)
            sec.right_margin  = Cm(3.17)

        # Normal (body) style
        normal = doc.styles["Normal"]
        normal.font.name = p["body"]
        normal.font.size = Pt(11)
        _set_all_fonts(normal.font._element, p["body"])

        # Heading styles
        levels = [
            ("Heading 1", 18, p["h1"], True),
            ("Heading 2", 14, p["h2"], True),
            ("Heading 3", 12, p["h3"], True),
        ]
        for sname, size, rgb, bold in levels:
            try:
                st = doc.styles[sname]
                st.font.name  = p["heading"]
                st.font.size  = Pt(size)
                st.font.bold  = bold
                st.font.color.rgb = RGBColor(*rgb)
                st.paragraph_format.space_before = Pt(10)
                st.paragraph_format.space_after  = Pt(4)
                _set_all_fonts(st.font._element, p["heading"])
            except Exception:
                pass

        # Table style — attempt to set default table border colour
        try:
            _patch_table_style(doc, p["accent"])
        except Exception:
            pass

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        return b""


def _set_all_fonts(rpr_element, font_name: str) -> None:
    try:
        from docx.oxml.ns import qn
        rFonts = rpr_element.get_or_add_rFonts()
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rFonts.set(qn(attr), font_name)
    except Exception:
        pass


def _patch_table_style(doc, hex_color: str) -> None:
    """Give the default Table Grid style a header row with the accent colour."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    try:
        st = doc.styles["Table Grid"]
        tbl_pr = st.element
        # We just ensure the style exists; actual header colouring is done
        # at render time by WordGenerator._render_table.
    except Exception:
        pass


async def seed_builtin_templates(db, template_dir: str) -> None:
    """
    Idempotently seed built-in templates into the DB.
    Skips any record whose ``original_name`` already exists.
    """
    from sqlalchemy import select
    from app.models.uploaded_file import UploadedFile

    os.makedirs(template_dir, exist_ok=True)

    for internal_name, display_name, palette_key in BUILTIN_TEMPLATES:
        fname = f"{internal_name}.docx"
        fpath = os.path.join(template_dir, fname)

        # Check DB
        existing = await db.execute(
            select(UploadedFile).where(UploadedFile.original_name == display_name)
        )
        if existing.scalar_one_or_none():
            continue  # already seeded

        # Build the docx
        docx_bytes = build_template_docx(palette_key)
        if not docx_bytes:
            continue

        # Write to disk
        with open(fpath, "wb") as f:
            f.write(docx_bytes)

        # Insert DB record (user_id=0 = system / builtin)
        rec = UploadedFile(
            report_id=None,
            user_id=0,
            filename=fname,
            original_name=display_name,
            file_type="docx",
            file_path=fpath,
            file_size=len(docx_bytes),
            extracted_text=None,
            is_template=True,
        )
        db.add(rec)

    await db.flush()
