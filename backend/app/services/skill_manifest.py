"""SkillManifest — Pydantic schema for structured skill file validation.

SOTA gap closed: baseline skill loader (`pipeline/skills_loader.py`) treated
SKILL.md files as unvalidated markdown blobs. A skill with malformed YAML
frontmatter or missing required fields would load silently with truncated
context, producing inscrutable downstream failures.

This module:

  1. Defines a Pydantic schema for SKILL.md frontmatter
  2. Parses + validates frontmatter on load
  3. Provides a clean accessor that returns (manifest, body) tuple
  4. Caches parsed manifests so we don't re-parse on every retrieval
  5. Surfaces validation errors to the caller (instead of silent skip)

Expected SKILL.md format::

    ---
    name: my-skill
    version: 1.2
    type: writing          # one of: writing, charting, table, qa, planning, retrieval
    phase: spec_gen        # one of: understand, plan, research, spec_gen, qa
    description: ...
    inputs:
      - {name: brief, type: string}
    outputs:
      - {name: content, type: markdown}
    ---

    # SKILL: My Skill
    ... markdown content ...
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator
except ImportError:  # graceful degradation if pydantic missing
    BaseModel = object  # type: ignore
    Field = lambda *args, **kwargs: None  # type: ignore
    ValidationError = Exception  # type: ignore
    field_validator = lambda *args, **kwargs: (lambda fn: fn)  # type: ignore

import os

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas (only used if pydantic is installed — graceful degradation)
# ─────────────────────────────────────────────────────────────────────────────

class _SkillIO(BaseModel):
    """One input/output declaration."""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True


class SkillManifest(BaseModel):
    """Validated skill frontmatter — the canonical schema for SKILL.md files."""

    name: str = Field(..., min_length=1, max_length=80)
    version: str = "1.0"
    type: Literal[
        "writing", "charting", "table", "qa", "planning",
        "retrieval", "data_analysis", "review", "general",
    ] = "general"
    phase: Literal[
        "understand", "plan", "research", "spec_gen", "doc_render", "qa", "any",
    ] = "any"
    description: str = ""
    inputs: list[_SkillIO] = Field(default_factory=list)
    outputs: list[_SkillIO] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.]*$", v):
            raise ValueError(f"Invalid skill name: {v!r} (must start alphanumeric, "
                             f"contain only letters/digits/_/-/.)")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ParsedSkill:
    """Parsed SKILL.md = manifest (validated frontmatter) + body (markdown)."""
    manifest: SkillManifest | None
    body: str
    raw_frontmatter: dict = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)
    file_path: str = ""

    @property
    def is_valid(self) -> bool:
        return self.manifest is not None and not self.validation_errors


def parse_skill_md(text: str, file_path: str = "") -> ParsedSkill:
    """Parse a SKILL.md document into validated manifest + body.

    If frontmatter is missing or invalid:
      - body still returned as the full text
      - manifest is None
      - validation_errors list populated for caller logging

    Never raises — caller can decide whether to use invalid skills.
    """
    if not text:
        return ParsedSkill(manifest=None, body="", file_path=file_path,
                           validation_errors=["empty file"])

    frontmatter: dict = {}
    body = text
    validation_errors: list[str] = []

    # Extract YAML frontmatter (between leading --- and second ---)
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if m:
            raw_yaml = m.group(1)
            body = text[m.end():].strip()
            try:
                import yaml
                frontmatter = yaml.safe_load(raw_yaml) or {}
                if not isinstance(frontmatter, dict):
                    validation_errors.append(f"frontmatter is not a mapping: got {type(frontmatter).__name__}")
                    frontmatter = {}
            except Exception as exc:
                validation_errors.append(f"YAML parse error: {exc}")
                frontmatter = {}

    # Infer name from file path if not provided
    if "name" not in frontmatter and file_path:
        stem = Path(file_path).parent.name or Path(file_path).stem
        if stem:
            frontmatter["name"] = stem

    # Validate via Pydantic
    manifest: SkillManifest | None = None
    if frontmatter:
        try:
            manifest = SkillManifest(**frontmatter)
        except ValidationError as exc:
            # Collect every individual field error
            try:
                for err in exc.errors():
                    loc = ".".join(str(p) for p in err.get("loc", []))
                    msg = err.get("msg", str(err))
                    validation_errors.append(f"{loc}: {msg}")
            except Exception:
                validation_errors.append(str(exc))
        except Exception as exc:
            validation_errors.append(f"manifest validation: {exc}")

    return ParsedSkill(
        manifest=manifest,
        body=body,
        raw_frontmatter=frontmatter,
        validation_errors=validation_errors,
        file_path=file_path,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Filesystem loader with caching
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=128)
def load_and_validate_skill(skill_name: str, base_dir: str | None = None) -> ParsedSkill:
    """Load a skill by name from the filesystem and validate it.

    Resolution order:
      1. {base_dir}/{skill_name}/SKILL.md
      2. fuzzy match (strip "custom-user-" prefix, normalize hyphens)

    Results are cached for repeat lookups in the same process. Use
    `clear_skill_cache()` after editing skill files in-place.
    """
    if base_dir is None:
        # Match the existing skills_loader default
        this_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.join(this_dir, "prompt_assets", "skills")

    candidates = [
        os.path.join(base_dir, skill_name, "SKILL.md"),
        os.path.join(base_dir, skill_name.replace("custom-user-", "").split("-")[0], "SKILL.md"),
    ]

    for path in candidates:
        if os.path.isfile(path):
            try:
                # Use smart encoding detection if available
                try:
                    from app.services.file_parser import read_text_file_smart
                    text = read_text_file_smart(path)
                except Exception:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                return parse_skill_md(text, file_path=path)
            except Exception as exc:
                return ParsedSkill(
                    manifest=None,
                    body="",
                    file_path=path,
                    validation_errors=[f"file read error: {exc}"],
                )

    # Fuzzy fallback
    try:
        if os.path.isdir(base_dir):
            needle = skill_name.replace("custom-user-", "").replace("-", "").lower()
            for d in os.listdir(base_dir):
                if needle and needle in d.replace("-", "").lower():
                    path = os.path.join(base_dir, d, "SKILL.md")
                    if os.path.isfile(path):
                        try:
                            from app.services.file_parser import read_text_file_smart
                            text = read_text_file_smart(path)
                        except Exception:
                            with open(path, "r", encoding="utf-8", errors="replace") as f:
                                text = f.read()
                        return parse_skill_md(text, file_path=path)
    except Exception:
        pass

    return ParsedSkill(
        manifest=None,
        body="",
        file_path="",
        validation_errors=[f"skill not found: {skill_name}"],
    )


def clear_skill_cache() -> None:
    """Force re-read of skill files (call after editing SKILL.md in dev)."""
    load_and_validate_skill.cache_clear()


# ─────────────────────────────────────────────────────────────────────────────
# Discovery + audit
# ─────────────────────────────────────────────────────────────────────────────

def discover_all_skills(base_dir: str | None = None) -> list[ParsedSkill]:
    """Walk the skills directory and return validated manifests for all skills.

    Useful for the admin UI (list skills with validation status), for the QA
    audit step (warn if any installed skill is broken), and for the docs
    generator.
    """
    if base_dir is None:
        this_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.join(this_dir, "prompt_assets", "skills")

    skills: list[ParsedSkill] = []
    if not os.path.isdir(base_dir):
        return skills

    for entry in sorted(os.listdir(base_dir)):
        skill_dir = os.path.join(base_dir, entry)
        if not os.path.isdir(skill_dir):
            continue
        skill_file = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(skill_file):
            continue
        parsed = load_and_validate_skill(entry, base_dir=base_dir)
        skills.append(parsed)

    return skills


def audit_skills(base_dir: str | None = None) -> dict:
    """One-shot health check over all skills — returns a summary.

    Output shape::

        {
          "total": 12,
          "valid": 10,
          "invalid": 2,
          "issues": [{"skill": "foo", "errors": [...]}, ...]
        }
    """
    all_skills = discover_all_skills(base_dir)
    issues = []
    for s in all_skills:
        if not s.is_valid:
            issues.append({
                "skill": Path(s.file_path).parent.name if s.file_path else "?",
                "errors": s.validation_errors,
            })

    return {
        "total": len(all_skills),
        "valid": sum(1 for s in all_skills if s.is_valid),
        "invalid": len(issues),
        "issues": issues,
    }
