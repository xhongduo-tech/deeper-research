#!/usr/bin/env python3
"""
CIA World Factbook JSON 下载器 — 使用官方 JSON API
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

OUTPUT_DIR = Path("/Users/xuhongduo/Projects/deep-research/data/worldview/L1_facts/cia_factbook")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://raw.githubusercontent.com/thecisawebsite/factbook.json/master"


def download_country_data():
    """下载所有国家/地区数据"""
    # 从 GitHub 镜像获取数据
    regions = [
        "africa", "australia-oceania", "central-america-n-caribbean",
        "central-asia", "east-n-southeast-asia", "europe",
        "middle-east", "north-america", "south-america", "south-asia",
    ]

    for region in regions:
        url = f"{BASE_URL}/{region}.json"
        out_path = OUTPUT_DIR / f"{region}.json"
        if out_path.exists() and out_path.stat().st_size > 1000:
            print(f"[CIA] {region} 已存在，跳过")
            continue

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            out_path.write_bytes(data)
            print(f"[CIA] {region} 下载成功 ({len(data)} bytes)")
        except Exception as e:
            print(f"[CIA] {region} 下载失败: {e}")

    # 同时保存一个说明文件
    readme = OUTPUT_DIR / "README.txt"
    readme.write_text("""CIA World Factbook Data
Source: https://www.cia.gov/the-world-factbook/
Downloaded via: factbook.json GitHub mirror
Contains: Country profiles, statistics, geography, economy, etc.
""", encoding="utf-8")

    print(f"[CIA] 完成。数据保存于: {OUTPUT_DIR}")


if __name__ == "__main__":
    download_country_data()
