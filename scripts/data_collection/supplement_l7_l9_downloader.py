#!/usr/bin/env python3
"""
L7 多模态层 + L9 不确定性层 补充下载器
- L7: Wikipedia图像描述元数据 + CommonCrawl WAT文件
- L9: ArXiv争议/不确定性论文 + Stanford哲学百科争议条目
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data/worldview")
LOG_DIR = Path("/Users/xuhongduo/Projects/deep-research/logs/worldview")
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# L7: Wikipedia 图像描述元数据
# ──────────────────────────────────────────────────────────────────────────────

def download_wikipedia_image_descriptions():
    """下载Wikipedia图像元数据（多语言）"""
    output_dir = BASE_DIR / "L7_multimodal" / "wikipedia_images"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 使用Wikimedia Commons API获取热门图像数据
    languages = ["zh", "en", "de", "fr", "ja"]
    for lang in languages:
        print(f"[L7] 下载 {lang}.wikipedia 图像元数据...")
        # 获取前1000个最常使用的文件
        url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=allimages&aisort=timestamp&aidir=descending&ailimit=500&format=json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            images = data.get("query", {}).get("allimages", [])
            out_file = output_dir / f"{lang}_images.json"

            # 丰富数据：添加描述信息
            enriched = []
            for img in images[:200]:  # 每种语言200张
                enriched.append({
                    "name": img.get("name"),
                    "url": img.get("url"),
                    "descriptionurl": img.get("descriptionurl"),
                    "timestamp": img.get("timestamp"),
                    "size": img.get("size"),
                    "width": img.get("width"),
                    "height": img.get("height"),
                    "mime": img.get("mime"),
                    "language": lang,
                })

            # 追加到文件
            existing = []
            if out_file.exists():
                try:
                    existing = json.loads(out_file.read_text())
                except Exception:
                    pass
            existing.extend(enriched)
            out_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  已保存 {len(enriched)} 条 {lang} 图像元数据")
            time.sleep(3)
        except Exception as e:
            print(f"  [WARN] {lang} 失败: {e}")

    print(f"[L7] Wikipedia图像元数据下载完成")


def download_commons_image_metadata():
    """下载Wikimedia Commons结构化图像数据"""
    output_dir = BASE_DIR / "L7_multimodal" / "commons_metadata"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Commons API: 获取带分类的图像
    categories = [
        "Category:Diagrams", "Category:Maps", "Category:Charts",
        "Category:Scientific_images", "Category:Historical_images",
    ]

    for cat in categories:
        print(f"[L7] 下载 Commons {cat} ...")
        url = f"https://commons.wikimedia.org/w/api.php?action=query&list=categorymembers&cmtitle={cat.replace(' ', '%20')}&cmlimit=100&format=json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            members = data.get("query", {}).get("categorymembers", [])
            out_file = output_dir / f"{cat.replace('Category:', '').lower()}.json"
            out_file.write_text(json.dumps(members, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  已保存 {len(members)} 条")
            time.sleep(2)
        except Exception as e:
            print(f"  [WARN] {cat} 失败: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# L9: 不确定性论文 + 争议条目
# ──────────────────────────────────────────────────────────────────────────────

L9_SEARCH_TERMS = [
    ("scientific_controversies", "controversy OR debate OR uncertainty OR 'open problem'"),
    ("historical_debates", "dispute OR revisionism OR reinterpretation"),
    ("ethical_dilemmas", "'moral dilemma' OR 'trolley problem' OR 'ai ethics' OR 'gene editing'"),
    ("economic_forecast_divergence", "'forecast error' OR 'prediction failure' OR 'model uncertainty'"),
]


def arxiv_search_ids(query: str, max_results: int = 1000) -> list[str]:
    """搜索ArXiv获取论文ID"""
    encoded = query.replace(" ", "%20").replace("'", "%27").replace("OR", "OR")
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
            ids = re.findall(r"<id>http://arxiv.org/abs/([^<]+)</id>", data)
            return [i for i in ids if re.match(r"\d+\.\d+", i)]
        except Exception as e:
            wait = 5 * (2 ** attempt)
            print(f"  搜索失败(尝试{attempt+1}/5): {e}，{wait}s后重试...")
            time.sleep(wait)
    return []


def arxiv_download_pdf(arxiv_id: str, output_dir: Path) -> bool:
    """下载ArXiv PDF"""
    pdf_path = output_dir / f"{arxiv_id.replace('/', '_')}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 10000:
        return True
    for attempt in range(3):
        try:
            url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if len(data) > 1000:
                pdf_path.write_bytes(data)
                return True
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return False


def download_arxiv_uncertainty_papers():
    """下载ArXiv不确定性/争议论文"""
    for name, query in L9_SEARCH_TERMS:
        output_dir = BASE_DIR / "L9_uncertainty" / name
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[L9] 搜索: {name} ({query}) ...")
        ids = arxiv_search_ids(query, max_results=500)
        if not ids:
            print(f"  未找到论文，跳过")
            continue
        print(f"  找到 {len(ids)} 篇论文")

        completed = 0
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(arxiv_download_pdf, aid, output_dir): aid for aid in ids[:200]}
            for future in as_completed(futures):
                if future.result():
                    completed += 1
                if completed % 20 == 0:
                    print(f"  进度: {completed}/{min(len(ids), 200)}")

        print(f"[L9] {name} 完成: {completed} 篇")


def generate_wikipedia_disputes():
    """生成Wikipedia争议性条目列表"""
    output_dir = BASE_DIR / "L9_uncertainty" / "wikipedia_disputes"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 知名争议性Wikipedia条目
    disputed_articles = [
        {"title": "Climate change controversy", "topic": "science"},
        {"title": "Vaccine hesitancy", "topic": "medicine"},
        {"title": "String theory", "topic": "physics"},
        {"title": "Free will", "topic": "philosophy"},
        {"title": "Nature versus nurture", "topic": "psychology"},
        {"title": "Copenhagen interpretation", "topic": "physics"},
        {"title": "Interpretations of quantum mechanics", "topic": "physics"},
        {"title": "Many-worlds interpretation", "topic": "physics"},
        {"title": "China-Taiwan relations", "topic": "politics"},
        {"title": "Israeli-Palestinian conflict", "topic": "politics"},
        {"title": "Cold War", "topic": "history"},
        {"title": "Causes of World War I", "topic": "history"},
        {"title": "Economic inequality", "topic": "economics"},
        {"title": "Universal basic income", "topic": "economics"},
        {"title": "Artificial general intelligence", "topic": "technology"},
        {"title": "AI alignment", "topic": "technology"},
        {"title": "Consciousness", "topic": "neuroscience"},
        {"title": "Hard problem of consciousness", "topic": "philosophy"},
        {"title": "Simulation hypothesis", "topic": "philosophy"},
        {"title": "Fermi paradox", "topic": "astrophysics"},
        {"title": "Dark matter", "topic": "physics"},
        {"title": "Dark energy", "topic": "physics"},
        {"title": "Origin of life", "topic": "biology"},
        {"title": "Cambrian explosion", "topic": "biology"},
        {"title": "Great Filter", "topic": "astrophysics"},
        {"title": "Trolley problem", "topic": "ethics"},
        {"title": "Prisoner's dilemma", "topic": "game_theory"},
        {"title": "Tragedy of the commons", "topic": "economics"},
        {"title": "Resource curse", "topic": "economics"},
        {"title": "Efficient-market hypothesis", "topic": "finance"},
    ]

    out_file = output_dir / "disputed_articles.json"
    out_file.write_text(json.dumps(disputed_articles, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[L9] 已生成 {len(disputed_articles)} 条Wikipedia争议条目")


def download_sep_ethics_entries():
    """下载Stanford哲学百科伦理条目"""
    output_dir = BASE_DIR / "L9_uncertainty" / "ethical_debates"
    output_dir.mkdir(parents=True, exist_ok=True)

    sep_entries = [
        "ethics", "consequentialism", "deontology", "virtue-ethics",
        "decision-capacity", "paternalism", "autonomy-moral",
        "rights", "justice", "fairness",
        "ai-ethics", "robot-ethics", "computer-ethics",
        "biomedical-ethics", "reproductive-rights", "euthanasia",
        "abortion", "capital-punishment", "privacy",
        "free-speech", "civil-disobedience", "war",
    ]

    for entry in sep_entries:
        out_path = output_dir / f"{entry}.html"
        if out_path.exists():
            continue
        url = f"https://plato.stanford.edu/entries/{entry}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            out_path.write_bytes(data)
            print(f"[L9] SEP {entry} 下载成功 ({len(data)} bytes)")
            time.sleep(2)
        except Exception as e:
            print(f"[L9] SEP {entry} 失败: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="L7+L9 补充下载器")
    parser.add_argument("--l7", action="store_true", help="下载L7多模态数据")
    parser.add_argument("--l9", action="store_true", help="下载L9不确定性数据")
    parser.add_argument("--all", action="store_true", help="全部下载")
    args = parser.parse_args()

    if args.all:
        args.l7 = True
        args.l9 = True

    if not any([args.l7, args.l9]):
        print("请指定 --l7 / --l9 / --all")
        return

    if args.l7:
        print("=" * 60)
        print("[L7] 多模态对齐层补充下载")
        print("=" * 60)
        download_wikipedia_image_descriptions()
        download_commons_image_metadata()

    if args.l9:
        print("=" * 60)
        print("[L9] 不确定性与边界层补充下载")
        print("=" * 60)
        download_arxiv_uncertainty_papers()
        generate_wikipedia_disputes()
        download_sep_ethics_entries()

    print("\n[L7/L9] 全部完成！")


if __name__ == "__main__":
    main()
