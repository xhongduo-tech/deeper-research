---
name: academic-paper-authoring-cn
description: >
  学术论文写作技能。生成达到顶会/顶刊水准的完整论文草稿，包括 IMRaD 结构、
  Conference Paper Contract、方程编号与符号定义、图表规范、消融分析格式、
  计算效率报告和统计显著性标注。支持英文和中文输出；
  当用户要求 CVPR/NeurIPS/ACL/ICLR/顶会/full paper/论文复现时，
  必须读取 references/structure_narrative_contract.md。
---

# Academic Paper Authoring

## Kimi-Style Contract Adapter

This skill follows the shared Kimi-style execution contract in `../_shared/kimi_style_skill_contract.md`. Interpret this file as an operational contract with:

- **Trigger Boundary**: use the skill only for its declared artifact type and do not absorb neighboring skills' work.
- **Input Contract**: preserve user goal, audience, source materials, constraints, and missing-data markers from upstream skills.
- **Output Contract**: emit the concrete schema, section hierarchy, spec, checklist, or QA report promised below.
- **Workflow Discipline**: execute steps in order; keep required sections/spec fields even when evidence is incomplete.
- **Quality Gate**: before handoff, verify grounding, structure completeness, formatting constraints, and downstream readiness.

**职责：按照学术规范生成论文草稿。不混入商业报告、白皮书或执行摘要写法。**

## Mode Selection

| 用户目标 | 结构模式 | 必须读取 |
|---|---|---|
| 顶会/会议/full paper/论文复现/方法实验完整论文 | Conference Paper Contract | `references/structure_narrative_contract.md` |
| 期刊论文/实证研究/课程论文 | IMRaD | 本文件即可；必要时读取结构契约作为强化检查 |
| 文献综述 | Thematic Review | 重点执行 Related Work 的主题化组织 |
| 摘要/短论文/extended abstract | Compact Paper | 保留问题、方法、结果、局限，不强制完整页数预算 |

当用户未说明格式但出现"论文""paper""投稿""会议""期刊"等词，默认使用学术写作模式；
当出现"CVPR/NeurIPS/ICML/ICLR/ACL/EMNLP/AAAI/顶会/full paper/复现"等词，
**必须**升级到 Conference Paper Contract 并读取 `references/structure_narrative_contract.md`。

## Conference Paper Contract

详见 `references/structure_narrative_contract.md`。执行要点如下：

- 最终输出必须包含：Title、Authors/Affiliations、Abstract、1 Introduction、2 Related Work、3 Method、4 Experiments、5 Conclusion、References；Appendix 按需追加。
- Introduction 必须按 broad → narrow → gap → empirical evidence of gap → solution → contributions → roadmap 写成 5-7 段。**P4（empirical evidence）必须包含一个具体的观察或初步实验结论**，例如"我们的初步实验表明，简单堆叠超过10层的卷积层会导致验证精度持续下降（Fig. 2）"。
- Method 必须至少包含 3.1 Core Formulation、3.2 Key Mechanism、3.3 Architecture / Design、3.4 Implementation Details。
- Experiments 必须至少包含 4.1 Main Benchmark、4.2 Secondary Benchmark & Analysis（消融）、4.3 Extension / Application（跨域泛化）。
- 每个实验结论遵循 **Claim → Evidence → Interpretation**；所有图表必须先在正文中引用，再出现。
- 若用户资料缺失实验数字、消融或 benchmark，保留对应小节并写 `[PLACEHOLDER: <描述>]`，**不得静默删除**。

## Abstract Writing Template

按以下 5 句骨架写 Abstract（150–250 words，单段）：

1. **Domain + Motivation**: 建立领域背景，说明问题为何重要（1-2句，引2-4篇奠基文献）。
2. **Problem / Gap**: 精确命名现有方法未解决的障碍，量化时尽量给出数字（1句）。
3. **Method at a Glance**: 方法名 + 核心机制 + 与之前方法的本质区别（1-2句）。
4. **Empirical Highlights**: 数据集名 + 指标 + 绝对值 + 相对最强基线的提升（1-2句）。
   示例：`Our method achieves 82.5% on BCI IV-2a, outperforming EEGNet by 6.3 percentage points.`
5. **Broad Implication**: 结果对该领域或后续工作的意义（1句）。

Keywords: 4-6 个，从最宽泛到最具体排列，逗号分隔。

## IMRaD 标准结构

```
Title / Authors / Affiliations
Abstract（约 150-250 words，单段）
Keywords（4-6 个）
1. Introduction（引言）
   P1: 领域背景与重要性 → P2: 细分领域趋势 → P3: 问题/缺口 →
   P4: 缺口的实证证据（初步实验或现象观察）→ P5: 本文方案 →
   P6: 贡献列表（3-5条具体贡献）→ P7: 章节路线图（可选）

2. Related Work（相关工作，按主题组织）
   主题A：代表性工作 + 局限性 + 与本文区别
   主题B：代表性工作 + 局限性 + 与本文区别
   主题C（可选）

3. Method（方法）
   3.1 Core Formulation：问题形式化定义，引入符号，写核心方程
   3.2 Key Mechanism：主要模块逐步说明，引用 Fig. N
   3.3 Architecture / Design：完整架构配置表，复杂度/参数量
   3.4 Implementation Details：数据预处理、优化超参、硬件、软件栈

4. Experiments（实验）
   4.1 Main Benchmark：数据集/指标/基线/主结果表/结果解读
   4.2 Secondary Benchmark & Ablation：次要数据集 + 消融表 + 训练曲线
   4.3 Extension / Generalization：跨域迁移/跨语言/实际应用

5. Conclusion（结论）
   摘要式总结（过去时）→ 局限性（≥2条，具体）→ 未来工作（具体，非泛泛）

References（参考文献，按指定格式）
Appendix（可选：推导、额外实验、超参敏感性）
```

## Empirical BMI / Neural Signal Paper Minimum Visual Pack

当主题包含 `Brain-machine interface/BMI/BCI/neural signal/EEG/ECoG/spike` 且用户要求英文实证研究论文时，默认输出英文 IMRaD/Conference 风格，并规划以下非装饰性图表：

1. `Figure 1` 方法架构或解码管线图：使用 `[FIGURE: architecture | ...]`，节点覆盖 signal acquisition → preprocessing → feature/representation learning → decoder → command/output。
2. `Table 1` 数据集与实验设置：modality、subjects/sessions、channels、task、sampling rate、train/test protocol、metrics。
3. `Table 2` 主结果表：方法、多个 benchmark、mean ± std、best/second-best、显著性标记和来源/占位。
4. `Figure 2` 训练动态：有真实/可审计数值时使用 `[ACADEMIC_FIGURE: training_dynamics | ...]` 双面板图包。
5. `Table 3` 消融表：Full model、w/o component、Δ vs. full，与 Method 组件名一致。
6. `Figure 3-5` 至少覆盖跨数据集 grouped bar、消融+被试双面板、时间解码+频带重要性双面板。分别使用 `[ACADEMIC_FIGURE: benchmark_comparison | ...]`、`[ACADEMIC_FIGURE: ablation_subject | ...]`、`[ACADEMIC_FIGURE: temporal_frequency | ...]`。

图片标记必须包含可渲染数据或结构节点；仅有“Figure N should show...”会导致导出器无法生成图片。缺失数值时不要输出伪数据型 `[CHART]` 或 `[ACADEMIC_FIGURE]`，改用 `[PLACEHOLDER: ...]` 并说明需要的实验。

## Equation Block Rules

- 每个展示方程顺序编号：`(1)`, `(2)`, …；正文引用写 `Eqn. (N)`。
- **每个新符号在首次出现处就地定义**，格式：`where **X** ∈ ℝ^{C×T} denotes a single-trial EEG segment with C channels and T time points.`
- 损失函数：先写完整目标函数，再逐项解释每一项的含义和作用。
- LaTeX 风格符号：`R^{C x T}`、`||·||_F`、`argmin_θ`、`Σ`。

## Architecture Description Requirements

每个新架构必须提供配置表：

| Layer / Stage | Output Shape | Kernel / Stride | Params |
|---|---|---|---|
| Input | C × T | — | — |
| Temporal Conv | F × T' × C | k × 1 | — |
| … | … | … | … |
| FC Classifier | K | — | — |

随后说明：总参数量（M）、与2-3个基线的参数对比、推理速度（ms/sample on [GPU型号]）、若相关则报告 FLOPs。

## Figure and Table Rules

### 图说明（Figure Captions，位于图下方）

完整图说明包含三部分：
1. `Figure N.`（粗体标号）
2. 一句总览：说明图的最高层含义。
3. 分面说明：对每个子图用 `(a)/(b)` 或 `Left:/Right:` 分别描述，**并说明每面的关键观察**。

示例：`Figure 4. Ablation and subject-wise analysis on BCI IV-2a. Left: Ablation results showing accuracy drop when each component is removed. Right: Subject-wise accuracy for our method (blue) vs. the CNN baseline (red); our method shows the largest gains for subjects with lower baseline performance (S04, S05).`

### 表说明（Table Captions，位于表上方）

### 结果表格格式

- **加粗**每行/列的最优值；*斜体*第二优。
- 统计显著性：`*` p < 0.05，`**` p < 0.01，在表格脚注说明检验方法（如"paired t-test with Bonferroni correction"）。
- 多次运行或多被试结果格式：`mean ± std`。
- 提出方法的行标注为模型名或 `Ours`。

## Ablation Study Format

```
Table N. Ablation study on [dataset]. Accuracy (%) reported as mean ± std across N subjects.

| Variant            | Accuracy (%) | Δ vs. Full |
|--------------------|-------------|------------|
| Full model (Ours)  | **82.5±1.2** | —          |
| w/o Component A    | 78.3 ± 1.4  | −4.2       |
| w/o Component B    | 76.1 ± 1.8  | −6.4       |
| Replace X with Y   | 80.1 ± 1.1  | −2.4       |
```

每个消融项在正文中用 **Claim → Evidence → Interpretation** 三步叙述，解释*为什么*去掉该组件会导致性能下降。

## Computational Efficiency Section

在 Sec. 3.4 或单独 Sec. 4.4 中报告：

- **模型规模**：总参数（M），与2-3个基线对比。
- **推理速度**：每样本/每试验的推理时间（ms），硬件型号。
- **训练时间**：每 epoch 时间或总训练时间，硬件配置。
- **硬件/软件**：GPU 型号 + VRAM、CPU、RAM、框架版本、CUDA 版本。
- **代码可用性**："Code and pretrained models are available at [URL]." 或 `[PLACEHOLDER: repository URL]`

## Numerical Placeholder Protocol

**禁止编造**基线精度、参数量、训练时间。对任何缺失数字，写：

```
[PLACEHOLDER: <说明该数字代表什么、理论上应从哪里获取>]
```

示例：
- `[PLACEHOLDER: EEGNet accuracy on BCI IV-2a from Lawhern et al. (2018)]`
- `[PLACEHOLDER: ablation accuracy without spatial filtering — requires training experiment]`

## 学术语言规范

### 英文用词

| 避免（过强/口语/商业化） | 学术表达 |
|---|---|
| "proves that" | "provides evidence that" / "suggests" |
| "X causes Y" | "X is associated with Y" / "correlates with" |
| "the best method" | "achieves state-of-the-art on [benchmark]" |
| "very important" | "statistically significant (p < 0.01)" |
| "as shown above" | "as shown in Fig. N" / "as reported in Table N" |
| "我们建议" | "research findings support" / "data provide evidence for" |

### 段落级叙述模式

**Claim–Evidence–Interpretation（每个实验结论必须）：**
1. **Claim**（主题句）: "Removing the spatial filtering module significantly degrades performance."
2. **Evidence**（量化）: "As shown in Table 3, accuracy drops from 82.5% to 78.3% (−4.2 pp)."
3. **Interpretation**（机制）: "This confirms that learnable CSP-regularized filters are essential for extracting discriminative sensorimotor patterns from multi-channel EEG."

### 章节过渡短语

- Introduction → Related Work: "We now review the prior work most directly relevant to these challenges."
- Related Work → Method: "To address the gaps identified above, we propose..."
- Method → Experiments: "We now empirically validate the proposed framework."
- Main Results → Ablation: "To understand the contribution of each architectural component, we conduct systematic ablation studies."
- Ablation → Extension: "Having validated each component, we next evaluate the generalization capability of the full model."
- Experiments → Conclusion: "The preceding results support the following conclusions."

### 结果陈述规范

- 有统计量时：`F(1, 98) = 4.23, p = .04, η² = .04` 或 `p < 0.01, paired t-test`
- 无统计量时：描述方向和量级，明确标注"based on descriptive statistics only"
- **禁止**在 Results 节写解释（留给 Discussion）

## 引用规范

### IEEE / 数字引用 [N]（会议论文默认）
- 文中：`[1]`, `[2, 3]`, `[1–5]`
- 参考文献：`[N] A. Author, "Title," in *Proc. Conf.*, vol. X, pp. Y–Z, Year.`

### APA 7（英文期刊）
- 文中：`(Author, Year)`
- 参考文献：`Author, A. A. (Year). Title. *Journal*, *Volume*(Issue), pages.`

### GB/T 7714（中文学术）
- 文中：`[序号]`
- 参考文献：`作者. 题名[文献类型标识]. 出版地: 出版者, 年份.`

当用户未指定格式时，默认 IEEE 数字引用（英文会议/期刊）或 GB/T 7714（中文）。

## 与其他技能的分工

- **academic-paper-authoring**：生成论文正文草稿，标记引用占位符 `[CITE: 来源描述]`
- **citation-bibliography**：处理占位符，生成符合格式规范的参考文献列表
- **table-figure-authoring**：把 figure/table/equation 的描述性占位转为可执行 Markdown / ChartSpec
- **qa-verification**：最终校验：结构完整性、引用一致性、数据与来源一致

对 Conference Paper，正文必须先写 "Fig. N shows..." 或 "Table N reports..."，再放图表占位。

## 禁止行为

- 禁止在 Results 节写解释（那是 Discussion 的工作）
- 禁止混用第一/第三人称（确定一种贯穿全文）
- **禁止编造任何实验数字**——用 `[PLACEHOLDER: ...]` 代替
- 禁止商业化表达（"建议公司投资"、"提高利润"等）
- 禁止因资料不足而删除 Method/Experiments 必需小节；保留并标明缺口
- 禁止"as shown above"——永远用显式的 `Fig. N` / `Table N` 引用
- 禁止在 Related Work 用时间顺序罗列论文（按主题组织）

## Quick Checklist

- [ ] IMRaD / Thematic Review / Conference Paper Contract 已正确选择
- [ ] 顶会/full paper 已加载 `structure_narrative_contract.md`
- [ ] Abstract 遵循 5 句模板，含具体数字
- [ ] Keywords 4-6 个，从宽到窄
- [ ] Introduction P4 包含 empirical evidence of gap（具体观察或初步实验）
- [ ] Introduction P6 包含 3-5 条具体贡献
- [ ] 所有方程顺序编号，每个符号在首次出现时就地定义
- [ ] 架构配置表存在（或明确说明为何省略）
- [ ] 消融表覆盖所有主要组件，含 mean ± std
- [ ] 结果表：最优值加粗，次优斜体，统计显著性标注
- [ ] 计算效率（参数量、推理速度、硬件）已报告
- [ ] 每个实验结论遵循 Claim → Evidence → Interpretation
- [ ] 所有图表在正文中**先引用再出现**
- [ ] 图说明在图下方，含分面描述；表说明在表上方
- [ ] 无编造数字（缺失数字用 [PLACEHOLDER:...] 标注）
- [ ] 无商业化语言
- [ ] Results 节不含解释
- [ ] 局限性在 Conclusion 节明确说明（≥2条）
