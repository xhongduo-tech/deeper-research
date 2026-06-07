"""Skill markdown loader for pipeline phases. Ported from simple_pipeline.py."""
from __future__ import annotations

import os
import re
import logging

logger = logging.getLogger(__name__)

# Locate the skills directory relative to this file
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_BASE_DIR = os.path.normpath(
    os.path.join(_THIS_DIR, "..", "prompt_assets", "skills")
)


def load_skill_md(skill_name: str) -> str:
    """Load a SKILL.md file from prompt_assets/skills/{skill_name}/."""
    paths_to_try = [
        os.path.join(_SKILL_BASE_DIR, skill_name, "SKILL.md"),
        os.path.join(_SKILL_BASE_DIR, skill_name.replace("custom-user-", "").split("-")[0], "SKILL.md"),
    ]
    for p in paths_to_try:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as exc:
                logger.warning("Failed to read skill %s: %s", skill_name, exc)
    # Fuzzy match fallback
    try:
        if os.path.isdir(_SKILL_BASE_DIR):
            needle = skill_name.replace("custom-user-", "").replace("-", "")
            for d in os.listdir(_SKILL_BASE_DIR):
                if needle in d.replace("-", ""):
                    p = os.path.join(_SKILL_BASE_DIR, d, "SKILL.md")
                    if os.path.isfile(p):
                        with open(p, "r", encoding="utf-8") as f:
                            return f.read()
    except Exception:
        pass
    return ""


def strip_yaml_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def extract_skills_from_brief(brief: str) -> list[str]:
    """Parse skill names from the user brief (e.g. 'Skill 栈：a、b、c')."""
    if not brief:
        return []
    m = re.search(r"[Ss]kill[\s栈:：]*([^\n]+)", brief)
    if m:
        raw = m.group(1).strip()
        names = [n.strip() for n in re.split(r"[、,，;；|/\s]+", raw) if n.strip()]
        return [n for n in names if len(n) > 2 and not n.startswith("参考") and not n.startswith("上传")]
    return []


def build_skill_context(skill_names: list[str]) -> str:
    """Build combined skill context for LLM system prompts.

    Uses the validating loader when available (logs frontmatter errors but does
    not block loading — broken skills still contribute their markdown body so
    behavior is backward-compatible with unvalidated SKILL.md files).
    """
    # Try the validating loader first
    try:
        from app.services.skill_manifest import load_and_validate_skill
        contexts = []
        for name in skill_names:
            parsed = load_and_validate_skill(name)
            if not parsed.body and parsed.validation_errors:
                logger.warning(
                    "Skill %s could not be loaded: %s",
                    name, "; ".join(parsed.validation_errors[:3]),
                )
                continue
            if parsed.validation_errors:
                # Frontmatter is broken but body is usable — log warning, keep going
                logger.warning(
                    "Skill %s has invalid frontmatter (will use body anyway): %s",
                    name, "; ".join(parsed.validation_errors[:2]),
                )
            content = parsed.body
            if len(content) > 6000:
                content = content[:6000] + "\n\n... [skill content truncated]"
            # If we have a valid manifest, prefer the canonical name
            display_name = (parsed.manifest.name if parsed.manifest else name)
            contexts.append(f"## Skill: {display_name}\n\n{content}")
        return "\n\n---\n\n".join(contexts) if contexts else ""
    except Exception as exc:
        logger.debug("Validating loader unavailable, using legacy path: %s", exc)

    # Legacy path (preserved for safety)
    contexts = []
    for name in skill_names:
        md = load_skill_md(name)
        if md:
            content = strip_yaml_frontmatter(md)
            if len(content) > 6000:
                content = content[:6000] + "\n\n... [skill content truncated]"
            contexts.append(f"## Skill: {name}\n\n{content}")
    return "\n\n---\n\n".join(contexts) if contexts else ""


def filter_skills_for_phase(skill_names: list[str], phase: str) -> list[str]:
    """Return only the skills relevant to a given pipeline phase."""
    phase_keywords = {
        "understand": ["intake", "planner", "grounding"],
        "plan":       ["chief", "planner", "grounding", "style", "miner"],
        "spec_gen":   ["authoring", "writing", "figure", "table", "citation",
                       "bibliography", "charting", "chart", "excel", "ppt"],
        "qa":         ["qa", "verify", "verification"],
    }
    keywords = phase_keywords.get(phase, [])
    if not keywords:
        return skill_names
    result = []
    for s in skill_names:
        s_lower = s.lower()
        if any(kw in s_lower for kw in keywords):
            result.append(s)
    return result or skill_names
