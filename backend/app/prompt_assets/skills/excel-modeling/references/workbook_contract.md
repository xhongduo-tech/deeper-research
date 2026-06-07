# Workbook Contract

## Recommended Sheets

- `README`: purpose, sources, update date, assumptions, and navigation.
- `Raw_*`: untouched source tables.
- `Clean_Data`: normalized analysis-ready data.
- `Inputs`: user-editable assumptions and scenario controls.
- `Calc`: formulas, pivots, model logic, and helper tables.
- `Outputs`: final tables, KPIs, and summaries.
- `Charts`: chart-ready ranges and embedded visuals.
- `QA`: checks, reconciliation, and known limitations.

## Formula Rules

- Prefer formulas over hard-coded calculated values.
- Keep assumptions on `Inputs`, not buried inside formulas.
- Use named ranges or structured tables when practical.
- Avoid volatile formulas unless needed.
- Flag formula errors such as `#DIV/0!`, `#N/A`, or broken references.

## Formatting

- Freeze header rows on review sheets.
- Use clear number formats for currency, percent, counts, and dates.
- Keep column widths readable.
- Apply light table styling; avoid decorative colors that obscure data.
- Add source notes and units near outputs.

## Export

- Workbook should open without repair prompts.
- Formulas, charts, filters, and frozen panes should survive export.
- Hidden sheets should be avoided unless the user requests them.
