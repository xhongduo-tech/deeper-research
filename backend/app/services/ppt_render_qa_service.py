"""Offline rendered-image QA for PPTX delivery artifacts.

This layer complements geometry-only PPTX inspection. It tries to render the
deck into images using locally available tools, then scores the actual pixels
for blank slides, margin clipping, density, contrast, and visual balance.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from statistics import mean

logger = logging.getLogger(__name__)


def score_rendered_images(image_paths: list[str]) -> dict:
    """Score rendered slide images with deterministic pixel heuristics."""
    try:
        from PIL import Image, ImageChops, ImageStat
    except Exception as exc:
        return {
            "rendered": bool(image_paths),
            "overall_score": 0,
            "passed": False,
            "issues": [f"Pillow不可用，无法执行图像级QA: {exc}"],
            "slides": [],
        }

    slide_scores = []
    issues: list[str] = []
    for idx, image_path in enumerate(image_paths, start=1):
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            gray = img.convert("L")
            w, h = gray.size
            stat = ImageStat.Stat(gray)
            variance = stat.var[0] if stat.var else 0.0

            # Ink mask: pixels that differ meaningfully from the dominant corner
            bg = Image.new("L", gray.size, int(gray.resize((1, 1)).getpixel((0, 0))))
            diff = ImageChops.difference(gray, bg)
            mask = diff.point(lambda p: 255 if p > 18 else 0)
            bbox = mask.getbbox()
            ink_pixels = sum(1 for p in mask.getdata() if p)
            ink_ratio = ink_pixels / max(w * h, 1)

            margin = max(12, int(min(w, h) * 0.035))
            edge_boxes = [
                (0, 0, w, margin),
                (0, h - margin, w, h),
                (0, 0, margin, h),
                (w - margin, 0, w, h),
            ]
            edge_ink = 0
            for box in edge_boxes:
                edge = mask.crop(box)
                edge_ink += sum(1 for p in edge.getdata() if p)
            edge_ratio = edge_ink / max(2 * margin * (w + h), 1)

            score = 100.0
            slide_issues: list[str] = []
            if variance < 20 or ink_ratio < 0.015 or not bbox:
                score -= 45
                slide_issues.append("渲染后疑似空白或内容过少")
            if ink_ratio > 0.55:
                score -= min(35, (ink_ratio - 0.55) * 100)
                slide_issues.append("渲染后内容密度过高，阅读压力较大")
            elif ink_ratio < 0.05:
                score -= 12
                slide_issues.append("渲染后版面偏空，信息量不足")
            if edge_ratio > 0.08:
                score -= min(30, edge_ratio * 160)
                slide_issues.append("边缘区域内容过多，存在裁切/贴边风险")
            if bbox:
                cx = ((bbox[0] + bbox[2]) / 2) / w
                cy = ((bbox[1] + bbox[3]) / 2) / h
                imbalance = max(abs(cx - 0.5), abs(cy - 0.5))
                if imbalance > 0.22:
                    score -= min(18, imbalance * 45)
                    slide_issues.append("渲染后视觉重心偏移")
            # Low contrast often shows up as low variance while not blank.
            if 20 <= variance < 120 and ink_ratio >= 0.05:
                score -= 10
                slide_issues.append("渲染后灰度对比偏低，投影可读性需复核")

            score = round(max(0.0, min(100.0, score)), 1)
            if slide_issues:
                issues.extend(f"第{idx}页：{issue}" for issue in slide_issues[:3])
            slide_scores.append({
                "slide_id": idx,
                "score": score,
                "ink_ratio": round(ink_ratio, 4),
                "edge_ink_ratio": round(edge_ratio, 4),
                "variance": round(variance, 1),
                "issues": slide_issues,
            })

    overall = round(mean(s["score"] for s in slide_scores), 1) if slide_scores else 0
    return {
        "rendered": True,
        "overall_score": overall,
        "passed": overall >= 72 and all(s["score"] >= 60 for s in slide_scores),
        "slide_count": len(slide_scores),
        "worst_slides": [s["slide_id"] for s in sorted(slide_scores, key=lambda x: x["score"])[:5] if s["score"] < 72],
        "issues": issues[:12],
        "slides": slide_scores,
    }


def render_pptx_to_images(pptx_path: str, workdir: str | None = None) -> tuple[list[str], list[str]]:
    """Render a PPTX to PNG images using local offline tooling when available."""
    issues: list[str] = []
    out_dir = Path(workdir or tempfile.mkdtemp(prefix="ppt-render-qa-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        return [], ["未找到LibreOffice/soffice，跳过真实渲染图像QA"]

    try:
        subprocess.run(
            [office, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except Exception as exc:
        return [], [f"PPTX转PDF失败，无法执行真实渲染图像QA: {exc}"]

    pdfs = sorted(out_dir.glob("*.pdf"))
    if not pdfs:
        return [], ["PPTX转PDF未生成文件，无法执行真实渲染图像QA"]
    pdf_path = pdfs[0]

    # Preferred: PyMuPDF if present.
    try:
        import fitz  # type: ignore
        doc = fitz.open(str(pdf_path))
        images = []
        for page_idx in range(len(doc)):
            pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            img_path = out_dir / f"slide-{page_idx + 1:03d}.png"
            pix.save(str(img_path))
            images.append(str(img_path))
        doc.close()
        return images, issues
    except Exception:
        pass

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        prefix = out_dir / "slide"
        try:
            subprocess.run(
                [pdftoppm, "-png", "-r", "144", str(pdf_path), str(prefix)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            return [str(p) for p in sorted(out_dir.glob("slide-*.png"))], issues
        except Exception as exc:
            return [], [f"PDF转PNG失败，无法执行真实渲染图像QA: {exc}"]

    return [], ["缺少PyMuPDF或pdftoppm，已生成PDF但无法转为图像QA输入"]


def score_pptx_rendered(pptx_path: str) -> dict:
    """Render a PPTX and run image-level QA. Never raises."""
    try:
        with tempfile.TemporaryDirectory(prefix="ppt-render-qa-") as tmp:
            images, render_issues = render_pptx_to_images(pptx_path, tmp)
            if not images:
                return {
                    "rendered": False,
                    "overall_score": None,
                    "passed": None,
                    "issues": render_issues,
                    "slides": [],
                }
            result = score_rendered_images(images)
            result["issues"] = render_issues + result.get("issues", [])
            return result
    except Exception as exc:
        logger.warning("[PPTRenderQA] failed: %s", exc)
        return {
            "rendered": False,
            "overall_score": None,
            "passed": None,
            "issues": [f"图像级QA异常: {exc}"],
            "slides": [],
        }


def combine_ppt_quality(geometry: dict, render_visual: dict) -> dict:
    """Combine geometry and rendered-image QA into one delivery metric."""
    geo_score = float(geometry.get("overall_score") or 0)
    visual_rendered = render_visual.get("rendered") is True
    if visual_rendered:
        visual_score = float(render_visual.get("overall_score") or 0)
        overall = round(geo_score * 0.45 + visual_score * 0.55, 1)
        passed = geo_score >= 68 and visual_score >= 72 and overall >= 72
    else:
        overall = round(geo_score, 1)
        passed = geo_score >= 70

    issues = []
    issues.extend(geometry.get("global_issues") or [])
    issues.extend(render_visual.get("issues") or [])
    return {
        "overall_score": overall,
        "passed": passed,
        "grade": geometry.get("grade"),
        "slide_count": geometry.get("slide_count") or render_visual.get("slide_count"),
        "worst_slides": sorted(set((geometry.get("worst_slides") or []) + (render_visual.get("worst_slides") or [])))[:8],
        "geometry_score": geo_score,
        "geometry_qa": geometry,
        "render_visual_score": render_visual.get("overall_score"),
        "render_visual_qa": render_visual,
        "global_issues": issues[:16],
    }
