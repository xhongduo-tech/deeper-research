---
name: bid-proposal-authoring-cn
description: >
  招投标/投标文件/响应文件写作技能。用于招标文件、投标响应、技术标、商务标、
  评分响应矩阵、资质证明、实施方案、售后服务和风险合规检查。
---

# Bid Proposal Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for bidding documents, RFP/RFQ responses, tender files, and
proposal packages.

## Inputs

- Tender requirements, scoring rules, eligibility conditions, deadlines.
- Company qualifications, solution materials, pricing assumptions, implementation plan.
- Uploaded RFP/tender docs and previous proposals.

## Outputs

| Output | Purpose |
|---|---|
| Compliance matrix | Requirement-to-response mapping |
| Proposal outline | Business, technical, implementation, service, risk sections |
| Response draft | Direct responses to tender requirements |
| Missing material list | Certificates, pricing, signatures, attachments |
| Bid QA | Deadline, format, scoring, and compliance checks |

## Workflow

1. **Parse Tender** - Extract mandatory requirements, scoring criteria, submission format, and deadlines.
2. **Build Compliance Matrix** - Map every requirement to response location and evidence.
3. **Draft Response** - Answer requirements directly before adding persuasive narrative.
4. **Assemble Evidence** - List required qualifications, cases, certificates, and attachments.
5. **Check Scoring Fit** - Emphasize high-weight criteria and differentiators.
6. **Verify Submission** - Check signatures, seals, naming, file format, page limits, and missing annexes.

## Quality Checklist

- [ ] Mandatory terms are all addressed.
- [ ] Scoring criteria are visibly answered.
- [ ] Missing attachments are listed.
- [ ] Technical and commercial claims are consistent.
- [ ] Submission constraints are checked.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality bid/proposal response with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "bid-proposal-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "requirement_matrix",
    "scoring_map",
    "response_outline",
    "evidence_attachment_list",
    "compliance_risks",
    "submission_checklist"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Mandatory terms addressed.
- High-weight criteria emphasized.
- Attachments listed.
- Submission constraints checked.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate bid/proposal response from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

