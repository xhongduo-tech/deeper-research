# Kimi-Style Skill Execution Contract

This shared contract applies to every prompt asset skill in this repository.
It follows the public Kimi/Moonshot skill pattern: a skill is a compact
`SKILL.md` knowledge package with clear trigger metadata, detailed Markdown
instructions, and optional `references/`, `scripts/`, and `assets/` for
progressive loading.

## Global Skill Shape

Every skill should be interpreted as a contract, not a loose prompt. The agent
must identify and preserve these fields even when the local `SKILL.md` uses
different headings:

1. **Trigger Boundary**: when to use the skill, when not to use it, and which
   neighboring skill owns adjacent work.
2. **Input Contract**: required user intent, source material, upstream outputs,
   constraints, and missing-data markers.
3. **Output Contract**: concrete artifact shape, schema, section hierarchy, or
   spec object that downstream code can consume.
4. **Workflow**: ordered execution steps with no silent skipping.
5. **Structure / Narrative Contract**: required sections, subsection budget,
   sequence, paragraph pattern, or slide/sheet/spec hierarchy.
6. **Grounding Rules**: source priority, citation/source anchors, numeric
   lineage, and how to mark unsupported claims.
7. **Quality Gates**: checklist items that must pass before the artifact moves
   to the next stage or export.
8. **Failure Mode**: what to do when evidence, structure, tools, or data are
   missing.

## Progressive Loading Rules

- Keep `SKILL.md` concise and operational. Move long examples, schemas, and
  style contracts into `references/`.
- Use `scripts/` for deterministic transformations or repeated validation.
- Use `assets/` for templates, images, sample files, and other output resources.
- Load detailed references only when the current task needs them, but obey
  references that are listed in the manifest or explicitly named by the skill.

## Universal Generation Funnel

All authoring and analysis skills follow the same funnel:

```
User goal
  -> trigger and format route
  -> evidence/source map
  -> structure contract
  -> draft/spec generation
  -> claim/table/chart/citation binding
  -> format/export plan
  -> QA gate and repair notes
```

Do not jump directly from user goal to prose, slides, charts, or workbook
content. Structure and evidence must be visible before final wording.

## Domain Contract Patterns

### Long-Form Document Skills

Use the academic-paper style as the benchmark: required hierarchy, section
budget, narrative arc, paragraph pattern, references, and completeness checklist.

For every document-type skill, derive:

- mandatory section hierarchy;
- recommended section budget or density;
- narrative progression from context to decision/contribution;
- table/figure/citation rules;
- completeness checklist.

When source material is incomplete, keep the required section and mark
`[数据待补充：...]`, `[来源待补充：...]`, or `[假设：...]`; do not delete the
section silently.

### PPT Skills

Slide generation must be SlideSpec-first:

- one slide role and one claim per slide;
- evidence and visual intent bound before copywriting;
- layout and density checked before export;
- preview, PPTX, notes, and QA read the same SlideSpec.

### Excel / Chart Skills

Sheet and chart generation must be spec-first:

- data dictionary and numeric lineage before analysis;
- workbook_spec / ChartSpec before rendering;
- source range, formula, unit, period, and filter retained for every key number;
- export followed by true file readback QA.

### Utility / Meta Skills

Utility skills do not draft final content unless explicitly responsible for it.
They transform state: intake contracts, evidence packs, routing decisions,
style profiles, conversion results, or QA reports. Their outputs must be
machine-readable enough for downstream skills.

## Claim-Evidence-Interpretation Pattern

Every substantive claim should use:

1. **Claim**: the judgment, finding, requirement, risk, or decision.
2. **Evidence**: source file, table, field, quote, calculation, benchmark, or
   explicit assumption.
3. **Interpretation**: why it matters for the target artifact and what boundary
   it does not cross.

## Cross-Reference Rules

- Reference figures, tables, sheets, sections, and appendices before relying on
  them.
- Keep numbering sequential within each artifact type.
- Tables need titles and source notes; figures/charts need captions or chart
  notes; spreadsheets need source sheets and calculation notes.

## KB Integration Protocol

Every KB-aware skill must handle knowledge base context according to these rules:

**Receiving KB context:**
- Accept `kb_context` array with each item containing: `chunk_id`, `score`, `text`, `source_doc`
- Filter: score ≥ 0.7 → cite as `[KB来源：文档名]`; score 0.5–0.7 → cite as `[低置信度参考：文档名]`; score < 0.5 → discard silently

**When KB is unavailable (kb_mounted = false):**
- Do not invent KB-style citations
- Use model knowledge only with `[基于行业惯例，无直接来源]` annotation
- Increase `[数据待补充：XXX]` usage rather than fabricating numbers
- Note the limitation explicitly in the output

**Conflict resolution:**
- When two sources give different numbers for the same indicator, present both values
- Format: "根据[来源A]，该指标为 M；根据[来源B]，同一指标为 N，两者存在差异"
- Never silently select one and discard the other

## Failure Recovery Protocol

When a skill cannot complete its full output due to missing inputs or failed dependencies:

1. **Partial completion is preferred over empty output** — produce what you can
2. **Mark every gap explicitly** — use `[数据待补充：XXX]`, `[来源待补充：XXX]`, or `[PLACEHOLDER: ...]`
3. **Never silently skip a required section** — keep the heading, mark the body as incomplete
4. **Propagate failure signals downstream** — use dedicated fields like `coverage_gaps`, `data_gaps`, `p0_issues`
5. **Provide a fallback** — if the primary path fails, use the most conservative known-good output rather than nothing

## Universal Completeness Checklist

Before handing off to the next skill, verify:

- [ ] Trigger and responsibility boundary are correct.
- [ ] User goal, target audience, output format, and constraints are preserved.
- [ ] Required structure/sections/spec fields are present.
- [ ] Every key claim or number has source, calculation, or assumption support.
- [ ] Missing evidence is marked explicitly (`[数据待补充]`), not hidden.
- [ ] KB context has been consumed with proper confidence-level citation.
- [ ] Conflicts between sources are documented, not silently resolved.
- [ ] Tables, charts, references, or citations are planned when the content
      requires them.
- [ ] Downstream skill inputs are named and shaped.
- [ ] QA blockers are listed when export should not proceed.
