# Planning Contract Reference

The planning contract is the highest-level instruction object for a document
run. Every downstream skill receives it and must report deviations.

## Required Fields

- `user_goal`: exact user question or task.
- `document_type`: normalized target type.
- `audience`: reader or decision-maker.
- `source_files`: current-task evidence files.
- `reference_examples`: style examples only.
- `selected_skills`: ordered skill list.
- `skill_routing`: stage-to-skill map.
- `outline_strategy`: section logic.
- `table_figure_strategy`: charts, tables, captions, and appendix policy.
- `citation_strategy`: references, footnotes, source labels, or assumptions.
- `quality_gates`: checks required before final handoff.

## Stage Outputs

Each stage must have:

- Owner.
- Inputs.
- Expected output.
- Failure condition.
- Repair strategy.
- User-visible summary.

## Failure Conditions

Pause or repair if:

- The user goal cannot be mapped to a document type.
- Required source files are unreadable.
- A reference example is mistakenly used as factual evidence.
- A specialized skill conflicts with user instructions.
- Preview and export content diverge.
