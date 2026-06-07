---
name: qa-verification-cn
version: "1.0"
description: >
  最终质量校验技能。在所有内容生成和 SOTA 精炼（DECRIM/AeSlides）完成后运行，
  执行格式合规、导出一致性、事实标注完整性的最终核查。不做内容写作，不做质量精炼。
  输出标准化 qa_status 报告，决定是否允许导出。
category: utility
pipeline_position: 5
depends_on:
  - word-authoring
  - research-report-authoring
  - ppt-director
  - ppt-layout
  - excel-modeling
feeds_into: []
kb_aware: false
input_schema:
  - name: draft_content
    type: string
    required: true
    description: 经 DECRIM 或 AeSlides 精炼后的最终草稿内容（Markdown / SlideSpec 列表 / 工作簿描述）
  - name: output_format
    type: string
    required: true
    description: "目标格式：word / ppt / excel，决定执行哪套检查清单"
  - name: chapter_plan
    type: array
    required: false
    description: 来自 document-chief-planner 的规划，用于核查章节完整性
  - name: target_title
    type: string
    required: false
    description: 来自 document-chief-planner 的目标标题，用于验证最终文档标题一致性
  - name: uncertainty_log
    type: array
    required: false
    description: 来自 research-report-authoring 的不确定性记录，用于核查标注是否完整
output_schema:
  - name: qa_status
    type: string
    description: "整体状态：pass（无阻断问题）/ warn（有警告但允许导出）/ blocked（存在 P0 问题，禁止导出）"
  - name: p0_issues
    type: array
    description: P0 阻断性问题列表，每项含问题描述和修复建议；此列表非空则 export_safe=false
  - name: p1_issues
    type: array
    description: P1 警告性问题列表，允许导出但需告知用户
  - name: p2_notes
    type: array
    description: P2 记录性信息，仅存档不阻断
  - name: export_safe
    type: boolean
    description: 是否允许执行导出操作；只有 qa_status 为 pass 或 warn 时才为 true
  - name: residual_risks
    type: array
    description: 已知风险提示，随最终文档一并展示给用户
quality_thresholds:
  min_score: 1.0
  retry_on_fail: false
  max_retries: 0
---

# QA Verification

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：最终门控校验。不重复 DECRIM 的内容质量工作，专注格式合规和导出安全。**

## 在流水线末尾的位置

```
DECRIM 精炼完成 → AeSlides 评分完成（PPT）
    ↓
QA Verification（本技能）← 你在这里
    ↓
导出/下载
```

DECRIM 已处理内容质量（9条约束），AeSlides 已处理视觉质量（PPT）。  
本技能处理的是 **格式合规、导出安全、事实标注完整性**。

## 检查清单（按格式分类）

### Word / DOCX 通用检查

| 检查项 | 通过条件 | 失败处理 |
|--------|---------|---------|
| 目标标题正确 | 标题来自用户需求，非参考文件标题 | 阻断，要求修正 |
| 章节结构完整 | 所有规划章节都有内容，无空章节 | 阻断，要求补全 |
| 数据标注完整 | 所有 [数据待补充] 已处理（填写或说明无法获取）| 标记警告 |
| 导出格式安全 | Markdown 标题层级正确（H1/H2/H3 顺序合理）| 自动修正 |
| 表格格式 | 所有 Markdown 表格可正确渲染 | 自动修正 |

### PPT / PPTX 通用检查

| 检查项 | 通过条件 | 失败处理 |
|--------|---------|---------|
| AeSlides 分数 | 平均分 ≥ 70（已由系统处理，确认记录即可）| 记录分数 |
| 封面信息完整 | 有标题、日期、汇报人 | 警告 |
| 结束页存在 | 有 closing 类型页 | 警告 |
| 每页有标题 | 无空标题页 | 阻断 |

### Excel / XLSX 通用检查

| 检查项 | 通过条件 | 失败处理 |
|--------|---------|---------|
| Sheet 命名 | 每个 Sheet 有描述性名称，非 Sheet1/Sheet2 | 警告 |
| 公式有效 | SUM/AVERAGE 公式引用范围正确（非空引用）| 标记 |
| 图表有标题 | 每个图表有标题（非"图表1"）| 警告 |
| 封面摘要 | 第一个 Sheet 是封面/摘要 | 警告 |

## 严重性分级

- **P0（阻断）** — 必须修复才能导出：目标标题错误、空章节、无法渲染的格式
- **P1（警告）** — 显示问题但允许导出：数据标注未处理、封面信息缺失
- **P2（记录）** — 仅记录不阻断：AeSlides 分数低于90但高于70

## 不属于本技能的工作

以下检查项已由其他机制处理，本技能不重复：

- ❌ 内容质量（DECRIM 已处理）
- ❌ 视觉几何美观度（AeSlides 已处理）
- ❌ 证据是否充分（data-grounding + word-authoring 应已处理）
- ❌ 重新写作任何章节（本技能只检查，不写内容）

## Outputs

```json
{
  "qa_status": "pass|warn|blocked",
  "p0_issues": [],
  "p1_issues": [],
  "p2_notes": [],
  "export_safe": true/false,
  "residual_risks": []
}
```

## Quick Checklist

- [ ] 目标标题来自用户需求（非参考文件标题）
- [ ] 无空章节/空页
- [ ] 所有表格和公式可正常渲染
- [ ] P0 问题已全部解决
- [ ] P1/P2 已记录在 qa_status 中
- [ ] export_safe 字段已明确填写
