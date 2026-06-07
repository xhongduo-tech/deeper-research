---
name: citation-bibliography-cn
description: >
  引用与参考文献处理技能。处理 academic-paper-authoring 输出中的 [CITE: 描述] 占位符，
  以及 word-authoring/research-report 中的 [来源：文件名] 锚点，
  生成符合指定格式规范的完整参考文献列表。
---

# Citation & Bibliography

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：将引用占位符转化为标准参考文献条目。不补充引用，只处理已标记的占位符。**

## 处理的两类引用标记

### 类型 A：学术论文占位符（来自 academic-paper-authoring）

```
[CITE: Smith et al. 关于 XX 的研究，发表于 Nature 2023]
```
→ 转化为对应格式的完整条目，插入参考文献列表

### 类型 B：证据锚点（来自 word-authoring / research-report-authoring）

```
[来源：sales_2024.xlsx p.3] 或 [来源：行业报告 第二章]
```
→ 转化为脚注或尾注格式，或收录到附录来源列表

## 支持的引用格式

### APA 7（英文学术默认）

```
文中引用：（Smith & Jones, 2023, p. 45）
参考文献：
Smith, J. A., & Jones, B. C. (2023). Title of article. Journal Name, 12(3), 45–67. https://doi.org/...
```

### GB/T 7714-2015（中文学术默认）

```
文中引用：[序号]，如 [1]
参考文献：
[1] 张三, 李四. 题名[J]. 期刊名, 2023, 12(3): 45-67.
[2] 王五. 书名[M]. 出版地: 出版社, 2023.
```

文献类型标识：`[J]`期刊 `[M]`专著 `[R]`报告 `[D]`学位论文 `[N]`报纸

### Chicago（人文社科）

```
文中引用：脚注形式
¹ John Smith, "Article Title," Journal Name 12, no. 3 (2023): 45.
参考文献：
Smith, John. "Article Title." Journal Name 12, no. 3 (2023): 45–67.
```

### 内部文件引用（非学术报告）

```
附录 A — 数据来源
序号 | 文件名 | 说明 | 引用章节
1    | sales_2024.xlsx | Q1-Q3 销售数据，含区域分解 | 第二章表1
```

## 无法解析时的处理规则

当引用占位符信息不足时：

| 情况 | 处理方式 |
|------|---------|
| 有文件名无页码 | 注明"见附件 XX，页码未标注" |
| 纯模型知识引用 | 标注"基于行业惯例，无正式来源，需核验" |
| 完全无法核实 | 标注 `[来源待补充]`，不虚构条目 |

**禁止**：不得补充作者/年份/刊名等信息（可能导致虚假引用）

## 格式切换逻辑

1. 用户在需求中指定格式 → 严格按指定格式
2. 报告类型为学术论文（academic-paper-authoring）且未指定 → 中文用 GB/T 7714，英文用 APA 7
3. 报告类型为研究报告/白皮书 → 用内部文件引用格式（附录来源列表）
4. 经营分析/PPT/Excel → 脚注或括号内简短标注，不生成独立参考文献列表

## Quick Checklist

- [ ] 所有 [CITE:] 和 [来源:] 占位符已处理
- [ ] 引用格式在全文统一（不混用 APA 和 GB）
- [ ] 无法核实的来源已标注"待补充"而非虚构
- [ ] 参考文献列表按格式要求排序（字母/序号）
- [ ] 内部文件引用已列入附录来源列表
