---
name: training-manual-authoring-cn
description: >
  培训手册/操作手册/课程材料写作技能。用于员工培训、系统操作、合规培训、
  SOP、教程和考核材料，负责学习目标、知识框架、步骤、案例、练习、考核和讲师备注。
---

# Training Manual Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for training manuals, SOPs, course handouts, onboarding guides,
and operational playbooks.

## Inputs

- Learner profile, training goal, required behavior, knowledge level.
- Source policies, product docs, screenshots, process docs, case materials.
- Required format: manual, SOP, lesson plan, quiz, facilitator guide.

## Outputs

| Output | Purpose |
|---|---|
| Learning map | Objectives, modules, prerequisites, outcomes |
| Manual draft | Concepts, procedures, examples, warnings, FAQs |
| Practice set | Exercises, cases, quizzes, answer key |
| Operational checklist | Step-by-step job aid |

## Workflow

1. **Define Learners** - Identify role, prior knowledge, training scenario, and expected behavior.
2. **Set Objectives** - Write measurable learning objectives.
3. **Organize Modules** - Move from concepts to procedures to cases to practice.
4. **Write Procedures** - Use numbered steps, expected results, warnings, and troubleshooting.
5. **Add Practice** - Include exercises, cases, quiz questions, and answer key.
6. **Verify Usability** - Check clarity, completeness, sequence, and operational safety.

## Quality Checklist

- [ ] Learning objectives are measurable.
- [ ] Procedures are step-by-step.
- [ ] Warnings and exceptions are visible.
- [ ] Exercises test real tasks.
- [ ] Manual can be used without trainer explanation.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality training manual with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "training-manual-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "learner_profile",
    "learning_objectives",
    "module_map",
    "procedure_steps",
    "practice_items",
    "answer_key",
    "job_aid"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Objectives measurable.
- Procedures stepwise.
- Warnings visible.
- Exercises test real tasks.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate training manual from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

