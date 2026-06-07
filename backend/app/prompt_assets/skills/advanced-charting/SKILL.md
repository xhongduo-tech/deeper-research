---
name: advanced-charting-cn
description: >
  高级图表生成技能。将业务问题、Markdown 表格、Excel/CSV 字段和分析结果转为
  可复用 ChartSpec，并约束 ECharts 预览、PPT/Word 图像或原生图表、Excel 原生图表同源输出。
---

# Advanced Charting

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：把数据、问题和叙事目标转成可审计、可渲染、可降级的 ChartSpec。**

## 生成顺序

1. 先识别图表目的：趋势、对比、构成、分布、相关性、绝对值 + 比率、流程转化、层级结构、贡献拆解、组图对照。
2. 再绑定字段：category、primary_metric、secondary_metric、unit、period、filter、source。
3. 再选择图型：pie/donut、bar、line、combo、scatter、heatmap、waterfall、funnel、radar，或场景化 `CHART_PACK`。
4. 最后输出同源规格：ECharts option、Office 原生图表参数、PNG fallback 参数、图注和来源。

## ChartSpec 最小字段

```json
{
  "chart_type": "bar|line|pie|donut|combo|scatter|heatmap|small_multiples|waterfall|funnel|treemap|sankey|boxplot|histogram|radar",
  "title": "结论式标题",
  "labels": ["分类或时间"],
  "series": [{"name": "指标名（含单位）", "values": [1, 2, 3]}],
  "unit": "万元",
  "secondary_unit": "%",
  "source_note": "来源与计算口径"
}
```

## Word 可执行标记

当下游是 DOCX 且需要图片时，正文中必须使用导出器可识别的单行标记，而不是自然语言占位：

```markdown
[CHART: bar | title="ResNet-EEG improves benchmark accuracy" | labels="BCI IV-2a,BCI IV-2b,OpenBMI" | series="EEGNet:76.2,80.1,71.4;ResNet-EEG:82.5,85.1,79.6" | unit="%" | source="Table 2"]
```

方法/流程/架构图使用：

```markdown
[FIGURE: architecture | title="BMI neural signal decoding pipeline" | nodes="Raw neural signal -> Preprocessing -> Representation learning -> Decoder -> Device command" | source="Method section"]
```

没有 `labels + values/series` 的 `[CHART]` 标记不会渲染。缺失实验数字时使用 `[PLACEHOLDER: required data]`，不要伪造数值来凑图。

## 通用复杂图包（非学术场景）

当分析不是单一趋势或单一对比，而是“趋势 + 结构 + 驱动 + KPI”这类组合阅读任务时，优先使用 `CHART_PACK`。图包同样是单行可执行标记，必须包含真实可渲染数字、caption 和 source。

### 经营概览 / 业务复盘

```markdown
[CHART_PACK: business_overview | title="Enterprise revenue drives Q4 acceleration" | periods="Q1,Q2,Q3,Q4" | revenue_values="120,138,156,184" | growth_values="8,15,13,18" | categories="Enterprise,SMB,Channel,Other" | category_values="96,54,28,6" | kpis="ARR:184;Gross margin:72;Net retention:118;New logos:42" | unit="RMB mn" | rate_unit="%" | caption="Figure 2. Operating dashboard combining trend, growth, segment mix and KPI snapshot." | source="Management data"]
```

### 财务桥 / 利润驱动拆解

```markdown
[CHART_PACK: financial_bridge | title="Margin expansion offsets higher acquisition cost" | labels="Starting profit,Volume,Price,Mix,COGS,Marketing,Ending profit" | values="120,32,18,9,-24,-15,140" | scenarios="Bear,Base,Bull" | scenario_values="112,140,168" | unit="RMB mn" | caption="Figure 3. Profit bridge and scenario range." | source="Finance model"]
```

### 转化漏斗 / 销售管道

```markdown
[CHART_PACK: conversion_funnel | title="Trial-to-paid conversion is the primary bottleneck" | stages="Visitors,Signups,Trials,Qualified,Customers" | values="50000,8200,3100,1240,560" | series="Organic:18000,3800,1600,720,360;Paid:22000,3000,980,330,120;Partner:10000,1400,520,190,80" | unit="Users" | caption="Figure 4. Conversion funnel with channel-level comparison." | source="Product analytics"]
```

### 风险矩阵 / 内控评估

```markdown
[CHART_PACK: risk_matrix | title="Data quality and vendor lock-in require priority mitigation" | risks="Data quality,Model drift,Vendor lock-in,Compliance,Latency" | probability="4.2,3.6,3.8,2.8,3.2" | impact="4.6,4.0,4.3,4.8,3.4" | categories="Technology,Compliance,Operations,Commercial" | category_values="38,24,18,20" | caption="Figure 5. Risk matrix and exposure by category." | source="Risk register"]
```

## 英文学术论文复杂图包

实证论文不要只输出单张普通柱状图。优先使用可执行多面板图包：

```markdown
[ACADEMIC_FIGURE: training_dynamics | title="Training dynamics on BCI IV-2a" | epochs="0,10,20,30,40,50,60,70,80,90,100" | loss_series="CNN Baseline:1.55,1.15,0.98,0.82,0.69,0.60,0.54,0.49,0.45,0.43,0.41;Ours (ResNet-EEG):1.12,0.86,0.64,0.50,0.41,0.34,0.30,0.28,0.26,0.24,0.23" | acc_series="CNN Baseline:66,68.5,69.3,70.4,71.2,71.8,72.3,72.6,72.8,72.9,73.2;Ours (ResNet-EEG):65.5,70.5,73.2,75.6,76.8,77.7,78.2,78.8,78.6,78.9,82.5" | caption="Figure 2. Training dynamics on BCI Competition IV-2a. Left: training loss convergence. Right: validation accuracy curves." | source="Training logs"]
```

```markdown
[ACADEMIC_FIGURE: benchmark_comparison | title="Cross-dataset performance comparison" | datasets="BCI IV-2a,BCI IV-2b,Physionet MI,OpenBMI,High-Gamma" | series="CSP+LDA:68.2,72.5,65.8,63.4,70.1;FBCSP:74.6,78.3,71.2,69.8,75.4;EEGNet:78.3,81.2,75.1,73.5,79.2;ResNet-EEG (Ours):82.5,85.1,79.4,77.8,83.6" | caption="Figure 3. Cross-dataset performance comparison across five benchmark datasets." | source="Table 2"]
```

```markdown
[ACADEMIC_FIGURE: ablation_subject | title="Ablation and subject-wise analysis" | variants="Full Model,w/o Adaptive Filtering,w/o Residual Connections,w/o Temporal Attention,w/o Multi-scale Fusion,Single-scale CNN" | ablation_values="82.5,78.3,76.1,79.8,77.4,73.2" | subjects="S01,S02,S03,S04,S05,S06,S07,S08,S09" | baseline_values="68.2,77.5,74.6,66.4,70.5,80.6,62.1,71.3,78.8" | ours_values="79.4,87.6,85.0,78.3,78.0,92.0,69.1,79.3,89.7" | caption="Figure 4. Left: ablation results. Right: subject-wise comparison between the proposed model and baseline." | source="Ablation and subject logs"]
```

```markdown
[ACADEMIC_FIGURE: temporal_frequency | title="Temporal decoding and frequency-band importance" | times="0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0" | series="Left Hand:51,60,63,68,71,69,73,71,77,73;Right Hand:50,60,60,64,67,73,68,71,72,72;Feet:47,54,58,62,60,70,66,67,67,70;Tongue:46,51,60,61,61,68,66,67,64,64" | bands="Delta (0.5-4Hz),Theta (4-8Hz),Alpha (8-13Hz),Beta (13-30Hz),Low Gamma (30-50Hz),High Gamma (50-100Hz)" | importance="0.12,0.18,0.28,0.35,0.22,0.15" | window="2.5,3.5" | caption="Figure 5. Left: temporal decoding accuracy. Right: relative feature importance across frequency bands." | source="Temporal decoding analysis"]
```

每个图包必须有 caption 和 source；数值来自实验日志、表格或明确占位，不能为了生成图片虚构数据。

## 图型选择

- 构成占比：优先 donut；分类少于 4 个可用 pie。
- 横向比较：分类名较长或超过 5 个时用横向 bar。
- 时间趋势：年份、月份、季度、日期维度优先 line。
- 绝对值 + 增速/占比/利润率：使用 combo，柱表示绝对值，折线表示比率。
- 多指标但单位一致：可用 grouped bar 或 multi-line。
- 多指标且单位不同：必须拆图或使用 combo，并标注双轴单位。
- 多地区/多产品/多客群同口径比较：优先 small_multiples 组图，保持坐标尺度一致。
- 增减贡献拆解：使用 waterfall，并标注起点、增减项和终点。
- 阶段转化/漏斗损耗：使用 funnel，必须保留每步转化率。
- 层级构成：使用 treemap；流向/来源去向：使用 sankey。
- 分布、异常值、置信区间：使用 histogram、boxplot 或带误差线的统计图，不要用饼图替代。
- 多维能力评估：可用 radar，但维度需 5-8 个且同向归一化。

## 复杂组图规则

- 每个图组必须有 `chart_pack_id`、统一标题、共享口径说明和子图编号。
- 小多图必须复用同一字段映射、单位、颜色编码和坐标尺度；如果尺度不同，必须显式标注。
- 组合图必须说明主轴/次轴单位和选择理由；双轴只用于“绝对值 + 比率/增速/利润率”。
- 图表密集报告应先输出 ChartSpec 列表，再输出正文，确保预览、PPT/DOCX/XLSX 导出同源。

## 降级规则

- ECharts 预览可直接消费 ChartSpec。
- PPTX 支持原生图表时优先原生图表；组合图或复杂图不可稳定编辑时使用 Plotly/Kaleido PNG。
- DOCX 默认使用 PNG，并在图下保留来源说明。
- XLSX 优先使用 Excel 原生 chart；组合图用 bar + line 叠加。

## 禁止

- 没有数据来源时编造数字。
- 饼图展示时间趋势。
- 双轴不写单位。
- 图表标题只写“销售数据”“趋势分析”这类话题句。

## Quick Checklist

- [ ] 图表标题是结论句
- [ ] 字段、单位、筛选、时间范围可追溯
- [ ] ChartSpec 能同时服务预览和导出
- [ ] 组合图的主轴/次轴单位明确
- [ ] 组图/复杂图有统一口径、子图编号和降级策略
- [ ] PNG 降级时仍保留来源与数据口径
