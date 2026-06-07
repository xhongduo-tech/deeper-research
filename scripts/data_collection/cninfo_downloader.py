#!/usr/bin/env python3
"""
巨潮资讯网批量下载器 — A股上市公司公告全量采集

功能：
- 按股票代码或公司名称批量搜索公告
- 支持年报/半年报/季报/全部公告类型筛选
- 自动下载PDF并提取文本
- 增量更新（已下载的跳过）

存储预算：
- 全部A股年报（约2万份 × 10MB）= ~200GB
- 全部公告（约74万份 × 平均2MB）= ~1.4TB
- 建议策略：优先下载年报+半年报，选择性下载重要公告

Usage:
    python cninfo_downloader.py --mode annual --limit 1000
    python cninfo_downloader.py --mode all --companies 工商银行,建设银行 --years 2020-2025
    python cninfo_downloader.py --mode batch --stock-list stocks.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data/kb_sources")
LOG_DIR = Path("/Users/xuhongduo/Projects/deep-research/logs/cninfo")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# CNINFO API endpoints
SEARCH_URL = "http://www.cninfo.com.cn/new/information/topSearch/query"
ANNOUNCE_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE = "http://static.cninfo.com.cn/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

# 公告类型代码映射
CATEGORY_MAP = {
    "annual": "category_ndbg_szsh",       # 年度报告
    "semi_annual": "category_bndbg_szsh", # 半年度报告
    "q1": "category_yjdbg_szsh",          # 一季度报告
    "q3": "category_sjdbg_szsh",          # 三季度报告
    "prospectus": "category_zqtz_szsh",   # 招股说明书
    "all": "",                            # 全部
}

# 交易所映射
EXCHANGE_MAP = {
    "sse": "sse",   # 上交所
    "szse": "szse", # 深交所
    "bjse": "bjse", # 北交所
    "all": "",      # 全部
}


class CNINFODownloader:
    """巨潮资讯网公告批量下载器"""

    def __init__(self, output_dir: Path, max_workers: int = 4, delay: float = 0.5):
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.downloaded_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.total_bytes = 0

    def search_company(self, keyword: str) -> list[dict]:
        """搜索公司，返回匹配的公司列表"""
        try:
            r = self.session.post(SEARCH_URL, data={"keyWord": keyword}, timeout=10)
            return r.json()
        except Exception as e:
            print(f"[ERROR] 搜索失败 {keyword}: {e}")
            return []

    def fetch_announcements(
        self,
        searchkey: str = "",
        column: str = "",
        category: str = "",
        page_num: int = 1,
        page_size: int = 30,
    ) -> dict:
        """获取公告列表"""
        payload = {
            "pageNum": page_num,
            "pageSize": page_size,
            "tabName": "fulltext",
            "searchkey": searchkey,
        }
        if column:
            payload["column"] = column
        if category:
            payload["category"] = category

        try:
            r = self.session.post(ANNOUNCE_URL, data=payload, timeout=15)
            return r.json()
        except Exception as e:
            print(f"[ERROR] 获取公告列表失败: {e}")
            return {}

    def download_pdf(self, adjunct_url: str, output_path: Path) -> bool:
        """下载PDF文件"""
        url = PDF_BASE + adjunct_url
        try:
            if output_path.exists():
                self.skipped_count += 1
                return True

            r = self.session.get(url, timeout=60, stream=True)
            r.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            size = output_path.stat().st_size
            self.total_bytes += size
            self.downloaded_count += 1
            return True

        except Exception as e:
            self.failed_count += 1
            print(f"[ERROR] 下载失败 {url}: {e}")
            return False

    def download_company_announcements(
        self,
        company_name: str,
        stock_code: str,
        category: str = "",
        years: Optional[list[int]] = None,
        max_pages: int = 100,
    ) -> int:
        """下载单个公司的全部公告"""
        safe_name = re.sub(r'[^\w一-鿿]', '_', company_name)
        company_dir = self.output_dir / f"{stock_code}_{safe_name}"
        company_dir.mkdir(parents=True, exist_ok=True)

        total_downloaded = 0
        for page in range(1, max_pages + 1):
            data = self.fetch_announcements(
                searchkey=company_name,
                category=category,
                page_num=page,
                page_size=30,
            )

            announcements = data.get("announcements") or []
            if not announcements:
                break

            for ann in announcements:
                title = ann.get("announcementTitle", "")
                adjunct_url = ann.get("adjunctUrl", "")
                ann_time = ann.get("announcementTime", "")

                # 年份过滤：先从标题提取报告年份，再从发布时间推算
                if years:
                    report_year = None
                    m = re.search(r'(\d{4})年年度报告', title)
                    if m:
                        report_year = int(m.group(1))
                    elif ann_time:
                        try:
                            report_year = datetime.fromtimestamp(int(ann_time) / 1000).year - 1
                        except (ValueError, OSError, OverflowError):
                            pass
                    if report_year is None or report_year not in years:
                        continue

                if not adjunct_url.lower().endswith(".pdf"):
                    continue

                # 生成文件名
                time_str = datetime.fromtimestamp(int(ann_time) / 1000).strftime("%Y-%m-%d") if ann_time else "unknown"
                safe_title = re.sub(r'[^\w一-鿿]', '_', title)[:50]
                filename = f"{time_str}_{safe_title}.pdf"
                output_path = company_dir / filename

                if self.download_pdf(adjunct_url, output_path):
                    total_downloaded += 1

                time.sleep(self.delay)

            has_more = data.get("hasMore", False)
            if not has_more:
                break

        return total_downloaded

    def batch_download_by_stock_list(
        self,
        stock_list_path: Path,
        category: str = "",
        years: Optional[list[int]] = None,
    ) -> None:
        """从股票列表文件批量下载"""
        with open(stock_list_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        print(f"[INFO] 开始批量下载 {len(lines)} 家公司...")

        for line in tqdm(lines, desc="Companies"):
            parts = line.split(",")
            if len(parts) >= 2:
                stock_code, company_name = parts[0].strip(), parts[1].strip()
            else:
                company_name = parts[0].strip()
                # 自动搜索代码
                results = self.search_company(company_name)
                if not results:
                    print(f"[WARN] 未找到公司: {company_name}")
                    continue
                stock_code = results[0].get("code", "unknown")

            count = self.download_company_announcements(
                company_name=company_name,
                stock_code=stock_code,
                category=category,
                years=years,
            )
            print(f"[INFO] {company_name}({stock_code}): 下载 {count} 份")

    def download_all_annual_reports(
        self,
        exchange: str = "sse",
        years: Optional[list[int]] = None,
        limit: int = 0,
    ) -> None:
        """批量下载全部年度报告（按交易所）"""
        output_dir = self.output_dir / f"annual_reports_{exchange}"
        output_dir.mkdir(parents=True, exist_ok=True)

        page = 1
        total_downloaded = 0

        while True:
            data = self.fetch_announcements(
                searchkey="",
                column=exchange,
                category=CATEGORY_MAP["annual"],
                page_num=page,
                page_size=30,
            )

            announcements = data.get("announcements") or []
            if not announcements:
                break

            for ann in announcements:
                if limit > 0 and total_downloaded >= limit:
                    print(f"[INFO] 达到限制数量 {limit}，停止下载")
                    return

                title = ann.get("announcementTitle", "")
                adjunct_url = ann.get("adjunctUrl", "")
                ann_time = ann.get("announcementTime", "")
                sec_name = ann.get("secName", "未知公司")
                sec_code = ann.get("secCode", "unknown")

                # 年份过滤：先从标题提取报告年份，再从发布时间推算
                if years:
                    report_year = None
                    m = re.search(r'(\d{4})年年度报告', title)
                    if m:
                        report_year = int(m.group(1))
                    elif ann_time:
                        try:
                            report_year = datetime.fromtimestamp(int(ann_time) / 1000).year - 1
                        except (ValueError, OSError, OverflowError):
                            pass
                    if report_year is None or report_year not in years:
                        continue

                if not adjunct_url.lower().endswith(".pdf"):
                    continue

                # 按公司组织目录
                safe_name = re.sub(r'[^\w一-鿿]', '_', sec_name)
                company_dir = output_dir / f"{sec_code}_{safe_name}"
                company_dir.mkdir(parents=True, exist_ok=True)

                time_str = datetime.fromtimestamp(int(ann_time) / 1000).strftime("%Y-%m-%d") if ann_time else "unknown"
                safe_title = re.sub(r'[^\w一-鿿]', '_', title)[:50]
                filename = f"{time_str}_{safe_title}.pdf"
                output_path = company_dir / filename

                if self.download_pdf(adjunct_url, output_path):
                    total_downloaded += 1
                    if total_downloaded % 10 == 0:
                        mb = self.total_bytes / 1024 / 1024
                        print(f"[PROGRESS] 已下载 {total_downloaded} 份, {mb:.1f} MB")

                time.sleep(self.delay)

            has_more = data.get("hasMore", False)
            if not has_more:
                break
            page += 1

        print(f"[DONE] 总共下载 {total_downloaded} 份, {self.total_bytes/1024/1024:.1f} MB")
        print(f"  成功: {self.downloaded_count}, 跳过: {self.skipped_count}, 失败: {self.failed_count}")


def main():
    parser = argparse.ArgumentParser(description="巨潮资讯网公告批量下载器")
    parser.add_argument("--mode", choices=["annual", "all", "batch", "company"], default="annual",
                        help="下载模式: annual=年报, all=全部公告, batch=批量, company=单公司")
    parser.add_argument("--exchange", choices=["sse", "szse", "bjse", "all"], default="sse",
                        help="交易所")
    parser.add_argument("--companies", type=str, default="",
                        help="公司名称列表，逗号分隔")
    parser.add_argument("--stock-list", type=Path, default=None,
                        help="股票列表文件路径（每行: 代码,名称）")
    parser.add_argument("--years", type=str, default="",
                        help="年份范围，如 2020-2025")
    parser.add_argument("--limit", type=int, default=0,
                        help="下载数量上限（0=无限制）")
    parser.add_argument("--workers", type=int, default=4,
                        help="并发下载数")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="下载间隔(秒)")
    parser.add_argument("--output", type=Path,
                        default=BASE_DIR / "cninfo_announcements",
                        help="输出目录")

    args = parser.parse_args()

    # 解析年份
    years = None
    if args.years:
        if "-" in args.years:
            start, end = map(int, args.years.split("-"))
            years = list(range(start, end + 1))
        else:
            years = [int(y) for y in args.years.split(",")]

    # 创建下载器
    downloader = CNINFODownloader(
        output_dir=args.output,
        max_workers=args.workers,
        delay=args.delay,
    )

    if args.mode == "annual":
        # 下载全部年报
        exchange = args.exchange if args.exchange != "all" else "sse"
        print(f"[INFO] 开始下载 {exchange} 交易所年度报告...")
        print(f"[INFO] 年份: {years or '全部'}")
        print(f"[INFO] 限制: {args.limit or '无限制'}")
        downloader.download_all_annual_reports(
            exchange=exchange,
            years=years,
            limit=args.limit,
        )

    elif args.mode == "company" and args.companies:
        for name in args.companies.split(","):
            name = name.strip()
            results = downloader.search_company(name)
            if results:
                code = results[0].get("code", "unknown")
                print(f"[INFO] 下载 {name}({code})...")
                downloader.download_company_announcements(
                    company_name=name,
                    stock_code=code,
                    years=years,
                )

    elif args.mode == "batch" and args.stock_list:
        downloader.batch_download_by_stock_list(
            stock_list_path=args.stock_list,
            years=years,
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
