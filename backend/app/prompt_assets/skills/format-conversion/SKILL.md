---
name: format-conversion-cn
description: >
  离线格式转换与渲染保真技能。约束 DOCX/PPTX/XLSX/PDF/HTML/Markdown 之间的转换、
  回读、截图渲染和质量门禁，保证内网部署下的交付文件可打开、可审计、版式稳定。
---

# Format Conversion

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：把生成内容变成真实可交付文件，并用离线工具回读验证。**

## Runtime Stack

- Office Open XML：DOCX/PPTX/XLSX 主交付格式。
- python-docx / python-pptx / openpyxl / XlsxWriter：生成可编辑 Office 文件。
- LibreOffice headless：离线转换 PDF 与渲染检查。
- Pandoc：Markdown/HTML/DOCX/PPTX 之间的结构化转换补充通道。
- PyMuPDF / Poppler：PDF 页面渲染为图片，用于空白页、溢出、低对比检查。

## Conversion Policy

- 交付文件必须先保存为真实文件，再回读检查。
- 转 PDF 时优先 LibreOffice headless；Markdown/HTML 中间格式可走 Pandoc。
- 转换链路不得改变事实数据、图表数据或引用编号。
- 转换失败必须写入 warning；关键交付失败必须阻断下载。

## Required QA

- 文件可打开。
- 页数或 sheet 数符合预期。
- 字体回退可用。
- 表格不越界。
- 图片和图表非空白。
- 来源说明仍存在。

## Quick Checklist

- [ ] 使用离线工具，不依赖外部 SaaS
- [ ] 回读真实文件
- [ ] PPT/DOCX 可转换 PDF
- [ ] XLSX 可读取公式、图表、冻结窗格和来源说明
- [ ] 强门禁失败时不交付
