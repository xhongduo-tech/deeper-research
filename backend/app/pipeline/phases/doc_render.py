"""DOC_RENDER phase — deterministic Python renderer applies DocumentSpec to template.

The renderer opens the uploaded template file (if any), preserves its styles/fonts/
layouts, and fills in the content from DocumentSpec. This replaces the old
"LLM generates markdown → markdown renderer guesses format" approach.

All errors propagate as PipelineError — no silent swallowing.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.pipeline.types import PipelineContext, PipelineError
from app.rendering.doc_spec import DocxSpec, PptxSpec, XlsxSpec

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DocRenderPhase:
    PHASE_NAME = "DOC_RENDER"

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx

    async def run(self) -> None:
        ctx = self.ctx
        if ctx.spec is None:
            raise PipelineError(self.PHASE_NAME, "DocumentSpec is None — SPEC_GEN must run first")

        template_path = await self._load_template_path()
        ref_structure_dict = ctx.understanding.get("reference_structure")
        ref_structure = None
        if ref_structure_dict:
            try:
                from app.rendering.ref_extractor import ReferenceStructure
                ref_structure = ReferenceStructure.from_dict(ref_structure_dict)
            except Exception as exc:
                logger.warning("[DOC_RENDER] Could not deserialise ref_structure: %s", exc)

        try:
            if isinstance(ctx.spec, DocxSpec):
                file_bytes, ext = await self._render_docx(ctx.spec, template_path, ref_structure)
            elif isinstance(ctx.spec, PptxSpec):
                file_bytes, ext = await self._render_pptx(ctx.spec, template_path)
            elif isinstance(ctx.spec, XlsxSpec):
                file_bytes, ext = await self._render_xlsx(ctx.spec)
            else:
                raise PipelineError(
                    self.PHASE_NAME,
                    f"Unknown DocumentSpec type: {type(ctx.spec).__name__}",
                )
        except PipelineError:
            raise
        except Exception as exc:
            raise PipelineError(
                self.PHASE_NAME,
                f"Document rendering failed: {exc}",
            ) from exc

        ctx.rendered_bytes = file_bytes
        ctx.rendered_ext = ext
        logger.info("[DOC_RENDER] Rendered %s (%d bytes)", ext, len(file_bytes))

    async def _load_template_path(self) -> str | None:
        """Load uploaded template first; otherwise use selected bundled PPTX template."""
        from sqlalchemy import select
        from app.models.uploaded_file import UploadedFile

        result = await self.ctx.db.execute(
            select(UploadedFile).where(
                UploadedFile.report_id == self.ctx.report.id,
                UploadedFile.is_template == True,
            )
        )
        f = result.scalar_one_or_none()
        if f and f.file_path:
            import os
            if os.path.isfile(f.file_path):
                return f.file_path
        if isinstance(self.ctx.spec, PptxSpec):
            from app.services.prompt_assets import (
                extract_visual_template,
                load_ppt_template_path,
            )

            selected_template = extract_visual_template(self.ctx.report.brief or "")
            bundled_template = load_ppt_template_path(selected_template)
            if bundled_template:
                logger.info(
                    "[DOC_RENDER] Using bundled PPTX template '%s': %s",
                    selected_template,
                    bundled_template,
                )
                return bundled_template
        return None

    async def _render_docx(self, spec: DocxSpec, template_path, ref_structure) -> tuple[bytes, str]:
        import asyncio
        from app.rendering.docx_renderer import DocxRenderer
        renderer = DocxRenderer()
        loop = asyncio.get_event_loop()
        file_bytes = await loop.run_in_executor(
            None, lambda: renderer.render(spec, template_path, ref_structure)
        )
        return file_bytes, "docx"

    async def _render_pptx(self, spec: PptxSpec, template_path) -> tuple[bytes, str]:
        import asyncio
        from app.rendering.pptx_renderer import PptxRenderer
        renderer = PptxRenderer()
        loop = asyncio.get_event_loop()
        file_bytes = await loop.run_in_executor(
            None, lambda: renderer.render(spec, template_path)
        )
        return file_bytes, "pptx"

    async def _render_xlsx(self, spec: XlsxSpec) -> tuple[bytes, str]:
        import asyncio
        from app.rendering.xlsx_renderer import XlsxRenderer
        renderer = XlsxRenderer()
        loop = asyncio.get_event_loop()
        file_bytes = await loop.run_in_executor(
            None, lambda: renderer.render(spec)
        )
        return file_bytes, "xlsx"
