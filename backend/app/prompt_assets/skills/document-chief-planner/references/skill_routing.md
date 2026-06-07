# Skill Routing Reference

Skill routing chooses the smallest stack that can complete the job with evidence,
format, and QA coverage.

## Default Word Stack

1. `intake-planner`
2. `document-chief-planner`
3. `data-grounding`
4. `reference-style-miner` when examples exist
5. Specialized document skill
6. `table-figure-authoring` when visual evidence exists
7. `advanced-charting` when charts or computed visuals are needed
8. `citation-bibliography` when citations or sources are required
9. `word-authoring`
10. `format-conversion`
11. `qa-verification`

## Routing Principles

- Put custom skills after source reading and before drafting.
- Put the specialized document skill before table, chart, citation, and drafting skills so it can set the section contract first.
- Put citation and table skills before full drafting when they affect section structure.
- Put QA at both pre-export and final-export gates for high-stakes documents.
- If multiple specialized skills apply, choose the primary deliverable skill and use secondary skills as constraints only.
- Infer the specialized skill from both normalized `report_type` and the user's original brief; users often say "写一篇 CVPR 风格论文" without selecting a report type.

## Examples

- Paper: `academic-paper-authoring`, `table-figure-authoring`, `citation-bibliography`.
- Full conference paper / CVPR / NeurIPS / ICLR style: `academic-paper-authoring` must load `references/structure_narrative_contract.md`; Method 3.1-3.4 and Experiments 4.1-4.3 are non-optional.
- Research report: `research-report-authoring`, `executive-summary`, `table-figure-authoring`, `citation-bibliography`.
- PRD: `prd-authoring`, `technical-document-authoring`.
- Bid: `bid-proposal-authoring`, `legal-document-authoring`, `table-figure-authoring`.
