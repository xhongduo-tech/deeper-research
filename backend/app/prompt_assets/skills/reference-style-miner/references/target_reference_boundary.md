# Target And Reference Boundary

This reference protects the final document from being hijacked by the uploaded
reference example.

## Boundary Table

| Element | Comes From Target Request | Comes From Reference Example |
|---|---|---|
| Final title | Yes | No |
| Target year/period | Yes | No, unless the reference is current evidence |
| Main question | Yes | No |
| Section structure | Usually yes, can adapt from reference | Yes, as pattern |
| Tone/formality | User request first, reference second | Yes, as guidance |
| Old facts/numbers | Only as baseline if relevant | No direct reuse |
| Future priorities | User request plus inferred continuity | Reference can suggest continuity |

## Title Guard

Bad titles:

- `参考我2025年的述职报告生成2026年述职报告`
- `2025年述职报告`
- `基于2025年述职报告的2026年述职报告` unless user explicitly asks for a comparative report.

Good titles:

- `2026年述职报告`
- `2026年度个人述职报告`
- `2026年数据智能中心述职报告`

## Content Adaptation

Reference content can become:

- structure pattern,
- KPI category,
- continuity clue,
- language density,
- expected table/appendix pattern.

Reference content cannot become:

- new-year achievement,
- final title,
- unsupported conclusion,
- copied project result,
- copied sensitive wording.
