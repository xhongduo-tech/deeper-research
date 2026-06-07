"""Financial data downloader using AkShare (primary) + Tushare (fallback).

AkShare is free, open-source, and requires no API token.
Tushare is used as fallback when AkShare fails.

Usage:
    python download_finance.py kb_039   # A-share market data
    python download_finance.py kb_040   # Macro economy
    python download_finance.py kb_041   # Fund NAV
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

logger = logging.getLogger("data_collection.finance")

REQUEST_DELAY = 1.5  # seconds between AkShare calls (be polite)

try:
    import akshare as ak
    _AKSHARE_AVAILABLE = True
except ImportError:
    _AKSHARE_AVAILABLE = False

try:
    import tushare as ts
    _TUSHARE_AVAILABLE = True
    tushare_token = os.environ.get("TUSHARE_PRO_TOKEN", "")
    if tushare_token:
        ts.set_token(tushare_token)
except ImportError:
    _TUSHARE_AVAILABLE = False


class FinanceDownloader(DownloaderBase):
    """Download financial data via AkShare with Tushare fallback."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        data_type = self.config.extra.get("data_type", "stock_daily")

        if data_type == "stock_daily":
            return self._download_stock_daily()
        elif data_type == "macro":
            return self._download_macro()
        elif data_type == "fund":
            return self._download_fund()
        else:
            return {"kb_id": self.kb_id, "error": f"Unknown data_type: {data_type}"}

    def _download_stock_daily(self) -> dict[str, Any]:
        """Download A-share daily prices, index data, stock list."""
        if not _AKSHARE_AVAILABLE:
            return {"kb_id": self.kb_id, "error": "akshare not installed"}

        downloaded = 0

        # 1. Stock list
        logger.info("[finance] Fetching stock list...")
        try:
            df = ak.stock_info_a_code_name()
            self._save_df("stock_list", df, "A股股票列表")
            downloaded += 1
        except Exception as exc:
            logger.error("[finance] stock_list failed: %s", exc)
            self.progress.log_error("stock_list", str(exc))
        time.sleep(REQUEST_DELAY)

        # 2. Index daily (上证指数、深证成指、创业板指)
        indices = [
            ("sh000001", "上证指数"),
            ("sz399001", "深证成指"),
            ("sz399006", "创业板指"),
            ("sh000016", "上证50"),
            ("sh000300", "沪深300"),
        ]
        for code, name in indices:
            try:
                df = ak.stock_zh_index_daily(symbol=code)
                self._save_df(f"index_{code}", df, f"{name} 日线行情")
                downloaded += 1
                logger.info("[finance] %s: %d rows", name, len(df))
            except Exception as exc:
                logger.error("[finance] index %s failed: %s", code, exc)
                self.progress.log_error(f"index_{code}", str(exc))
            time.sleep(REQUEST_DELAY)

        # 3. Top 50 stocks by market cap (daily price)
        logger.info("[finance] Fetching top stock prices...")
        try:
            df_spot = ak.stock_zh_a_spot_em()
            if not df_spot.empty:
                top_codes = df_spot["代码"].head(50).tolist()
                price_count = 0
                for code in top_codes:
                    try:
                        df = ak.stock_zh_a_hist(
                            symbol=code, period="daily",
                            start_date="20200101", end_date="20260604",
                            adjust="qfq"
                        )
                        if not df.empty:
                            self._save_df(f"daily_{code}", df, f"{code} 日线行情")
                            price_count += 1
                        time.sleep(0.5)
                    except Exception:
                        pass
                downloaded += price_count
                logger.info("[finance] Downloaded %d stock prices", price_count)
        except Exception as exc:
            logger.error("[finance] spot/top prices failed: %s", exc)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded, "data_type": "stock_daily"}

    def _download_macro(self) -> dict[str, Any]:
        """Download macroeconomic indicators."""
        if not _AKSHARE_AVAILABLE:
            return {"kb_id": self.kb_id, "error": "akshare not installed"}

        downloaded = 0
        indicators = [
            ("macro_china_cpi", "CPI月度数据"),
            ("macro_china_ppi", "PPI月度数据"),
            ("macro_china_gdp", "GDP季度数据"),
            ("macro_china_lpr", "LPR利率"),
            ("macro_china_money_supply", "货币供应量M2"),
            ("macro_china_consumer_goods_retail", "社会消费品零售总额"),
            ("macro_china_fx_gold", "外汇和黄金储备"),
        ]

        for func_name, title in indicators:
            try:
                func = getattr(ak, func_name)
                df = func()
                if not df.empty:
                    self._save_df(func_name, df, title)
                    downloaded += 1
                    logger.info("[finance] %s: %d rows", title, len(df))
            except Exception as exc:
                logger.error("[finance] %s failed: %s", func_name, exc)
                self.progress.log_error(func_name, str(exc))
            time.sleep(REQUEST_DELAY)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded, "data_type": "macro"}

    def _download_fund(self) -> dict[str, Any]:
        """Download mutual fund data."""
        if not _AKSHARE_AVAILABLE:
            return {"kb_id": self.kb_id, "error": "akshare not installed"}

        downloaded = 0

        # 1. Fund list
        try:
            df = ak.fund_name_em()
            self._save_df("fund_list", df, "公募基金列表")
            downloaded += 1
            logger.info("[finance] Fund list: %d rows", len(df))
        except Exception as exc:
            logger.error("[finance] fund_list failed: %s", exc)
        time.sleep(REQUEST_DELAY)

        # 2. Daily NAV for top funds
        try:
            df_daily = ak.fund_open_fund_daily_em()
            self._save_df("fund_daily", df_daily, "公募基金每日净值")
            downloaded += 1
            logger.info("[finance] Fund daily: %d rows", len(df_daily))
        except Exception as exc:
            logger.error("[finance] fund_daily failed: %s", exc)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded, "data_type": "fund"}

    def _save_df(self, name: str, df: pd.DataFrame, title: str) -> None:
        """Save DataFrame as CSV + Markdown."""
        csv_path = self.output_dir / f"{name}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        md_content = f"# {title}\n\n"
        md_content += f"Total rows: {len(df)} | Columns: {', '.join(df.columns.astype(str))}\n\n"

        try:
            md_content += df.head(100).to_markdown(index=False)
            if len(df) > 100:
                md_content += f"\n\n... ({len(df) - 100} more rows)\n"
        except Exception:
            # Fallback if tabulate not available
            md_content += df.head(50).to_string(index=False)

        filename = f"doc_{name}.md"
        self.save_text(filename, md_content, metadata={
            "title": title,
            "rows": len(df),
            "columns": list(df.columns.astype(str)),
            "csv_file": str(csv_path),
        })


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_finance.py <kb_id>")
        print("Examples: kb_039 (A股), kb_040 (宏观), kb_041 (基金)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with FinanceDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
