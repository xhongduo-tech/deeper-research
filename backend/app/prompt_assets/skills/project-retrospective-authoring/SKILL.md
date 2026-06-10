---
name: project-retrospective-authoring-cn
description: >
  项目复盘报告写作技能。用于项目复盘、阶段复盘、交付复盘、事故/问题复盘和
  里程碑总结，负责目标-过程-结果-偏差-根因-经验-行动计划的闭环结构。
---

# Project Retrospective Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for project retrospective and postmortem documents; do not turn the output into a generic project introduction or performance review.
- **Input Contract**: preserve user goal, project scope, timeline, evidence, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the retrospective structure, evidence map, root-cause analysis, lessons learned, action plan, and QA handoff packet.
- **Workflow Discipline**: reason from facts to causes to actions; keep accountability precise and constructive.
- **Quality Gate**: before handoff, verify that every major conclusion has evidence or is labeled as an assumption.

Use this skill for 项目复盘, 复盘报告, 阶段复盘, postmortem, retrospective, milestone review, and delivery review documents.

## Inputs

- Project background, goals, scope, stakeholders, timeline, milestones, and acceptance criteria.
- Uploaded project plans, meeting notes, issue logs, delivery records, dashboards, budgets, and customer/user feedback.
- Known constraints: confidentiality level, audience, tone, blame sensitivity, and required output format.

## Outputs

| Output | Purpose |
|---|---|
| Retrospective frame | Project scope, target, baseline, audience, and review question |
| Timeline and event map | Key milestones, decisions, changes, blockers, and delivery facts |
| Outcome assessment | Target vs actual, quality/cost/schedule/scope impact |
| Gap and root-cause analysis | Evidence-backed causes, not vague blame |
| Lessons learned | Reusable process, collaboration, technical, data, and governance lessons |
| Action plan | Concrete owners, deadlines, measures, dependencies, and follow-up checks |

## Workflow

1. **Lock Review Scope** - Identify the project, stage, time range, audience, and whether the user wants a delivery review, problem review, or learning review.
2. **Reconstruct The Timeline** - Build a concise sequence of milestones, decisions, risk events, changes, and outcomes from uploaded materials or user facts.
3. **Compare Target And Actual** - Assess schedule, scope, cost, quality, user/customer value, and team collaboration against the original goals.
4. **Diagnose Gaps** - For each major gap, separate symptoms, direct causes, root causes, constraints, and controllable factors.
5. **Extract Lessons** - Turn causes into reusable practices, standards, checklists, or governance improvements.
6. **Define Actions** - Produce owners, deadlines, success metrics, and follow-up cadence; avoid empty "加强沟通" style actions.
7. **Set Tone** - Use factual, candid, constructive language. Acknowledge responsibility without personal blame unless source materials explicitly require accountability statements.

## Recommended Structure

1. 项目背景与目标
2. 过程回顾
3. 结果达成情况
4. 偏差与根因分析
5. 经验沉淀
6. 改进措施与行动计划
7. 附录与证据

## Quality Checklist

- [ ] Review scope and audience are explicit.
- [ ] Target vs actual comparison is visible.
- [ ] Timeline facts and major conclusions have evidence anchors.
- [ ] Root causes go beyond symptoms and personal blame.
- [ ] Lessons are reusable.
- [ ] Action plan contains owner, deadline, metric, and follow-up method.

## Execution Contract V2

When Chief routes work to this skill, return structured outputs, explicit risks, and a handoff packet for downstream authoring.

### Required Output Schema

```json
{
  "skill": "project-retrospective-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "retrospective_frame",
    "timeline_event_map",
    "target_actual_assessment",
    "gap_root_cause_analysis",
    "lessons_learned",
    "action_plan",
    "handoff_to_word_authoring"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": ["word-authoring", "qa-verification"],
  "quality_gate": "pass|fail"
}
```

### Failure Modes And Repair

- Generic project description replaces retrospective analysis.
- No target-vs-actual comparison.
- Root causes are slogans or personal blame without evidence.
- Lessons are not reusable.
- Action items have no owner, deadline, metric, or follow-up checkpoint.
