# Dynamic Queue

Chief should expose work as a dynamic queue, not a fixed prophecy.

## Default Nodes

1. `user_prompt`: preserve original request and constraints.
2. `intake_parse`: parse deliverable, audience, scope, and missing inputs.
3. `asset_select`: select skills, templates, and references.
4. `source_read`: read uploaded files and knowledge bases.
5. `evidence_build`: produce evidence pack, data dictionary, conflicts, assumptions.
6. `draft_or_model`: write narrative, report, deck, or spreadsheet model.
7. `layout_or_format`: apply PPT/Word/Excel presentation rules.
8. `qa_verification`: check facts, logic, structure, formatting, and export readiness.
9. `handoff`: provide final artifact and residual risks.

## Node Contract

Each node should define:

- `id`
- `owner`
- `inputs`
- `expected_output`
- `status`
- `next_node_candidates`
- `pause_condition`
- `visible_summary`

## Queue Rules

- Reveal the next executable node after current-node results are known.
- Add a clarification node when missing inputs block correctness.
- Add a repair node when QA finds unsupported claims, overflow, or broken export.
- Do not show all future nodes as certain if evidence extraction may change scope.
