---
name: ppt-narrative-cn
description: >
  PPT 叙事内容写作技能。在 PPT Director 输出 SlideSpec 后运行，
  为每张幻灯片写具体的正文要点和演讲者备注。遵守 PMRC 叙事弧线，
  不重新设计叙事结构（那已由 PMRC 完成）。
---

# PPT Narrative

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：给每张幻灯片写实质内容，遵循 PMRC 弧线，不重新规划叙事结构。**

## 在流水线中的位置

PPT Director → **PPT Narrative（本技能）** → SlideTailor 布局 → AeSlides 评分

本技能的输入是 SlideSpec（每页的 role、title、claim、evidence、visual_intent），  
输出是每页的正文要点、数据展示、演讲者备注。

## Inputs

- 每页的 SlideSpec（来自 ppt-director）
- `evidence_pack`（来自 data-grounding）
- `story_thread`（PMRC 确定的叙事线索，贯穿全片）
- `.pptd` 模板中的字数和密度限制

## 每页的写作规范

### 要点（Bullet Points）

- **每条 ≤ 25字**，可直接放进幻灯片，不是完整句子
- **每条必须包含数字或明确判断**，不接受纯观点
- **每页要点数：3-5条**，不超过6条
- 第一条是最重要的（读者只看一条也要记住的那条）

### 数据展示规则

| visual_intent | 写法 |
|--------------|------|
| 数据图 | 写图表的标题、X/Y轴含义、关键数据点 |
| 对比表 | 写表格的对比维度和关键差异结论 |
| 流程图 | 写步骤名称和每步的关键输出 |
| 文字强调 | 写最重要的一句判断，字号提示"大字显示" |

### 演讲者备注（Speaker Note）

每页必须写演讲者备注，包含：
1. **过渡语** — 从上一页如何引入这页（第一页除外）
2. **数据解释** — 图表/数字的背景说明
3. **Q&A 预备** — 这页可能被问到什么，怎么回答（简短）

## PMRC 连贯性要求

story_thread 是贯穿全片的叙事线索，每页的要点不能与之矛盾：

- **P 阶段页** — 要点聚焦量化问题，结尾暗示"为什么必须解决"
- **M 阶段页** — 要点聚焦时机和后果，引导到解决方案
- **R 阶段页** — 要点聚焦方案效果，用数字和对比说话
- **C 阶段页** — 要点聚焦行动，必须有责任人/时间节点/量化目标

## 禁止行为

- 禁止每页超过6条要点（幻灯片不是文章）
- 禁止要点超过25字（不能直接放进幻灯片就是太长了）
- 禁止没有数字支撑的纯观点要点（如"需要加强重视"）
- 禁止重新改变 PMRC 确定的叙事弧线（那已经是最优结构）
- 禁止在演讲者备注里省略过渡语

## Workflow

1. **读取 SlideSpec** — 理解每页的 role、claim、evidence、visual_intent
2. **按 PMRC 阶段写要点** — 每阶段有不同的写作重点（见上表）
3. **从证据包接入数字** — 每条要点对应 evidence_pack 中的具体数据
4. **写数据展示说明** — 图表/表格的标题、维度、关键数据点
5. **写演讲者备注** — 过渡语 + 背景说明 + Q&A 预备
6. **密度自检** — 每页要点数 ≤ 6，每条 ≤ 25字

## Quick Checklist

- [ ] 每页要点数 3-5 条，不超过 6 条
- [ ] 每条要点 ≤ 25 字且含数字或明确判断
- [ ] 演讲者备注包含过渡语
- [ ] story_thread 在全片连贯体现
- [ ] 未重新设计叙事结构（只写内容，不改结构）
