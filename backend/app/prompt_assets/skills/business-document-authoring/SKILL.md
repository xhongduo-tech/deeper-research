---
name: business-document-authoring-cn
description: >
  商业计划书、可行性研究、述职报告、经营方案和管理汇报类 Word 文档技能。
  负责目标拆解、业务逻辑、数据口径、财务/资源假设、路线图、风险和行动建议。
---

# Business Document Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for business plans, feasibility reports, performance reviews,
strategy plans, management proposals, and operating documents.

## Inputs

- Business objective, audience, organization, time horizon, and decision ask.
- Uploaded business data, prior plans, market notes, financial assumptions, or KPI files.
- Required output: plan, review, feasibility study, proposal, or board memo.

## Outputs

| Output | Purpose |
|---|---|
| Business logic tree | Goal, drivers, constraints, resources, risks, and KPIs |
| Draft document | Executive summary, analysis, plan, financial/resource view, and roadmap |
| Data appendix | KPI tables, assumptions, benchmarks, and calculation notes |
| Action plan | Initiatives, owners, milestones, dependencies, and measures |

## Workflow

1. **Frame The Decision** - Clarify what approval, alignment, funding, or action the document seeks.
2. **Diagnose Current State** - Use data and evidence to describe baseline, gap, causes, and constraints.
3. **Build Options Or Plan** - Compare options or initiatives by value, cost, risk, and feasibility.
4. **Quantify Assumptions** - Label assumptions for TAM, ROI, budget, capacity, timeline, or KPI uplift.
5. **Write Management Narrative** - Keep the document decision-oriented and concise, with clear trade-offs.
6. **Verify Actionability** - Ensure recommendations include owner, timing, dependency, and measurable outcome.

## Quality Checklist

- [ ] Executive summary states conclusion and request.
- [ ] Business claims are supported by data or labeled assumptions.
- [ ] Financial/resource assumptions are visible.
- [ ] Roadmap connects to KPIs and risks.
- [ ] Final output is readable by busy decision-makers.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality business document with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "business-document-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "decision_ask",
    "business_logic_tree",
    "kpi_story",
    "option_comparison",
    "resource_plan",
    "action_roadmap"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Decision ask is clear.
- Business claims are quantified.
- Trade-offs are explicit.
- Roadmap connects to KPIs.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate business document from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

