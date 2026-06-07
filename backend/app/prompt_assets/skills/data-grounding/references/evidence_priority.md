# Evidence Priority

Use this hierarchy when claims conflict:

1. Explicit user instruction and user-provided corrections.
2. Uploaded source files with clear provenance.
3. Retrieved knowledge-base material selected for this task.
4. Current web/search material, when the workflow provides it.
5. Model prior knowledge.
6. Template examples, which are visual/style examples only and never evidence.

Evidence does not outrank the user's task intent. Uploaded files answer the
user's question; they are not automatically the outline, topic, or conclusion.

## Reliability Tags

- `confirmed`: Directly supported by a source passage, table, or user instruction.
- `calculated`: Derived from source data; include formula or denominator.
- `inferred`: Reasonable interpretation from evidence; do not present as raw fact.
- `assumed`: Needed to proceed but not proven; expose to the user or QA.
- `conflict`: Sources disagree; summarize both sides and prefer the stronger source.
- `missing`: Required fact was not found.

## Conflict Handling

- Prefer the source with the closest date, primary authorship, and task relevance.
- Keep original wording for legal, policy, financial, or technical definitions.
- If a source appears stale, mark the date and avoid "current/latest" language.
- Do not average conflicting numbers unless the user asked for estimation and the method is stated.

## Evidence Pack Shape

For each material claim, provide:

- `claim`: concise Chinese claim.
- `source_ref`: file name, page/section/table when available.
- `support`: short excerpt or table row summary.
- `status`: reliability tag.
- `notes`: conflicts, caveats, or calculation method.

## Relevance Gate

For every extracted fact, keep a relevance label:

- `direct`: explicitly answers a requested topic, entity, metric, period, or decision.
- `supporting`: gives context needed to understand a direct answer.
- `background`: useful only if space remains.
- `discard`: unrelated to the user request, even if prominent in the uploaded file.

Downstream writing should primarily use `direct` and `supporting` evidence.
Do not let a long uploaded document drag the deliverable away from the
input-box request.
