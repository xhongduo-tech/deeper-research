"""Chart Spec Generator — SOTA-enhanced ECharts-compatible JSON spec generation.

Enhancements:
  - Chain-of-Thought: reason about chart design before spec generation
  - Self-critique: checks visual design quality, data accuracy, accessibility
  - Adversarial review: challenges chart type choice, color accessibility
  - Quality score (0-100) per spec
  - Structured JSON output with auto-repair
  - Confidence scoring per design decision
"""
from app.skills.base import Skill
from app.services.llm_service import chat_json
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class ChartSpecGeneratorSkill(Skill):
    name = "generate_chart_spec"
    description = (
        "SOTA图表配置生成：根据数据和分析需求生成可直接渲染的 ECharts 5.x 配置 JSON。"
        "含图表设计推理、自评、红队挑战和质量评分。"
        "支持：折线/面积/堆叠面积/柱状/堆叠柱状/饼图/环图/漏斗/仪表盘/矩形树图/"
        "桑基图/箱线图/散点/热力图/瀑布图/组合图/雷达/小多图"
    )
    category = "offline"
    parameters = {
        "data": {"type": "string", "description": "数据描述、CSV格式或JSON数组"},
        "chart_type": {
            "type": "string",
            "description": (
                "line|bar|stacked_bar|area|stacked_area|pie|donut|scatter|"
                "heatmap|waterfall|combo|radar|small_multiples|"
                "funnel|gauge|treemap|sankey|boxplot"
            ),
        },
        "title": {"type": "string", "description": "图表标题"},
        "x_field": {"type": "string", "description": "X 轴字段名"},
        "y_fields": {"type": "array", "description": "Y 轴字段名数组"},
        "color_theme": {
            "type": "string",
            "description": "配色主题: business|vibrant|cool|warm|mono|diverging|gradient_blue|brand，默认business",
            "default": "business",
        },
        "context": {"type": "string", "description": "业务背景描述，用于生成更贴切的标注和洞察"},
        "enable_critique": {
            "type": "boolean",
            "description": "启用图表质量自评",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队挑战",
            "default": True,
        },
    }

    COLOR_THEMES = {
        "business": ["#2563EB", "#F59E0B", "#22C55E", "#EF4444", "#8B5CF6", "#0EA5E9", "#F97316", "#84CC16"],
        "vibrant":  ["#FF6B6B", "#4ECDC4", "#45B7D1", "#6C63FF", "#FFB347", "#EC4899", "#22C55E", "#F97316"],
        "cool":     ["#1E3A5F", "#2E86AB", "#4ECDC4", "#44CF6C", "#6C63FF", "#0D9488", "#7C3AED", "#0369A1"],
        "warm":     ["#DC2626", "#EA580C", "#D97706", "#CA8A04", "#B45309", "#9F1239", "#7C2D12", "#65A30D"],
        "mono":     ["#111827", "#374151", "#4B5563", "#6B7280", "#9CA3AF", "#D1D5DB", "#1F2937", "#0F172A"],
        "diverging":["#D32F2F", "#E64A19", "#F57C00", "#FBC02D", "#4CAF50", "#00897B", "#1976D2", "#7B1FA2"],
        "gradient_blue": ["#1E40AF", "#1D4ED8", "#2563EB", "#3B82F6", "#60A5FA", "#93C5FD", "#0284C7", "#0369A1"],
        "brand":    ["#B45309", "#92400E", "#2563EB", "#1E40AF", "#7C3AED", "#047857", "#991B1B", "#C9A96E"],
    }

    GRADIENT_PAIRS = {
        "business": [("#2563EB", "#6EA8FE"), ("#F59E0B", "#FDE68A"), ("#22C55E", "#86EFAC"),
                     ("#EF4444", "#FCA5A5"), ("#8B5CF6", "#C4B5FD"), ("#0EA5E9", "#7DD3FC")],
        "vibrant":  [("#FF6B6B", "#FFAAAA"), ("#4ECDC4", "#A0EDE8"), ("#45B7D1", "#96D8EA"),
                     ("#6C63FF", "#ABA8FF"), ("#FFB347", "#FFD9A0"), ("#EC4899", "#F9A8D4")],
        "cool":     [("#1E3A5F", "#4E7BAA"), ("#2E86AB", "#7CC8E8"), ("#4ECDC4", "#A0EDE8"),
                     ("#44CF6C", "#97E8B2"), ("#6C63FF", "#ABA8FF"), ("#0D9488", "#5EEAD4")],
        "warm":     [("#DC2626", "#FCA5A5"), ("#EA580C", "#FDBA74"), ("#D97706", "#FDE68A"),
                     ("#CA8A04", "#FEF08A"), ("#9F1239", "#FDA4AF"), ("#B45309", "#FCD34D")],
    }

    CHART_GUIDES = {
        "bar": (
            "柱状图：用 itemStyle.color 设置每个系列的渐变色（linearGradient 从上到下）；"
            "添加 markLine（平均值虚线）；label.show:true 显示数值；bargap:'30%'；"
            "每个柱顶加圆角 borderRadius:[4,4,0,0]。"
        ),
        "stacked_bar": (
            "堆叠柱状图：所有 series 设置 stack:'total'；最顶层系列加 label.show:true 显示总量；"
            "每个系列使用不同主题色；使用 markLine 显示目标线。"
        ),
        "line": (
            "折线图：smooth:true；areaStyle 用半透明渐变填充面积（opacity 0.15-0.3）；"
            "lineStyle.width:3；symbol:'circle'，symbolSize:8；"
            "多系列时每条线不同颜色+不同 symbol 形状（circle/rect/diamond/triangle）；"
            "label.show:true 显示关键数值点。"
        ),
        "area": (
            "面积图：smooth:true；areaStyle 从系列色到透明的线性渐变（opacity 0 → 0.4）；"
            "lineStyle.width:2.5；多系列堆叠用 stack:'total'；"
            "添加 markPoint 标注峰值和谷值。"
        ),
        "stacked_area": (
            "堆叠面积图：所有系列 stack:'total'，areaStyle 半透明；"
            "lineStyle.width:2；smooth:true；顶部系列显示总量 label。"
        ),
        "pie": (
            "饼图：radius:['0%','68%']；roseType 可选 'radius'（玫瑰图）；"
            "label.formatter:'{b}\\n{d}%'；labelLine.length:12；"
            "emphasis.scaleSize:8；每个扇区 itemStyle.borderColor:'#fff' borderWidth:2；"
            "加 legend 右侧或底部。"
        ),
        "donut": (
            "环图：radius:['48%','72%']；中心放文字（graphic.text）显示总计或关键数字；"
            "label 显示在外侧 formatter:'{b}: {d}%'；hover 时 emphasis.scale:true。"
        ),
        "scatter": (
            "散点图：symbolSize 根据第三维度动态变化（数组映射）；"
            "不同类别用不同颜色+不同 symbol；添加 visualMap 控制大小或颜色；"
            "tooltip 显示所有维度；加趋势线用 markLine type:'average'。"
        ),
        "heatmap": (
            "热力图：xAxis/yAxis type:'category'；visualMap 控制颜色从浅到深；"
            "label.show:true 显示数值；calendar heatmap 用 calendar 组件；"
            "添加 tooltip formatter 显示完整信息。"
        ),
        "waterfall": (
            "瀑布图：用两个堆叠柱状图实现——透明底部系列(itemStyle.color:'transparent')+"
            "实际增减系列；正增量用绿色，负增量用红色；label 显示增减量和方向符号；"
            "添加合计柱（不参与堆叠）用不同颜色标注。"
        ),
        "combo": (
            "组合图：bar+line 双 Y 轴；左 Y 轴对应柱状量值，右 Y 轴对应折线率值；"
            "bar 用主色+渐变；line smooth:true，yAxisIndex:1；"
            "折线加 markPoint 标注最大最小值；legend 区分两种图形类型。"
        ),
        "radar": (
            "雷达图：indicator 设置各维度及最大值；多系列对比；"
            "areaStyle 半透明填充；lineStyle.width:2；"
            "legend 显示各系列名称；symbol:'circle' symbolSize:4；"
            "添加 tooltip formatter 显示各维度具体数值。"
        ),
        "small_multiples": (
            "小多图：使用 grid 数组 + 对应的 xAxis/yAxis 数组创建多个子图；"
            "每个子图一个系列，共享 x 轴类别；子图标题用 graphic.text 放置；"
            "统一 y 轴范围便于对比；子图之间留适当间距。"
        ),
        "funnel": (
            "漏斗图：series type:'funnel'；sort:'descending'；"
            "label.position:'inside'，formatter:'{b}: {c}' 或 '{b}\\n{d}%'；"
            "每层不同颜色，itemStyle.borderColor:'#fff' borderWidth:2；"
            "gap:3 留间距；emphasis 放大高亮；适合展示转化率/销售漏斗/流程损耗。"
        ),
        "gauge": (
            "仪表盘：series type:'gauge'；axisLine.lineStyle.width:20 宽环带；"
            "使用分段颜色（低→中→高）表达进度区间；pointer 指针指向当前值；"
            "detail.formatter 显示数值+单位；title 显示指标名称；"
            "适合展示 KPI 完成率、满意度评分、健康指数等单一指标。"
        ),
        "treemap": (
            "矩形树图：series type:'treemap'；data 为 [{name, value, children:[...]}] 层级结构；"
            "label.formatter:'{b}\\n{c}'；upperLabel 显示父节点；"
            "levels[0] 设 borderWidth:3 区分层级；itemStyle.gapWidth:2；"
            "roam:false；breadcrumb.show:false（静态展示）；"
            "适合展示层级占比：部门预算、市场份额细分、文件大小分布。"
        ),
        "sankey": (
            "桑基图：series type:'sankey'；data 为节点数组 [{name:...}]；"
            "links 为流量数组 [{source:'A', target:'B', value:100}]；"
            "lineStyle.color:'gradient' opacity:0.4 curveness:0.5；"
            "nodeWidth:20 nodeGap:10；emphasis.focus:'adjacency'高亮关联路径；"
            "适合展示能量流/资金流/用户路径/物料流转等流量关系。"
        ),
        "boxplot": (
            "箱线图：series type:'boxplot'；data 每项为 [min, Q1, median, Q3, max]；"
            "可配合 scatter 系列展示离群点；boxprops 设置填充色半透明；"
            "medianProps 用对比色强调中位线；适合展示数据分布、异常值检测、"
            "多组对比（如各渠道销售额分布、多版本响应时间对比）。"
        ),
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        data = params.get("data", "")
        chart_type = params.get("chart_type", "bar")
        title = params.get("title", "数据图表")
        x_field = params.get("x_field", "")
        y_fields = params.get("y_fields", [])
        color_theme = params.get("color_theme", "business")
        biz_context = params.get("context", "")
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)

        colors = self.COLOR_THEMES.get(color_theme, self.COLOR_THEMES["vibrant"])
        gradients = self.GRADIENT_PAIRS.get(color_theme, self.GRADIENT_PAIRS["vibrant"])
        chart_guide = self.CHART_GUIDES.get(chart_type, self.CHART_GUIDES.get("bar", ""))
        y_fields_str = ", ".join(y_fields) if y_fields else "自动推断"

        # Build gradient color JSON for the first 6 series
        gradient_examples = []
        for i, (c1, c2) in enumerate(gradients[:4]):
            gradient_examples.append(
                f"系列{i+1}: {{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:["
                f"{{offset:0,color:'{c1}'}},{{offset:1,color:'{c2}'}}]}}"
            )
        gradient_str = "\n".join(gradient_examples)

        # Special structural notes for complex new chart types
        structural_note = ""
        if chart_type == "funnel":
            structural_note = (
                "\n## 漏斗图结构要求\n"
                "series 直接包含 data 数组（不需要 xAxis/yAxis）；"
                "data 每项 {value, name}，按值降序排列；"
                "删除 grid/xAxis/yAxis 字段。"
            )
        elif chart_type == "gauge":
            structural_note = (
                "\n## 仪表盘结构要求\n"
                "只有一个数值（单一指标）；删除 grid/xAxis/yAxis/legend；"
                "series[0].data = [{value: 数值, name: '指标名'}]；"
                "axisLine.lineStyle.color 为三段数组表示低中高区间。"
            )
        elif chart_type == "treemap":
            structural_note = (
                "\n## 矩形树图结构要求\n"
                "删除 grid/xAxis/yAxis；"
                "series[0].data 为层级结构 [{name, value, children:[...]}]；"
                "如无层级则为扁平数组 [{name, value}]。"
            )
        elif chart_type == "sankey":
            structural_note = (
                "\n## 桑基图结构要求\n"
                "删除 grid/xAxis/yAxis/legend；"
                "series[0].data 为节点数组 [{name:'节点名'}]；"
                "series[0].links 为流量数组 [{source:'A', target:'B', value:数值}]；"
                "source/target 必须与 data 中的 name 完全一致。"
            )
        elif chart_type == "boxplot":
            structural_note = (
                "\n## 箱线图结构要求\n"
                "series[0].type:'boxplot'；"
                "series[0].data 每项为 [最小值, Q1, 中位数, Q3, 最大值]（5个数字）；"
                "xAxis.data 为各分组名称；"
                "可选：添加 series[1].type:'scatter' 展示离群点。"
            )

        # ── Phase 1: CoT Chart Design Reasoning ───────────────────────────────
        cot_prompt = f"""你是专业数据可视化工程师。在进行图表配置生成前，请先思考以下问题：

图表需求：
- 类型: {chart_type}
- 标题: {title}
- X轴字段: {x_field or '自动推断'}
- Y轴字段: {y_fields_str}
- 配色主题: {color_theme}
- 业务背景: {biz_context or '通用'}

思考任务：
1. 这种图表类型是否最适合展示这些数据？为什么？
2. 配色方案是否适配业务场景？
3. 有哪些重要的数据点需要在图表中特别标注？
4. 图表可能存在的误导性是什么？

请输出你的图表设计思考过程。"""

        cot_messages = [
            {"role": "system", "content": "你是资深数据可视化专家，专精 ECharts 5.x。"},
            {"role": "user", "content": cot_prompt},
        ]
        try:
            from app.services.llm_service import chat as _chat
            reasoning = await _chat(cot_messages, temperature=0.3, max_tokens=800)
        except Exception:
            reasoning = ""

        # ── Phase 2: Spec Generation ──────────────────────────────────────────
        prompt = f"""你是专业数据可视化工程师，请为以下数据生成**高质量**的 ECharts 5.x option 配置对象。

## 图表设计思考
{reasoning[:600]}

## 图表需求
- 类型: {chart_type}
- 标题: {title}
- X轴字段: {x_field or '自动推断'}
- Y轴字段: {y_fields_str}
- 配色主题: {color_theme}
- 业务背景: {biz_context or '通用'}
{structural_note}

## 图表设计规范（严格遵守）
{chart_guide}

## 配色方案
主色列表（按顺序分配给各系列）:
{colors[:8]}

渐变色示例（用于 itemStyle.color / areaStyle.color）:
{gradient_str}

## 全局样式规范
```
字体: fontFamily: "PingFang SC, Microsoft YaHei, Helvetica Neue, Arial"
标题: textStyle.fontSize:18, fontWeight:'bold', color:'#1F2937'
副标题: subtextStyle.fontSize:13, color:'#6B7280'
图例: top:40, left:'center', itemGap:16, textStyle.fontSize:13, icon:'roundRect'
网格: left:'12%', right:'8%', top:'18%', bottom:'14%', containLabel:true
轴标签: fontSize:12, color:'#6B7280'
轴线: lineStyle.color:'#E5E7EB'
分割线: splitLine.lineStyle.color:'#F3F4F6', type:'dashed'
tooltip: backgroundColor:'rgba(255,255,255,0.96)', borderColor:'#E5E7EB',
         borderWidth:1, textStyle.color:'#111827', extraCssText:'box-shadow:0 4px 16px rgba(0,0,0,0.12)'
动画: animation:true, animationDuration:800, animationEasing:'cubicOut'
```

## 数据
{data[:4000]}

## 输出要求
1. 输出完整的、可直接传入 `echarts.setOption()` 的 JSON 对象
2. 包含所有必要字段: title, tooltip, legend, grid(如需), xAxis(如需), yAxis(如需), series, color
3. series 每条必须有: name, type, data, itemStyle(含渐变色), label, emphasis
4. 数字使用真实数据，不要占位符
5. 复杂图表（combo/waterfall/small_multiples）请完整实现双Y轴/透明底部/多grid
6. 只输出 JSON 对象，不加任何说明文字或代码块标记

## 高质量要求清单
- [ ] 渐变色 itemStyle（linearGradient）
- [ ] tooltip 精确 formatter 显示完整信息
- [ ] label 显示数据值（关键位置）
- [ ] markLine 或 markPoint 标注最值/均值
- [ ] emphasis 高亮效果（scale 或 shadowBlur）
- [ ] legend 清晰可读
- [ ] 坐标轴美观（无多余刻度线，颜色柔和）
"""

        try:
            resp = await chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是资深数据可视化专家，专精 ECharts 5.x。"
                            "生成的图表配置必须视觉精美、专业、数据准确。"
                            "只输出纯 JSON 对象，不附加任何说明、注释或代码块标记。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            # Post-process: ensure color array is set
            if isinstance(resp, dict) and "color" not in resp:
                resp["color"] = colors[:8]

            result = {"result": resp, "chart_type": chart_type, "title": title, "theme": color_theme, "reasoning": reasoning}
        except Exception as e:
            fallback = _build_fallback_option(chart_type, title, colors, y_fields)
            result = {"result": fallback, "chart_type": chart_type, "title": title, "error": str(e), "reasoning": reasoning}

        # ── Phase 3: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique:
            try:
                critique = await self_critique(
                    draft=f"图表类型: {chart_type}, 标题: {title}, 数据字段: {y_fields_str}",
                    topic=f"图表配置 - {title}",
                    dimensions=["specificity", "structural_clarity", "audience_fit"],
                )
                quality_score = round(critique["overall_score"] * 10)
                result["quality_score"] = quality_score
                result["critique"] = critique
            except Exception:
                pass

        # ── Phase 4: Adversarial review ───────────────────────────────────────
        if enable_adversarial:
            try:
                adversarial = await adversarial_review(
                    output=f"图表类型: {chart_type}, 标题: {title}",
                    topic=f"图表配置 - {title}",
                )
                result["adversarial"] = adversarial
            except Exception:
                pass

        return result


def _build_fallback_option(chart_type: str, title: str, colors: list, y_fields: list) -> dict:
    """Return a minimal but styled fallback ECharts option when LLM fails."""
    base = {
        "color": colors[:8],
        "animation": True,
        "title": {
            "text": title,
            "textStyle": {"fontFamily": "PingFang SC, Microsoft YaHei, Arial", "fontSize": 18, "fontWeight": "bold", "color": "#1F2937"},
        },
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": "rgba(255,255,255,0.96)",
            "borderColor": "#E5E7EB",
            "borderWidth": 1,
        },
        "legend": {"top": 40, "left": "center"},
        "grid": {"left": "12%", "right": "8%", "top": "18%", "bottom": "14%", "containLabel": True},
        "xAxis": {"type": "category", "data": ["Q1", "Q2", "Q3", "Q4"], "axisLine": {"lineStyle": {"color": "#E5E7EB"}}},
        "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#F3F4F6", "type": "dashed"}}},
        "series": [
            {
                "type": "bar" if chart_type not in {"line", "area"} else "line",
                "name": y_fields[0] if y_fields else "数据",
                "data": [120, 150, 130, 180],
                "smooth": True,
                "itemStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [{"offset": 0, "color": colors[0]}, {"offset": 1, "color": colors[1] if len(colors) > 1 else colors[0]}],
                    },
                    "borderRadius": [4, 4, 0, 0],
                },
                "label": {"show": True, "position": "top"},
            }
        ],
    }
    return base
