/**
 * TechIntroModal — beginner-friendly explanations of the platform's 6 AI capabilities.
 * Fixes: proper scroll region, smooth expand/collapse, modal entrance animation.
 */
import { useState, useEffect, useRef } from "react";
import { X, ChevronRight, ExternalLink, Sparkles, BookOpen, Cpu, ArrowRight } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Step {
  icon: string;
  label: string;
  desc: string;
}

interface Tech {
  id: string;
  icon: string;
  name: string;
  badge: string;
  badgeColor: string;
  tagline: string;
  analogy: string;
  analogyIcon: string;
  steps: Step[];
  implementation: string[];
  useCases: string[];
  relatedPage?: string;
  relatedLabel?: string;
}

// ── Definitions ───────────────────────────────────────────────────────────────

const TECHS: Tech[] = [
  {
    id: "knowledge_graph",
    icon: "🕸️",
    name: "知识图谱",
    badge: "Knowledge Graph",
    badgeColor: "#2563eb",
    tagline: "把零散知识变成一张有关联的地图",
    analogy: "想象你在整理人脉圈：每个人是一个节点，他们之间的关系（同事、朋友、家人）是连线。知识图谱就是这样——把文档里的概念、事件、实体，以及它们之间的关系，用一张图清晰地画出来，让隐藏在文字深处的结构浮出水面。",
    analogyIcon: "🗺️",
    steps: [
      { icon: "📄", label: "文本输入", desc: "用户上传或输入研究文本、报告、新闻等内容" },
      { icon: "🔍", label: "实体抽取", desc: "AI 识别文本中的关键「名词」——人物、机构、产品、政策、概念等" },
      { icon: "🔗", label: "关系识别", desc: "判断实体之间的关系类型：因果、隶属、竞争、合作、影响……" },
      { icon: "📊", label: "图谱构建", desc: "将实体和关系组织成节点-边的网络结构，按重要性排列" },
      { icon: "✨", label: "推理增强", desc: "沿图路径做语义推理，发现隐含关联和深层逻辑链" },
    ],
    implementation: [
      "使用大语言模型通过结构化提示词一次性抽取实体和关系，返回 JSON 格式",
      "实体存入 OntologyNode 表，关系存入 OntologyEdge 表（SQLite）",
      "前端 SVG 力导向图：纯 React + requestAnimationFrame 实现弹簧-排斥力模拟布局",
      "支持本体感知查询扩展：在 RAG 检索前，通过图谱邻居节点扩充搜索词，提升召回",
    ],
    useCases: ["竞争情报分析", "学术文献梳理", "风险传导路径追踪", "政策影响链分析"],
  },
  {
    id: "ontology",
    icon: "🏛️",
    name: "本体论建模",
    badge: "Ontology Modeling",
    badgeColor: "#7c3aed",
    tagline: "为每个行业建立标准的「概念词典」",
    analogy: "医生之所以能快速沟通，是因为医学有标准术语体系——【心肌梗塞】不会被说成【心脏坏掉了】。本体论就是给特定行业建立这样一套标准词典：概念分层（大类→小类）、关系规则（A包含B、C导致D）、行业特有的 KPI 分类体系。有了它，AI 理解文本时就不会词穷或误解。",
    analogyIcon: "📚",
    steps: [
      { icon: "🎯", label: "选择领域", desc: "指定目标行业：金融、医疗、科技、制造、零售……" },
      { icon: "🧠", label: "LLM 构建", desc: "大模型基于训练知识，输出该领域的核心概念树、关系网络和业务规则" },
      { icon: "📋", label: "KPI 分类", desc: "自动生成领域专属 KPI 分类体系（财务类、运营类、风控类……）" },
      { icon: "💾", label: "持久化", desc: "框架存入 DomainSchema 表，后续分析自动引用，无需重复构建" },
      { icon: "🔄", label: "查询增强", desc: "研究某个概念时，本体框架自动补充相关上下层概念，提升分析深度" },
    ],
    implementation: [
      "DomainSchema 表存储：core_concepts、relations、kpi_taxonomy、business_rules",
      "构建时使用 Heavy LLM 路由，温度设为 0.2 确保输出稳定性",
      "与 RAG 检索集成：query_expand_with_ontology() 在检索前扩充查询词",
      "支持增量更新：同一领域重新构建时自动覆盖旧框架",
    ],
    useCases: ["行业研究报告标准化", "跨部门术语统一", "新员工知识体系搭建", "合规审查术语匹配"],
  },
  {
    id: "sentiment",
    icon: "💬",
    name: "舆情情感分析",
    badge: "Sentiment Analysis",
    badgeColor: "#059669",
    tagline: "读懂文字背后的情绪、立场和风险",
    analogy: "同一件事，不同媒体的报道语气完全不同。你能分辨出哪篇是「看好」、哪篇是「担忧」、哪篇在「中立陈述」——但当你要处理几百篇文章时，就需要 AI 帮你。舆情分析不只是「正面/负面」，它还能告诉你：谁在被批评、批评的是哪个方面（产品质量？财务风险？管理问题？）……",
    analogyIcon: "🌡️",
    steps: [
      { icon: "📰", label: "文本输入", desc: "输入新闻、研报、社交评论、内部报告等任意文本" },
      { icon: "🎭", label: "整体定调", desc: "判断文本整体情感：正面/负面/中性/混合，给出极性分数（-1 到 +1）" },
      { icon: "🎯", label: "实体解析", desc: "识别文中每个关键实体的独立情感：A公司被正面评价，B产品被质疑" },
      { icon: "🔬", label: "方面细分", desc: "进一步细分到具体方面：财务/风险/产品/市场/管理/政策" },
      { icon: "⚠️", label: "信号提取", desc: "自动提炼风险信号（需警惕）和机会信号（值得关注）" },
    ],
    implementation: [
      "SentimentRecord 表记录每条文本的情感分数，支持实体级细粒度",
      "OpinionProfile 表聚合同一主题下多条记录，自动计算均值极性、情感分布",
      "Dashboard API 返回跨文档汇总：实体情感排行、分布饼图数据",
      "前端使用 Recharts：PieChart（分布）+ BarChart（实体极性）",
    ],
    useCases: ["媒体监测与舆情预警", "投资标的舆情评估", "品牌形象追踪", "政策反应分析"],
  },
  {
    id: "causal",
    icon: "⚡",
    name: "因果推理",
    badge: "Causal Analysis",
    badgeColor: "#d97706",
    tagline: "从「发生了什么」追溯到「为什么发生」",
    analogy: "医生诊断病因不只看症状，还要追问：是什么导致的？能不能追到根本原因？如果去掉某个环节，病情会如何变化？因果推理做的就是这件事——从现象出发，往前追 2-3 层原因，找到真正的驱动因素，还能做「假如当时…会怎样」的反事实推演。",
    analogyIcon: "🔬",
    steps: [
      { icon: "📄", label: "输入内容", desc: "提供研究文本、事件描述或分析背景" },
      { icon: "🔗", label: "因果链提取", desc: "AI 识别「A → B → C」形式的因果链条，支持1-3层深度" },
      { icon: "🎯", label: "根因分析", desc: "找到最底层的根本驱动因素，标注影响权重（高/中/低）" },
      { icon: "🔄", label: "反事实推演", desc: "「如果去掉X因素，结果会不同吗？」——模拟2-3个反事实场景" },
      { icon: "🕐", label: "时间维度", desc: "标注每条因果链的时滞：即时/短期/中期/长期" },
    ],
    implementation: [
      "CausalAnalysisSkill 是一个纯 LLM 推理技能，通过结构化 Markdown 提示词引导模型输出",
      "支持 depth 参数（1-3）控制因果链追溯深度，自动收敛提示词格式",
      "作为 Skills 体系的一员，可在研究 Agent 的 ReAct 循环中被自动调用",
      "输出为标准 Markdown 格式，可直接写入报告的「原因分析」章节",
    ],
    useCases: ["事故根因分析", "业绩波动归因", "政策效果评估", "市场变化溯源"],
  },
  {
    id: "domain_classify",
    icon: "🗂️",
    name: "领域智能分类",
    badge: "Domain Intelligence",
    badgeColor: "#0891b2",
    tagline: "让 AI 自动感知「这是什么行业」的问题",
    analogy: "同样一句话「ROE 下滑，负债率上升」，在金融分析师眼里意味着风险，在普通用户眼里可能只是陌生词汇。领域分类就是让 AI 先搞清楚「我在和谁说话、谈的是什么领域」，然后切换对应的专家视角来分析，避免用通用视角处理专业问题。",
    analogyIcon: "🧭",
    steps: [
      { icon: "🔎", label: "关键词扫描", desc: "快速扫描输入中的行业专有词汇：ROE/ROA（金融）、GMV（电商）、CT（医疗）……" },
      { icon: "🎯", label: "领域匹配", desc: "映射到预定义领域列表：金融/医疗/科技/制造/零售/房地产/通用" },
      { icon: "🏛️", label: "本体激活", desc: "激活对应领域的本体框架，调取该领域的概念体系和KPI标准" },
      { icon: "🧠", label: "专家模式", desc: "后续分析全程使用行业专家视角，回答更贴近业务实际" },
      { icon: "📊", label: "基准对标", desc: "自动引入行业基准数据：行业均值、优秀水平、落后水平" },
    ],
    implementation: [
      "KnowledgeEnricherAgent._detect_domain() 基于关键词映射快速分类（O(n) 复杂度）",
      "可通过 OntologyAgent.build_domain() 为新领域动态构建专属本体",
      "与 ModelRouter 集成：heavy_llm 路由用于领域框架构建，light_llm 用于快速分类",
      "领域信息透传到所有下游 Agent，影响提示词构建和结果解读",
    ],
    useCases: ["多行业混合研究", "自动化报告路由", "跨领域对比分析", "新领域快速上手"],
  },
  {
    id: "insight_fusion",
    icon: "🔮",
    name: "智能洞察融合",
    badge: "Insight Fusion",
    badgeColor: "#be185d",
    tagline: "把所有分析结果融合成「一句话判断」",
    analogy: "一个顶级分析师不只会做一项分析——他会综合财务数据、市场动态、竞争格局、政策环境，最终给出「这家公司值得投资」或「现在不是时机」这样的综合判断。洞察融合就是让 AI 扮演这位分析师：把知识图谱、情感分析、因果推理、基准对标的结果全部汇总，提炼出非显而易见的深层洞察。",
    analogyIcon: "💡",
    steps: [
      { icon: "📥", label: "多维输入", desc: "汇集知识图谱、舆情情感、因果推理、行业基准等多个维度结果" },
      { icon: "🔍", label: "矛盾检测", desc: "识别不同来源之间的信息矛盾：A说利好，B说利空——谁更可信？" },
      { icon: "⚖️", label: "置信度加权", desc: "按数据来源可靠性、分析置信度加权，避免片面信息主导结论" },
      { icon: "💎", label: "非显然洞察", desc: "筛选出「非显而易见」的发现：表面矛盾背后的规律、反直觉的结论" },
      { icon: "📝", label: "情景推演", desc: "给出基准/乐观/悲观三种情景，各配概率和关键假设" },
    ],
    implementation: [
      "KnowledgeEnricherAgent._synthesize_insights() 执行多信源综合推理",
      "InsightGeneratorSkill 可独立运行，接受任意文本输入并输出结构化洞察",
      "VerifierAgent 对关键结论进行交叉验证：多来源支撑 vs 孤证",
      "最终洞察写入报告的「深层洞察与情景推演」章节，配有置信度标注",
    ],
    useCases: ["投资决策支持", "战略规划分析", "风险综合评估", "竞争格局判断"],
  },

  // ── 三种新技术 ──────────────────────────────────────────────────────────────

  {
    id: "argument_mining",
    icon: "⚖️",
    name: "论证挖掘",
    badge: "Argument Mining",
    badgeColor: "#7c3aed",
    tagline: "评估报告和文章的逻辑骨架是否经得起推敲",
    analogy: "你看到一份研究报告说「AI将取代80%的工作」——但你不知道这结论是怎么来的：它有什么数据支撑？推理过程是否有跳跃？有没有被忽视的反驳证据？论证挖掘就像给文章做「逻辑体检」：拆解出「主张→证据→推理规则→结论」的完整链条，标出无支撑的断言和逻辑漏洞。",
    analogyIcon: "🔍",
    steps: [
      { icon: "📄", label: "文本输入", desc: "输入报告、研究、提案、新闻评论等任意文本" },
      { icon: "🎯", label: "主张识别", desc: "提取文中所有明确主张（事实型/评价型/因果型/预测型）" },
      { icon: "🔗", label: "证据链接", desc: "将每条主张与支撑它的数据、案例、类比一一对应" },
      { icon: "🧩", label: "推理规则还原", desc: "识别隐含的推理规则（Warrant）——证据为何能支持主张" },
      { icon: "⚠️", label: "漏洞检测", desc: "标记无支撑断言、逻辑谬误（稻草人/滑坡/循环论证等）和被忽视的反驳" },
    ],
    implementation: [
      "ArgumentMiningSkill 基于图尔明论证模型（Toulmin Model）设计提示词结构",
      "输出 JSON 包含 main_claims、evidence、warrant、fallacies、strength_score 字段",
      "谬误类型库：9种常见逻辑谬误，每种配有判断标准和示例",
      "强度评分 1-10 综合考虑证据质量、逻辑一致性和论点完整性",
    ],
    useCases: ["投资研报质量评估", "法律文书审查", "政策方案论证分析", "内容真实性核查"],
  },
  {
    id: "temporal_analysis",
    icon: "📅",
    name: "时序分析",
    badge: "Temporal Analysis",
    badgeColor: "#0891b2",
    tagline: "把文字里的「历史」和「未来」都画出来",
    analogy: "一份年报里散落着「三年前」「上季度」「预计明年」等时间引用——你很难在脑子里拼出一条清晰的时间线。时序分析就是自动做这件事：把所有时间信息提取出来，按顺序排成时间轴，识别「什么时候出现了拐点」「趋势是加速还是减速」，再往后推演「基于现在的轨迹，未来最可能发生什么」。",
    analogyIcon: "🗓️",
    steps: [
      { icon: "📝", label: "时间引用扫描", desc: "识别文中所有时间表达：绝对日期、相对时间、模糊表述" },
      { icon: "⏱️", label: "事件排序", desc: "将事件按时间顺序重建完整时间线，处理时序冲突" },
      { icon: "📈", label: "趋势检测", desc: "识别上升/下降/波动/周期性趋势，定位关键拐点" },
      { icon: "🔄", label: "周期识别", desc: "检测季度/年度/多年周期规律，判断当前所处阶段" },
      { icon: "🔮", label: "未来推演", desc: "基于识别到的趋势，生成有概率标注的未来情景" },
    ],
    implementation: [
      "TemporalAnalysisSkill 输出结构化 timeline（按时间排序的事件数组）",
      "趋势方向标签：ascending/descending/volatile/cyclical/stable",
      "拐点检测：每条趋势线附带 inflection_points 数组（时间+触发因素）",
      "未来推演：probability（high/medium/low）+ key_assumptions + risk_factors",
    ],
    useCases: ["战略规划时间线梳理", "竞争对手行为追踪", "政策演变分析", "市场周期判断"],
  },
  {
    id: "contradiction_detection",
    icon: "🔴",
    name: "矛盾检测",
    badge: "Contradiction Detection",
    badgeColor: "#dc2626",
    tagline: "找出文本里前后打架的地方，或多篇文章互相矛盾的地方",
    analogy: "一份报告里前面说「市场份额提升了5%」，后面的数据表格却显示下降了3%——这种矛盾很容易被人工阅读漏掉。矛盾检测就是做这个「找茬」的事：不只是数字层面，还包括因果方向矛盾（A说X导致Y，B说Y导致X）、归因矛盾（A说是管理层的决策，B说是外部环境导致的）等更隐蔽的冲突。",
    analogyIcon: "🆚",
    steps: [
      { icon: "📋", label: "主张提取", desc: "从文本中提取所有可验证的事实性陈述和判断" },
      { icon: "🔎", label: "矛盾搜索", desc: "在主张之间进行成对比较，检测六类矛盾：事实/时序/因果/数据/归因/价值" },
      { icon: "🏷️", label: "严重性分级", desc: "按矛盾对结论的影响程度分级：严重/重要/次要" },
      { icon: "🤔", label: "矛盾调和", desc: "尝试给出每处矛盾的可能解释（如定义差异/时间差/引用片面）" },
      { icon: "📊", label: "可信度评估", desc: "综合矛盾分布给出整体一致性评分（0-100）和可信度建议" },
    ],
    implementation: [
      "ContradictionDetectorSkill 支持单文档（内部一致性）和双文档（跨文档对比）两种模式",
      "六类矛盾分类器：factual/temporal/causal/normative/statistical/attribution",
      "一致性得分 0-100，critical 矛盾每处扣 20 分",
      "resolution_hypothesis 字段尝试提供非对抗性解释，避免误判补充性陈述为矛盾",
    ],
    useCases: ["研究报告内部审查", "尽职调查信息交叉核验", "新闻报道一致性检查", "会议纪要与决议比对"],
  },
];

// ── Step diagram ──────────────────────────────────────────────────────────────

function StepDiagram({ steps, color }: { steps: Step[]; color: string }) {
  return (
    <div className="relative pl-1">
      {/* vertical line */}
      <div className="absolute left-[19px] top-4 bottom-4 w-px"
        style={{ background: `${color}33` }} />
      <div className="flex flex-col gap-2.5">
        {steps.map((step, i) => (
          <div key={i} className="flex gap-3 items-start"
            style={{ animation: `step-in 0.3s ${0.05 * i}s both`, opacity: 0 }}>
            <style>{`@keyframes step-in{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}`}</style>
            <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 text-base relative z-10"
              style={{ background: "var(--bg-panel)", border: `1.5px solid ${color}30`, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              {step.icon}
            </div>
            <div className="flex-1 pt-1 pb-0.5">
              <div className="text-[12.5px] font-semibold leading-tight" style={{ color: "var(--ink-800)" }}>{step.label}</div>
              <div className="text-[11.5px] leading-[1.5] mt-0.5" style={{ color: "var(--ink-500)" }}>{step.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Animated expandable card ──────────────────────────────────────────────────

function TechCard({
  tech, expanded, onToggle, onNavigate,
}: {
  tech: Tech;
  expanded: boolean;
  onToggle: () => void;
  onNavigate: (page: string) => void;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);

  return (
    <div
      className="rounded-2xl border overflow-hidden transition-all duration-200"
      style={{
        background: "var(--bg-panel)",
        borderColor: expanded ? tech.badgeColor + "50" : "var(--border)",
        boxShadow: expanded ? `0 0 0 2px ${tech.badgeColor}12, 0 4px 16px rgba(0,0,0,0.06)` : "none",
      }}
    >
      {/* ── Header (always visible) ── */}
      <button
        className="w-full flex items-center gap-3 p-4 text-left group"
        onClick={onToggle}
      >
        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0 transition-transform duration-200 group-hover:scale-105"
          style={{ background: tech.badgeColor + "15" }}>
          {tech.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[14px] font-bold" style={{ color: "var(--ink-900)" }}>{tech.name}</span>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
              style={{ background: tech.badgeColor + "15", color: tech.badgeColor }}>
              {tech.badge}
            </span>
          </div>
          <p className="text-[12px] mt-0.5 truncate" style={{ color: "var(--ink-500)" }}>{tech.tagline}</p>
        </div>
        <div className="flex-shrink-0 transition-transform duration-200"
          style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)", color: "var(--ink-400)" }}>
          <ChevronRight size={16} />
        </div>
      </button>

      {/* ── Expandable body ── */}
      <div
        ref={bodyRef}
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{ maxHeight: expanded ? "800px" : "0px", opacity: expanded ? 1 : 0 }}
      >
        <div className="border-t px-4 pb-4 pt-3 flex flex-col gap-4" style={{ borderColor: tech.badgeColor + "20" }}>

          {/* Analogy */}
          <div className="rounded-xl p-3.5"
            style={{ background: tech.badgeColor + "08", border: `1px solid ${tech.badgeColor}20` }}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-base">{tech.analogyIcon}</span>
              <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: tech.badgeColor }}>
                通俗理解
              </span>
            </div>
            <p className="text-[12.5px] leading-6" style={{ color: "var(--ink-700)" }}>{tech.analogy}</p>
          </div>

          {/* Steps */}
          <div>
            <div className="flex items-center gap-1.5 mb-3">
              <Cpu size={12} style={{ color: "var(--ink-400)" }} />
              <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--ink-400)" }}>工作原理</span>
            </div>
            <StepDiagram steps={tech.steps} color={tech.badgeColor} />
          </div>

          {/* Implementation */}
          <div>
            <div className="flex items-center gap-1.5 mb-2.5">
              <BookOpen size={12} style={{ color: "var(--ink-400)" }} />
              <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--ink-400)" }}>我们的实现</span>
            </div>
            <div className="flex flex-col gap-1.5">
              {tech.implementation.map((item, i) => (
                <div key={i} className="flex gap-2 text-[12px]" style={{ color: "var(--ink-600)" }}>
                  <span className="mt-0.5 w-4 h-4 rounded text-[9px] flex items-center justify-center flex-shrink-0 font-bold"
                    style={{ background: tech.badgeColor + "18", color: tech.badgeColor }}>
                    {i + 1}
                  </span>
                  <span className="leading-[1.6]">{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Use cases + CTA */}
          <div className="flex items-start justify-between gap-3 flex-wrap pt-1">
            <div>
              <div className="text-[10.5px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--ink-400)" }}>适用场景</div>
              <div className="flex flex-wrap gap-1.5">
                {tech.useCases.map(uc => (
                  <span key={uc} className="text-[11px] px-2 py-0.5 rounded-full border"
                    style={{ borderColor: tech.badgeColor + "35", color: tech.badgeColor, background: tech.badgeColor + "08" }}>
                    {uc}
                  </span>
                ))}
              </div>
            </div>
            {tech.relatedPage && (
              <button
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-white flex-shrink-0 transition-opacity hover:opacity-85"
                style={{ background: tech.badgeColor }}
                onClick={() => onNavigate(tech.relatedPage!)}
              >
                {tech.relatedLabel}
                <ArrowRight size={13} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main modal ────────────────────────────────────────────────────────────────

export function TechIntroModal({
  open,
  onClose,
  initialTechId,
  onNavigate,
}: {
  open: boolean;
  onClose: () => void;
  initialTechId?: string;
  onNavigate?: (page: string) => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(initialTechId ?? TECHS[0].id);
  const [filter, setFilter] = useState<"all" | "knowledge" | "analysis" | "advanced">("all");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      if (initialTechId) setExpandedId(initialTechId);
    } else {
      const t = setTimeout(() => setMounted(false), 200);
      return () => clearTimeout(t);
    }
  }, [open, initialTechId]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!mounted) return null;

  const CATEGORIES = [
    { key: "all" as const, label: "全部能力" },
    { key: "knowledge" as const, label: "知识理解", ids: ["knowledge_graph", "ontology", "domain_classify"] },
    { key: "analysis" as const, label: "智能分析", ids: ["sentiment", "causal", "insight_fusion"] },
    { key: "advanced" as const, label: "高阶推理", ids: ["argument_mining", "temporal_analysis", "contradiction_detection"] },
  ];

  const filtered = filter === "all"
    ? TECHS
    : TECHS.filter(t => CATEGORIES.find(c => c.key === filter)?.ids?.includes(t.id));

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[200]"
        style={{
          background: "rgba(0,0,0,0.45)",
          backdropFilter: "blur(3px)",
          WebkitBackdropFilter: "blur(3px)",
          animation: open ? "backdrop-in 0.2s ease" : "backdrop-out 0.2s ease forwards",
        }}
        onClick={onClose}
      />

      {/* Modal panel */}
      <div
        className="fixed z-[201] flex flex-col rounded-2xl overflow-hidden"
        style={{
          top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          width: "calc(100vw - 32px)",
          maxWidth: "660px",
          height: "calc(100vh - 48px)",
          maxHeight: "620px",
          background: "var(--bg)",
          border: "1px solid var(--border)",
          boxShadow: "0 24px 64px rgba(0,0,0,0.22)",
          animation: open
            ? "modal-in 0.22s cubic-bezier(0.34,1.4,0.64,1)"
            : "modal-out 0.18s ease forwards",
        }}
      >
        <style>{`
          @keyframes backdrop-in  { from{opacity:0} to{opacity:1} }
          @keyframes backdrop-out { from{opacity:1} to{opacity:0} }
          @keyframes modal-in     { from{opacity:0;transform:translate(-50%,-50%) scale(0.93)} to{opacity:1;transform:translate(-50%,-50%) scale(1)} }
          @keyframes modal-out    { from{opacity:1;transform:translate(-50%,-50%) scale(1)} to{opacity:0;transform:translate(-50%,-50%) scale(0.95)} }
        `}</style>

        {/* ── Header ── */}
        <div className="flex-shrink-0 px-5 pt-5 pb-4 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: "linear-gradient(135deg,#2563eb,#7c3aed)" }}>
                  <Sparkles size={14} color="#fff" />
                </div>
                <h2 className="text-[17px] font-bold" style={{ color: "var(--ink-900)" }}>平台智能能力介绍</h2>
              </div>
              <p className="text-[12.5px] mt-1" style={{ color: "var(--ink-500)" }}>
                了解 DataAgent 如何运用 6 种 AI 技术，帮你从文本中提炼知识、洞察规律
              </p>
            </div>
            <button
              className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors hover:bg-[var(--hover)] flex-shrink-0"
              style={{ color: "var(--ink-400)" }}
              onClick={onClose}
            >
              <X size={16} />
            </button>
          </div>

          {/* Category filter */}
          <div className="flex gap-1.5 mt-3">
            {CATEGORIES.map(cat => (
              <button
                key={cat.key}
                className="px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all duration-150"
                style={{
                  background: filter === cat.key ? "var(--brand, #2563eb)" : "var(--bg-panel)",
                  color: filter === cat.key ? "#fff" : "var(--ink-600)",
                  border: `1px solid ${filter === cat.key ? "transparent" : "var(--border)"}`,
                }}
                onClick={() => setFilter(cat.key)}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Scrollable content ── */}
        <div
          className="flex-1 overflow-y-auto"
          style={{ overflowY: "auto", minHeight: 0 }}
        >
          <div className="px-5 py-3 flex flex-col gap-2.5 pb-4">
            {filtered.map(tech => (
              <TechCard
                key={tech.id}
                tech={tech}
                expanded={expandedId === tech.id}
                onToggle={() => setExpandedId(prev => prev === tech.id ? null : tech.id)}
                onNavigate={(page) => {
                  onClose();
                  onNavigate?.(page);
                }}
              />
            ))}
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="flex-shrink-0 px-5 py-3 border-t flex items-center justify-between"
          style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}>
          <p className="text-[11px]" style={{ color: "var(--ink-400)" }}>
            🔒 所有 AI 能力均在本地/内网运行，无外部数据传输
          </p>
          <button
            className="text-[12px] font-medium hover:underline transition-colors"
            style={{ color: "var(--brand, #2563eb)" }}
            onClick={onClose}
          >
            关闭介绍
          </button>
        </div>
      </div>
    </>
  );
}

// ── Trigger badge ─────────────────────────────────────────────────────────────

export function TechIntroBadge({
  techId,
  onOpen,
  className = "",
}: {
  techId?: string;
  onOpen: (techId?: string) => void;
  className?: string;
}) {
  const tech = techId ? TECHS.find(t => t.id === techId) : null;
  return (
    <button
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11.5px] font-medium transition-all hover:shadow-sm active:scale-95 ${className}`}
      style={{
        borderColor: tech ? tech.badgeColor + "35" : "var(--border)",
        background: tech ? tech.badgeColor + "06" : "var(--bg-panel)",
        color: tech ? tech.badgeColor : "var(--ink-500)",
      }}
      onClick={() => onOpen(techId)}
    >
      <Sparkles size={11} />
      {tech ? `了解${tech.name}` : "了解平台能力"}
    </button>
  );
}

export { TECHS };
export default TechIntroModal;
