# ChartSpec Contract

ChartSpec 是图表生成的唯一语义源。模型不得分别为前端预览、Word/PPT 插图和 Excel 图表生成三份不一致的数据。

## Required

- `chart_type`
- `title`
- `labels`
- `series`
- `unit`
- `source_note`

## Optional

- `secondary_unit`
- `orientation`
- `source_range`
- `filter`
- `aggregation`
- `confidence`

## Acceptance

- 关键图表必须能解释每个 series 的来源字段或计算公式。
- 导出失败时允许从原生图表降级为 PNG，但不得改变 ChartSpec 数据。
- QA 必须检查图表是否空白、是否有标题、是否有来源说明。
