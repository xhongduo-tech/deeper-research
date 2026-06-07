#!/bin/bash
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     DataAgent 世界观知识库 — 实时状态面板                    ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║ 生成时间: $(date '+%Y-%m-%d %H:%M:%S')                           ║"
echo "╠══════════════════════════════════════════════════════════════╣"
printf "║ %-28s │ %6s │ %8s ║\n" "指标" "数值" "状态"
echo "╠══════════════════════════════════════════════════════════════╣"

TOTAL_GB=$(python3 /Users/xuhongduo/Projects/deep-research/scripts/data_collection/coverage_validator_v3.py --check --threshold 1 2>/dev/null | grep "总计:" | sed 's/.*总计: \([0-9.]*\)GB.*/\1/')
[ -z "$TOTAL_GB" ] && TOTAL_GB="?"
printf "║ %-28s │ %6s │ %8s ║\n" "总存储量" "${TOTAL_GB}GB" "3.5TB目标"

DL_COUNT=$(ps aux | grep -E 'python3.*(download|cninfo|worldview|supplement|retry|cia)' | grep -v grep | wc -l | xargs)
printf "║ %-28s │ %6s │ %8s ║\n" "运行中下载进程" "$DL_COUNT" "活跃"

CNINFO_COUNT=$(find /Users/xuhongduo/Projects/deep-research/data/kb_sources/cninfo_annual_* -name '*.pdf' 2>/dev/null | wc -l | xargs)
printf "║ %-28s │ %6s │ %8s ║\n" "CNINFO年报PDF" "$CNINFO_COUNT" "持续下载"

ARXIV_COUNT=$(find /Users/xuhongduo/Projects/deep-research/data/worldview/L3_causal -name '*.pdf' 2>/dev/null | wc -l | xargs)
printf "║ %-28s │ %6s │ %8s ║\n" "ArXiv论文PDF" "$ARXIV_COUNT" "批量中"

LAWS_COUNT=$(ls /Users/xuhongduo/Projects/deep-research/data/worldview/L4_normative/china_laws/ 2>/dev/null | wc -l | xargs)
printf "║ %-28s │ %6s │ %8s ║\n" "法律法规条目" "$LAWS_COUNT" "已完成"

echo "╚══════════════════════════════════════════════════════════════╝"
