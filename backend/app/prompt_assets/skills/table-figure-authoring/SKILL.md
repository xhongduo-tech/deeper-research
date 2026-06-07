---
name: table-figure-authoring-cn
description: >
  表格与图表写作技能。决定在哪个章节插入表格/图表，设计表格结构，
  生成图表的标题和数据引用说明。输出可直接写入 Markdown 的标准表格、
  可执行 ChartSpec/FIGURE 标记和图注，供 Word/PPT 导出器渲染图片。
---

# Table & Figure Authoring

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：设计表格结构、图表规格和图注来源。只在有可审计数据或结构节点时输出可执行图表/图片标记；不编造实验结果。**

## 表格 vs 图表的选择规则

| 情况 | 用表格 | 用图表 |
|------|--------|--------|
| 读者需要查具体数字 | ✅ | ❌ |
| 展示趋势/变化方向 | ❌ | ✅（折线图）|
| 比较多个维度 | ✅（行列对比）| ✅（条形图）|
| 成分/占比 | ❌ | ✅（饼图/堆叠条形）|
| 数据点 > 10 行且读者不需精确值 | ❌ | ✅ |
| 需要审计/引用原始数据 | ✅ | ❌ |

两者都合适时：用表格，在表格下方附趋势图。

## Markdown 表格格式规范

### 标准格式

```markdown
**表 1：2023-2024 年各区域销售收入对比**（单位：万元，来源：sales_2024.xlsx）

| 区域 | 2023年 | 2024年 | 同比增长 |
|------|--------|--------|---------|
| 华北 | 12,300 | 13,800 | +12.2% |
| 华南 | 8,700  | 8,200  | -5.7%  |
| **合计** | **21,000** | **22,000** | **+4.8%** |
```

### 必须遵守

- 表标题写在表格**上方**，格式：`**表 N：[描述性标题]**（单位：XX，来源：XX）`
- 有合计/均值时，最后一行加粗
- 数字右对齐（Markdown 用 `---:` 对齐标识符）
- 有单位的列，单位写在表头而非每个单元格
- 没有数据的格子写 `—` 而非空白

## 图表可执行指令格式

当 Word/PPT 需要生成图片时，输出图表指令供 `document_generator.py` 处理。指令必须包含可渲染数据；只有 `data_ref` 而没有 `labels/values/series` 时不会生成图片。

```
[CHART: bar | title="ResNet-EEG outperforms EEGNet across public benchmarks" | labels="BCI IV-2a,BCI IV-2b,Physionet,OpenBMI" | series="EEGNet:76.2,80.1,73.8,71.4;ResNet-EEG:82.5,85.1,81.3,79.6" | unit="%" | source="Table 2"]
```

参数说明：
- `bar|line|pie|scatter|stacked_bar` — 图类型
- `title` — 结论式标题（必须是判断句，不是话题句）
- `labels` — 横轴分类或时间标签，逗号分隔
- `values` — 单系列数据；多系列时使用 `series="名称:1,2;名称:3,4"`
- `unit` — 数值单位，如 `%`、`ms/sample`
- `source` — 原始数据来源

方法架构、流程、解码管线等非数值图片使用：

```
[FIGURE: architecture | title="ResNet-EEG decoding pipeline" | nodes="Raw EEG -> Temporal filtering -> Adaptive spatial filtering -> Residual decoder -> Class probabilities" | source="Method design"]
```

复杂学术图必须使用 `ACADEMIC_FIGURE` 多面板图包，而不是把多个单图分散输出。可用类型：

- `training_dynamics`：训练 loss + 验证 accuracy 双面板。
- `benchmark_comparison`：多方法、多数据集 grouped bar。
- `ablation_subject`：消融柱状图 + subject-wise 对比双面板。
- `temporal_frequency`：时间解码曲线 + 频带重要性双面板。

图包格式由 `advanced-charting` 定义；正文先写 `Figure N shows...`，下一行放 `[ACADEMIC_FIGURE: ...]`，图注写在 marker 的 `caption` 字段中，避免图片后再重复输出一条普通段落。

## 学术论文图表约定

当 `academic-paper-authoring` 触发 Conference Paper Contract 时：

- 正文必须先引用，再出现图表：先写 `Fig. 1 shows...` 或 `Table 2 reports...`。
- 图注位于图下方，表题位于表上方。
- 结果表必须标出 best result；可用 Markdown 加粗表示。
- 消融表必须能对应 Method 中的组件名称，避免使用“方案1/方案2”这类不可追踪命名。
- 实证研究论文默认至少规划：方法架构图、训练/验证曲线图、主结果表、消融表、泛化/跨数据集表；若资料不足，表格单元格写 `[PLACEHOLDER: ...]`，图片标记不输出虚假数值。
- 图表没有数据时保留文字占位并写 `[PLACEHOLDER: benchmark/ablation/curve data required]`，不得编造数值。

### 英文学术表格格式

```markdown
Table 2. Classification accuracy (%) on public BMI datasets. Values are mean ± std across subjects; best results are bolded and second-best results are italicized.

| Method | BCI IV-2a | BCI IV-2b | OpenBMI | Params (M) |
|---|---:|---:|---:|---:|
| CSP+LDA | 68.2 ± 8.1 | 72.5 ± 6.3 | 63.4 ± 5.8 | — |
| EEGNet | *76.2 ± 5.4* | *80.1 ± 4.9* | *71.4 ± 4.7* | 0.02 |
| ResNet-EEG (Ours) | **82.5 ± 4.3** | **85.1 ± 3.8** | **79.6 ± 4.1** | 1.84 |
```

- 表题在表格上方，格式为 `Table N. ...`，包含样本口径、单位、统计口径。
- 数值列使用右对齐 `---:`；缺失值用 `—`；多次运行或多被试用 `mean ± std`。
- 表后补一句脚注：显著性标记、检验方法、数据来源或 `[PLACEHOLDER: source needed]`。

## 图表标题规则

| 错误（话题句）| 正确（结论句）|
|--------------|--------------|
| 各区域销售数据 | 华南是唯一同比下滑区域，降幅 5.7% |
| 年度趋势分析 | 收入连续 6 季度增长，Q3 增速首次放缓 |
| 成本结构图 | 人工成本占比从 32% 升至 41%，挤压利润空间 |

## 放置规则

- **表格**：论述该数据的段落**之后**
- **图表**：在表格下方（如有配套表格）或直接跟随结论句
- **同一章节**：表格数量 ≤ 2，图表数量 ≤ 2，超过则拆章节

## 数据来源标注

每张表格和图表必须注明数据来源：
- 来自上传文件：`来源：文件名 p.XX 或 Sheet名`
- 来自计算：`来源：根据 [字段A/字段B] 计算`
- 来自模型知识：`来源：行业惯例（置信度：中，需核验）`
- 无来源时：写 `[数据待补充]`，不写假数字

## Quick Checklist

- [ ] 表格标题在上方，图表标题在图下方
- [ ] 每张表/图有数据来源
- [ ] 图表标题是结论句，不是话题句
- [ ] 数值列有单位（在表头，不在单元格）
- [ ] 无数据的格子写"—"而非空白
- [ ] 每章节表格+图表合计 ≤ 4 个（否则拆章节）
