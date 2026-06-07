#!/usr/bin/env python3
"""
世界观知识库持续监控器
- 每30分钟运行覆盖率检查
- 报告进度变化
- 自动补充覆盖率 < 1% 的层
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data")
LOG_DIR = Path("/Users/xuhongduo/Projects/deep-research/logs/coverage")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def run_coverage_check() -> dict:
    """运行覆盖率检查，返回结果"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "coverage_validator_v3.py"), "--check", "--threshold", "1"],
        capture_output=True, text=True, timeout=300,
    )
    # 解析输出中的总计行
    total_gb = 0.0
    budget_gb = 3500.0
    for line in result.stdout.split("\n"):
        if line.startswith("总计:"):
            # 格式: "总计: 121.76GB / 3500GB (3.5%)"
            parts = line.replace("总计: ", "").split(" / ")
            if len(parts) == 2:
                total_gb = float(parts[0].replace("GB", "").strip())
                budget_pct = parts[1].split("(")[-1].replace(")", "").replace("%", "").strip()
                budget_gb = float(parts[1].split("GB")[0].strip())
    return {"total_gb": total_gb, "budget_gb": budget_gb, "raw_output": result.stdout}


def check_running_downloads() -> list[str]:
    """检查正在运行的下载进程"""
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True, text=True, timeout=10,
    )
    downloads = []
    for line in result.stdout.split("\n"):
        if any(x in line for x in ["cninfo_downloader", "worldview_bulk", "supplement_l3_l4", "retry_failed", "supplement_commoncrawl", "wet_bulk_embedder", "bulk_importer"]):
            if "grep" not in line:
                downloads.append(line.strip())
    return downloads


def load_history() -> list[dict]:
    """加载历史监控记录"""
    hist_file = LOG_DIR / "monitor_history.json"
    if hist_file.exists():
        return json.loads(hist_file.read_text())
    return []


def save_history(history: list[dict]):
    """保存历史监控记录"""
    hist_file = LOG_DIR / "monitor_history.json"
    hist_file.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 世界观知识库监控启动")

    # 运行覆盖率检查
    coverage = run_coverage_check()
    total_gb = coverage["total_gb"]
    pct = (total_gb / 3500) * 100

    # 检查运行中的下载
    running = check_running_downloads()

    # 记录历史
    history = load_history()
    entry = {
        "time": datetime.now().isoformat(),
        "total_gb": round(total_gb, 2),
        "pct": round(pct, 2),
        "running_downloads": len(running),
    }

    # 计算增量
    if history:
        last = history[-1]
        delta = round(total_gb - last["total_gb"], 2)
        entry["delta_gb"] = delta
        print(f"  总数据量: {total_gb:.2f}GB ({pct:.2f}%) | 较上次: +{delta:.2f}GB")
    else:
        print(f"  总数据量: {total_gb:.2f}GB ({pct:.2f}%)")

    print(f"  运行中下载进程: {len(running)}")
    for d in running[:5]:
        # 提取进程名
        parts = d.split()
        if len(parts) >= 11:
            print(f"    {parts[10]} {parts[11] if len(parts) > 11 else ''}")

    history.append(entry)
    # 只保留最近100条
    if len(history) > 100:
        history = history[-100:]
    save_history(history)

    # 如果总覆盖率 < 5% 且运行中的下载进程 < 10，建议启动更多下载
    if pct < 5 and len(running) < 10:
        print(f"  [ALERT] 覆盖率 {pct:.1f}% 过低，建议启动更多下载")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 监控完成\n")


if __name__ == "__main__":
    main()
