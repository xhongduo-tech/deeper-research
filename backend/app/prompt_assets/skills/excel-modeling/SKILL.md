---
name: excel-modeling-cn
description: >
  Excel数据建模技能。在 LIDA 四阶段（Summarize/Goals/VizGen/Infographer）框架下，
  接收 DataAnalyst 的 pandas 分析结果，构建可交付的 Excel 工作簿结构和公式建议。
  不执行代码，不生成图表像素，只输出 workbook_spec 供 document_generator.py 调用。
---

# Excel Modeling

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：将 DataAnalyst 分析结果转化为可交付的 Excel 工作簿结构定义。**

## 在 LIDA 流水线中的位置

```
LIDA-1 Summarize（自动：数据摘要）
LIDA-2 Goals（自动：确定分析目标）
LIDA-3 VizGen（DataAnalyst：pandas + 沙箱执行 → chart_configs）
    ↓
Excel Modeling（本技能）← 你在这里
    ↓ workbook_spec
LIDA-4 Infographer（document_generator.py → openpyxl 写文件）
```

## Inputs

- `analysis_results`: DataAnalyst pandas 输出（指标、汇总、分组统计）
- `chart_configs`: `_extract_chart_configs()` 提取的图表配置
- `user_goal`: 原始用户需求（决定 Sheet 命名和分析重点）
- `data_dictionary`: 字段名、单位、口径说明

## Outputs — workbook_spec

```json
{
  "sheets": [
    {
      "name": "描述性Sheet名（非Sheet1）",
      "purpose": "该Sheet分析目标",
      "table_structure": {
        "headers": ["列名（含单位）"],
        "key_formulas": ["=SUM(B2:B100) — 合计行"],
        "freeze_pane": "B2"
      },
      "charts": [
        {"chart_type": "bar", "title": "结论式图表标题", "x_axis": "维度", "y_axis": "指标（单位）"}
      ]
    }
  ],
  "cover_sheet": "摘要Sheet名称",
  "data_integrity_notes": ["口径说明", "空值处理方式"]
}
```

## Sheet 设计规则

### 封面/摘要 Sheet（必须是第一个 Sheet）

| 内容 | 规范 |
|------|------|
| 报告标题 | 来自用户需求，不是"数据分析"之类通称 |
| 关键结论 | 3-5条，每条有数字支撑 |
| 数据范围 | 时间区间、来源、记录数 |
| 更新日期 | 填写或留明确占位符 |

### 数据 Sheet 规范

- Sheet 命名描述性（"销售明细"不是"Sheet2"）
- 表头必须含单位（"收入（万元）"不是"收入"）
- 首行或首列数据区冻结窗格
- 数值表格最后一行给 `=SUM()` 合计，不写死数字

### 图表 Sheet 规范

- **图表标题是结论**：不是"销售数据"，是"Q3 华北超目标 12%"
- 坐标轴标签含单位
- 多于3个数据系列时必须加图例

## 公式安全规则

| 禁止 | 原因 | 替代方案 |
|------|------|---------|
| `=INDIRECT()` | 动态地址易出错 | 固定引用 |
| 跨工作簿引用 | 路径变化即失效 | 合并到同一工作簿 |
| 超3层 IF 嵌套 | 难以维护 | `IFS()` 或辅助列 |
| `=SUM(A:A)` 整列 | 性能极差 | `=SUM(A2:A10000)` |

## 与 DataAnalyst 分工

| 工作 | DataAnalyst | Excel Modeling |
|------|-------------|----------------|
| 执行 pandas 计算 | ✅ | ❌ |
| 提取 chart_configs | ✅ | ❌ |
| Sheet 结构定义 | ❌ | ✅ |
| 公式建议 | ❌ | ✅ |
| 口径/单位说明 | ❌ | ✅ |

## Quick Checklist

- [ ] 第一个 Sheet 是封面/摘要
- [ ] 所有 Sheet 有描述性名称
- [ ] 表头含单位
- [ ] 图表标题是结论句，不是话题句
- [ ] 无整列引用、无跨工作簿引用
- [ ] data_integrity_notes 说明空值和口径
