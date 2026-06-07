---
name: policy-document-authoring-cn
description: >
  政策解读、制度方案、实施意见和规范性文件写作技能。用于政策研究、制度建设、
  管理办法、实施细则和内部规范，负责依据、适用范围、原则、职责、流程、监督、
  风险和落地机制。
---

# Policy Document Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for policy interpretation, institutional documents, management
rules, implementation opinions, and internal governance documents.

## Inputs

- Policy basis, organizational context, scope, regulated objects, and authority.
- Uploaded laws, policies, internal rules, meeting decisions, or governance materials.
- Required format: policy interpretation, management measure, implementation plan, guidance.

## Outputs

| Output | Purpose |
|---|---|
| Policy basis map | Source policies and obligations |
| Governance structure | Scope, principles, roles, processes, supervision |
| Implementation plan | Tasks, owners, timeline, and assessment |
| Compliance risks | Legal, operational, privacy, and audit concerns |

## Workflow

1. **Identify Authority** - Determine legal/policy basis and organizational authority.
2. **Define Scope** - Clarify who and what the document applies to.
3. **Set Principles** - State guiding principles and non-negotiable requirements.
4. **Assign Responsibilities** - Define departments, roles, procedures, and accountability.
5. **Design Implementation** - Add schedule, reporting, supervision, training, and assessment.
6. **Check Compliance** - Verify terminology, hierarchy, conflicts, and auditability.

## Quality Checklist

- [ ] Policy basis is explicit.
- [ ] Scope and roles are clear.
- [ ] Procedures are actionable.
- [ ] Supervision and accountability exist.
- [ ] Compliance risks are visible.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality policy/governance document with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "policy-document-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "policy_basis_map",
    "scope_objects",
    "principles",
    "roles_responsibilities",
    "procedures",
    "supervision",
    "compliance_risks"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Basis is explicit.
- Scope clear.
- Roles actionable.
- Auditability covered.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate policy/governance document from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

