"""GitHub repository cloner — clone selected repos and extract documentation.

Clones repos shallowly, extracts README + docs + source code comments.
Stores as Markdown for ingestion.

Usage:
    python download_git.py kb_025
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from base import DownloaderBase
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.git")


class GitDownloader(DownloaderBase):
    """Clone GitHub repos and extract readable content."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        repos = self.config.extra.get("repos", [])
        if not repos:
            return {"kb_id": self.kb_id, "downloaded": 0, "error": "No repos configured"}

        cloned = 0
        for repo in repos:
            try:
                self._clone_and_extract(repo)
                cloned += 1
            except Exception as exc:
                logger.error("[git] Failed %s: %s", repo, exc)
                self.progress.log_error(repo, str(exc))

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "cloned": cloned, "repos": repos}

    def _clone_and_extract(self, repo: str) -> None:
        """Clone a repo and extract ALL source code + docs into markdown files."""
        if self.progress.is_file_done(repo):
            logger.info("[git] Skipping already cloned: %s", repo)
            return

        repo_name = repo.replace("/", "_")
        clone_dir = self.output_dir / "_clones" / repo_name
        clone_dir.parent.mkdir(parents=True, exist_ok=True)

        # Shallow clone
        if not clone_dir.exists():
            logger.info("[git] Cloning %s...", repo)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(clone_dir)],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git clone failed: {result.stderr}")

        # Extract ALL text files from the repo (code + docs + config)
        text_extensions = {
            ".md", ".rst", ".txt", ".py", ".js", ".ts", ".jsx", ".tsx",
            ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp", ".cs",
            ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".m", ".mm",
            ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
            ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf",
            ".sql", ".html", ".css", ".scss", ".less", ".vue", ".svelte",
            ".dockerfile", ".makefile", ".cmake", ".gradle", ".xml",
            ".pl", ".pm", ".lua", ".nim", ".dart", ".erl", ".ex", ".exs",
            ".hs", ".lhs", ".clj", ".cljs", ".elm", ".fs", ".fsx",
            ".v", ".sv", ".vhd", ".vhdl", ".tf", ".tfvars",
        }
        skip_dirs = {".git", "node_modules", "vendor", "target", "build", "dist", ".idea", ".vscode", "__pycache__"}

        total_chars = 0
        files_saved = 0
        for root, dirs, files in os.walk(clone_dir):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() not in text_extensions:
                    continue
                try:
                    size = fpath.stat().st_size
                    if size > 2_000_000:  # Skip files > 2MB
                        continue
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    if len(content) < 10:
                        continue
                    rel = fpath.relative_to(clone_dir)
                    safe_rel = str(rel).replace("/", "_").replace("\\", "_")
                    if len(safe_rel) > 200:
                        safe_rel = safe_rel[:200]

                    out_filename = f"doc_{repo_name}_{safe_rel}.md"
                    md_content = f"# {repo} / {rel}\n\n```\n{content}\n```\n"
                    self.save_text(out_filename, md_content, metadata={
                        "repo": repo,
                        "file": str(rel),
                        "source": f"https://github.com/{repo}/blob/main/{rel}",
                    })
                    total_chars += len(content)
                    files_saved += 1
                except Exception:
                    pass

        self.progress.mark_file_done(repo, f"{repo_name}_{files_saved}files", total_chars)
        logger.info("[git] Extracted %s: %d files, %d chars", repo, files_saved, total_chars)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_git.py <kb_id>")
        print("Example: kb_025 (GitHub repos)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with GitDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
