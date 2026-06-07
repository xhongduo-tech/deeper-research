---
name: technical-document-authoring-cn
description: >
  技术方案、产品需求文档、培训手册、架构设计和实施文档技能。负责用户场景、
  功能规格、架构、接口、非功能需求、验收标准、运维、安全、版本规划和可执行说明。
---

# Technical Document Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for technical solutions, PRDs, architecture documents, training
manuals, implementation plans, and engineering handoff documents.

## Inputs

- Product/technical goal, users, systems, constraints, and target readers.
- Uploaded requirements, diagrams, APIs, logs, data models, screenshots, or prior docs.
- Required depth: overview, PRD, architecture, implementation, operations, or training.

## Outputs

| Output | Purpose |
|---|---|
| Technical plan | Scope, assumptions, architecture, dependencies, risks, and milestones |
| Specification draft | Requirements, flows, interfaces, data, security, and acceptance criteria |
| Diagrams/tables | Architecture views, process flows, API tables, risk matrix, and test cases |
| Verification list | Completeness, consistency, feasibility, and handoff checks |

## Workflow

1. **Define Scope** - Identify in-scope/out-of-scope functions, users, systems, and success metrics.
2. **Read Existing Materials** - Extract requirements, constraints, architecture facts, and open questions.
3. **Model The System** - Organize modules, data flow, dependencies, interfaces, and non-functional requirements.
4. **Write Specifications** - Use precise requirement language, acceptance criteria, and testable conditions.
5. **Add Operational Detail** - Include rollout, monitoring, security, permissions, fallback, and maintenance.
6. **Verify Handoff Quality** - Check ambiguity, missing dependencies, contradictory requirements, and feasibility.

## Quality Checklist

- [ ] Scope and non-scope are explicit.
- [ ] Requirements are testable and prioritized.
- [ ] Architecture and data/interface tables are consistent.
- [ ] Risks, dependencies, and rollout steps are visible.
- [ ] Final document can be used by product, engineering, QA, and operations.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality technical document with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "technical-document-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "scope_non_scope",
    "architecture_view",
    "requirement_table",
    "interface_data_specs",
    "nfrs",
    "acceptance_tests"
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
- Dependencies are visible.
- Architecture and data specs match.
- Operations/security are covered.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate technical document from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

