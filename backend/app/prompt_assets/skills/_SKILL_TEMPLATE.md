---
name: <slug>                        # 小写 kebab-case，如 ppt-director
version: "1.0"
description: >
  一段话说明技能的核心职责：所属领域、触发时机、主要能力、交付物类型。
  避免列举细节，保留给正文。建议 2-4 句话，中文书写。
category: ppt | doc | sheet | utility | meta
  # ppt     — 演示文稿相关（ppt-director, ppt-narrative, ppt-layout）
  # doc     — Word/PDF 长文档相关（word-authoring, research-report-authoring）
  # sheet   — Excel/数据工作簿相关（excel-modeling）
  # utility — 跨格式辅助技能（data-grounding, citation-bibliography, qa-verification）
  # meta    — 流水线编排/路由技能（intake-planner, document-chief-planner, skill-factory）
pipeline_position: 1                # 1-5，在5阶段流水线中的位置
  # 1 — 接收与规划（intake-planner）
  # 2 — 结构设计（document-chief-planner, ppt-director）
  # 3 — 内容起草（word-authoring, research-report-authoring, ppt-narrative）
  # 4 — 质量精炼（DECRIM, AeSlides）— 通常由系统内置，不单独为技能
  # 5 — 验证与导出（qa-verification）
depends_on:                         # 本技能依赖哪些上游技能输出才能运行
  - intake-planner
  - document-chief-planner
feeds_into:                         # 本技能的输出被哪些下游技能消费
  - qa-verification
kb_aware: true                      # true = 可调用知识库（RAG）检索；false = 不访问知识库
input_schema:
  - name: user_goal
    type: string
    required: true
    description: 用户原始输入，来自 intake-planner，禁止改写
  - name: output_format
    type: string
    required: true
    description: "目标格式：ppt / word / excel"
  - name: evidence_pack
    type: object
    required: false
    description: 来自 data-grounding 的结构化证据，含事实列表和来源锚点
  - name: constraints
    type: object
    required: false
    description: 量化约束（页数、字数、受众、保密等级等）
output_schema:
  - name: <output_field_1>
    type: string | object | array
    description: 该输出字段的用途与格式说明
  - name: <output_field_2>
    type: object
    description: 该输出字段的用途与格式说明
quality_thresholds:
  min_score: 0.85                   # 最低可接受质量分（0-1）
  retry_on_fail: true               # 未达到质量门时是否自动重试
  max_retries: 2                    # 最多重试次数（建议 1-3）
---

# <技能名称（中文展示名）>

**职责边界一句话说明：做什么，不做什么。**

## 在流水线中的位置

```
上游技能（已完成输出）
    ↓ [上游输出字段名] 已就绪
本技能（当前技能名）← 你在这里
    ↓ [本技能输出字段名]
下游技能
```

## 触发时机

描述何时由 intake-planner 或 document-chief-planner 路由到本技能，以及前置条件。

## Inputs

| 字段 | 来源 | 说明 |
|------|------|------|
| `user_goal` | intake-planner | 原始用户输入，不得改写 |
| `[字段名]` | [来源技能] | [字段用途] |

## Outputs

| 字段 | 类型 | 说明 |
|------|------|------|
| `[字段名]` | string / object / array | [字段用途] |

## KB-Aware 上下文接入（若 kb_aware: true）

若知识库已挂载，在执行前执行 RAG 检索：
- **检索关键词**：从 `user_goal` 提取 3-5 个领域关键词
- **召回数量**：top-K = 5（默认），可由 `constraints.kb_top_k` 覆盖
- **接入策略**：将召回的知识片段作为 `kb_context` 注入到提示前缀
- **置信度处理**：相似度 < 0.7 的片段标记为 `[低置信度参考]`，不作为权威来源

## Workflow

1. **步骤1** — 说明做什么，基于哪些输入
2. **步骤2** — 说明做什么
3. **步骤N** — ...
4. **输出** — 输出格式和字段

## 质量门控

本技能输出须满足以下条件，否则触发重试（最多 `max_retries` 次）：

| 质量维度 | 通过条件 | 失败处理 |
|----------|---------|---------|
| 完整性 | 所有必填输出字段已填写 | 重试 |
| 来源可查 | 所有数字/事实有来源锚点 | 重试 |
| 逻辑一致 | 各字段间无矛盾 | 重试 |

## 与相邻技能的分工

| 职责 | 本技能 | 相邻技能 |
|------|--------|---------|
| [职责描述] | ✅ | ❌（由 [技能名] 负责）|

## Non-Negotiables

- 最重要的约束1（不得违反）
- 最重要的约束2
- 最重要的约束3

## Quick Checklist

- [ ] 检查项1
- [ ] 检查项2
- [ ] 检查项3
- [ ] 输出质量分 ≥ `quality_thresholds.min_score`
