---
name: data-grounding-cn
description: >
  事实 grounding 技能。在任何写作技能运行前，将上传文件、知识库片段、搜索结果
  转化为可追溯的证据包。职责是"读清楚"，不是"写内容"。
  支持多级证据优先级、KB 置信度过滤、冲突仲裁协议、降级模式。
category: grounding
pipeline_position: 1.5
depends_on:
  - intake-planner
feeds_into:
  - word-authoring
  - research-report-authoring
  - ppt-director
  - document-chief-planner
kb_aware: true
input_schema:
  - name: user_goal
    type: string
    required: true
    description: 用户原始需求，来自 intake-planner，用于筛选相关证据
  - name: uploaded_files
    type: array
    required: false
    description: 上传文件的解析文本，每项含 filename、role（source_evidence/style_reference/template）、text
  - name: kb_context
    type: array
    required: false
    description: 来自 RAG 检索的知识库片段，每项含 chunk_id、score、text、source_doc
  - name: format_track
    type: string
    required: false
    description: "目标格式轨道：ppt / word / excel，影响证据打包优先级"
output_schema:
  - name: evidence_pack
    type: object
    description: 按相关性和置信度排序的可引用事实，附来源锚点
  - name: data_dictionary
    type: object
    description: 关键指标的单位、口径、时间段、分母说明，保障跨章数据一致
  - name: conflict_log
    type: array
    description: 来源之间数字冲突的记录，双方都保留，不擅自裁定
  - name: assumption_list
    type: array
    description: 无法直接确认的数字或结论，标注假设依据
  - name: coverage_gaps
    type: array
    description: 任务需要但材料里没有的数据，供写作技能标注"数据待补充"
  - name: source_inventory
    type: array
    description: 所有可用来源的清单，含可靠性等级和可引用性评估
quality_thresholds:
  min_score: 0.85
  retry_on_fail: true
  max_retries: 1
---

# Data Grounding

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.

**职责：把原始材料转化为可引用的结构化证据，供所有写作技能调用。**

## 证据优先级层级

按来源可靠性从高到低排序：

| 层级 | 来源类型 | 引用格式 | 置信度标签 |
|------|---------|---------|-----------|
| L1 | 用户上传的原始数据文件（XLSX/CSV）| `[来源：文件名 Sheet/行列]` | 高置信度 |
| L2 | 用户上传的文档（PDF/DOCX/PPT）| `[来源：文件名 p.XX]` | 高置信度 |
| L3 | 知识库检索片段（score ≥ 0.7）| `[KB来源：文档名 chunk_id]` | 中高置信度 |
| L4 | 知识库检索片段（score 0.5-0.7）| `[低置信度参考：文档名]` | 低置信度 |
| L5 | 模型内部知识 / 行业惯例推断 | `[基于行业惯例，无直接来源]` | 推断，需人工验证 |

**L4 以下（score < 0.5）的 KB 片段丢弃，不进入 evidence_pack。**

## 核心原则

每一个数字、排名、趋势、因果判断，必须有以下三者之一：
1. **来源锚点** — 文件名 + 页/表/段落
2. **计算说明** — 用了什么数据怎么算出来的
3. **假设标注** — 明确标注为"估算"或"推断"，并说明依据

没有以上三者之一的数字，**不得进入下游写作阶段**。

## Inputs

- 上传文件（PDF、DOCX、XLSX、CSV、TXT、Markdown）
- 知识库检索片段（含相似度分数）
- 网页搜索结果（如已启用）
- 当前任务的 `user_goal` 和 `format_track`

**注意**：模板和 style_reference 文件不是事实来源，不得从中提取数字。

## Outputs

| 输出 | 内容 |
|------|------|
| `evidence_pack` | 与任务相关的可引用事实，按 L1-L5 分层标注 |
| `data_dictionary` | 关键指标的单位、口径、时间段、分母说明 |
| `conflict_log` | 来源之间的数字冲突，保留双方，不擅自裁定 |
| `assumption_list` | 无法确认的数字或结论，标注假设依据 |
| `coverage_gaps` | 任务需要但材料里没有的数据，供写作技能标注"数据待补充" |
| `source_inventory` | 全部来源清单，含层级标注和可引用性评估 |

## KB 集成协议

### 知识库片段处理流程

```
RAG 检索结果（来自 intake-planner.kb_routing）
    ↓ 按 score 过滤
score ≥ 0.7 → L3 证据（可直接引用）
score 0.5–0.7 → L4 低置信度（标注后可用）
score < 0.5 → 丢弃
    ↓ 提取
保留原始 chunk_id 作为引用锚点
评估时效性（优先用较新的片段）
    ↓ 加入 evidence_pack
```

### KB 降级模式（kb_mounted = false 时）

当知识库未挂载时，data-grounding 技能：
1. 依赖用户上传文件作为唯一 L1/L2 来源
2. 对于任务所需但文件中找不到的领域背景知识，使用 L5（推断）并在 coverage_gaps 中标注
3. 告知下游写作技能：`kb_available: false`，触发下游技能的"数据待补充"标注模式

**KB 降级不等于放弃证据**。降级时应尽量：
- 从上传文件中挖掘更多隐含数字（表格数据、注释中的比例等）
- 使用模型知识补充行业基准（L5），但必须标注"基于行业惯例，需验证"

## 冲突仲裁协议

当两个来源对同一指标给出不同数字时：

### 第一步：记录冲突
```
conflict_log 条目格式：
{
  "indicator": "指标名称",
  "source_a": {"value": "XX", "source": "文件A p.XX", "date": "日期/版本"},
  "source_b": {"value": "YY", "source": "文件B p.XX", "date": "日期/版本"},
  "resolution": "待下游技能裁定 | 推荐使用 source_a（更新）| 两者均呈现"
}
```

### 第二步：提供仲裁建议（不裁定）

根据以下规则给出**建议**（不强制）：
- 时间更新的来源通常更可靠 → 建议使用较新来源
- 原始数据 > 二手分析 → 建议使用 L1/L2 而非 L3
- 样本范围更大的数据更可靠 → 建议引用范围更广的

### 第三步：传递给下游

下游写作技能在引用冲突指标时，应：
- 写"根据[文件A]，XX 指标为 M；根据[文件B]，同一指标为 N，两者存在差异" 
- 不得只引用其中一个而不提另一个（除非 conflict_log 明确建议了裁定方向）

## Workflow

1. **清点来源** — 列出所有可用文件、KB片段，按 L1-L5 层级标注，排除 style_reference
2. **提取** — 按任务需求抽取相关段落、表格、数字。不相关的不要
3. **标准化** — 统一时间周期、货币单位、计量单位、分母口径。原始值和转换值都保留
4. **核验冲突** — 多来源同一指标不一致时，触发冲突仲裁协议
5. **KB 片段融合** — score ≥ 0.7 的 KB 片段纳入 L3，0.5-0.7 纳入 L4，< 0.5 丢弃
6. **打包证据** — 每条证据附：层级(L1-L5)、来源、位置、任务相关性
7. **列覆盖缺口** — 任务需要但材料里找不到的数据，明确列出

## evidence_pack 格式

```json
{
  "kb_available": true,
  "total_sources": 3,
  "facts": [
    {
      "id": "e001",
      "level": "L2",
      "text": "Q3 营收 3.2亿元，同比增长 18%",
      "source": "sales_report_2026.xlsx",
      "location": "Sheet1 B5:C5",
      "relevance": "直接回答用户的收入分析需求",
      "confidence": "高"
    },
    {
      "id": "e002",
      "level": "L3",
      "text": "行业平均毛利率约 35%",
      "source": "行业白皮书",
      "location": "chunk_abc123",
      "relevance": "支持毛利对比分析",
      "confidence": "中高（KB score: 0.82）"
    }
  ],
  "low_confidence_refs": [
    {
      "id": "e003",
      "level": "L4",
      "text": "…",
      "source": "…",
      "confidence": "低（KB score: 0.58，仅供参考）"
    }
  ]
}
```

## Failure Modes（本技能特有）

- **文件不可读** → 标注文件名和错误原因，在 coverage_gaps 中记录
- **数字来源冲突** → 触发冲突仲裁协议，双方保留在 conflict_log，给出建议但不强制裁定
- **KB 全部低于阈值** → kb_available 降级，通知下游，从 L5 补充
- **无任何相关证据** → 生成空 evidence_pack（facts: []），在 coverage_gaps 中详细列出缺失项，并标注任务无法完成的风险
- **style_reference 误用** → 主动拒绝提取，在 source_inventory 中标注"style_reference，不得用于事实"

## 与下游技能的交接

向下游传递的关键字段：

| 字段 | 用途 |
|------|------|
| `kb_available` | 下游技能判断是否启用 KB 引用格式 |
| `conflict_log` | 下游技能在引用冲突指标时需呈现双方 |
| `coverage_gaps` | 下游写作时标注 `[数据待补充：XXX]` 的依据 |
| `data_dictionary` | 跨章节统一单位和口径 |

## Quick Checklist

- [ ] 每条证据有层级标注（L1-L5）和来源锚点（文件名 + 位置）
- [ ] KB 片段已按 score 过滤（< 0.5 已丢弃）
- [ ] data_dictionary 包含所有关键指标的单位和口径
- [ ] 数字冲突已进入 conflict_log，含仲裁建议但未强制裁定
- [ ] style_reference 文件中的数字未被当作事实提取
- [ ] coverage_gaps 已列出（无缺口也要写"无"）
- [ ] kb_available 字段已明确（true/false/partial）
- [ ] source_inventory 列出了所有来源及其层级
