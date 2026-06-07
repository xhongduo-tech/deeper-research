---
name: research-report-authoring-cn
version: "1.0"
description: >
  深度研究报告写作技能。用于生成结构严谨、证据充分的行业/专项研究报告。
  与 word-authoring 的区别：本技能强调文献综述、研究方法论叙述和不确定性量化，
  适用于"研究报告/白皮书/专项研究"类型，而非日常经营分析报告。支持 RAG 知识库
  检索作为一手文献来源，所有引用须标注来源和置信度。
category: doc
pipeline_position: 3
depends_on:
  - intake-planner
  - document-chief-planner
  - data-grounding
feeds_into:
  - citation-bibliography
  - qa-verification
kb_aware: true
input_schema:
  - name: chapter_plan
    type: object
    required: true
    description: 来自 document-chief-planner 的章节骨架，包含每章的核心论点、证据分配、目标字数
  - name: evidence_pack
    type: object
    required: true
    description: 来自 data-grounding 的结构化证据，含事实列表、来源锚点和置信度评级
  - name: kb_context
    type: array
    required: false
    description: 来自 RAG 检索的知识库片段，相似度 ≥ 0.7 的结果作为参考文献来源
  - name: user_goal
    type: string
    required: true
    description: 用户原始研究问题，用于对齐结论与研究问题
  - name: constraints
    type: object
    required: false
    description: 字数、受众级别（研究人员/政策制定者/行业专家）、引用格式等约束
output_schema:
  - name: report_markdown
    type: string
    description: 完整的研究报告 Markdown 草稿，包含所有标准章节（摘要-背景-方法-文献-发现-讨论-结论-附录）
  - name: citation_list
    type: array
    description: 报告中引用的所有来源列表，每项含来源名称、页码/章节、置信度评级
  - name: uncertainty_log
    type: array
    description: 低置信度和中置信度断言的汇总列表，供 qa-verification 审查
  - name: data_gaps
    type: array
    description: 标注为 [数据待补充] 的位置列表及说明
quality_thresholds:
  min_score: 0.90
  retry_on_fail: true
  max_retries: 2
---

# Research Report Authoring

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：生成具备研究方法论和文献综述框架的深度报告，区别于经营分析的叙事逻辑。**

## 与 word-authoring 的核心区别

| 维度 | word-authoring（经营报告）| research-report-authoring（研究报告）|
|------|--------------------------|--------------------------------------|
| 受众 | 管理层/决策者 | 研究人员/政策制定者/行业专家 |
| 结构 | 执行摘要→分析→建议 | 摘要→文献→方法→发现→讨论→结论 |
| 证据要求 | 内部数据+行业数据 | 一手数据+二手文献+方法论说明 |
| 不确定性 | 可省略假设说明 | **必须**量化置信区间和局限性 |
| 行动导向 | 具体可执行建议 | 研究发现+政策含义 |

## 标准结构

```
1. 执行摘要（300-500字）
   └─ 研究问题 + 方法 + 3-5条核心发现 + 政策/商业含义

2. 研究背景与问题
   └─ 研究缘起、现有研究的不足、本报告的研究问题

3. 研究方法
   └─ 数据来源（含时间范围、样本规模）
   └─ 分析框架（定量/定性/混合）
   └─ 局限性声明

4. 文献综述/现有研究梳理
   └─ 关键文献/报告观点（来自上传材料或知识库）
   └─ 共识与争议点

5. 核心发现（每条发现必须有证据）
   └─ 发现1：[量化结论] — 来源：[文件/数据]
   └─ 发现N...

6. 讨论与分析
   └─ 对核心发现的深度解读
   └─ 竞争假说的检验
   └─ 与已有研究的异同

7. 结论与含义
   └─ 对研究问题的回答
   └─ 对政策/商业决策的含义
   └─ 未来研究方向

8. 附录（可选）
   └─ 数据来源列表、计算方法说明
```

## 写作规范

### 不确定性量化（必须）

每条核心发现必须说明置信度：
- **高置信度**（有直接数据支撑）："根据上传的销售数据，Q3 收入 3.2 亿元 [来源：sales_report.xlsx Sheet1]"
- **中置信度**（有间接证据）："结合行业基准推算，约 XX（假设 YY）[基于行业惯例，无直接来源]"
- **低置信度/推断**："基于现有信息推测，需进一步验证"

禁止无来源的精确数字（如"增长了 23.4%"但无来源）。

### 文献引用格式

上传原始数据：`[来源：文件名 Sheet/p.XX]` （高置信度）
上传文档：`[来源：文件名 p.XX]` （高置信度）
知识库片段（score ≥ 0.7）：`[KB来源：文档名]` （中高置信度）
知识库片段（score 0.5–0.7）：`[低置信度参考：文档名]` （低置信度，需注意）
模型知识：`[基于行业惯例，无直接来源]`
无法确认：`[数据待补充：XXX]`

**引用冲突处理**：若 data-grounding 的 conflict_log 中存在冲突，在正文中同时呈现两个数字：
"根据 [来源A]，该指标为 M；而 [来源B] 显示为 N，两者存在差异，本报告采用 [更新/更权威的] 来源数据。"

### 局限性声明（必须写）

在方法论章节明确说明：
- 数据时间范围（如"数据截至 XXXX 年，不反映最新情况"）
- 样本局限（如"仅涵盖用户上传的 N 份文件"）
- KB 可用性（"知识库已挂载，提供 N 个相关片段" 或 "知识库未挂载，行业基准依赖模型知识"）
- 推断假设（如"假设行业整体趋势与样本一致"）

### 结构完整性要求

即使数据不足，以下章节**不得删除**，必须保留章节标题并用 `[数据待补充：XXX]` 标注缺口：
- 研究方法（哪怕只有定性描述）
- 局限性声明（哪怕只有一条）
- 数据来源列表（哪怕只列出"用户上传文件"）

### 执行摘要写作规则（5点结构）

```
1. 研究问题（1句）：本报告研究……
2. 数据与方法（1-2句）：基于……分析/调研……
3. 核心发现（3-5条 bullet）：
   • 发现1：[量化结论] [来源]
   • 发现2：[量化结论] [来源]
4. 关键不确定性（1-2句）：以下方面数据不足，结论存在不确定性……
5. 含义（1句）：上述发现对…… 具有……意义
```

## 与 DECRIM 的协作

DECRIM 的 9 条约束对研究报告同样适用，但权重不同：
- **来源可查性** — 权重最高，文献综述每条都要有来源
- **不确定性量化** — 比经营报告要求更严格；每条发现都要说明置信度等级
- **逻辑一致性** — 发现→讨论→结论必须一脉相承；禁止在结论中引入新发现
- **冲突处理** — DECRIM 会检查 conflict_log；未处理的冲突是 P1 问题

## Quick Checklist

- [ ] 执行摘要含研究问题、方法、3-5条核心发现、不确定性、含义
- [ ] 每条发现有来源标注（L1-L5 格式）和置信度说明
- [ ] 方法论章节说明数据来源、样本规模、局限性
- [ ] KB 可用性已在方法论中说明
- [ ] 冲突数据已在正文中呈现双方（来自 data-grounding.conflict_log）
- [ ] 不确定性已量化（高/中/低置信度）
- [ ] 结论只回答研究问题，不引入新内容
- [ ] 无无来源精确数字
- [ ] 必需章节无一被静默删除（用 [数据待补充] 标注缺口）
