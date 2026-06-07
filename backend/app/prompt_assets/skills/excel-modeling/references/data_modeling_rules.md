# Data Modeling Rules

## Profiling

- Identify columns, types, units, date ranges, categories, and unique keys.
- Count rows, missing values, duplicates, outliers, and invalid values.
- Detect mixed units, currencies, date formats, and percent formats.
- Preserve the original raw data before cleaning.

## Cleaning

- Standardize entity names, date formats, region/category labels, and numeric types.
- Keep a cleaning log for dropped rows, filled values, and corrected labels.
- Do not overwrite raw data.
- Mark imputed values and assumptions.

## Metric Design

- Define numerator, denominator, unit, period, and aggregation rule.
- Separate historical actuals from forecast or scenario outputs.
- Use consistent metric names across sheets and downstream PPT/Word.
- Avoid comparing metrics across different scopes without caveats.

## Reconciliation

- Check row counts before and after cleaning.
- Reconcile totals to source tables when possible.
- Explain differences caused by filtering, deduplication, or missing values.
