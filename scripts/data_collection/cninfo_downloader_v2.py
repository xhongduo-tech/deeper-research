#!/usr/bin/env python3
"""
巨潮资讯网批量下载器 V2 — 绕过WAF频率限制

关键策略：
- 每次请求前访问首页刷新Cookie
- 3-5秒随机间隔
- 指数退避重试（403/空响应时等待30-120秒）
- 完整浏览器请求头

Usage:
    python cninfo_downloader_v2.py --exchange sse --years 2020-2025 --limit 1000
"""

from __future__ import annotations

import argparse
import random
import re
import time
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data/kb_sources")
ANNOUNCE_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE = "http://static.cninfo.com.cn/"

CATEGORY_MAP = {
    "annual": "category_ndbg_szsh",
    "semi_annual": "category_bndbg_szsh",
    "q1": "category_yjdbg_szsh",
    "q3": "category_sjdbg_szsh",
    "all": "",
}


def create_session():
    """创建带完整浏览器头的会话"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Origin": "http://www.cninfo.com.cn",
        "Referer": "http://www.cninfo.com.cn/new/information/company/query",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Connection": "keep-alive",
    })
    return session


def refresh_session(session: requests.Session):
    """访问首页刷新Cookie和会话状态"""
    try:
        session.get("http://www.cninfo.com.cn", timeout=10)
    except Exception:
        pass


def fetch_with_retry(session: requests.Session, url: str, payload: dict, max_retries: int = 5):
    """带指数退避的请求"""
    for attempt in range(max_retries):
        try:
            r = session.post(url, data=payload, timeout=15)
            if r.status_code == 200 and len(r.text) > 10:
                return r.json()
            # 403 or empty response — WAF triggered
            wait = 30 * (2 ** attempt) + random.uniform(0, 30)
            print(f"  [WAF]  attempt {attempt+1}/{max_retries}, waiting {wait:.0f}s...")
            time.sleep(wait)
            refresh_session(session)
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            wait = 10 * (2 ** attempt)
            print(f"  [ERROR] attempt {attempt+1}/{max_retries}: {e}, waiting {wait:.0f}s...")
            time.sleep(wait)
    return {}


def download_all_annual_reports(
    exchange: str = "sse",
    years: list[int] | None = None,
    limit: int = 0,
    output_dir: Path | None = None,
    category_key: str = "annual",
):
    """批量下载指定类别报告"""
    if output_dir is None:
        output_dir = BASE_DIR / f"cninfo_{category_key}_{exchange}"
    output_dir.mkdir(parents=True, exist_ok=True)

    session = create_session()
    refresh_session(session)
    time.sleep(random.uniform(2, 4))

    category = CATEGORY_MAP.get(category_key, CATEGORY_MAP["annual"])
    page = 1
    total_downloaded = 0
    total_bytes = 0
    skipped = 0
    failed = 0

    print(f"[START] 下载 {exchange.upper()} 交易所年度报告")
    print(f"[CONFIG] 年份: {years or '全部'} | 上限: {limit or '无限制'}")

    while True:
        if limit > 0 and total_downloaded >= limit:
            print(f"[LIMIT] 达到上限 {limit}，停止")
            break

        payload = {
            "pageNum": page,
            "pageSize": 30,
            "tabName": "fulltext",
            "column": exchange,
            "searchkey": "",
            "category": category,
        }

        print(f"[FETCH] 第 {page} 页...")
        data = fetch_with_retry(session, ANNOUNCE_URL, payload)

        announcements = data.get("announcements") or []
        if not announcements:
            print("[DONE] 无更多公告")
            break

        for ann in announcements:
            if limit > 0 and total_downloaded >= limit:
                break

            title = ann.get("announcementTitle", "")
            adjunct_url = ann.get("adjunctUrl", "")
            ann_time = ann.get("announcementTime", "")
            sec_name = ann.get("secName", "未知")
            sec_code = ann.get("secCode", "unknown")

            # 年份过滤：先从标题提取报告年份，再从发布时间推算
            if years:
                report_year = None
                # 尝试从标题提取，如 "2025年年度报告" / "2025年第一季度报告" / "2025年半年度报告"
                m = re.search(r'(\d{4})年', title)
                if m:
                    report_year = int(m.group(1))
                elif ann_time:
                    try:
                        ann_year = datetime.fromtimestamp(int(ann_time) / 1000).year
                        # 年度报告发布时间通常比报告年份晚1年；季报/半年报通常同一年
                        report_year = ann_year - 1 if category_key == "annual" else ann_year
                    except (ValueError, OSError, OverflowError):
                        pass
                if report_year is None or report_year not in years:
                    continue

            if not adjunct_url.lower().endswith(".pdf"):
                continue

            # 组织目录
            safe_name = re.sub(r"[^\w一-鿿]", "_", sec_name)[:30]
            company_dir = output_dir / f"{sec_code}_{safe_name}"
            company_dir.mkdir(parents=True, exist_ok=True)

            time_str = datetime.fromtimestamp(int(ann_time) / 1000).strftime("%Y-%m-%d") if ann_time else "unknown"
            safe_title = re.sub(r"[^\w一-鿿]", "_", title)[:40]
            filename = f"{time_str}_{safe_title}.pdf"
            output_path = company_dir / filename

            if output_path.exists():
                skipped += 1
                continue

            # 下载PDF
            pdf_url = f"{PDF_BASE}{adjunct_url}"
            try:
                time.sleep(random.uniform(1, 3))
                r = session.get(pdf_url, timeout=60)
                if r.status_code == 200 and len(r.content) > 1000:
                    output_path.write_bytes(r.content)
                    total_downloaded += 1
                    total_bytes += len(r.content)
                    if total_downloaded % 10 == 0:
                        mb = total_bytes / 1024 / 1024
                        print(f"[PROGRESS] 已下载 {total_downloaded} 份, {mb:.1f} MB, 跳过 {skipped}")
                else:
                    failed += 1
                    print(f"  [FAIL] {sec_name} {title[:30]}: HTTP {r.status_code}")
            except Exception as e:
                failed += 1
                print(f"  [ERROR] {sec_name} {title[:30]}: {e}")

            time.sleep(random.uniform(2, 5))

        has_more = data.get("hasMore", False)
        if not has_more:
            print("[DONE] 已到达最后一页")
            break

        page += 1
        time.sleep(random.uniform(3, 6))

    mb = total_bytes / 1024 / 1024
    gb = mb / 1024
    print(f"\n[SUMMARY]")
    print(f"  下载: {total_downloaded} 份")
    print(f"  跳过: {skipped} 份")
    print(f"  失败: {failed} 份")
    print(f"  总量: {mb:.1f} MB ({gb:.2f} GB)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="sse", choices=["sse", "szse", "bjse"])
    parser.add_argument("--category", default="annual", choices=list(CATEGORY_MAP.keys()))
    parser.add_argument("--years", type=str, default="2020-2025")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    years = None
    if args.years:
        start, end = map(int, args.years.split("-"))
        years = list(range(start, end + 1))

    download_all_annual_reports(
        exchange=args.exchange,
        years=years,
        limit=args.limit,
        output_dir=args.output,
        category_key=args.category,
    )


if __name__ == "__main__":
    main()
