---
name: word-authoring-cn
version: "1.0"
description: >
  Word 长文档起草技能。按 document-chief-planner 制定的章节骨架，逐章调用证据包写作。
  知道自己的输出会被 DECRIM 精炼，因此专注于内容完整和证据接入，不过度追求语言完美。
  可接入知识库上下文（kb_context）补充行业背景和标准数据。
category: doc
pipeline_position: 3
depends_on:
  - intake-planner
  - document-chief-planner
  - data-grounding
feeds_into:
  - citation-bibliography
  - qa-verification
kb_aware: true
input_schema:
  - name: chapter_plan
    type: array
    required: true
    description: 来自 document-chief-planner 的章节骨架，每项含标题、核心论点、证据来源、目标字数
  - name: evidence_pack
    type: object
    required: true
    description: 来自 data-grounding 的结构化证据，含事实列表、来源锚点和置信度
  - name: data_dictionary
    type: object
    required: false
    description: 字段/指标释义字典，保证跨章数据口径一致
  - name: user_goal
    type: string
    required: true
    description: 用户原始需求，用于确保每章内容对齐整体目标
  - name: kb_context
    type: array
    required: false
    description: 来自 RAG 检索的知识库片段，作为行业背景和标准数据补充；相似度 < 0.7 的结果标记为低置信度
  - name: output_format
    type: object
    required: false
    description: 字数、受众、导出格式等约束
output_schema:
  - name: report_markdown
    type: string
    description: 完整的 Markdown 草稿，包含所有章节；使用 ## 章节标题、Markdown 表格、[来源：文件名 p.XX] 格式
  - name: data_gaps
    type: array
    description: 所有 [数据待补充：XXX] 标注的位置列表及说明，供 DECRIM 和 qa-verification 处理
  - name: evidence_coverage
    type: object
    description: 各章节证据引用覆盖率报告（已引用/规划证据数量比），用于 DECRIM 评分参考
quality_thresholds:
  min_score: 0.85
  retry_on_fail: true
  max_retries: 2
---

# Word Authoring

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：按规划逐章起草，接入证据，输出结构完整的 Markdown 草稿。**

## 与 DECRIM 的合作模型

本技能输出后，DECRIM（word_critique_refiner.py）会自动运行：
- 评估9条质量约束（数据充实度、来源可查、逻辑一致等）
- 对失败的约束定位原因，指导重写
- 最多2轮迭代，目标内容分 ≥ 90/100

因此本技能的写作策略是：
- **优先接入证据** — 每个论点都要有来自 evidence_pack 的事实支撑
- **结构完整比语言优美更重要** — DECRIM 会处理论点深度，不要为了流畅而省略内容
- **数据缺口要显式标注** — 写 `[数据待补充：XXX]`，让 DECRIM 知道哪里需要加强

## Inputs

- `chapter_plan`（来自 document-chief-planner）
- `evidence_pack` 和 `data_dictionary`（来自 data-grounding）
- `user_goal`（原始需求）
- `output_format` 约束（字数、受众、导出格式）
- `kb_context`（可选，来自 RAG 检索）

## 证据层级引用规则

来自 data-grounding 的证据按层级使用不同引用格式：

| 层级 | 来源类型 | 引用格式 | 置信度标签 |
|------|---------|---------|-----------|
| L1/L2 | 用户上传的数据/文档 | `[来源：文件名 p.XX]` | 高置信度，可直接使用 |
| L3 | KB 片段（score ≥ 0.7）| `[KB来源：文档名]` | 中高置信度 |
| L4 | KB 片段（score 0.5–0.7）| `[低置信度参考：文档名]` | 使用时需加限制性语言 |
| L5 | 模型知识/行业惯例 | `[基于行业惯例，无直接来源]` | 仅在无 L1-L4 时使用 |

L4 证据必须搭配"可能""据行业惯例"等限制性语言。L5 证据不得写成确定性事实。

## Outputs

- 完整的 Markdown 草稿，包含所有章节
- 每章使用 `## 章节标题` 格式
- 数据表格用 Markdown 表格格式
- 证据引用按层级格式（L1-L5 规则）
- 数据缺口用 `[数据待补充：XXX]` 标注
- `data_gaps`: 所有 `[数据待补充]` 标注的位置列表

## 写作规范

### 每章的结构

```
## [章节标题]

[核心论点，一句话，来自 chapter_plan]

[展开论述，引用 evidence_pack 中的数据]
[数字必须有来源：如"根据上传的销售数据，Q3 营收 3.2亿元[来源：sales_2026.xlsx]"]

[分析和洞察]

[小结 / 过渡到下一章]
```

### 表格格式

当 chapter_plan 要求表格时：
- 表头必须含单位
- 数字对齐
- 最后一行为合计/均值（如适用）
- 表格标题和数据来源说明写在表格上方

## Academic Paper Mode

当 chapter_plan 来自 `academic-paper-authoring` 技能或用户目标包含"论文/paper/conference/journal/实证研究"时，**激活 Academic Paper Mode**，覆盖如下默认规则：

### 引用格式（覆盖默认）

- 用 `[CITE: <描述来源的一句话>]` 代替 `[来源：文件名]`，由 `citation-bibliography` 技能后续处理
- 数字引用写 `[N]`（如 `[1]`, `[2, 3]`）；APA 写 `(Author, Year)`
- 禁止数字引用和 APA 混用

### 数字/数据缺口（覆盖默认）

- 用 `[PLACEHOLDER: <描述>]` 代替 `[数据待补充：XXX]`，格式与 `academic-paper-authoring` 一致

### 方程格式

- 每个展示方程顺序编号：独占一行，末尾写 `(N)`
- 每个新符号在首次出现时**就地定义**：`where **X** ∈ ℝ^{C×T} denotes...`
- 正文引用写 `Eqn. (N)`

### 图表交叉引用

- 先在正文句子中引用，再出现图/表：`Fig. N shows...` / `as reported in Table N`
- 禁止写 `as shown above` / `下图所示`——永远用显式编号
- 图注写在图下方；表注写在表上方

### 结果叙述

- 每个实验结论遵循 **Claim → Evidence → Interpretation** 三步
- Results 节只陈述结果，不解释（解释留给 Discussion）
- 定量结果：`mean ± std`，标注统计显著性 `p < 0.01`

### 禁止行为（Academic Paper Mode）

- 禁止编造任何基线准确率、参数量、训练时间——用 `[PLACEHOLDER: ...]`
- 禁止在 Results 节加解释
- 禁止混用第一/第三人称
- 禁止商业化表达

### 一般文档禁止行为

- 禁止编造数字（没有来源的数字写 `[数据待补充]`）
- 禁止复述附件中与用户需求无关的内容（style_reference 的事实不得写入正文）
- 禁止目标文档标题使用参考文件标题
- 禁止在不同章节使用不一致的口径（统一单位、时间段）

## Workflow

1. **确认规划** — 读取 chapter_plan，理解每章的核心论点和证据分配
2. **按章起草** — 逐章写作，每章先写核心论点，再展开，引入对应证据
3. **数据接入** — 从 evidence_pack 提取相关数字，附来源锚点
4. **标注缺口** — evidence_pack 里找不到的数据，用 `[数据待补充：XXX]` 标注
5. **保持一致** — 跨章使用统一的术语、单位、时间段
6. **输出完整草稿** — 包含所有章节，使用标准 Markdown 格式

## Quick Checklist

通用：
- [ ] 每章有核心论点
- [ ] 每个数字有来源引用或 [数据待补充] / [PLACEHOLDER:...] 标注
- [ ] 数据缺口已显式标注（不是静默省略）
- [ ] 所有章节已起草，无章节标题留空
- [ ] 未从 style_reference 提取事实

Academic Paper Mode（激活时额外检查）：
- [ ] 引用格式统一（[N] 或 (Author, Year)，二选一贯穿全文）
- [ ] 每个方程顺序编号，每个新符号在首次出现时就地定义
- [ ] 所有 Fig./Table/Eqn. 在正文中先引用再出现
- [ ] Results 节无解释性语句
- [ ] 所有实验结论遵循 Claim → Evidence → Interpretation
- [ ] 无编造基线数字（均用 [PLACEHOLDER:...]）
- [ ] 人称视角全文一致
