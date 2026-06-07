"""
Causal Analysis Skill — multi-layer cause-effect extraction with confidence scoring.

Implements:
  - 1-3 layer causal chain extraction with root cause identification
  - Confidence scoring per causal link (corroborated / plausible / speculative)
  - Counterfactual reasoning (what-if scenarios)
  - Intervention point identification
  - Temporal lag estimation per link
  - Feedback loop detection (A→B→A cycles)
"""
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router


class CausalAnalysisSkill(Skill):
    name = "causal_analysis"
    category = "analysis"
    description = (
        "从文本中提取多层因果链、根本驱动因素和连锁效应，"
        "输出置信度评分、干预点识别、反事实推演和时间滞后估计"
    )
    parameters = {
        "text":    {"type": "string",  "description": "待分析文本"},
        "topic":   {"type": "string",  "description": "分析主题", "default": ""},
        "depth":   {"type": "integer", "description": "因果链深度（1-3）", "default": 2},
        "mode":    {
            "type": "string",
            "description": "分析模式: full | chains_only | root_cause | intervention",
            "default": "full",
        },
    }

    # Confidence level definitions injected into prompt
    _CONFIDENCE_GUIDE = """
置信度判断标准：
- **高** (Corroborated)：文本中有直接证据，因果关系被明确陈述或数据支持
- **中** (Plausible)：文本中有间接证据，因果关系符合逻辑但未直接证明
- **低** (Speculative)：基于领域常识推断，文本中无直接依据"""

    async def execute(self, text: str = "", topic: str = "",
                      depth: int = 2, mode: str = "full", **kwargs) -> dict:
        # Support both positional and params-dict calling conventions
        params = kwargs.get("params", {})
        if params:
            text  = params.get("text",  text)
            topic = params.get("topic", topic)
            depth = int(params.get("depth", depth))
            mode  = params.get("mode",  mode)

        depth = min(max(int(depth), 1), 3)
        depth_chain = " → ".join(["因素"] + ["效应"] * depth)

        layer_example = (
            "A导致B → B导致C" if depth == 1 else
            "A导致B → B导致C → C导致D" if depth == 2 else
            "A导致B → B导致C → C导致D → D导致E"
        )

        system_msg = f"""你是专业因果推理分析师，具备系统性思维和跨领域因果分析能力。{self._CONFIDENCE_GUIDE}

你的任务是从给定文本中进行严格的因果分析，遵循：
1. 区分相关性（correlation）和因果性（causation）
2. 识别混淆变量（confounders）
3. 区分直接原因和根本原因（proximate vs. root cause）
4. 标注每个因果关系的置信度"""

        sections = []

        if mode in ("full", "chains_only"):
            sections.append(f"""### 🔗 核心因果链（深度 {depth} 层）

格式：[触发因素] →[关系类型]→ [结果] →[关系类型]→ ... （每链置信度：高/中/低）
示例：{layer_example}
关系类型标签：导致/促进/抑制/加速/阻碍/触发/放大

列出 3-5 条最重要的因果链，按重要性排序。
每条链最后注明：时间滞后（即时/短期1-3月/中期3-12月/长期1年+）""")

        if mode in ("full", "root_cause"):
            sections.append("""### 🎯 根本驱动因素分析

对文本涉及的核心问题，识别最底层的根本原因（Root Causes）：
| 驱动因素 | 类型 | 影响权重 | 置信度 | 依据 |
|---------|------|---------|---------|------|
（类型：结构性/周期性/触发性/政策性/技术性；影响权重：高/中/低）""")

        if mode in ("full",):
            sections.append("""### 🔄 反馈环识别
检查是否存在正反馈环（A→B→A放大）或负反馈环（A→B→A抑制），列出发现的环路。
若无明显环路，说明"文本中未发现显著反馈环"。""")

        if mode in ("full", "intervention"):
            sections.append("""### ⚡ 干预点与应对策略

识别因果链中的关键干预节点（改变这个节点可以打断负面链条或加速正面链条）：
| 干预点 | 当前状态 | 建议干预方式 | 预期效果 | 可行性 |
|-------|---------|------------|---------|-------|""")

        if mode in ("full",):
            sections.append("""### 📊 反事实推演（What-If 场景）

选择最关键的 1-2 个驱动因素，进行反事实推演：
- **场景A（去除因素X）**：若X不存在/被控制，情况会如何演变？
- **场景B（强化因素Y）**：若Y被放大2倍，产生什么连锁反应？""")

        user_content = f"""分析主题：{topic or '（文本自动识别）'}
因果链深度：{depth}层

---
**待分析文本：**
{text[:3000]}
---

请提供完整的因果分析报告：

{''.join(sections)}

### 📝 分析摘要
用 3-4 句话总结核心因果逻辑和最重要的发现，供决策者快速阅读。"""

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_content},
        ]

        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
        analysis = await chat(
            messages, model=model, base_url=base_url, api_key=api_key,
            temperature=0.2, max_tokens=2000
        )

        return {
            "result":  analysis,
            "topic":   topic,
            "depth":   depth,
            "mode":    mode,
        }
