---
name: performance-review-authoring-cn
description: >
  述职报告/年度总结/团队复盘技能。用于个人、团队、部门和项目述职，负责目标回顾、
  KPI 达成、重点项目、经验沉淀、问题反思、人才团队、下一阶段计划和资源诉求。
---

# Performance Review Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for 述职报告, annual review, quarterly review, team recap, or
management performance documents.

## Inputs

- Role/team scope, period, goals, KPI data, project list, outcomes, issues.
- Uploaded performance data, meeting notes, OKRs, dashboards, and prior plans.
- Audience and evaluation criteria.

## Outputs

| Output | Purpose |
|---|---|
| Target review identity | Title, year/period, role/team, audience, and review purpose |
| Review structure | Goals, results, projects, lessons, issues, next plan |
| KPI narrative | Data-backed performance story |
| Project recap | Highlights, challenges, learnings, impact |
| Next plan | Goals, initiatives, resources, risks |

## Workflow

1. **Lock Target Review** - Derive the final title and review period from the user request. For "参考我2025年的述职报告生成2026年述职报告", use `2026年述职报告`, not the prompt sentence and not `2025年述职报告`.
2. **Classify Reference Role** - Treat prior-year reviews as structure, KPI category, continuity, lessons, and baseline. Do not treat old-year achievements as new-year achievements.
3. **Anchor To Goals** - Start from target-year goals/OKRs/KPIs. If target-year data is missing, mark it as planned priority or assumption.
4. **Quantify Results** - Use data, before/after, target vs actual, and business impact only when evidence supports it.
5. **Explain Projects** - For each key project, state role, action, result, and learning.
6. **Reflect Honestly** - Identify issues, root causes, and corrective actions.
7. **Plan Next Stage** - Define goals, initiatives, resources, support needed, and risks.
8. **Tune Tone** - Balance confidence, accountability, and evidence.

## Cross-Year Reference Rules

When the user asks to reference a previous-year review:

| Previous-year content | Correct transformation for target year |
|---|---|
| 2025 title | Block as final title; derive 2026 title from user request |
| 2025 KPI categories | Reuse as measurement framework if still relevant |
| 2025 achievements | Use only as baseline/context, not 2026 results |
| 2025 problems | Convert into 2026 improvement agenda |
| 2025 unfinished projects | Convert into 2026 continuation priorities |
| 2025 next plan | Evaluate whether it becomes 2026 priority, milestone, or risk |

Good phrasing:

- `2026年应优先推进B，原因是2025年A项目暴露出跨部门协同和数据闭环不足。`
- `基于2025年已完成的A能力建设，2026年重点转向B场景规模化。`
- `2025年遗留的流程断点，应在2026年通过B专项治理完成闭环。`

Bad phrasing:

- `参考我2025年的述职报告生成2026年述职报告`
- `2025年述职报告`
- `2026年完成了2025年报告中列出的成果` when there is no 2026 evidence.

## Quality Checklist

- [ ] KPI achievement is clear.
- [ ] Activity is connected to outcomes.
- [ ] Issues are not hidden.
- [ ] Next plan is measurable.
- [ ] Resource requests are justified.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality performance review with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "performance-review-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "target_review_identity",
    "goal_baseline",
    "kpi_results",
    "project_recaps",
    "impact_story",
    "reflection",
    "next_stage_plan",
    "resource_requests"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Outcomes tied to goals.
- Final title and period match the target request, not the reference.
- KPI story quantified.
- Problems acknowledged.
- Next plan measurable.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.
- Prior-year achievements are presented as target-year achievements.
- The final title copies "参考..." prompt wording.

### Test Prompts

- Generate performance review from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.
- Reference 2025 review to generate 2026 review: title must be `2026年述职报告`; 2025 issues should become 2026 priorities such as "2026年应优先推进B...".

