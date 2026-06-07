# Extraction Rules

## File Extraction

- Preserve headings, table titles, page numbers, dates, authors, and version labels.
- Ignore watermarks, navigation text, repeated headers/footers, and template filler.
- Keep original Chinese and English entity names; add normalized aliases only after extraction.
- For scanned or OCR material, mark low-confidence readings rather than silently correcting them.

## Table Extraction

- Capture column names, units, time periods, row labels, footnotes, and formulas.
- Preserve negative signs, percentages, currencies, decimal places, and scale words such as "万" or "亿".
- Do not merge rows or columns when the hierarchy carries meaning.
- When a table is too large, extract the rows and columns relevant to the user goal plus totals.

## Metric Normalization

- Record original unit before converting.
- State denominator for rates, shares, averages, and per-capita values.
- Do not compare metrics across different periods or scopes without a caveat.
- Keep source currency and exchange-rate assumptions visible.

## Citation Hints

Use compact refs suitable for downstream notes:

- `file.pdf p.12`
- `report.docx §2.3`
- `data.xlsx Sheet1!B2:F20`
- `KB:policy:2025-04`

## Anti-Hallucination Checks

- If a requested number is absent, return `missing` or an estimate plan.
- If the user asks for a chart, verify the required fields exist before proposing it.
- If evidence is qualitative only, avoid inventing precise percentages or rankings.
