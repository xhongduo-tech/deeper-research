# Complex Chart Rules

## Combo Chart

Use combo charts when one table contains an absolute metric and a rate metric over a temporal axis.

Examples:

- `收入（万元）` + `同比增长率`
- `成本（万元）` + `毛利率`
- `用户数` + `转化率`

Rules:

- Bar series comes first.
- Rate-like series uses line.
- Both axes must name units.
- If more than two units appear, split the chart.

## Pie / Donut

Use only for positive composition data with 2-8 categories. If categories exceed 8, use bar chart and group the tail as `其他`.

## Bar

Use for ranking and category comparison. Prefer horizontal bars when labels are long.

## Line

Use for time series, trend, and multi-period comparison. Do not use line charts for unordered categories.
