"""Government data downloader — 国务院政府工作报告、统计局公报、央行报告等.

Handles Chinese government websites with polite delays and retry logic.
Output: Markdown files with YAML frontmatter metadata.
"""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

from base import DownloaderBase, html_to_markdown
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.gov")


class GovWorkReportDownloader(DownloaderBase):
    """Download State Council Government Work Reports (2020-2026)."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        start_year, end_year = self.config.time_range
        downloaded = 0

        for year in range(start_year, end_year + 1):
            if year > 2026:
                break
            url = f"https://www.gov.cn/premier/{year-1}-{year % 100 + 1}/03/05/content_{year}.htm"
            # Actual URL pattern varies; use search-based approach
            try:
                result = self._fetch_report(year)
                if result:
                    downloaded += 1
            except Exception as exc:
                logger.error("[gov] Failed to fetch %d report: %s", year, exc)
                self.progress.log_error(url, str(exc))

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded, "target_years": end_year - start_year + 1}

    # Known government work report URLs (gov.cn uses article IDs, not year-based URLs)
    KNOWN_REPORTS = {
        2020: "https://www.gov.cn/premier/2020-03/05/content_5489146.htm",
        2021: "https://www.gov.cn/premier/2021-03/05/content_5592689.htm",
        2022: "https://www.gov.cn/premier/2022-03/05/content_5676331.htm",
        2023: "https://www.gov.cn/premier/2023-03/05/content_5745078.htm",
        2024: "https://www.gov.cn/premier/2024-03/05/content_6939576.htm",
        2025: "https://www.gov.cn/premier/2025-03/05/content_6943270.htm",
    }

    def _fetch_report(self, year: int) -> bool:
        """Fetch a single year's government work report."""
        if year < 2020 or year > 2026:
            logger.debug("[gov] Skipping year %d", year)
            return True

        url = self.KNOWN_REPORTS.get(year)
        if not url:
            logger.warning("[gov] No known URL for year %d", year)
            return False

        if self.progress.is_file_done(url):
            logger.info("[gov] Skipping already downloaded: %d", year)
            return True

        try:
            resp = self.fetch(url)
            html = resp.text
            title_match = re.search(r"<title>(.*?)</title>", html, re.I)
            title = title_match.group(1).strip() if title_match else f"政府工作报告 {year}"

            md = html_to_markdown(html)
            if len(md) < 500:
                logger.warning("[gov] Content too short for %d, skipping", year)
                return False

            filename = f"doc_{year:04d}_{year}_政府工作报告.md"
            self.save_text(filename, md, metadata={
                "title": title,
                "year": year,
                "source": url,
                "category": "政府工作报告",
            })
            self.progress.mark_file_done(url, str(self.output_dir / filename), len(md))
            logger.info("[gov] Downloaded %d report (%d chars)", year, len(md))
            return True
        except Exception as exc:
            logger.error("[gov] Failed to fetch %d: %s", year, exc)
            self.progress.log_error(url, str(exc))
            return False


class StatsDownloader(DownloaderBase):
    """Download National Bureau of Statistics reports."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        # Annual statistical communiques
        start_year, end_year = self.config.time_range
        downloaded = 0

        for year in range(start_year, end_year + 1):
            url = f"https://www.stats.gov.cn/sj/zxfb/202403/t20240301_{year}.html"
            if self.progress.is_file_done(url):
                continue
            try:
                resp = self.fetch(url)
                md = html_to_markdown(resp.text)
                if len(md) < 200:
                    continue
                filename = f"doc_{year:04d}_统计公报.md"
                self.save_text(filename, md, metadata={"year": year, "source": url})
                self.progress.mark_file_done(url, str(self.output_dir / filename), len(md))
                downloaded += 1
            except Exception as exc:
                logger.error("[stats] %d: %s", year, exc)
                self.progress.log_error(url, str(exc))

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}


class PBCMonetaryDownloader(DownloaderBase):
    """Download PBOC Monetary Policy Execution Reports (quarterly)."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        start_year, end_year = self.config.time_range
        downloaded = 0

        for year in range(start_year, end_year + 1):
            for quarter in range(1, 5):
                url = (
                    f"https://www.pbc.gov.cn/zhengcehuobisi/"
                    f"11140/11199/21648/index{year}_{quarter}.html"
                )
                if self.progress.is_file_done(url):
                    continue
                try:
                    resp = self.fetch(url)
                    md = html_to_markdown(resp.text)
                    if len(md) < 500:
                        continue
                    filename = f"doc_{year}Q{quarter}_货币政策报告.md"
                    self.save_text(filename, md, metadata={
                        "year": year, "quarter": quarter, "source": url,
                    })
                    self.progress.mark_file_done(url, str(self.output_dir / filename), len(md))
                    downloaded += 1
                except Exception as exc:
                    logger.error("[pbc] %dQ%d: %s", year, quarter, exc)
                    self.progress.log_error(url, str(exc))

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}


class GenericWebCrawler(DownloaderBase):
    """Generic crawler for law/policy/intl sites. Fetches landing page + linked pages."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        downloaded = 0
        base_url = self.config.source_url

        # Fetch base page
        try:
            resp = self.fetch(base_url)
            html = resp.text
            md = html_to_markdown(html)
            if len(md) > 200:
                self.save_text("doc_index.md", md, metadata={"source": base_url, "type": "index"})
                self.progress.mark_file_done(base_url, str(self.output_dir / "doc_index.md"), len(md))
                downloaded += 1
        except Exception as exc:
            logger.error("[crawl] Base page failed %s: %s", base_url, exc)
            self.progress.log_error(base_url, str(exc))

        # Extract links and follow a few
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http"):
                    links.append(href)
                elif href.startswith("/"):
                    from urllib.parse import urljoin
                    links.append(urljoin(base_url, href))

            # Deduplicate and limit
            seen = set()
            unique_links = []
            for link in links:
                if link not in seen and link != base_url:
                    seen.add(link)
                    unique_links.append(link)

            # Follow up to 30 links
            for link in unique_links[:30]:
                if self.progress.is_file_done(link):
                    continue
                try:
                    resp = self.fetch(link)
                    md = html_to_markdown(resp.text)
                    if len(md) > 500:
                        url_hash = link.replace("/", "_").replace(":", "")[:40]
                        filename = f"doc_{url_hash}.md"
                        self.save_text(filename, md, metadata={"source": link})
                        self.progress.mark_file_done(link, str(self.output_dir / filename), len(md))
                        downloaded += 1
                except Exception:
                    pass
        except Exception as exc:
            logger.error("[crawl] Link extraction failed: %s", exc)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}


# ── CLI entrypoint ──────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_gov.py <kb_id>")
        print("Examples: kb_001 (政府工作报告), kb_003 (统计公报), kb_004 (央行报告)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    dispatch = {
        "kb_001": GovWorkReportDownloader,
        "kb_003": StatsDownloader,
        "kb_004": PBCMonetaryDownloader,
        "kb_005": GenericWebCrawler,
        "kb_006": GenericWebCrawler,
        "kb_007": GenericWebCrawler,
        "kb_008": GenericWebCrawler,
        "kb_009": GenericWebCrawler,
        "kb_010": GenericWebCrawler,
        "kb_011": GenericWebCrawler,
        "kb_035": GenericWebCrawler,
        "kb_036": GenericWebCrawler,
        "kb_037": GenericWebCrawler,
        "kb_038": GenericWebCrawler,
    }

    cls = dispatch.get(kb_id, GenericWebCrawler)
    with cls(config) as dl:
        result = dl.run()
        print(result)


def get_downloader(config):
    """Return the appropriate downloader class for a given config. Used by master_scheduler."""
    dispatch = {
        "kb_001": GovWorkReportDownloader,
        "kb_003": StatsDownloader,
        "kb_004": PBCMonetaryDownloader,
        "kb_005": GenericWebCrawler,
        "kb_006": GenericWebCrawler,
        "kb_007": GenericWebCrawler,
        "kb_008": GenericWebCrawler,
        "kb_009": GenericWebCrawler,
        "kb_010": GenericWebCrawler,
        "kb_011": GenericWebCrawler,
        "kb_035": GenericWebCrawler,
        "kb_036": GenericWebCrawler,
        "kb_037": GenericWebCrawler,
        "kb_038": GenericWebCrawler,
    }
    cls = dispatch.get(config.kb_id, GenericWebCrawler)
    return cls(config)


if __name__ == "__main__":
    main()
