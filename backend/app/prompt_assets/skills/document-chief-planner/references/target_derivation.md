# Target Derivation Rules

When the user asks to generate a new document "with reference to" an old
document, the old document is not the target. The planner must derive the target
document identity from the user's requested deliverable.

## Core Rule

The final title, topic, year, audience, and main emphasis must come from the
user's requested target, not from the reference file name or reference title.

## Examples

| User Request | Reference File | Correct Target Title | Wrong Title |
|---|---|---|---|
| 参考我2025年的述职报告生成2026年述职报告 | 2025年述职报告.docx | 2026年述职报告 | 参考我2025年的述职报告生成2026年述职报告 |
| 参考去年部门总结，写今年工作计划 | 2025年度总结.pdf | 2026年工作计划 | 2025年度总结 |
| 参考旧版PRD，生成新版支付模块PRD | 支付模块PRD_v1.docx | 支付模块PRD v2.0 | 支付模块PRD_v1 |

## Target Fields

Derive and lock these fields before outline generation:

- `target_title`
- `target_period`
- `target_document_type`
- `target_audience`
- `target_main_question`
- `reference_role`
- `content_transformation_policy`

## Reference Role Labels

- `structure_reference`: use headings, section order, density.
- `style_reference`: use tone, formality, phrasing rhythm.
- `metric_reference`: reuse KPI categories or measurement framework, not old values.
- `continuity_reference`: carry forward unresolved projects, lessons, and next-year priorities if relevant.
- `evidence_source`: only when the user explicitly says the reference file contains current-task facts.

## Transformation Policy

For cross-period documents:

- Old-period achievements become baseline or retrospective context.
- Old-period problems become improvement agenda.
- Old-period unfinished work becomes continuation plan.
- New-period user goal becomes the document's title, emphasis, and recommendations.
- Do not present old-year data as new-year performance.

## Planning Gate

Before drafting, Chief must verify:

- The final title is not a prompt sentence.
- The final title does not include "参考..." unless the user explicitly requests that wording.
- The target period matches the user request.
- The reference file's title is not copied as the final title.
- Each section answers the target task, not the old document's task.
