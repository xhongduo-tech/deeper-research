#!/usr/bin/env python3
"""Check offline PPT render QA dependencies inside the backend runtime."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess


def _cmd_version(cmd: str, *args: str) -> str:
    path = shutil.which(cmd)
    if not path:
        return ""
    try:
        env = os.environ.copy()
        env.setdefault("HOME", "/tmp")
        env.setdefault("XDG_CACHE_HOME", "/tmp/.cache")
        env.setdefault("XDG_CONFIG_HOME", "/tmp/.config")
        result = subprocess.run(
            [path, *(args or ("--version",))],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=8,
            env=env,
        )
        lines = [
            line.strip()
            for line in (result.stdout or "").splitlines()
            if line.strip() and "dconf-" not in line and "dconf will not work properly" not in line
        ]
        return lines[0] if lines else path
    except Exception:
        return path


def main() -> int:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdftoppm = shutil.which("pdftoppm")
    pandoc = shutil.which("pandoc")
    checks = {
        "soffice": {
            "ok": bool(soffice),
            "path": soffice or "",
            "version": _cmd_version("soffice") if shutil.which("soffice") else _cmd_version("libreoffice"),
        },
        "pdftoppm": {
            "ok": bool(pdftoppm),
            "path": pdftoppm or "",
            "version": _cmd_version("pdftoppm", "-v"),
        },
        "pymupdf": {
            "ok": importlib.util.find_spec("fitz") is not None,
        },
        "pillow": {
            "ok": importlib.util.find_spec("PIL") is not None,
        },
        "python_pptx": {
            "ok": importlib.util.find_spec("pptx") is not None,
        },
        "pandoc": {
            "ok": bool(pandoc),
            "path": pandoc or "",
            "version": _cmd_version("pandoc"),
        },
        "duckdb": {
            "ok": importlib.util.find_spec("duckdb") is not None,
        },
        "polars": {
            "ok": importlib.util.find_spec("polars") is not None,
        },
        "pyarrow": {
            "ok": importlib.util.find_spec("pyarrow") is not None,
        },
        "vl_convert": {
            "ok": importlib.util.find_spec("vl_convert") is not None,
        },
    }
    checks["render_image_qa_ready"] = all(
        checks[name]["ok"] for name in ("soffice", "pymupdf", "pillow", "python_pptx")
    ) or all(
        checks[name]["ok"] for name in ("soffice", "pdftoppm", "pillow", "python_pptx")
    )
    checks["advanced_data_runtime_ready"] = all(
        checks[name]["ok"] for name in ("duckdb", "polars", "pyarrow")
    )
    checks["format_conversion_ready"] = checks["soffice"]["ok"] and checks["pandoc"]["ok"]
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["render_image_qa_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
