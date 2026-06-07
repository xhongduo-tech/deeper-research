---
name: meeting-minutes-authoring-cn
description: >
  会议纪要写作技能。用于经营会、项目会、评审会、战略会和专题会，将会议材料、
  讨论记录和决议整理为正式纪要，包含会议信息、议题、讨论要点、决议事项、
  责任人、截止时间、风险和跟踪机制。
---

# Meeting Minutes Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill when the document type is 会议纪要 or the source material is
meeting transcripts, notes, agendas, or decision records.

## Inputs

- Meeting title, time, location, host, attendees, agenda, notes, and materials.
- Uploaded recordings/transcripts or written notes.
- Required formality and distribution scope.

## Outputs

| Output | Purpose |
|---|---|
| Meeting metadata | Time, place, attendees, absentees, recorder |
| Topic summaries | Discussion by agenda item |
| Decision list | Decisions with rationale and constraints |
| Action register | Owner, deadline, deliverable, status, dependency |
| Follow-up risks | Items requiring escalation or clarification |

## Workflow

1. **Normalize Meeting Facts** - Confirm date, participants, meeting purpose, and agenda.
2. **Group Discussion** - Organize discussion by agenda, not by raw transcript order when messy.
3. **Extract Decisions** - Separate decisions from opinions, suggestions, and open questions.
4. **Create Action Register** - Assign owner, deadline, deliverable, and follow-up mechanism.
5. **Write Formal Minutes** - Use concise, neutral, traceable language.
6. **Verify Names And Dates** - Check participant names, responsibilities, and deadlines.

## Quality Checklist

- [ ] Metadata is complete.
- [ ] Decisions are explicit.
- [ ] Action items have owner and deadline.
- [ ] Open issues are visible.
- [ ] Tone is factual and neutral.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality meeting minutes with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "meeting-minutes-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "meeting_metadata",
    "agenda_summary",
    "decision_register",
    "action_register",
    "open_issues",
    "followup_plan"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Decisions differ from opinions.
- Actions have owner/deadline.
- Names/dates checked.
- Tone is neutral.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate meeting minutes from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

