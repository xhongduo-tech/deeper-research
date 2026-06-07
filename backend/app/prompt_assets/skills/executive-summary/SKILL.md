---
name: executive-summary-cn
description: >
  执行摘要写作技能。在完整报告草稿已生成后运行，从全文中提炼决策者所需的
  最高优先级信息，输出独立可读的执行摘要。不是报告引言，不是内容目录，
  是可单独呈送给不读正文的决策者的完整简报。
---

# Executive Summary

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：从完整报告中提炼决策者视角的独立简报。不是引言，不是目录，是完整交付物。**

## 执行摘要 ≠ 引言

| 维度 | 引言（Introduction）| 执行摘要（Executive Summary）|
|------|---------------------|-------------------------------|
| 读者 | 读完整报告的人 | 只读这一页的决策者 |
| 目的 | 铺垫背景，引入正文 | 独立完整，替代正文阅读 |
| 内容 | 研究背景和问题 | 发现 + 结论 + 行动建议 |
| 顺序 | 背景→问题→研究方法 | 结论优先（先给结果，再给依据）|
| 长度 | 无固定限制 | **不超过 1 页（约 300-500 字）** |

## 写作结构（固定顺序）

```
[1] 核心结论（1-2句）
    这份报告的最重要发现/判断是什么

[2] 关键发现（3-5条带数字的要点）
    每条 ≤ 25 字，必须有数字或明确判断

[3] 主要建议（2-3条具体可执行的行动）
    必须有责任主体/时间节点/量化目标

[4] 背景说明（可选，1-2句）
    只写帮助理解结论的最少背景，不做铺垫
```

## 写作规范

### 结论优先原则

**错误顺序**（引言写法）：
> "随着市场环境的变化，公司面临诸多挑战。本报告对 XXX 进行了深入分析，发现……"

**正确顺序**（执行摘要写法）：
> "Q3 盈利能力下滑 8 个百分点，核心原因是华南渠道成本上升。建议在 30 天内启动渠道重组，预计可挽回 2000 万毛利。"

### 每条发现的格式

```
• [量化结论]：[关键数字] — [简短原因/背景]
```

例：`• 收入超目标 12%：华北贡献 74%，华南同比下滑 5 个百分点`

### 建议格式（必须可执行）

| 不可接受 | 可接受 |
|---------|--------|
| "建议加强管理" | "在 Q4 启动 XX 项目（负责人：XX，预算：XX 万）" |
| "需要关注风险" | "立即启动 XX 风控措施，30 天内完成" |

## 从报告草稿提炼的规则

1. **扫描章节末尾**：每章结论段通常含核心判断
2. **收集所有数字**：从正文中抽取最有力的 5-8 个数字，只用最关键的 3 个
3. **找明确建议**：正文中的"建议""应当""需要"段落
4. **去掉背景**：所有铺垫性内容（"随着 XX 的发展……"）一律删除
5. **检查独立性**：删除正文后，执行摘要仍能被理解

## 长度控制

- **硬限制：不超过 500 字**（含标点）
- 如超出，按以下顺序删减：背景说明 → 建议细节 → 发现数量（保留最重要的 3 条）

## Quick Checklist

- [ ] 结论优先（第一句是核心结论，不是背景）
- [ ] 每条发现有数字支撑
- [ ] 建议有责任主体或时间节点
- [ ] 独立可读（不依赖正文）
- [ ] 全文不超过 500 字
- [ ] 无引言式铺垫语句
