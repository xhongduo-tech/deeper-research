from app.rendering.doc_spec import DocxSpec, PptxSpec, XlsxSpec, DocumentSpec
from app.rendering.ref_extractor import (
    extract_docx_structure,
    extract_pptx_structure,
    ReferenceStructure,
    ReferenceSection,
)
from app.rendering.docx_renderer import DocxRenderer
from app.rendering.pptx_renderer import PptxRenderer
from app.rendering.xlsx_renderer import XlsxRenderer

__all__ = [
    "DocxSpec", "PptxSpec", "XlsxSpec", "DocumentSpec",
    "extract_docx_structure", "extract_pptx_structure",
    "ReferenceStructure", "ReferenceSection",
    "DocxRenderer", "PptxRenderer", "XlsxRenderer",
]
