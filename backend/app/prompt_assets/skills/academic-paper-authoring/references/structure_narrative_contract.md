# Structure & Narrative Contract

Generalized from ResNet-style top-tier conference papers. Use this contract when
drafting, reproducing, or checking a complete scientific paper for venues such as
CVPR, ICCV, NeurIPS, ICML, ICLR, ACL, EMNLP, AAAI, SIGIR, KDD, or similar.

## Complete Section Hierarchy

All full conference-paper outputs must contain the following sections. Do not
skip required Method or Experiments subsections because data is incomplete; keep
the subsection and mark the gap explicitly.

```
Title
├── Authors & Affiliations
├── Abstract (single paragraph, about 150-250 words)
├── 1. Introduction (5-7 paragraphs)
│   ├── P1: Domain context
│   ├── P2: Sub-domain and trend
│   ├── P3: Problem or gap
│   ├── P4: Empirical evidence of the gap
│   ├── P5: Proposed solution at high level
│   ├── P6: Contribution list (3-5 items)
│   └── P7: Paper roadmap (optional)
├── 2. Related Work
│   └── Thematic blocks, not a paper-by-paper chronology
├── 3. Method / Approach
│   ├── 3.1 Core Formulation
│   ├── 3.2 Key Mechanism
│   ├── 3.3 Architecture / Design
│   └── 3.4 Implementation Details
├── 4. Experiments / Results
│   ├── 4.1 Main Benchmark
│   ├── 4.2 Secondary Benchmark & Analysis
│   └── 4.3 Extension / Application
├── 5. Conclusion
│   ├── Summary
│   ├── Limitations
│   └── Future Work (optional)
├── References
└── Supplementary / Appendix (optional)
    ├── A. Additional Experimental Details
    ├── B. Additional Results
    └── C. Derivation / Proof / Other
```

## Section Budget Rules

| Section | Pages | Body Share | Purpose |
|---|---:|---:|---|
| Introduction | 1-1.5 | 15-20% | Motivation, problem, contributions |
| Related Work | 0.5-1 | 8-12% | Positioning and differentiation |
| Method | 2-3 | 30-40% | Formulation, design, implementation |
| Experiments | 2.5-3.5 | 35-45% | Validation, analysis, ablation |
| Conclusion | 0.3-0.5 | 4-6% | Summary, limitations, future work |
| References | about 1 | n/a | Complete bibliography |

## Narrative Logic

Each major section follows a funnel: broad context -> specific problem -> paper
contribution. The paper should feel inevitable by the time the method appears.

### Introduction Arc

Write the Introduction in exactly 5-7 paragraphs for full papers.

1. **Domain Context**: name the broad field, cite seminal works, and state why
   the field matters.
2. **Sub-domain and Trend**: zoom into the current technical trend and cite
   recent work; use quantitative evidence when available.
3. **Problem or Gap**: name the obstacle or open question. A rhetorical question
   or surprising empirical finding is acceptable when it creates real tension.
4. **Empirical Evidence of the Gap**: preview the concrete observation, pilot
   result, or figure that proves the problem is non-trivial.
5. **Proposed Solution**: state the core idea in one or two sentences and explain
   the intuition. Reference the key figure if one exists.
6. **Contributions**: list 3-5 specific contributions, such as a formulation,
   architecture, benchmark validation, state-of-the-art result, analysis, or
   transfer application.
7. **Roadmap**: optional; one compact sentence per later section.

### Related Work Arc

Organize by theme, not by chronology. Use bold paragraph headings unless the
target venue requires numbered subsections.

```
2. Related Work
    Theme A
      Representative works + limitation + difference from this paper
    Theme B
      Representative works + limitation + difference from this paper
    Theme C (optional)
      Representative works + limitation + difference from this paper
```

Rules:

- Start each theme by defining the theme and citing representative work.
- Discuss families of approaches, not isolated summaries.
- End each theme with the explicit difference from the current approach.

### Method Arc

All four subsections are required for full papers.

**3.1 Core Formulation**

- Define the problem formally.
- Introduce notation and define every symbol near first use.
- State the key equation as a numbered equation.
- Explain the reformulation or theoretical insight.

**3.2 Key Mechanism**

- Explain the main building block with a figure reference when possible.
- Describe how the mechanism operates step by step.
- Discuss variants and design choices.
- Use inline math for simple expressions and numbered equations for central
  formulations.

**3.3 Architecture / Design**

- Present the full architecture with a figure or structured table.
- Describe design rules or principles.
- Compare with relevant baselines.
- Discuss complexity such as FLOPs, parameters, memory, or latency when relevant.

**3.4 Implementation Details**

- Data preprocessing and augmentation.
- Optimization hyperparameters.
- Hardware, training time, and software stack.
- Evaluation protocol and reproducibility details.

### Experiments Arc

All three subsections are required for full papers.

**4.1 Main Benchmark**

- Dataset description, including size, classes, and split.
- Evaluation metrics with definitions.
- Baseline methods and why they are relevant.
- Main results table.
- Interpretation of what the results mean and why they matter.

**4.2 Secondary Benchmark & Analysis**

- Additional dataset, task, or diagnostic setting.
- Ablations that remove or vary components systematically.
- Analysis figures such as training curves or distributions.
- Bold observation statements supported by data.

**4.3 Extension / Application**

- Transfer to a related task or domain.
- Comparison with task-specific state of the art.
- Evidence that the method generalizes beyond the main benchmark.

### Conclusion Arc

Use two or three short paragraphs.

1. **Summary**: restate the problem and solution in past tense and highlight the
   most important empirical result.
2. **Limitations**: acknowledge one or two genuine limitations. Required for many
   venues since 2022.
3. **Future Work**: optional, but should be concrete rather than generic.

## Paragraph-Level Patterns

### Claim-Evidence-Interpretation

Every experimental claim should follow:

1. **Claim**: what changed or was found.
2. **Evidence**: the table, figure, equation, or benchmark result.
3. **Interpretation**: what the evidence implies and what it does not prove.

### Forward Reference

Reference figures and tables before they appear:

- Correct: "Fig. 1 illustrates the residual block."
- Correct: "Table 2 reports the main benchmark results."
- Incorrect: "As shown in the figure above."

### Citation Density

| Location | Density | Purpose |
|---|---|---|
| Introduction P1 | 2-4 citations per paragraph | Establish domain |
| Introduction P2 | 2-3 citations per paragraph | Show trend |
| Method | 0-1 citations per paragraph | Present own work |
| Experiments baselines | 1 citation per baseline | Attribute prior work |
| Related Work | 1-2 citations per sentence where appropriate | Cover the field |

## Abstract Template

Write the Abstract as a single paragraph of 150–250 words following this 5-sentence spine:

1. **Domain + Motivation** (1–2 sentences): Establish the field, state why it matters, and cite the core capability that makes the problem tractable.
2. **Problem / Gap** (1 sentence): Name the specific obstacle that existing work has not solved. Quantify when possible ("accuracy plateau at X%", "Y% drop under cross-subject shift").
3. **Method at a Glance** (1–2 sentences): State the proposed approach in one or two sentences. Name the key mechanism (architecture, algorithm, or formulation) and what makes it different.
4. **Empirical Highlights** (1–2 sentences): Report the most important numbers — dataset name, metric, absolute value, and improvement delta vs. the strongest baseline. Example: "Our method achieves 82.5% on BCI IV-2a, outperforming EEGNet by 6.3 percentage points."
5. **Broad Implication** (1 sentence): Generalize the result: what does it establish for the field or for future work?

Keywords: provide 4–6 terms, ordered from broadest to most specific. Separate by comma.

## Equation Block Rules

- Number every display equation sequentially: `(1)`, `(2)`, …
- Define every new symbol at its first appearance, inline: "where **X** ∈ ℝ^{C×T} denotes a single-trial EEG segment with C channels and T time points."
- Do not reuse a symbol with two meanings in the same paper.
- Reference equations in prose as `Eqn. (N)`.
- For loss functions: write the full objective, then describe each term separately in the paragraph below.
- Use LaTeX-style notation in plaintext: `R^{C x T}`, `||·||_F`, `argmin_θ`.

## Figure and Table Rules

### Figure Captions

Figure captions appear **below** the figure. A complete caption has three parts:

1. **Label**: `Figure N.` or `Fig. N.` (consistent within the paper).
2. **One-sentence overview**: what the figure shows at the highest level.
3. **Panel-by-panel description** (when applicable): describe each subfigure using `(a)`, `(b)`, `Left:`, `Right:`, etc. Include the key observation for each panel. Example: "Left: Training loss convergence over 100 epochs. Right: Validation accuracy curves. Bold curves = validation; thin curves = training. ResNet-EEG-34 (blue) converges faster than the CNN baseline (red)."

### Table Captions

Table captions appear **above** the table.

### Result Table Format

Every comparison table must follow:

- **Bold** the best value in each row or column.
- *Italic* the second-best.
- Mark statistically significant improvements with `*` (p < 0.05) or `**` (p < 0.01) and explain the test in the caption footnote.
- Include a row for the proposed method labeled `Ours` or the model name.
- Include mean ± std when averaged over multiple runs or subjects.

## Architecture Description Template

When presenting a new architecture, include a configuration table with:

| Layer / Stage | Output Shape | Kernel / Stride | #Params |
|---|---|---|---|
| Input | C × T | — | — |
| Temporal Conv | F × T' × C | k × 1 | — |
| … | … | … | … |
| FC (Classifier) | K | — | — |

Follow with a complexity note: total parameter count, inference latency on the target hardware (ms/trial), and FLOPs when relevant.

## Ablation Study Format

Present ablation as a table where each row removes or replaces one component:

| Variant | Accuracy (%) | Δ vs. Full |
|---|---|---|
| Full model (Ours) | **82.5 ± 1.2** | — |
| w/o Component A | 78.3 ± 1.4 | −4.2 |
| w/o Component B | 76.1 ± 1.8 | −6.4 |
| … | … | … |

Rules:
- Always include the full model as the first row.
- Report mean ± std across subjects / seeds.
- Add one sentence per component stating *why* the drop occurred mechanistically.

## Numerical Placeholder Protocol

When source data for a specific number is not available, use this format instead of fabricating values:

```
[PLACEHOLDER: <description of what the number represents and where it would come from>]
```

Examples:
- `[PLACEHOLDER: classification accuracy on BCI IV-2a from the original EEGNet paper (Lawhern et al., 2018)]`
- `[PLACEHOLDER: ablation accuracy for the variant without spatial filtering — requires experiment]`

Never invent benchmark numbers, parameter counts, or training times. Always use the placeholder and note the missing data in a comment after the sentence.

## Computational Efficiency Section

Include the following in Sec. 3.4 (Implementation Details) or a dedicated Sec. 4.4:

- **Model size**: total parameters (M), comparison to 2–3 baselines.
- **Inference speed**: ms per trial on specified hardware (GPU model + VRAM).
- **Training time**: minutes per epoch or total training time on specified hardware.
- **Hardware spec**: GPU, CPU, RAM, framework version, CUDA version.
- **Code availability**: "Code and pretrained models will be released at [URL]." or "[PLACEHOLDER: repository URL]"

## English Writing Quality

### Hedging Vocabulary

| Strong claim (avoid in empirical claims) | Hedged version |
|---|---|
| "proves that" | "provides evidence that" / "suggests" |
| "shows that X causes Y" | "is associated with" / "correlates with" |
| "the best method" | "achieves state-of-the-art performance on [benchmark]" |
| "always works" | "consistently improves on all five evaluated benchmarks" |

### Claim–Evidence–Interpretation Pattern

Every experimental paragraph must follow:

1. **Claim** (topic sentence): "Removing the spatial filtering module significantly degrades performance."
2. **Evidence** (quantitative): "As shown in Table 3, accuracy drops from 82.5% to 78.3% (−4.2 percentage points)."
3. **Interpretation** (mechanism): "This confirms that learnable CSP-regularized filters are essential for extracting discriminative spatial patterns from multi-channel EEG."

### Transition Phrases Between Sections

- Intro → Related Work: "We now review prior work most relevant to these challenges."
- Related Work → Method: "To address the gaps identified above, we propose..."
- Method → Experiments: "We now empirically validate the proposed framework."
- Results → Ablation: "To understand the contribution of each component, we conduct systematic ablation studies."
- Experiments → Conclusion: "The preceding results support the following conclusions."

## Cross-Reference Conventions

| Element | Format | Example |
|---|---|---|
| Figures | `Fig. N` | `Fig. 1`, `Fig. 2 (left)`, `Figs. 3 and 4` |
| Tables | `Table N` | `Table 1`, `Tables 2 and 3` |
| Sections | `Sec. N` | `Sec. 3.1`, `Sec. 4` |
| Equations | `Eqn. (N)` | `Eqn. (1)`, `Eqns. (2) and (3)` |
| Appendix | `See Sec. A of the appendix` | `See Sec. B of the appendix` |

Forward-reference rule: **always** cite the figure or table in prose **before** it appears. Never write "as shown above" — always use the explicit label.

## Completeness Checklist

Sections:

- [ ] Title, authors, affiliations.
- [ ] Abstract as one paragraph following the 5-sentence template.
- [ ] Keywords (4–6 terms, broad to specific).
- [ ] 1. Introduction with 5-7 paragraphs (P4 = empirical evidence of gap).
- [ ] 2. Related Work organized thematically (not chronologically).
- [ ] 3. Method with 3.1 Core Formulation, 3.2 Key Mechanism, 3.3 Architecture, 3.4 Implementation Details.
- [ ] 4. Experiments with 4.1 Main Benchmark, 4.2 Secondary & Ablation, 4.3 Extension / Generalization.
- [ ] 5. Conclusion with Summary, Limitations (≥2), Future Work.
- [ ] References (complete bibliography, no [CITE:] placeholders remaining).
- [ ] Appendix when extra details, proofs, or results are needed.

Equations and symbols:

- [ ] Every equation is numbered sequentially.
- [ ] Every symbol is defined at first use.
- [ ] Loss/objective function is written in full, with terms explained below.

Visual elements:

- [ ] Every figure is referenced in prose before appearing.
- [ ] Figure captions below figures, with panel-by-panel description.
- [ ] Every table is referenced in prose before appearing.
- [ ] Table captions above tables.
- [ ] Best result in each column bold; second-best italic.
- [ ] Statistical significance markers present on result tables.

Architecture and ablation:

- [ ] Architecture configuration table present (or explanation of why not needed).
- [ ] Parameter count and inference speed reported.
- [ ] Ablation table covers every major component.
- [ ] Each ablation component accompanied by a mechanistic interpretation.

Numerical integrity:

- [ ] No fabricated benchmark numbers — use [PLACEHOLDER:...] for missing data.
- [ ] All reported numbers have units.
- [ ] Results reported as mean ± std when averaged over subjects/runs.

Page and density:

- [ ] Total page count matches the target when specified.
- [ ] No required section is unreasonably short or silently skipped.
- [ ] Figures and tables distributed across the paper, not crammed at the end.
