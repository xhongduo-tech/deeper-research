# Style Profile Schema

```json
{
  "document_type": "",
  "audience": "",
  "heading_levels": [],
  "section_sequence": [],
  "paragraph_density": "",
  "tone": "",
  "table_patterns": [],
  "figure_patterns": [],
  "citation_patterns": [],
  "appendix_pattern": "",
  "do_follow": [],
  "do_not_follow": []
}
```

## Extraction Notes

- `section_sequence` should use roles, not copied headings when headings contain sensitive facts.
- `table_patterns` should describe structure: comparison table, scoring matrix, KPI table, risk register.
- `figure_patterns` should describe purpose: trend, architecture, funnel, roadmap, causal chain.
- `do_not_follow` should include weak writing, overlong sections, missing sources, or inconsistent numbering.
