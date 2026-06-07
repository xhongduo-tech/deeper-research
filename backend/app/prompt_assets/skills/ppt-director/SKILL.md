---
name: ppt-director-cn
version: "1.0"
description: >
  PPT 执行导演技能。在 PMRC 叙事重构完成后运行，负责将 PMRC 输出的叙事弧线
  转化为每张幻灯片的具体内容指令（SlideSpec）。不做叙事重构（那是 PMRC 的工作），
  不做布局选择（那是 SlideTailor 的工作）。
category: ppt
pipeline_position: 2
depends_on:
  - intake-planner
  - ppt-narrative
  - data-grounding
feeds_into:
  - ppt-layout
  - qa-verification
kb_aware: true
input_schema:
  - name: pmrc_output
    type: object
    required: true
    description: PMRC 叙事重构的结果，包含 story_thread、narrative_type、opening_hook、closing_cta
  - name: pmrc_sections
    type: array
    required: true
    description: 每页的叙事规划，包含 role、claim、evidence、visual_intent（来自 ppt-narrative/PMRC）
  - name: evidence_pack
    type: object
    required: true
    description: 来自 data-grounding 的结构化证据，含事实列表和来源锚点
  - name: pptd_template
    type: object
    required: false
    description: .pptd 模板描述文件（布局约束、色彩方案等），若无则使用默认模板
  - name: constraints
    type: object
    required: false
    description: 受众、风格、页数等约束，来自 intake-planner
output_schema:
  - name: slide_specs
    type: array
    description: SlideSpec 列表，每页一个 JSON 对象，包含 slide_id、slide_role、pmrc_phase、title、claim、evidence、visual_intent、key_message、speaker_note；slide_type 字段留空
  - name: slide_count
    type: integer
    description: 总幻灯片数量
  - name: pmrc_distribution
    type: object
    description: P/M/R/C 各阶段幻灯片数量分布，用于验证叙事结构合理性
quality_thresholds:
  min_score: 0.88
  retry_on_fail: true
  max_retries: 2
---

# PPT Director

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.


**在 PMRC 叙事弧线已确定的前提下运行。负责内容执行，不做叙事设计。**

## 在 SOTA PPT 流水线中的位置

```
PMRC 叙事重构（已完成）
    ↓ story_thread、opening_hook、closing_cta 已确定
PPT Director（本技能）← 你在这里
    ↓ 每页 SlideSpec 输出
SlideTailor 布局选择（per-slide，自动）
    ↓
AeSlides 几何评分（下载时，自动）
```

## Inputs

- `pmrc_output`: story_thread、narrative_type、opening_hook、closing_cta
- `pmrc_sections`: 每页的 role、claim、evidence、visual_intent（来自 PMRC）
- `evidence_pack`（来自 data-grounding）
- `.pptd` 模板描述（如有）
- 受众和风格约束

## Outputs — SlideSpec（每页一个）

```json
{
  "slide_id": "s01",
  "slide_role": "cover|problem|motivation|evidence|insight|recommendation|conclusion",
  "pmrc_phase": "P|M|R|C",
  "title": "结论式标题（不超过12字，是判断句而非话题句）",
  "claim": "这页要证明的一个核心断言",
  "evidence": ["具体数字或事实，附来源"],
  "visual_intent": "数据图|对比表|流程图|文字强调|图片+数字",
  "key_message": "读者离开这页时必须记住的一句话",
  "speaker_note": "演讲者备注（补充背景、数据解释、过渡语）",
  "slide_type": "由 SlideTailor 填充，此处留空"
}
```

## 标题写作规则

PPT 标题是**结论句**，不是话题句：

| 错误（话题句）| 正确（结论句）|
|--------------|--------------|
| Q3 销售数据 | Q3 销售额超目标 12%，华北增速最快 |
| 市场现状分析 | 市场份额从 18% 降至 14%，竞争格局恶化 |
| 建议与展望 | 三项行动可在 90 天内扭转颓势 |

## PMRC 阶段内容要求

| 阶段 | 内容重点 | 禁忌 |
|------|---------|------|
| P（Problem）| 量化问题，用数字说明严重性 | 只描述现象不给数字 |
| M（Motivation）| 说明为什么现在解决（时机、后果）| 与 P 内容重复 |
| R（Results）| 方案、证据、对比、可量化效果 | 没有数字支撑的纯文字主张 |
| C（Conclusion）| 具体可执行的行动，有时间/责任人 | 模糊的"建议加强""继续推进" |

## PMRC 降级模式

当 `pmrc_output` 为空或不完整时（PMRC 重构失败），启用**降级叙事模板**：

```
降级叙事 = 线性结构（无 PMRC 阶段）
├── 封面（cover）
├── 目录（agenda）
├── 背景/现状（context） × 1-2页
├── 分析/发现（analysis） × N页（由 evidence_pack 决定）
├── 结论/建议（recommendation） × 1-2页
└── 结束（closing）
```

降级时必须在 `pmrc_distribution` 中注明：`"mode": "fallback_linear"`。

## 证据密度要求

每页 SlideSpec 的 `evidence` 字段：
- **数据页**（evidence/insight/recommendation）：至少 1 条来自 evidence_pack 的具体数字
- **文字页**（problem/motivation）：至少 1 条可量化的现象描述
- **封面/封底**：不需要数字，但 `key_message` 必须填写

若 evidence_pack 为空或相关性低，对应幻灯片的 `evidence` 写 `["[数据待补充：XXX]"]`，不得留空。

## Workflow

1. **接收 PMRC 输出** — 读取 story_thread、每页的 role 和 claim；若 PMRC 失败则切换降级模式
2. **为每页写结论式标题** — 不超过12字，是判断而非话题
3. **接入证据** — 从 evidence_pack 为每页的 claim 找具体数字支撑；无数字则标注"[数据待补充]"
4. **写 key_message** — 每页最重要的一句话，读者离开后能复述的（不超过20字）
5. **写 speaker_note** — 演讲者需要的背景信息、数据解释、页间过渡（2-4句）
6. **检查 PMRC 阶段分布** — P/M/R/C 各占的比例；正常模式下 P ≥ 1页，M ≥ 1页，R ≥ 2页，C ≥ 1页
7. **输出 SlideSpec 列表** — 每页一个 JSON，`slide_type` 字段留空

## Quick Checklist

通用：
- [ ] 每页标题是结论句，不是话题句（不超过12字）
- [ ] 数据页有具体数字（来自 evidence_pack，或标注"[数据待补充]"）
- [ ] key_message 不超过20字
- [ ] speaker_note 已填写（2-4句）
- [ ] slide_type 字段留空（给 SlideTailor 填）

PMRC 模式：
- [ ] PMRC 四个阶段都有对应幻灯片（P ≥ 1，M ≥ 1，R ≥ 2，C ≥ 1）
- [ ] pmrc_distribution 中记录了各阶段页数

降级模式：
- [ ] pmrc_distribution 中注明 "mode": "fallback_linear"
- [ ] 线性结构包含封面、内容、结论、封底
