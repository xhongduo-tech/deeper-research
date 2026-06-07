---
name: feasibility-study-authoring-cn
description: >
  可行性研究/立项论证技能。用于项目可研、投资论证、系统建设、数据平台、
  技术改造和业务变革，负责技术、经济、组织、法律合规、资源、风险和结论建议。
---

# Feasibility Study Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill for 可行性分析 or any document that must decide whether a project
should proceed.

## Inputs

- Project background, objectives, scope, budget, timeline, constraints.
- Technical materials, cost data, market demand, policy/legal requirements.
- Alternative solutions and decision criteria.

## Outputs

| Output | Purpose |
|---|---|
| Feasibility framework | Technical, economic, organizational, legal, risk dimensions |
| Cost-benefit model | Cost, benefit, ROI/TCO, assumptions |
| Option comparison | Alternatives and scoring |
| Risk controls | Key risks, probability, impact, mitigation |
| Recommendation | Go/no-go/conditional-go conclusion |

## Workflow

1. **Frame Decision** - Define whether the document supports go/no-go, funding, or option selection.
2. **Analyze Need** - Describe baseline pain, demand, urgency, and consequences of no action.
3. **Assess Feasibility** - Evaluate technical, economic, organizational, legal, and operational feasibility.
4. **Compare Options** - Score alternatives by cost, benefit, risk, complexity, and timeline.
5. **Quantify Assumptions** - Label TCO, ROI, benefit, capacity, and adoption assumptions.
6. **Recommend Path** - State conclusion, conditions, implementation stages, and risk controls.

## Quality Checklist

- [ ] Decision conclusion is clear.
- [ ] Assumptions are visible.
- [ ] Options are compared fairly.
- [ ] Risks have mitigation actions.
- [ ] Recommendation follows evidence.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality feasibility study with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "feasibility-study-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "decision_frame",
    "need_analysis",
    "option_set",
    "technical_assessment",
    "economic_model",
    "risk_controls",
    "go_no_go"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Conclusion is clear.
- Assumptions visible.
- Options compared fairly.
- Risks have controls.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate feasibility study from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

