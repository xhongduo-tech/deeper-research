---
name: document-chief-planner-cn
version: "1.0"
description: >
  Word/DOCX 文档结构规划技能。负责锁定目标文档的标题、受众、章节骨架和证据分配计划。
  不负责质量精炼（由 DECRIM 在起草后完成），不负责写正文（由 word-authoring 完成）。
  可调用知识库检索行业结构惯例，辅助章节设计。
category: meta
pipeline_position: 2
depends_on:
  - intake-planner
feeds_into:
  - word-authoring
  - research-report-authoring
  - data-grounding
  - table-figure-authoring
kb_aware: true
input_schema:
  - name: user_goal
    type: string
    required: true
    description: 用户原始输入，来自 intake-planner，绝对保留，不改写
  - name: uploaded_files
    type: array
    required: false
    description: 上传文件清单，每项含 name、type、role（source_evidence / style_reference / template）
  - name: constraints
    type: object
    required: false
    description: 量化约束（字数、受众、导出格式、保密等级等），来自 intake-planner
  - name: kb_context
    type: array
    required: false
    description: 来自 RAG 检索的知识库片段，辅助章节设计（如行业标准结构）
output_schema:
  - name: target_title
    type: string
    description: 目标文档的正确标题，必须来自用户需求，不得是参考文件标题
  - name: target_period
    type: string
    description: 报告周期（如"2026年Q1"），从用户需求推导
  - name: reference_role
    type: object
    description: 每个参考文件的角色映射（structure / style / metric / continuity）
  - name: chapter_plan
    type: array
    description: 章节骨架，每项含标题、核心论点、证据来源、预期表图、目标字数、写作提示
  - name: table_figure_plan
    type: array
    description: 需要表格或图表的章节列表，含数据来源说明
  - name: citation_strategy
    type: object
    description: 引用格式和注脚策略
  - name: quality_gates
    type: object
    description: 起草前、预览前、下载前各阶段的质量门控条件
quality_thresholds:
  min_score: 0.88
  retry_on_fail: true
  max_retries: 2
---

# Document Chief Planner

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责边界：规划结构，不写内容，不做质量精炼（那是 DECRIM 的工作）。**

## 与 DECRIM 的分工

| 阶段 | 负责者 | 工作内容 |
|------|--------|----------|
| 结构规划 | **本技能** | 章节骨架、证据分配、引用策略 |
| 内容起草 | word-authoring | 按规划逐章写作 |
| 质量精炼 | **DECRIM** | 9条约束评分 → 批判 → 重写（≤2轮）|
| 导出校验 | qa-verification | 格式、链接、导出一致性 |

规划时**不需要**为"内容质量"设置修复循环，DECRIM 会处理。

## Inputs

- `user_goal`（来自 intake-planner，原始输入）
- 上传的 source_evidence 文件（事实来源）
- 上传的 style_reference 文件（结构/风格参考，不是事实）
- 输出格式约束、字数、受众

## Outputs

| 输出 | 用途 |
|------|------|
| `target_title` | 目标文档的正确标题（来自用户需求，非参考文件标题）|
| `target_period` | 报告周期（如"2026年Q1"）|
| `reference_role` | 参考文件的角色：structure / style / metric / continuity |
| `chapter_plan` | 每章：标题、核心论点、证据需求、目标字数 |
| `table_figure_plan` | 哪些章节需要表格/图表，数据来源 |
| `citation_strategy` | 引用格式和注脚策略 |
| `quality_gates` | 起草前、预览前、下载前各需要满足什么条件 |

## 目标标题推导规则

这是最容易出错的地方，必须严格执行：

- 用户说"参考2025述职生成2026述职" → `target_title = "2026年述职报告"`
- 2025年的文件只能提供：结构参考、基线数据、连续性对比、经验教训
- 2025年的事实**不得**作为2026年的当期事实
- 目标标题**不得**是用户输入的句子，**不得**是参考文件的标题

## Chapter Plan 格式

每章的规划必须包含：

```
章节N: [标题]
- 核心论点：（一句话，这章要证明什么）
- 证据来源：（具体引用哪个上传文件的哪个数据）
- 预期表格/图：（有/无，描述）
- 目标字数：（数字）
- 写作提示：（给 word-authoring 的具体指令）
```

## 章节数量与字数预算

根据输出格式约束和用户需求复杂度，遵循以下预算规则：

| 报告类型 | 推荐章节数 | 每章目标字数 | 总字数参考 |
|---------|----------|------------|----------|
| 简报/执行摘要 | 3-5 章 | 300-600 字 | 1,500-3,000 字 |
| 标准分析报告 | 5-8 章 | 500-1,000 字 | 3,000-8,000 字 |
| 深度研究报告 | 6-10 章 | 800-1,500 字 | 5,000-15,000 字 |
| 学术论文 | 由 academic-paper-authoring 技能处理 | — | — |

若用户指定字数，按用户要求分配。若用户未指定，默认"标准分析报告"预算。

## 证据分配规则

章节规划时必须完成"证据预分配"——即在写作前确认每章有足够的证据支撑：

```
证据充足（可直接起草）：evidence_pack 中有 ≥1 条直接相关的 L1/L2 证据
证据有限（需补充）：仅有 L3/L4/L5 证据，或无直接数字
证据缺失（需标注）：evidence_pack 中无相关证据，起草时必须用 [数据待补充]
```

在 `chapter_plan` 的每章中标注证据状态，让 word-authoring 技能提前知道哪章会有数据缺口。

## 质量门控定义

`quality_gates` 字段必须明确定义三个阶段的门控条件：

```json
{
  "pre_draft": [
    "evidence_pack 已接收，source_inventory 已确认",
    "style_reference 与 source_evidence 已完全分离",
    "target_title 已从用户需求中提取（非参考文件标题）"
  ],
  "pre_preview": [
    "所有章节已起草（无章节标题留空）",
    "每章有至少一个证据引用或显式 [数据待补充] 标注",
    "目标文档标题与 target_title 一致"
  ],
  "pre_export": [
    "DECRIM 评分 ≥ 85/100（由 DECRIM 报告）",
    "qa-verification 通过（qa_status = pass 或 warn）",
    "无 P0 阻断问题"
  ]
}
```

## Workflow

1. **锁定目标身份** — 从用户需求（而非参考文件）确定 `target_title` 和 `target_period`
2. **分类参考文件** — 明确每个参考文件只能扮演哪种角色（structure/style/metric/continuity）
3. **设计章节骨架** — 决定章节数量、顺序、每章的核心论点；对照章节数量预算
4. **分配证据** — 为每章指定来自 evidence_pack 的证据（L1-L5），标注证据充足度
5. **规划表图** — 哪些章节需要表格、图表，数据从哪来，交给 table-figure-authoring
6. **定质量门控** — 填写三阶段质量门控（pre_draft / pre_preview / pre_export）

## Non-Negotiables

- target_title 必须来自用户需求，不得来自参考文件
- 参考文件的事实内容不得流入目标文档的当期事实层
- 不得在规划阶段就开始写正文段落
- 质量循环留给 DECRIM，不要在此阶段设置"写完后自我评分再改"的循环
- 章节数量不得远超或远低于字数预算（避免每章内容过于稀薄或拼凑）

## Quick Checklist

- [ ] target_title 来自用户需求，不是参考文件标题
- [ ] 每章有核心论点和证据来源（含证据充足度标注）
- [ ] style_reference 与 source_evidence 已严格分离
- [ ] 章节数量符合报告类型的字数预算范围
- [ ] quality_gates 三个阶段已全部定义
- [ ] 未在规划阶段写任何正文
