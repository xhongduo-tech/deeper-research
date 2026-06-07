#!/usr/bin/env python3
"""
世界观知识库覆盖率验证器 — 持续监控 + 自动补充建议

功能:
- 扫描各层实际数据量 vs 预算目标
- 标记覆盖率不足的层 (<50%预算)
- 生成补充下载建议列表
- 输出覆盖率报告 (JSON + Markdown)

Usage:
    python coverage_validator.py --report
    python coverage_validator.py --check --threshold 30
    python coverage_validator.py --auto-supplement
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config_worldview_v1 import ALL_LAYERS

BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data")
REPORT_DIR = Path("/Users/xuhongduo/Projects/deep-research/logs/coverage")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class LayerCoverage:
    layer_id: str
    layer_name: str
    budget_gb: float
    actual_gb: float
    source_count: int
    completed_sources: int
    failed_sources: int
    coverage_pct: float
    status: str  # "good" | "warning" | "critical"
    supplement_suggestions: list[str]


import os

def get_dir_size_gb(path: Path) -> float:
    """获取目录大小 (GB) — 使用os.walk避免外部进程开销"""
    if not path.exists():
        return 0.0
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except (OSError, FileNotFoundError):
                    pass
        return total / 1024 / 1024 / 1024
    except Exception:
        return 0.0


def scan_kb_sources() -> dict[str, float]:
    """扫描kb_sources目录下各数据源大小"""
    sizes = {}
    kb_dir = BASE_DIR / "kb_sources"
    if not kb_dir.exists():
        return sizes

    for subdir in kb_dir.iterdir():
        if subdir.is_dir():
            sizes[subdir.name] = get_dir_size_gb(subdir)
    return sizes


def scan_worldview_sources() -> dict[str, float]:
    """扫描worldview目录下各数据源大小"""
    sizes = {}
    wv_dir = BASE_DIR / "worldview"
    if not wv_dir.exists():
        return sizes

    for subdir in wv_dir.rglob("*"):
        if subdir.is_dir():
            # 用相对路径作为key
            rel = subdir.relative_to(wv_dir)
            sizes[str(rel)] = get_dir_size_gb(subdir)
    return sizes


# 旧数据源到层的映射
KB_SOURCE_LAYER_MAP: dict[str, str] = {
    # L1 基础事实层
    "kb_001": "L1", "kb_002": "L1", "kb_003": "L1", "kb_004": "L1",
    "kb_005": "L1", "kb_006": "L1", "kb_007": "L1", "kb_008": "L1",
    "kb_009": "L1", "kb_010": "L1", "kb_011": "L1", "kb_031": "L1",
    "kb_032": "L1", "kb_033": "L1", "kb_034": "L1", "kb_039": "L1",
    "kb_040": "L1", "kb_041": "L1", "kb_090": "L1",
    # L2 关系网络层
    "kb_088": "L2",
    # L3 因果与机制层
    "kb_015": "L3", "kb_016": "L3", "kb_017": "L3", "kb_018": "L3",
    "kb_044": "L3", "kb_045": "L3", "kb_046": "L3", "kb_047": "L3",
    # L4 价值规范层
    "kb_008": "L4", "kb_009": "L4", "kb_010": "L4", "kb_011": "L4",
    "kb_035": "L4", "kb_076": "L4",
    # L5 认知与思维层
    "kb_028": "L5", "kb_029": "L5", "kb_030": "L5", "kb_057": "L5",
    "kb_058": "L5", "kb_059": "L5", "kb_060": "L5", "kb_061": "L5",
    # L6 程序与实用层
    "kb_019": "L6", "kb_020": "L6", "kb_021": "L6", "kb_022": "L6",
    "kb_023": "L6", "kb_024": "L6", "kb_048": "L6", "kb_049": "L6",
    "kb_050": "L6", "kb_051": "L6", "kb_052": "L6", "kb_053": "L6",
    "kb_054": "L6", "kb_055": "L6", "kb_056": "L6", "kb_092": "L6",
    "kb_093": "L6",
    # L7 多模态对齐层 (暂无)
    # L8 时序演化层
    "kb_038": "L8",
    # L9 不确定性层 (暂无)
}

# 数据源名称关键词到层的映射
SOURCE_KEYWORDS: dict[str, list[str]] = {
    "L0": ["wikidata_schema", "schema_org", "dbpedia_ontology", "wordnet", "wikipedia_categor"],
    "L1": ["wikidata", "geonames", "osm", "pubchem", "uniprot", "wikipedia", "world_bank", "un_data", "cia", "stats_gov", "cninfo", "annual", "gov_work", "national_stats", "pbc", "mof", "customs", "ndrc"],
    "L2": ["triple", "relation", "dependency", "citation", "commoncrawl", "link"],
    "L3": ["arxiv", "causal", "mechanism", "model"],
    "L4": ["regulation", "law", "constitution", "judicial", "csrc"],
    "L5": ["cognitive", "psychology", "thinking", "decision"],
    "L6": ["github", "code", "docs", "python", "pytorch", "react", "vue", "go", "rust", "docker", "kubernetes", "tensorflow", "postgresql", "mongodb", "redis", "linux"],
    "L7": ["multimodal", "image", "audio", "video"],
    "L8": ["temporal", "timeseries", "history", "evolution"],
    "L9": ["uncertainty", "error", "boundary", "contradiction"],
}


def estimate_source_size(kb_id: str, source_name: str, kb_sizes: dict, wv_sizes: dict) -> float:
    """估算单个数据源的实际大小"""
    size = 0.0

    # 1. 先检查 worldview 目录 (精确匹配kb_id)
    for key, s in wv_sizes.items():
        if kb_id.lower() in key.lower():
            size = max(size, s)

    # 2. 检查 kb_sources 目录 (精确匹配kb_id)
    for key, s in kb_sizes.items():
        if kb_id.lower() in key.lower():
            size = max(size, s)

    # 3. 检查旧数据源映射
    for old_id, layer in KB_SOURCE_LAYER_MAP.items():
        if old_id in kb_id.lower():
            for key, s in kb_sizes.items():
                if old_id in key.lower():
                    size = max(size, s)

    # 4. 根据名称关键词匹配
    name_lower = source_name.lower()
    for key, s in kb_sizes.items():
        key_lower = key.lower()
        # CNINFO特殊处理
        if "cninfo" in name_lower and "cninfo" in key_lower:
            size = max(size, s)
        # 银行报告
        elif "银行" in source_name and ("bank" in key_lower or "icbc" in key_lower or "ccb" in key_lower):
            size = max(size, s)
        # 体育数据
        elif "体育" in source_name and "sports" in key_lower:
            size = max(size, s)
        # 舆情数据
        elif "舆情" in source_name and ("yuqing" in key_lower or "hot" in key_lower or "weibo" in key_lower):
            size = max(size, s)

    return size


def check_coverage(threshold_pct: float = 50.0) -> list[LayerCoverage]:
    """检查各层覆盖率"""
    kb_sizes = scan_kb_sources()
    wv_sizes = scan_worldview_sources()

    results: list[LayerCoverage] = []

    for layer in ALL_LAYERS:
        actual_total = 0.0
        completed = 0
        failed = 0
        suggestions = []

        for source in layer.data_sources:
            actual = estimate_source_size(source.kb_id, source.name, kb_sizes, wv_sizes)
            actual_total += actual

            # 检查是否已完成
            state_file = Path(f"/Users/xuhongduo/Projects/deep-research/logs/worldview/download_state.json")
            if state_file.exists():
                try:
                    state = json.loads(state_file.read_text())
                    if state.get(source.kb_id, {}).get("completed"):
                        completed += 1
                    elif state.get(source.kb_id, {}).get("failed"):
                        failed += 1
                except Exception:
                    pass

            # 如果该源实际为0或很小，加入补充建议
            source_budget_gb = layer.budget_gb / len(layer.data_sources)
            if actual < source_budget_gb * 0.1:
                suggestions.append(f"{source.kb_id}: {source.name} (当前{actual:.2f}GB, 目标~{source_budget_gb:.0f}GB)")

        coverage_pct = (actual_total / layer.budget_gb) * 100 if layer.budget_gb > 0 else 0

        if coverage_pct >= threshold_pct:
            status = "good"
        elif coverage_pct >= threshold_pct / 2:
            status = "warning"
        else:
            status = "critical"

        results.append(LayerCoverage(
            layer_id=layer.layer_id,
            layer_name=layer.layer_name,
            budget_gb=layer.budget_gb,
            actual_gb=actual_total,
            source_count=len(layer.data_sources),
            completed_sources=completed,
            failed_sources=failed,
            coverage_pct=coverage_pct,
            status=status,
            supplement_suggestions=suggestions[:5],  # 每层最多5条建议
        ))

    return results


def generate_report(results: list[LayerCoverage]) -> str:
    """生成Markdown覆盖率报告"""
    lines = []
    lines.append("# 世界观知识库覆盖率报告")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    total_budget = sum(r.budget_gb for r in results)
    total_actual = sum(r.actual_gb for r in results)
    total_pct = (total_actual / total_budget) * 100 if total_budget > 0 else 0

    lines.append("## 总体概况")
    lines.append(f"- 总预算: **{total_budget:.0f} GB**")
    lines.append(f"- 实际存储: **{total_actual:.2f} GB**")
    lines.append(f"- 总体覆盖率: **{total_pct:.1f}%**")
    lines.append("")

    # 状态分布
    good = sum(1 for r in results if r.status == "good")
    warning = sum(1 for r in results if r.status == "warning")
    critical = sum(1 for r in results if r.status == "critical")
    lines.append(f"- 覆盖良好: {good} 层 | 警告: {warning} 层 | 严重不足: {critical} 层")
    lines.append("")

    lines.append("## 各层详情")
    lines.append("")
    lines.append("| 层 | 名称 | 预算(GB) | 实际(GB) | 覆盖率 | 状态 |")
    lines.append("|---|---|---|---|---|---|")

    for r in results:
        status_emoji = {"good": "🟢", "warning": "🟡", "critical": "🔴"}.get(r.status, "⚪")
        lines.append(
            f"| {r.layer_id} | {r.layer_name} | {r.budget_gb:.0f} | {r.actual_gb:.2f} | "
            f"{r.coverage_pct:.1f}% | {status_emoji} {r.status} |"
        )

    lines.append("")

    # 需要补充的层
    critical_layers = [r for r in results if r.status == "critical"]
    if critical_layers:
        lines.append("## 🔴 急需补充的层")
        lines.append("")
        for r in critical_layers:
            lines.append(f"### {r.layer_id} {r.layer_name} (覆盖率 {r.coverage_pct:.1f}%)")
            for s in r.supplement_suggestions:
                lines.append(f"- {s}")
            lines.append("")

    warning_layers = [r for r in results if r.status == "warning"]
    if warning_layers:
        lines.append("## 🟡 需要关注的层")
        lines.append("")
        for r in warning_layers:
            lines.append(f"- **{r.layer_id} {r.layer_name}**: {r.coverage_pct:.1f}% ({r.actual_gb:.1f}/{r.budget_gb:.0f} GB)")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="世界观知识库覆盖率验证器")
    parser.add_argument("--check", action="store_true", help="执行覆盖率检查")
    parser.add_argument("--threshold", type=float, default=50.0, help="覆盖率阈值 (%)")
    parser.add_argument("--report", action="store_true", help="生成报告文件")
    parser.add_argument("--auto-supplement", action="store_true", help="自动生成补充下载列表")
    args = parser.parse_args()

    if not args.check and not args.report and not args.auto_supplement:
        args.check = True
        args.report = True

    print("[INFO] 正在扫描数据目录...")
    results = check_coverage(threshold_pct=args.threshold)

    if args.check:
        print("\n" + "=" * 70)
        print("覆盖率检查结果")
        print("=" * 70)
        for r in results:
            status_color = {"good": "\033[92m", "warning": "\033[93m", "critical": "\033[91m"}.get(r.status, "")
            reset = "\033[0m"
            print(
                f"{r.layer_id:3} {r.layer_name:12} | "
                f"实际: {r.actual_gb:7.2f}GB / 预算: {r.budget_gb:4.0f}GB | "
                f"覆盖: {status_color}{r.coverage_pct:5.1f}%{reset} | "
                f"状态: {r.status:8} | 完成: {r.completed_sources}/{r.source_count}"
            )

        total_budget = sum(r.budget_gb for r in results)
        total_actual = sum(r.actual_gb for r in results)
        total_pct = (total_actual / total_budget) * 100 if total_budget > 0 else 0
        print(f"\n总计: {total_actual:.2f}GB / {total_budget:.0f}GB ({total_pct:.1f}%)")

    if args.report:
        report = generate_report(results)
        report_path = REPORT_DIR / f"coverage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"\n[REPORT] 报告已保存: {report_path}")

        # 同时保存JSON
        json_path = REPORT_DIR / f"coverage_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_data = [
            {
                "layer_id": r.layer_id,
                "layer_name": r.layer_name,
                "budget_gb": r.budget_gb,
                "actual_gb": r.actual_gb,
                "coverage_pct": r.coverage_pct,
                "status": r.status,
                "source_count": r.source_count,
                "completed_sources": r.completed_sources,
            }
            for r in results
        ]
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[JSON] 数据已保存: {json_path}")

    if args.auto_supplement:
        supplement = []
        for r in results:
            if r.status in ("warning", "critical"):
                for s in r.supplement_suggestions:
                    kb_id = s.split(":")[0].strip()
                    supplement.append(kb_id)

        if supplement:
            list_path = REPORT_DIR / "supplement_list.txt"
            list_path.write_text("\n".join(supplement), encoding="utf-8")
            print(f"\n[SUPPLEMENT] 建议补充 {len(supplement)} 个数据源，列表已保存: {list_path}")
            print("运行以下命令启动补充下载:")
            print(f"  python worldview_bulk_downloader.py --source {' '.join(supplement[:10])}")
        else:
            print("\n[SUPPLEMENT] 所有层覆盖率良好，无需补充")


if __name__ == "__main__":
    main()
