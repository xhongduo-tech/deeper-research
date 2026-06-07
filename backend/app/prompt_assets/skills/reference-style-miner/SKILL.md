---
name: reference-style-miner-cn
description: >
  参考风格提取技能。分析用户上传的 style_reference 文件，提取其结构特征、
  语言风格、格式约束，生成可供写作技能复用的风格规范卡。
  关键约束：只提取风格，禁止将 style_reference 中的事实内容写入正文。
---

# Reference Style Miner

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：从风格参考文件提取结构和语言特征，不提取事实内容。**

## 核心安全约束

**style_reference 中的数字、案例、结论、观点，一律不得写入目标报告正文。**

风格参考文件（模板）存在的唯一目的是：告诉系统"这份报告应该长什么样子"，而不是"内容是什么"。混用会导致：
- 目标报告出现无关数字（如模板示例公司的数据混入正文）
- 标题与用户需求无关（用了模板标题）
- 用户最常见的投诉：生成的报告像"模板而不是我要的内容"

## 提取内容（允许）

### 结构特征

```json
{
  "section_count": 7,
  "section_naming_pattern": "一级标题用数字编号（一、二、三）",
  "has_executive_summary": true,
  "has_appendix": true,
  "heading_levels_used": ["H1", "H2", "H3"],
  "table_placement": "每章至少1张表，位置在论述之后"
}
```

### 语言风格

```json
{
  "tone": "正式/客观",
  "person": "第三人称",
  "sentence_length": "长句（≥20字）为主，间以短句结论",
  "transition_patterns": ["在此基础上", "综合来看", "综上所述"],
  "number_format": "中文数字（万、亿）+ 百分比",
  "avoid_words": ["非常", "很", "简单说", "换句话说"]
}
```

### 格式约束

```json
{
  "page_margin": "正文区域偏窄，留白较多",
  "font_hint": "标题加粗，正文不加粗",
  "table_style": "三线表（无竖线）",
  "figure_caption_position": "图下方，表上方",
  "citation_format": "脚注形式（非尾注）"
}
```

## 禁止提取的内容

- ❌ 任何具体数字（营收、增长率、市场规模等）
- ❌ 公司名称、产品名称、人名
- ❌ 任何结论性判断（"市场前景良好"之类）
- ❌ 案例描述（"XX 公司在 20XX 年做了……"）

如果 style_reference 同时也包含用户上传的"证据资料"，本技能只输出风格规范，不做证据提取（那是 data-grounding 的职责）。

## Output — style_card

```json
{
  "source_file": "文件名",
  "extraction_confidence": "high|medium|low",
  "structure": { ... },
  "language": { ... },
  "format": { ... },
  "usage_note": "本卡片只约束格式和语言风格，不约束内容主题和取舍"
}
```

`extraction_confidence` 低于 medium 时，在 usage_note 中说明原因（如"文件格式为扫描件，无法识别结构"）。

## Quick Checklist

- [ ] 已提取结构特征（章节数、标题格式）
- [ ] 已提取语言风格（语气、人称、句式）
- [ ] 已提取格式约束（表格样式、图注位置）
- [ ] 未提取任何具体数字或事实结论
- [ ] usage_note 声明"不约束内容主题"
