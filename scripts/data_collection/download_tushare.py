"""Tushare Pro financial data downloader.

Downloads A-share / HK / fund / macro data via Tushare Pro API.
Requires: tushare>=1.2.0, pandas

Usage:
    python download_tushare.py kb_039   # A股行情
    python download_tushare.py kb_040   # 宏观经济
    python download_tushare.py kb_041   # 基金数据
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from base import DownloaderBase
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.tushare")

# Lazy import tushare to avoid hard dependency
try:
    import tushare as ts
    _TUSHARE_AVAILABLE = True
except ImportError:
    _TUSHARE_AVAILABLE = False

TUSHARE_TOKEN = os.environ.get("TUSHARE_PRO_TOKEN", "")
REQUEST_DELAY = 0.2  # seconds between API calls (5 QPS max)


def _get_pro():
    """Get initialized Tushare Pro interface."""
    if not _TUSHARE_AVAILABLE:
        raise ImportError("tushare not installed. Run: pip install tushare pandas")
    if not TUSHARE_TOKEN:
        raise ValueError("TUSHARE_PRO_TOKEN not set in environment")
    pro = ts.pro_api(TUSHARE_TOKEN)
    return pro


class TushareStockDownloader(DownloaderBase):
    """Download A-share stock daily prices and basic info."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        pro = _get_pro()
        downloaded = 0

        # 1. Stock basics
        logger.info("[tushare] Fetching stock basics...")
        try:
            df_basic = pro.stock_basic(exchange="", list_status="L")
            self._save_df("stock_basic", df_basic, "A股基础信息")
            downloaded += 1
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            logger.error("[tushare] stock_basic failed: %s", exc)
            self.progress.log_error("stock_basic", str(exc))

        # 2. Daily prices for top 500 stocks by market cap (2020-2026)
        logger.info("[tushare] Fetching daily prices...")
        ts_codes = df_basic["ts_code"].head(500).tolist() if "df_basic" in dir() else []
        price_count = 0

        for ts_code in ts_codes[:200]:  # Limit to top 200 for speed
            if self.progress.is_file_done(f"daily_{ts_code}"):
                continue
            try:
                df = pro.daily(ts_code=ts_code, start_date="20200101", end_date="20260604")
                if not df.empty:
                    self._save_df(f"daily_{ts_code}", df, f"{ts_code} 日线行情")
                    self.progress.mark_file_done(f"daily_{ts_code}", ts_code, len(df))
                    price_count += 1
                time.sleep(REQUEST_DELAY)
            except Exception as exc:
                logger.debug("[tushare] daily %s failed: %s", ts_code, exc)
                # Continue with next stock

        downloaded += price_count

        # 3. Index data (上证指数、深证成指、创业板指)
        logger.info("[tushare] Fetching index data...")
        indices = ["000001.SH", "399001.SZ", "399006.SZ"]
        for idx_code in indices:
            try:
                df = pro.index_daily(ts_code=idx_code, start_date="20200101", end_date="20260604")
                if not df.empty:
                    self._save_df(f"index_{idx_code}", df, f"{idx_code} 指数行情")
                    downloaded += 1
                time.sleep(REQUEST_DELAY)
            except Exception as exc:
                logger.error("[tushare] index %s failed: %s", idx_code, exc)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _save_df(self, name: str, df: pd.DataFrame, title: str) -> None:
        """Save a DataFrame as Markdown table + CSV."""
        # Save as CSV
        csv_path = self.output_dir / f"{name}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        # Save as Markdown (sample first 100 rows)
        md_content = f"# {title}\n\n"
        md_content += f"Total rows: {len(df)} | Columns: {', '.join(df.columns)}\n\n"
        md_content += df.head(100).to_markdown(index=False)
        if len(df) > 100:
            md_content += f"\n\n... ({len(df) - 100} more rows)\n"

        filename = f"doc_{name}.md"
        self.save_text(filename, md_content, metadata={
            "title": title,
            "rows": len(df),
            "columns": list(df.columns),
            "csv_file": str(csv_path),
        })


class TushareMacroDownloader(DownloaderBase):
    """Download macroeconomic indicators."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        pro = _get_pro()
        downloaded = 0

        macro_indicators = [
            ("gdp", "GDP季度数据", {"start_q": "2020Q1", "end_q": "2026Q2"}),
            ("cpi", "CPI月度数据", {"start_m": "202001", "end_m": "202606"}),
            ("ppi", "PPI月度数据", {"start_m": "202001", "end_m": "202606"}),
            ("m_m", "货币供应量", {"start_m": "202001", "end_m": "202606"}),
        ]

        for indicator, title, kwargs in macro_indicators:
            try:
                method = getattr(pro, indicator)
                df = method(**kwargs)
                if not df.empty:
                    self._save_df(indicator, df, title)
                    downloaded += 1
                time.sleep(REQUEST_DELAY)
            except Exception as exc:
                logger.error("[tushare] %s failed: %s", indicator, exc)
                self.progress.log_error(indicator, str(exc))

        # CNBS macro data (macro_cnbs)
        try:
            df = pro.cnbs(start_m="202001", end_m="202606")
            if not df.empty:
                self._save_df("cnbs", df, "国家资产负债表")
                downloaded += 1
        except Exception as exc:
            logger.error("[tushare] cnbs failed: %s", exc)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _save_df(self, name: str, df: pd.DataFrame, title: str) -> None:
        csv_path = self.output_dir / f"{name}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        md_content = f"# {title}\n\n"
        md_content += f"Total rows: {len(df)}\n\n"
        md_content += df.to_markdown(index=False)

        filename = f"doc_{name}.md"
        self.save_text(filename, md_content, metadata={
            "title": title, "rows": len(df), "csv_file": str(csv_path),
        })


class TushareFundDownloader(DownloaderBase):
    """Download mutual fund NAV and basic info."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        pro = _get_pro()
        downloaded = 0

        # Fund basics
        try:
            df = pro.fund_basic(market="E")
            self._save_df("fund_basic", df, "公募基金基础信息")
            downloaded += 1
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            logger.error("[tushare] fund_basic failed: %s", exc)

        # Fund NAV for top funds
        try:
            df_funds = pro.fund_basic(market="E")
            fund_codes = df_funds["ts_code"].head(100).tolist() if not df_funds.empty else []
            nav_count = 0
            for fund_code in fund_codes[:50]:
                try:
                    df = pro.fund_nav(ts_code=fund_code, start_date="20200101", end_date="20260604")
                    if not df.empty:
                        self._save_df(f"nav_{fund_code}", df, f"{fund_code} 基金净值")
                        nav_count += 1
                    time.sleep(REQUEST_DELAY)
                except Exception:
                    pass
            downloaded += nav_count
        except Exception as exc:
            logger.error("[tushare] fund_nav batch failed: %s", exc)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _save_df(self, name: str, df: pd.DataFrame, title: str) -> None:
        csv_path = self.output_dir / f"{name}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        md_content = f"# {title}\n\nTotal rows: {len(df)}\n\n{df.head(200).to_markdown(index=False)}"
        if len(df) > 200:
            md_content += f"\n\n... ({len(df) - 200} more rows)\n"
        self.save_text(f"doc_{name}.md", md_content, metadata={"title": title, "rows": len(df)})


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_tushare.py <kb_id>")
        print("Examples: kb_039 (A股行情), kb_040 (宏观经济), kb_041 (基金数据)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    dispatch = {
        "kb_039": TushareStockDownloader,
        "kb_040": TushareMacroDownloader,
        "kb_041": TushareFundDownloader,
    }

    cls = dispatch.get(kb_id, TushareStockDownloader)
    with cls(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
