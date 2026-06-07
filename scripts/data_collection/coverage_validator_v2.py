#!/usr/bin/env python3
"""
世界观知识库覆盖率验证器 v2 — 正确统计 worldview/ + kb_sources/ 双目录
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config_worldview_v1 import ALL_LAYERS, get_all_sources

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
    status: str
    supplement_suggestions: list[str]


# ═══════════════════════════════════════════════════════════════════════════════
# 旧 kb_sources 目录名 → 新 source kb_id 映射
# ═══════════════════════════════════════════════════════════════════════════════
LEGACY_KB_TO_SOURCE: dict[str, str] = {
    # L0 元知识层
    "kb_088_wikidata": "L0_001",
    "kb_169_dbpedia": "L0_003",
    # L1 基础事实层
    "kb_086_wikipedia_zh": "L1_006",
    "kb_087_wikipedia_en": "L1_006",
    "kb_d01_wikipedia_zh": "L1_006",
    "kb_d02_wikipedia_en": "L1_006",
    "kb_099_wikipedia_de": "L1_006",
    "kb_100_wikipedia_fr": "L1_006",
    "kb_101_wikipedia_es": "L1_006",
    "kb_102_wikipedia_ja": "L1_006",
    "kb_103_wikipedia_ru": "L1_006",
    "kb_104_wikipedia_pt": "L1_006",
    "kb_105_wikipedia_it": "L1_006",
    "kb_106_wikipedia_ko": "L1_006",
    "kb_107_wikipedia_ar": "L1_006",
    "kb_108_wikipedia_nl": "L1_006",
    "kb_109_wikipedia_pl": "L1_006",
    "kb_110_wikipedia_sv": "L1_006",
    "kb_111_wikipedia_tr": "L1_006",
    "kb_170_geonames": "L1_002",
    "kb_031_world_bank": "L1_007",
    "kb_033_un_data": "L1_008",
    "kb_090_cia_factbook": "L1_009",
    "cninfo_annual_sse": "L1_011",
    "cninfo_annual_szse": "L1_011",
    "cninfo_annual_bjse": "L1_011",
    "kb_002_stats_yearbook": "L1_010",
    "kb_002_national_stats": "L1_010",
    "kb_003_national_stats": "L1_010",
    "kb_003_stats_yearbook": "L1_010",
    "kb_039_a_share": "L1_011",
    "kb_040_macro_econ": "L1_010",
    "kb_041_fund_nav": "L1_011",
    "kb_new_002_bank_annual_report": "L1_011",
    "kb_new_003_central_enterprises": "L1_011",
    "kb_new_004_regional_economy": "L1_010",
    "kb_new_006_internet_giants": "L1_011",
    "kb_new_022_stock_announcements": "L1_011",
    # L2 关系网络层
    "kb_094_paperswithcode_nlp": "L2_005",
    "kb_095_paperswithcode_cv": "L2_005",
    "kb_096_paperswithcode_ml": "L2_005",
    "kb_112_commoncrawl_2024_51_seg1": "L2_006",
    "kb_113_commoncrawl_2024_51_seg2": "L2_006",
    "kb_114_commoncrawl_2024_51_seg3": "L2_006",
    "kb_115_commoncrawl_2024_51_seg4": "L2_006",
    "kb_116_commoncrawl_2024_51_seg5": "L2_006",
    "kb_117_commoncrawl_2024_42_seg1": "L2_006",
    "kb_118_commoncrawl_2024_42_seg2": "L2_006",
    "kb_119_commoncrawl_2024_33_seg1": "L2_006",
    "kb_120_commoncrawl_2024_33_seg2": "L2_006",
    "kb_121_commoncrawl_2024_26_seg1": "L2_006",
    "kb_122_commoncrawl_2024_18_seg1": "L2_006",
    "kb_123_commoncrawl_2024_10_seg1": "L2_006",
    "kb_124_commoncrawl_2023_50_seg1": "L2_006",
    "kb_125_github_system_tools": "L2_004",
    "kb_126_github_databases": "L2_004",
    "kb_127_github_ai_ml": "L2_004",
    "kb_128_github_frontend": "L2_004",
    "kb_129_github_backend": "L2_004",
    "kb_130_github_security": "L2_004",
    "kb_131_github_compilers": "L2_004",
    "kb_132_github_os": "L2_004",
    "kb_133_github_mobile": "L2_004",
    "kb_134_github_gamedev": "L2_004",
    # L3 因果与机制层
    "kb_015_arxiv_cs_ai": "L3_001",
    "kb_016_arxiv_math_physics": "L3_001",
    "kb_016_arxiv_others": "L3_001",
    "kb_017_pubmed": "L3_002",
    "kb_018_arxiv_econ": "L3_001",
    "kb_018_ssrn": "L3_006",
    "kb_044_arxiv_quantum": "L3_001",
    "kb_045_arxiv_security": "L3_001",
    "kb_046_arxiv_robotics": "L3_001",
    "kb_047_arxiv_data_science": "L3_001",
    "kb_097_cnki_oa": "L3_002",
    "kb_098_pmc_fulltext": "L3_002",
    "kb_064_openstax_textbooks": "L3_003",
    "kb_028_mit_ocw_math": "L3_004",
    "kb_135_arxiv_systems": "L3_001",
    "kb_136_arxiv_se_pl": "L3_001",
    "kb_137_arxiv_hci_graphics": "L3_001",
    "kb_138_arxiv_bio": "L3_002",
    "kb_139_arxiv_physics": "L3_001",
    "kb_140_arxiv_stats": "L3_001",
    "kb_141_arxiv_eess": "L3_001",
    "kb_142_arxiv_econ_full": "L3_006",
    "kb_143_arxiv_chem": "L3_001",
    "kb_144_arxiv_earth": "L3_001",
    # L4 价值与规范层
    "kb_008_constitution": "L4_001",
    "kb_009_admin_regulations": "L4_001",
    "kb_010_judicial_interp": "L4_002",
    "kb_011_finance_regulations": "L4_003",
    "kb_035_banking_regulation": "L4_003",
    "kb_076_csrc_regulations": "L4_003",
    "kb_091_chinese_classics": "L4_006",
    "kb_new_001_court_judgment": "L4_002",
    # L5 认知与思维层
    "kb_028_math_textbooks": "L5_001",
    "kb_029_discrete_math": "L5_001",
    "kb_030_statistical_learning": "L5_003",
    "kb_057_arxiv_pure_math": "L5_002",
    "kb_058_arxiv_applied_math": "L5_002",
    "kb_059_3b1b_math": "L5_001",
    "kb_060_mathworld": "L5_003",
    "kb_061_nist_dlmf": "L5_004",
    "kb_062_gutenberg_english": "L5_005",
    "kb_063_gutenberg_chinese": "L5_005",
    "kb_145_gutenberg_french": "L5_005",
    "kb_146_gutenberg_german": "L5_005",
    "kb_147_gutenberg_spanish": "L5_005",
    "kb_148_gutenberg_italian": "L5_005",
    "kb_149_gutenberg_portuguese": "L5_005",
    "kb_150_gutenberg_russian": "L5_005",
    "kb_151_gutenberg_dutch": "L5_005",
    "kb_152_gutenberg_other": "L5_005",
    "kb_065_tech_books": "L5_003",
    "kb_066_economics_books": "L5_003",
    "kb_070_wikibooks": "L5_001",
    # L6 程序与实用层
    "kb_019_python_docs": "L6_001",
    "kb_020_pytorch_docs": "L6_002",
    "kb_021_react_docs": "L6_002",
    "kb_022_vue_docs": "L6_002",
    "kb_023_go_docs": "L6_001",
    "kb_024_rust_docs": "L6_001",
    "kb_048_java_spring_docs": "L6_001",
    "kb_049_nodejs_docs": "L6_001",
    "kb_050_docker_docs": "L6_002",
    "kb_051_kubernetes_docs": "L6_002",
    "kb_052_tensorflow_docs": "L6_002",
    "kb_053_postgresql_docs": "L6_002",
    "kb_054_mongodb_docs": "L6_002",
    "kb_055_redis_docs": "L6_002",
    "kb_056_linux_kernel_docs": "L6_003",
    "kb_089_stackoverflow": "L6_004",
    "kb_092_python_peps": "L6_001",
    "kb_093_mdn_web": "L6_001",
    "kb_026_leetcode": "L6_005",
    "kb_027_owasp": "L6_006",
    # L7 多模态对齐层 — 旧系统无此层
    # L8 时序演化层
    "kb_001_gov_work_reports": "L8_002",
    "kb_004_pbc_monetary": "L8_001",
    "kb_032_imf_weo": "L8_003",
    "kb_032_imf_reports": "L8_003",
    "kb_071_oecd_reports": "L8_003",
    "kb_038_digital_transform": "L8_002",
    # L9 不确定性层 — 旧系统无此层
}


def get_dir_size_gb(path: Path) -> float:
    """递归获取目录大小 (GB)"""
    if not path.exists():
        return 0.0
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except (OSError, FileNotFoundError):
                    pass
        return total / 1024 / 1024 / 1024
    except Exception:
        return 0.0


def scan_all_kb_sizes() -> dict[str, float]:
    """扫描所有数据目录，返回 kb_id -> size_gb 映射"""
    sizes: dict[str, float] = {}

    # 1. 扫描 worldview/ 目录 — 新架构直接按 output_dir 对应
    wv_dir = BASE_DIR / "worldview"
    if wv_dir.exists():
        for subdir in wv_dir.rglob("*"):
            if subdir.is_dir():
                size = get_dir_size_gb(subdir)
                if size > 0:
                    rel = str(subdir.relative_to(wv_dir))
                    sizes[f"worldview:{rel}"] = size

    # 2. 扫描 kb_sources/ 目录 — 旧架构
    kb_dir = BASE_DIR / "kb_sources"
    if kb_dir.exists():
        for subdir in kb_dir.iterdir():
            if subdir.is_dir():
                size = get_dir_size_gb(subdir)
                if size > 0:
                    sizes[f"kb:{subdir.name}"] = size

    return sizes


def estimate_source_size(source, all_sizes: dict[str, float]) -> tuple[float, list[str]]:
    """
    估算单个数据源的实际大小。
    返回 (size_gb, found_paths)
    """
    total = 0.0
    found = []

    # 1. 检查 worldview/ 下的 output_dir 对应路径
    output_dir = Path(source.output_dir)
    if output_dir.exists():
        size = get_dir_size_gb(output_dir)
        if size > 0:
            total += size
            found.append(f"worldview:{output_dir.name}")

    # 2. 检查 worldview/ 下包含 kb_id 关键词的目录
    wv_dir = BASE_DIR / "worldview"
    kb_id_lower = source.kb_id.lower()
    if wv_dir.exists():
        for subdir in wv_dir.rglob("*"):
            if subdir.is_dir():
                rel = str(subdir.relative_to(wv_dir))
                # 精确匹配 kb_id 或其变体
                if kb_id_lower in rel.lower():
                    size = get_dir_size_gb(subdir)
                    if size > 0 and size not in [total]:
                        total = max(total, size)
                        found.append(f"worldview:{rel}")

    # 3. 通过旧 kb_sources 映射查找
    for legacy_dir, mapped_id in LEGACY_KB_TO_SOURCE.items():
        if mapped_id == source.kb_id:
            legacy_path = BASE_DIR / "kb_sources" / legacy_dir
            if legacy_path.exists():
                size = get_dir_size_gb(legacy_path)
                if size > 0:
                    total += size
                    found.append(f"kb:{legacy_dir}")

    # 4. 名称关键词匹配（兜底）
    name_lower = source.name.lower()
    kb_dir = BASE_DIR / "kb_sources"
    if kb_dir.exists():
        for subdir in kb_dir.iterdir():
            if not subdir.is_dir():
                continue
            dn = subdir.name.lower()
            matched = False
            # CNINFO
            if "cninfo" in name_lower and "cninfo" in dn:
                matched = True
            elif "巨潮" in source.name and "cninfo" in dn:
                matched = True
            # 银行
            elif "银行" in source.name and any(x in dn for x in ["bank", "icbc", "ccb", "abc", "boc", "bocom"]):
                matched = True
            # 体育
            elif "体育" in source.name and "sports" in dn:
                matched = True
            # 舆情
            elif "舆情" in source.name and any(x in dn for x in ["yuqing", "hot", "weibo", "zhihu", "baidu", "toutiao"]):
                matched = True
            # 通用关键词
            elif any(kw in dn for kw in name_lower.split()[:2] if len(kw) > 3):
                matched = True

            if matched:
                size = get_dir_size_gb(subdir)
                if size > 0 and f"kb:{subdir.name}" not in found:
                    total += size
                    found.append(f"kb:{subdir.name}")

    return total, found


def check_coverage(threshold_pct: float = 50.0) -> list[LayerCoverage]:
    """检查各层覆盖率"""
    all_sizes = scan_all_kb_sizes()
    print(f"[DEBUG] 扫描到 {len(all_sizes)} 个数据目录")

    # 打印最大的10个目录
    sorted_sizes = sorted(all_sizes.items(), key=lambda x: x[1], reverse=True)
    print("[DEBUG] 最大的10个数据目录:")
    for name, size in sorted_sizes[:10]:
        print(f"  {name}: {size:.2f} GB")

    results: list[LayerCoverage] = []

    for layer in ALL_LAYERS:
        actual_total = 0.0
        completed = 0
        failed = 0
        suggestions = []

        for source in layer.data_sources:
            actual, found_paths = estimate_source_size(source, all_sizes)
            actual_total += actual

            # 检查是否已完成（基于 output_dir 存在且有内容）
            if actual > 0.01:
                completed += 1

            # 如果该源实际很小，加入补充建议
            source_budget_gb = layer.budget_gb / max(len(layer.data_sources), 1)
            if actual < source_budget_gb * 0.1:
                suggestions.append(
                    f"{source.kb_id}: {source.name} "
                    f"(当前{actual:.2f}GB, 目标~{source_budget_gb:.0f}GB)"
                )

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
            supplement_suggestions=suggestions[:5],
        ))

    return results


def generate_report(results: list[LayerCoverage]) -> str:
    """生成Markdown覆盖率报告"""
    lines = []
    lines.append("# 世界观知识库覆盖率报告 v2")
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

    good = sum(1 for r in results if r.status == "good")
    warning = sum(1 for r in results if r.status == "warning")
    critical = sum(1 for r in results if r.status == "critical")
    lines.append(f"- 覆盖良好: {good} 层 | 警告: {warning} 层 | 严重不足: {critical} 层")
    lines.append("")

    lines.append("## 各层详情")
    lines.append("")
    lines.append("| 层 | 名称 | 预算(GB) | 实际(GB) | 覆盖率 | 状态 | 完成/总数 |")
    lines.append("|---|---|---|---|---|---|---|")

    for r in results:
        status_emoji = {"good": "G", "warning": "W", "critical": "C"}.get(r.status, "?")
        lines.append(
            f"| {r.layer_id} | {r.layer_name} | {r.budget_gb:.0f} | {r.actual_gb:.2f} | "
            f"{r.coverage_pct:.1f}% | {status_emoji} {r.status} | {r.completed_sources}/{r.source_count} |"
        )

    lines.append("")

    critical_layers = [r for r in results if r.status == "critical"]
    if critical_layers:
        lines.append("## 急需补充的层")
        lines.append("")
        for r in critical_layers:
            lines.append(f"### {r.layer_id} {r.layer_name} (覆盖率 {r.coverage_pct:.1f}%)")
            for s in r.supplement_suggestions:
                lines.append(f"- {s}")
            lines.append("")

    warning_layers = [r for r in results if r.status == "warning"]
    if warning_layers:
        lines.append("## 需要关注的层")
        lines.append("")
        for r in warning_layers:
            lines.append(
                f"- **{r.layer_id} {r.layer_name}**: {r.coverage_pct:.1f}% "
                f"({r.actual_gb:.1f}/{r.budget_gb:.0f} GB)"
            )
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="世界观知识库覆盖率验证器 v2")
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
        print("\n" + "=" * 80)
        print("覆盖率检查结果")
        print("=" * 80)
        for r in results:
            sc = {"good": "\033[92m", "warning": "\033[93m", "critical": "\033[91m"}.get(r.status, "")
            reset = "\033[0m"
            print(
                f"{r.layer_id:3} {r.layer_name:12} | "
                f"实际: {r.actual_gb:7.2f}GB / 预算: {r.budget_gb:4.0f}GB | "
                f"覆盖: {sc}{r.coverage_pct:5.1f}%{reset} | "
                f"状态: {r.status:8} | 完成: {r.completed_sources}/{r.source_count}"
            )

        total_budget = sum(r.budget_gb for r in results)
        total_actual = sum(r.actual_gb for r in results)
        total_pct = (total_actual / total_budget) * 100 if total_budget > 0 else 0
        print(f"\n总计: {total_actual:.2f}GB / {total_budget:.0f}GB ({total_pct:.1f}%)")

    if args.report:
        report = generate_report(results)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"coverage_report_{ts}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"\n[REPORT] 报告已保存: {report_path}")

        json_path = REPORT_DIR / f"coverage_data_{ts}.json"
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
        else:
            print("\n[SUPPLEMENT] 所有层覆盖率良好，无需补充")


if __name__ == "__main__":
    main()
