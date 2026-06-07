# Professional Document Matrix

Use this matrix to route document types and required sections.

| Type | Primary Skill | Required Sections |
|---|---|---|
| 论文 | `academic-paper-authoring` | Title, authors, abstract, introduction, related work, method, experiments/results, conclusion, limitations, references |
| 研究报告 | `research-report-authoring` | Executive summary, methodology, findings, analysis, risks, recommendations, appendix |
| 公文/制度 | `official-document-authoring`, `policy-document-authoring` | Basis, scope, requirements, responsibilities, implementation, supervision, attachments |
| 会议纪要 | `meeting-minutes-authoring` | Metadata, agenda, discussion summary, decisions, action register, open issues |
| 新闻稿 | `press-release-authoring` | Headline, dateline, lead, body, quote, background, contact/boilerplate |
| 合同/协议 | `legal-document-authoring` | Parties, definitions, scope, payment, acceptance, IP, confidentiality, breach, dispute, signatures |
| 招投标 | `bid-proposal-authoring` | Requirement matrix, response, technical plan, implementation, service, qualifications, annexes |
| 商业计划 | `business-document-authoring` | Opportunity, solution, market, model, traction, financials, team, ask |
| 可研 | `feasibility-study-authoring` | Need, options, technical feasibility, economic feasibility, organization/legal, risks, recommendation |
| 述职 | `performance-review-authoring` | Goals, KPI results, projects, reflection, team, next plan, resource needs |
| 技术方案 | `technical-document-authoring` | Scope, architecture, modules, interfaces, NFRs, implementation, operations, risks |
| PRD | `prd-authoring` | Objective, users, scope, stories, requirements, flows, data, NFRs, acceptance |
| 培训手册 | `training-manual-authoring` | Objectives, modules, procedures, cases, exercises, assessment, job aid |

## Routing Rule

If a user chooses a broad type but uploads a specialized reference, route both:
the broad skill provides general quality and the specialized/custom skill
controls structure.

For top-tier conference/full-paper requests, load the academic paper structure
contract and preserve required Method and Experiments subsections even when
source evidence is incomplete.
