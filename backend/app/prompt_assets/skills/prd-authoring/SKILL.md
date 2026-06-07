---
name: prd-authoring-cn
description: >
  产品需求文档 PRD 写作技能。用于产品规划、功能需求、用户故事、流程、交互、
  数据埋点、非功能需求、验收标准、版本计划和研发/测试交付。
---

# PRD Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill when the document type is 产品需求文档, PRD, feature spec, or
product requirements.

## Inputs

- Product goal, users, scenarios, pain points, constraints, and success metrics.
- Uploaded research notes, screenshots, logs, analytics, prior PRDs, or design files.
- Target platform, release scope, dependencies, and stakeholders.

## Outputs

| Output | Purpose |
|---|---|
| Product brief | Objective, users, scenarios, success metrics |
| Requirement spec | Functional and non-functional requirements |
| User stories | Actor, need, value, priority, acceptance criteria |
| Flow/data specs | Process, states, permissions, edge cases, analytics |
| Test checklist | Acceptance, regression, and launch criteria |

## Workflow

1. **Define Problem** - State user problem, business goal, and success metric.
2. **Scope MVP** - Separate must-have, should-have, later, and out-of-scope items.
3. **Write User Stories** - Express requirement from user role and measurable outcome.
4. **Specify Flows** - Cover happy path, edge cases, permissions, errors, and empty states.
5. **Define Data And Metrics** - Add fields, events, dashboards, and privacy requirements.
6. **Write Acceptance Criteria** - Make each requirement testable by QA and engineering.
7. **Check Dependencies** - List API, data, design, legal, operations, and rollout dependencies.

## Core Contracts

- PRD section schema: `references/prd_schema.md`

## Quality Checklist

- [ ] Requirements are testable.
- [ ] Scope and non-scope are explicit.
- [ ] Edge cases are covered.
- [ ] Dependencies and risks are visible.
- [ ] Acceptance criteria are concrete.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality product requirements document with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "prd-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "problem_statement",
    "user_personas",
    "scope_table",
    "user_stories",
    "functional_specs",
    "analytics_plan",
    "acceptance_criteria"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Requirements are testable.
- Scope/non-scope clear.
- Edge cases covered.
- Dependencies listed.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate product requirements document from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

