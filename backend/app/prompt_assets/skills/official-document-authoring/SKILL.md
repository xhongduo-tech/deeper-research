---
name: official-document-authoring-cn
description: >
  公文、会议纪要、通知、实施意见、新闻稿和行政商务材料写作技能。负责正式语体、
  主体信息、任务分解、责任闭环、发布口径、附件说明、编号和格式规范。
---

# Official Document Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for 公文、会议纪要、通知、实施意见、新闻稿 or other formal
administrative documents.

## Inputs

- Issuing body, audience, purpose, policy basis, meeting facts, or announcement facts.
- Uploaded source materials, decisions, attendance list, dates, tasks, and attachments.
- Required tone: formal, concise, authoritative, neutral, or media-facing.

## Outputs

| Output | Purpose |
|---|---|
| Formal outline | Header fields, recipients, body hierarchy, attachments, and sign-off |
| Draft document | Official prose with responsibilities, dates, and action items |
| Tracking list | Decisions, owners, deadlines, dependencies, and follow-ups |
| Format QA | Title, numbering, dates, names, attachments, and tone checks |

## Workflow

1. **Confirm Document Type** - Distinguish notice, opinion, meeting minutes, briefing, or press release.
2. **Extract Facts** - Read user materials for dates, departments, decisions, people, policy basis, and constraints.
3. **Build Formal Structure** - Create header fields, purpose, body sections, action requirements, attachments, and sign-off.
4. **Draft In Formal Voice** - Use precise, restrained language; avoid unsupported slogans and vague commitments.
5. **Close Responsibilities** - For tasks, include owner, deadline, deliverable, and inspection mechanism.
6. **Verify Format** - Check titles, numbering, dates, departments, attachments, and confidentiality labels.

## Quality Checklist

- [ ] Issuer, recipient, date, subject, and purpose are clear.
- [ ] Decisions and tasks have owners and deadlines where applicable.
- [ ] Tone matches administrative or media requirements.
- [ ] Attachments and references are mentioned consistently.
- [ ] No example/sample facts leak into the final document.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality official document with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "official-document-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "document_type",
    "issuer_recipient_fields",
    "policy_basis",
    "task_breakdown",
    "responsibility_matrix",
    "attachment_list"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Formal fields are complete.
- Responsibilities and deadlines are explicit.
- Tone is administrative and precise.
- Attachments are consistent.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate official document from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

