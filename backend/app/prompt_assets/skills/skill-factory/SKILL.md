---
name: skill-factory-cn
version: "1.0"
description: >
  技能工厂元技能。当用户需求属于当前技能库未覆盖的报告类型时，
  动态生成适合该类型的写作约束规范，作为临时技能卡注入生成流水线。
  支持两种模式：单次临时技能卡（single_use）和持久化个人技能（persistent）。
  这是系统处理长尾需求的最后一道适配层。
category: meta
pipeline_position: 2
depends_on:
  - intake-planner
feeds_into:
  - word-authoring
  - ppt-director
  - research-report-authoring
  - qa-verification
kb_aware: false
input_schema:
  - name: user_goal
    type: string
    required: true
    description: 用户原始输入，来自 intake-planner，触发 skill-factory 时必须未匹配到任何现有技能
  - name: output_format
    type: string
    required: true
    description: "目标格式：ppt / word / excel，决定临时技能卡注入哪条流水线"
  - name: persist_skill
    type: boolean
    required: false
    description: "true = 将生成的技能卡持久化为个人技能；false（默认）= 单次使用"
  - name: skill_name_hint
    type: string
    required: false
    description: 用户希望保存的技能名称（仅 persist_skill=true 时使用）
output_schema:
  - name: temp_skill_card
    type: object
    description: 生成的临时/持久技能卡，包含 skill_name、target_audience、delivery_purpose、recommended_structure、language_style、quality_gates、ttl 字段
  - name: injected_prefix
    type: string
    description: 注入生成流水线系统提示前缀的文本块
  - name: persist_path
    type: string
    description: "若 persist_skill=true，写入的技能文件路径；否则为 null"
quality_thresholds:
  min_score: 0.80
  retry_on_fail: true
  max_retries: 2
---

# Skill Factory

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**职责：为未覆盖的报告类型即席生成写作约束规范（临时或持久技能卡）。不替代现有技能，不负责内容写作。**

## 在流水线中的位置

```
intake-planner（无法匹配任何现有技能）
    ↓ user_goal + output_format 传入
skill-factory（本技能）← 你在这里
    ↓ temp_skill_card + injected_prefix
word-authoring / ppt-director（接收注入前缀继续执行）
    ↓
qa-verification
```

## Skill Graph — 技能图谱

下图展示了 skill-factory 在整体技能图谱中的位置。所有技能均由 intake-planner 路由；skill-factory 仅在无匹配时激活，作为长尾适配层，其输出以"注入前缀"形式叠加到通用写作技能上。

```
[用户输入]
    │
    ▼
intake-planner ─── 匹配成功 ──→ [对应专属技能]
    │
    └── 无匹配 ──→ skill-factory
                        │
                        ├── single_use ──→ 注入 word-authoring / ppt-director
                        └── persistent  ──→ 写入 custom-*/SKILL.md → 注册到技能库
```

## 触发时机

当 `intake-planner` 无法将用户需求映射到任何现有技能时，激活本技能：

```
现有技能覆盖范围：
- word-authoring（通用经营报告）
- research-report-authoring（研究/白皮书）
- academic-paper-authoring（学术论文）
- ppt-director + ppt-narrative（演示文稿）
- excel-modeling（数据分析工作簿）
- bid-proposal-authoring（标书/投标方案）
- legal-document-authoring（法律文书）
- meeting-minutes-authoring（会议纪要）
- official-document-authoring（政府/行政公文）
- press-release-authoring（新闻稿）
- prd-authoring（产品需求文档）
- training-manual-authoring（培训手册）
- ...
```

如果用户需求类型不在上述列表，Skill Factory 接管。

## 临时技能卡生成流程

### Step 1：识别报告类型特征

从用户需求提取：
- **目标受众**（谁看）
- **交付目的**（看完做什么决策）
- **典型结构**（有没有领域惯例）
- **语言风格要求**（正式/非正式，技术/非技术）

### Step 2：生成临时技能卡

```json
{
  "skill_name": "临时技能：[报告类型]",
  "target_audience": "...",
  "delivery_purpose": "...",
  "recommended_structure": ["章节1", "章节2", "..."],
  "language_style": {
    "tone": "...",
    "person": "...",
    "key_constraints": ["..."]
  },
  "quality_gates": ["每章必须有...", "禁止..."],
  "ttl": "single_use"
}
```

`ttl` 取值：
- `single_use` — 临时技能卡，只在当前报告生成中有效，不持久化
- `persistent` — 将技能卡写入 `skills/custom-<slug>/SKILL.md` 并注册到技能库，供后续复用

### Step 3：注入生成流水线

临时技能卡作为 `asset_context` 的一部分，附加到 `word-authoring` 或 `ppt-director` 的系统提示前缀：

```
【临时技能约束：[报告类型]】
目标受众：...
结构约束：...
语言风格：...
```

## 保存为个人技能（Save as Personal Skill）

当用户希望将临时技能卡持久化时（`persist_skill: true`），执行以下流程：

### 持久化步骤

1. **确认命名** — 从 `skill_name_hint` 或报告类型自动生成 slug（格式：`custom-<领域>-<动作>`，如 `custom-dd-report`）
2. **生成完整 SKILL.md** — 按照 `_SKILL_TEMPLATE.md` 结构填写，`category` 设为 `doc/ppt/sheet`，`version` 设为 `"1.0"`
3. **写入文件** — 路径：`skills/custom-<slug>/SKILL.md`；`persist_path` 字段记录此路径
4. **注册到技能库** — 将新技能 slug 追加到 `intake-planner` 的技能路由表（`references/dynamic_queue.md`）
5. **返回确认** — 向用户展示保存路径和触发关键词，说明如何在下次使用

### 个人技能命名约定

- 前缀固定为 `custom-`，防止与官方技能冲突
- 示例：`custom-dd-report`（尽调报告）、`custom-policy-brief`（政策简报）、`custom-postmortem`（复盘报告）
- 保存后可通过名称直接触发，无需再次经过 skill-factory

### 质量门控（持久化模式）

持久化技能卡须通过额外验证：
- 技能 slug 不与现有技能重名
- SKILL.md 结构完整（参照 `_SKILL_TEMPLATE.md` 所有必填字段）
- `quality_gates` 字段非空（至少 2 条）

## 什么不是 Skill Factory 的工作

- ❌ 替代现有技能（如果有合适的技能，使用它）
- ❌ 生成永久技能文件（Skill Factory 的卡片是临时的）
- ❌ 对数据质量负责（那是 data-grounding 的工作）
- ❌ 做格式转换（那是 document_generator.py 的工作）

## 常见长尾场景示例

| 用户需求类型 | 生成的关键约束 |
|-------------|--------------|
| 投资者 DD 报告 | 财务真实性优先；每项数据需注明来源；风险必须量化 |
| 政策简报（Policy Brief）| 1-2页；问题-政策选项-建议三段式；语言通俗无术语 |
| 复盘报告 | 时间线结构；问题/原因/改进措施三要素；无回避归因 |
| 竞品分析快报 | 对比表优先；结论在表格上方；每项有来源 |
| 路演 Pitch Deck | 故事线（痛点→解决方案→市场→团队→融资需求）；每页1个数字 |

## Quick Checklist

- [ ] 确认用户需求确实不匹配现有任何技能
- [ ] 临时技能卡包含 target_audience、recommended_structure、language_style、quality_gates 四个核心字段
- [ ] ttl 字段已明确设置（`single_use` 或 `persistent`）
- [ ] 临时技能卡已注入生成流水线的系统提示前缀
- [ ] 若 persist_skill=true：SKILL.md 已写入 `custom-*/` 路径，slug 已注册到路由表
- [ ] 生成结果经 qa-verification 做格式合规检查
