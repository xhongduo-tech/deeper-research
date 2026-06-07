---
name: press-release-authoring-cn
description: >
  新闻稿/通稿写作技能。用于产品发布、企业公告、活动新闻、合作发布和成果发布，
  负责新闻价值、导语、主体、引语、背景、事实核验、传播口径和媒体友好表达。
---

# Press Release Authoring Skill

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


Use this skill when the selected document type is 新闻稿 or when the user needs
a media-facing release.

## Inputs

- Announcement facts: who, what, when, where, why, how.
- Quotes, approved messaging, product facts, customer facts, and company boilerplate.
- Target media/audience and risk/compliance constraints.

## Outputs

| Output | Purpose |
|---|---|
| Release angle | News hook and headline direction |
| Press release draft | Headline, dateline, lead, body, quote, boilerplate |
| Fact checklist | Facts requiring approval or source support |
| Media notes | Optional summary, keywords, and contact block |

## Workflow

1. **Find News Hook** - Identify what is new, important, timely, or broadly relevant.
2. **Write Lead** - Answer who/what/when/where/why/how in the first paragraph.
3. **Develop Body** - Add product, market, customer, or event details in decreasing importance.
4. **Add Quotes** - Use quotes for viewpoint and emphasis, not facts better stated plainly.
5. **Add Boilerplate** - Provide concise company/project background.
6. **Fact Check** - Verify dates, names, numbers, claims, availability, and approval-sensitive language.

## Quality Checklist

- [ ] Headline is specific and newsworthy.
- [ ] Lead contains core facts.
- [ ] Claims are verifiable.
- [ ] Quotes sound human and approved.
- [ ] Boilerplate is concise.

## Execution Contract V2

This section upgrades the skill from a writing hint into an executable contract.
When Chief routes work to this skill, the skill must return structured outputs,
explicit risks, and a handoff packet for the next stage.

### Operating Role

This skill's role is to produce a high-quality press release with domain-specific structure and QA.

### Required Output Schema

```json
{
  "skill": "press-release-authoring",
  "status": "pass|needs_repair|blocked",
  "outputs": [
    "news_angle",
    "headline_options",
    "lead",
    "body_facts",
    "quote_slots",
    "boilerplate",
    "approval_risks"
  ],
  "evidence_refs": [],
  "assumptions": [],
  "risks": [],
  "handoff_to": [],
  "quality_gate": "pass|fail"
}
```

### Stage Gates

- Lead answers 5W1H.
- Claims are approved/verifiable.
- Quotes add viewpoint.
- Boilerplate is concise.

### Failure Modes And Repair

- Generic content replaces domain logic.
- Required fields or sections are missing.
- Facts are not grounded in current-task sources.
- Reference example content leaks into draft.

### Test Prompts

- Generate press release from uploaded source files and verify required schema fields.
- Use a reference example: mimic structure only, not facts.

