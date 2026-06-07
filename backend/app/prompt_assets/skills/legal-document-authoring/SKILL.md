---
name: legal-document-authoring-cn
description: >
  合同、协议、招投标和法务商务文件写作技能。负责主体信息、定义、权责边界、
  交付验收、付款、知识产权、保密、违约、争议解决、附件和风险提示。
---

# Legal Document Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for contracts, agreements, bidding documents, memoranda, service
terms, and other legal/business documents. It is drafting support, not legal advice.

## Inputs

- Parties, project scope, commercial terms, deliverables, dates, acceptance criteria.
- Uploaded term sheets, prior contracts, bidding requirements, compliance constraints.
- Jurisdiction, governing law, confidentiality, and signature requirements when provided.

## Outputs

| Output | Purpose |
|---|---|
| Clause plan | Clause hierarchy, definitions, obligations, risks, and attachments |
| Draft clauses | Clear numbered terms with balanced responsibilities |
| Risk notes | Ambiguities, missing commercial terms, and legal review points |
| QA checklist | Subject info, numbering, cross-references, dates, and signatures |

## Workflow

1. **Identify Parties And Deal** - Confirm parties, background, scope, price, schedule, and governing assumptions.
2. **Define Terms** - Normalize names, deliverables, milestones, acceptance standards, and confidential information.
3. **Draft Clause Structure** - Cover scope, obligations, payment, acceptance, IP, confidentiality, breach, termination, dispute, force majeure, and annexes.
4. **Balance Obligations** - Flag one-sided, missing, vague, or unenforceable terms for human review.
5. **Check Cross References** - Verify clause numbering, attachment references, dates, names, and signature blocks.
6. **Disclose Limits** - Mark clauses requiring lawyer review or jurisdiction-specific validation.

## Quality Checklist

- [ ] Parties and commercial terms are complete or explicitly marked missing.
- [ ] Definitions are consistent across clauses.
- [ ] Acceptance and breach mechanisms are measurable.
- [ ] Risk notes are visible and actionable.
- [ ] Final document does not claim to replace professional legal review.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality legal/business document with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "legal-document-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "party_registry",
    "definition_table",
    "clause_plan",
    "obligation_matrix",
    "risk_notes",
    "signature_block"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Parties are complete.
- Definitions are consistent.
- Acceptance/payment/breach are measurable.
- Legal review limits are disclosed.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate legal/business document from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

