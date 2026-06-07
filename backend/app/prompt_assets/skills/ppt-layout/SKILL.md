---
name: ppt-layout-cn
description: >
  PPT 版式辅助技能。在 SlideTailor 自动选型的基础上，提供版式使用指南和密度控制规则。
  SlideTailor 已自动识别 slide_type，本技能负责执行层面的版式约束。
---

# PPT Layout

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：版式执行约束。SlideTailor 已选好布局类型，本技能负责确保内容填充不违反版式规则。**

## SlideTailor 已处理的工作

系统的 SlideTailor（ppt_layout_selector.py）已根据内容类型自动选型：

| slide_type | 典型场景 |
|-----------|---------|
| `cover` | 封面页（标题 + 副标题 + 日期）|
| `title_content` | 标题 + 要点列表（通用型）|
| `data_chart` | 标题 + 图表（数据为主）|
| `comparison` | 标题 + 左右对比（多方案/多维度对比）|
| `big_number` | 核心数字强调（1-3个大数字）|
| `process` | 流程图（步骤 → 步骤 → 结果）|
| `quote_highlight` | 引言/金句强调页 |
| `closing` | 结束页（行动号召 + 联系方式）|

本技能的工作是：**根据已选定的 slide_type，执行对应的内容密度和排版约束**。

## 各版式的内容约束

### cover（封面）
- 主标题：≤ 16字，不写副词和"报告""分析"等套语
- 副标题：场合 + 日期 + 汇报人
- 无正文要点

### title_content（标题+内容，最常用）
- 标题：结论句，≤ 12字
- 要点：3-5条，每条 ≤ 25字
- 不超过 1 张图或 1 张表

### data_chart（数据图表）
- 标题：图表的结论，不是"XX数据"
- 图表占 60% 面积，文字说明 ≤ 3条
- 必须标注数据来源和时间范围

### comparison（对比）
- 标题：对比的核心结论
- 左右各 2-3 条要点
- 结尾有综合判断（哪方更优，理由是什么）

### big_number（大数字）
- 1-3 个数字，每个 ≤ 8 位数
- 每个数字下方 1 行说明（≤ 15字）
- 不写长段落

### process（流程）
- 步骤数：3-6 步
- 每步标题 ≤ 8字 + 关键输出 ≤ 15字
- 不写详细描述（那是演讲者备注的工作）

### closing（结束）
- 行动号召：1-2句，具体可执行
- 联系/跟进信息
- 不加新内容

## AeSlides 评分会检测的问题

以下问题会导致 AeSlides 给低分（触发自动修正）：

| 问题 | AeSlides 检测方式 | 如何避免 |
|------|-----------------|---------|
| 元素碰撞 | 检测重叠面积 > 5% | 内容不要超出版式预留区域 |
| 留白不足 | 留白率 < 20% | 不要在每个区域塞满内容 |
| 视觉不平衡 | 质心偏移 > 30% | 左右/上下内容量要大致平衡 |
| 文字过密 | 单页字符数 > 400 | 超过 400 字必须拆成两页 |

## 密度红线

**任何版式下，单页字符数（包括标题和要点）不得超过 400 字。**

超过 400 字的幻灯片必须：
1. 删减：去掉最不重要的要点
2. 拆页：将内容拆成两页
3. 转移：详细内容移到演讲者备注

## Quick Checklist

- [ ] 每页版式类型与内容类型匹配
- [ ] 单页字符数 ≤ 400
- [ ] 数据图表有来源说明
- [ ] 对比页有综合结论
- [ ] 封面无正文要点
