# Content Grounding

## Evidence Priority

1. User-uploaded files and corrections.
2. Mounted knowledge-base retrieval.
3. User prompt.
4. Current verified research when provided by the workflow.
5. Model prior knowledge.

## Slide Evidence Rules

- Material claims need evidence refs in notes, source labels, or QA metadata.
- Numeric claims need source, calculation, or assumption status.
- If a figure is inferred, label it as an estimate.
- If source files are present, mention source sections in notes when space allows.
- Do not use `.pptd` demo topics, titles, or numbers as content.

## Claim Compression

When evidence is long, compress it into:

- One conclusion title.
- 2-4 supporting bullets.
- One metric, table, chart, or diagram if it improves comprehension.
- Source/caveat in notes.

## Requirement Alignment

For each slide, record the user requirement it answers. If a slide cannot be
mapped to a requested topic, question, audience need, metric, or deliverable
constraint, remove it or move it to appendix.

Good slide flow starts from the user's requested angle, then selects supporting
evidence. It should not follow the uploaded document order unless the user asked
for a file summary or conversion.

## Unsupported Content

Remove or mark:

- Exact rankings without data.
- "显著提升/大幅下降" without comparison basis.
- Current market claims without current source.
- Causal claims from correlation-only data.
