---
name: intake-planner-cn
version: "1.0"
description: >
  任务接收与格式路由技能。生成开始时运行一次，将用户输入、附件、格式约束转化为
  所有下游技能共享的"任务契约"，并标记对应的 SOTA 算法链路。负责检测知识库挂载
  状态并将 kb_aware 路由决策传递给所有下游技能。
category: meta
pipeline_position: 1
depends_on: []
feeds_into:
  - document-chief-planner
  - ppt-director
  - research-report-authoring
  - skill-factory
  - data-grounding
kb_aware: true
input_schema:
  - name: user_input_raw
    type: string
    required: true
    description: 用户输入框原文，绝对保留，不改写、不摘要、不翻译
  - name: output_format_hint
    type: string
    required: false
    description: "用户明确指定的格式（pptx / docx / xlsx），若未指定则从语境推断"
  - name: uploaded_files
    type: array
    required: false
    description: 上传文件清单，每项含文件名和 MIME 类型
  - name: mounted_kb
    type: object
    required: false
    description: 当前挂载的知识库信息（kb_id、kb_name、文档数量），null 表示未挂载
output_schema:
  - name: user_goal
    type: string
    description: 原始输入，一字不改
  - name: output_format
    type: string
    description: "锁定的目标格式：ppt / word / excel"
  - name: sota_chain
    type: array
    description: 激活的 SOTA 算法链路，有序列表
  - name: uploaded_files
    type: array
    description: 每文件标注角色：source_evidence / style_reference / template
  - name: constraints
    type: object
    description: 量化约束（页数、字数、保密等级等）
  - name: kb_routing
    type: object
    description: 知识库路由决策，含 kb_mounted（布尔）、kb_id、推荐检索关键词、需传递 kb_context 的下游技能列表
  - name: missing_inputs
    type: array
    description: 缺失但需要的输入，及安全假设
  - name: risk_log
    type: array
    description: 歧义、冲突、超出能力边界的问题
quality_thresholds:
  min_score: 0.95
  retry_on_fail: true
  max_retries: 1
---

# Intake Planner

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**运行时机：每次生成的第一步，只运行一次。不生成任何正文内容。**

## 核心职责

读懂用户需求，锁定格式轨道，分类附件，标记 SOTA 链路，交给下游。

## Inputs

- 用户输入框原文（绝对保留，不改写）
- 输出格式：pptx / docx / xlsx
- 上传文件清单（名称、类型）
- 挂载知识库
- 显式约束：页数、字数、受众、行业、截止时间

## Outputs

| 字段 | 内容 |
|------|------|
| `user_goal` | 原始输入，一字不改 |
| `output_format` | ppt / word / excel |
| `audience` | 目标读者（角色 + 背景） |
| `sota_chain` | 激活的 SOTA 算法链路 |
| `uploaded_files` | 每文件标注角色：source_evidence / style_reference / template |
| `constraints` | 量化约束（页数、字数、保密等级等） |
| `missing_inputs` | 缺失但需要的输入，及安全假设 |
| `risk_log` | 歧义、冲突、超出能力边界的问题 |

## SOTA 格式路由

格式确定后，标记对应的 SOTA 算法链路：

- **PPT** → PMRC 叙事重构（outline 阶段） → SlideTailor 布局选择（per-slide） → AeSlides 几何评分（下载时）
- **Word** → 结构规划 → 分章起草 → DECRIM 约束精炼（9条约束，≤2轮，目标 ≥90分）
- **Excel** → DataAnalyst 代码执行 → LIDA 四阶图表流水线 → openpyxl 数值/色阶/公式渲染

## Workflow

1. **保留原文** — `user_goal` 存原始输入，禁止改写、摘要、翻译
2. **识别格式** — 从指令或语境推断，锁定 `output_format`，激活对应 `sota_chain`
3. **分类附件** — 每个上传文件明确标注：是事实来源还是风格参考还是模板（三者严格不混）
4. **提取约束** — 量化所有限制（"几十页" 改为 "30-50页"，模糊的要问清楚）
5. **列缺失项** — 确实需要但没有的信息：列出来，注明是"需要询问"还是"可以假设"
6. **标记风险** — 需求歧义、附件与需求不匹配、格式超出当前能力边界

## KB-Aware 路由（KB-Aware Routing）

知识库（RAG）检测与路由是 intake-planner 的专属职责。所有下游技能通过 `kb_routing` 字段获取知识库上下文决策，不自行检测知识库状态。

### 检测逻辑

```
mounted_kb 非空？
    ├─ 是 → kb_mounted = true
    │         ├─ 提取检索关键词（从 user_goal 取 3-5 个领域关键词）
    │         ├─ 标记哪些下游技能需要 kb_context（见下方路由表）
    │         └─ 将 kb_routing 写入任务契约
    └─ 否 → kb_mounted = false
              ├─ kb_context 对所有下游技能为 null
              └─ 依赖知识库的技能降级到"仅上传文件"模式
```

### 下游技能 KB 路由表

| 技能 | 是否需要 kb_context | 用途 |
|------|-------------------|------|
| `document-chief-planner` | 可选 | 检索行业标准章节结构，辅助骨架设计 |
| `research-report-authoring` | **推荐** | 作为一手文献来源，补充文献综述 |
| `word-authoring` | 可选 | 补充行业背景数据，降低"数据待补充"比例 |
| `ppt-director` | 可选 | 补充行业对比基准数据，增强证据密度 |
| `data-grounding` | 可选 | 扩展证据池，将知识库检索结果纳入 evidence_pack |
| `skill-factory` | 否 | 技能工厂不访问知识库 |
| `qa-verification` | 否 | 纯格式核查，不需要业务知识 |

### 检索关键词生成规则

从 `user_goal` 提取关键词时：
1. 优先提取**领域名词**（行业/产品/技术术语），不取动词和介词
2. 关键词数量：3-5 个
3. 若用户上传了文件，从文件名中追加 1-2 个补充关键词
4. 将关键词写入 `kb_routing.search_keywords`，供下游技能执行 RAG 检索时使用

### KB 置信度传递规则

- 向下游技能明确传递：知识库检索结果的相似度阈值为 **0.7**
- 相似度 ≥ 0.7：标记为正常参考来源，格式 `[KB来源：文档名]`
- 相似度 0.5-0.7：标记为低置信度参考，格式 `[低置信度参考：文档名]`
- 相似度 < 0.5：丢弃，不传递给下游

### 降级模式

知识库未挂载时（`kb_mounted: false`），下游技能的行为：
- `research-report-authoring`：文献综述章节改为基于上传文件 + 模型知识，所有来自模型知识的引用标注 `[基于行业惯例，无直接来源]`
- `word-authoring`：缺少行业基准数据时用 `[数据待补充]` 显式标注
- `document-chief-planner`：章节结构依赖领域惯例而非知识库检索，需在 risk_log 中记录

## Non-Negotiables

- `user_goal` 必须是原始输入，禁止任何形式的改写
- 文件角色三选一：source_evidence / style_reference / template，不可混用
- 格式轨道一旦锁定，下游所有技能不得擅自变更
- 此阶段禁止生成任何正文、大纲、建议内容

## Quick Checklist

- [ ] user_goal 未被改写
- [ ] output_format 已锁定，sota_chain 已标记
- [ ] 每个上传文件已标注角色（source_evidence / style_reference / template）
- [ ] constraints 已量化
- [ ] missing_inputs 已列出（无缺失也要写"无"）
- [ ] kb_routing.kb_mounted 已明确（true / false）
- [ ] 若 kb_mounted=true：search_keywords 已提取（3-5个），下游 kb_context 接收列表已标记
- [ ] 若 kb_mounted=false：降级模式已在 risk_log 中记录
