/**
 * HtmlPage — HTML report generation, styled to match the Docs page layout.
 * Centered single-column hero → input card → template gallery.
 */
import { useState, useRef, useMemo, useEffect } from "react";
import { Code2, Download, Eye, Wand2, Copy, Check, Palette, Layers, Plus, X, Images, GitBranch, Columns3, Milestone, UsersRound, AlertTriangle, Network, Workflow, Upload, FileCode2, Brain, BarChart3, ChevronDown, Paperclip, ArrowUp, FolderOpen, Search } from "lucide-react";
import { api, Project } from "../lib/api";

// ── Thumbnail previews ────────────────────────────────────────────────────────

const ThumbGantt = () => (
  <div className="w-full h-full p-2.5 relative overflow-hidden" style={{ background: "#f8fafc" }}>
    <div className="absolute left-10 right-3 top-4 h-px" style={{ background: "#cbd5e1" }} />
    {[0, 1, 2, 3].map((i) => (
      <div key={i} className="absolute top-3 bottom-3 w-px" style={{ left: `${34 + i * 15}%`, background: "#e2e8f0" }} />
    ))}
    <div className="absolute left-2 top-7 bottom-2 flex flex-col justify-between">
      {["WBS", "设计", "开发", "验收"].map((item) => (
        <span key={item} className="text-[5px] font-semibold" style={{ color: "#64748b" }}>{item}</span>
      ))}
    </div>
    {[
      { y: 29, l: 30, w: 31, c: "#2563eb", label: "A" },
      { y: 47, l: 43, w: 26, c: "#10b981", label: "B" },
      { y: 65, l: 58, w: 25, c: "#f59e0b", label: "C" },
      { y: 82, l: 74, w: 15, c: "#ef4444", label: "M" },
    ].map((bar) => (
      <div key={bar.label} className="absolute h-3 rounded-full shadow-sm" style={{ top: `${bar.y}%`, left: `${bar.l}%`, width: `${bar.w}%`, background: bar.c }}>
        <span className="absolute left-1 top-1/2 -translate-y-1/2 text-[5px] font-bold text-white">{bar.label}</span>
      </div>
    ))}
    {[
      { l: 60, t: 33, w: 15, r: 28 },
      { l: 68, t: 51, w: 14, r: 28 },
    ].map((line, i) => (
      <div key={i} className="absolute h-0.5 origin-left" style={{ left: `${line.l}%`, top: `${line.t}%`, width: `${line.w}%`, transform: `rotate(${line.r}deg)`, background: "#475569" }} />
    ))}
    <div className="absolute right-2 top-3 rounded-md px-1.5 py-0.5 text-[5px] font-bold" style={{ background: "#dbeafe", color: "#2563eb" }}>关键路径</div>
    <div className="absolute right-7 bottom-2 w-2.5 h-2.5 rotate-45" style={{ background: "#ef4444" }} />
  </div>
);

const ThumbKanban = () => (
  <div className="w-full h-full p-2 grid grid-cols-[1fr_1fr_1fr_32px] gap-1.5" style={{ background: "#f8fafc" }}>
    {[
      { title: "To Do", c: "#64748b", cards: ["#e2e8f0", "#f1f5f9", "#e2e8f0"] },
      { title: "Doing", c: "#2563eb", cards: ["#dbeafe", "#bfdbfe", "#fee2e2"] },
      { title: "Done", c: "#10b981", cards: ["#dcfce7", "#bbf7d0"] },
    ].map((col, i) => (
      <div key={col.title} className="rounded-md border p-1 min-w-0" style={{ background: "#fff", borderColor: "#e2e8f0" }}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[4.8px] font-bold" style={{ color: col.c }}>{col.title}</span>
          <span className="text-[4.5px] rounded px-0.5" style={{ background: `${col.c}16`, color: col.c }}>WIP {i + 2}</span>
        </div>
        {col.cards.map((card, n) => (
          <div key={n} className="h-3 rounded mb-1 border-l-2 relative" style={{ background: card, borderLeftColor: n === 2 && i === 1 ? "#ef4444" : col.c }}>
            <div className="absolute left-1 top-1 h-0.5 rounded w-2/3 bg-white/80" />
            <div className="absolute left-1 bottom-1 h-0.5 rounded w-1/2 bg-white/70" />
          </div>
        ))}
      </div>
    ))}
    <div className="rounded-md border p-1 relative" style={{ background: "#0f172a", borderColor: "#334155" }}>
      <div className="text-[4.8px] font-bold mb-1" style={{ color: "#38bdf8" }}>燃尽</div>
      {[74, 62, 50, 36, 26].map((y, i, arr) => (
        <div key={i} className="absolute w-1.5 h-1.5 rounded-full" style={{ left: `${20 + i * 15}%`, top: `${y}%`, background: "#38bdf8" }}>
          {i < arr.length - 1 && (
            <div className="absolute h-0.5 origin-left" style={{ left: 5, top: 3, width: 10, transform: `rotate(${arr[i + 1] < y ? -28 : 18}deg)`, background: "#38bdf8" }} />
          )}
        </div>
      ))}
    </div>
  </div>
);

const ThumbTimeline = () => (
  <div className="w-full h-full p-3 relative overflow-hidden" style={{ background: "#fff" }}>
    <div className="relative h-full">
      <div className="absolute left-3 right-3 top-1/2 h-0.5" style={{ background: "#cbd5e1" }} />
      {[12, 36, 62, 86].map((x, i) => (
        <div key={x} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%`, top: "50%" }}>
          <div className="w-3 h-3 rounded-full border-2 shadow-sm" style={{ background: "#fff", borderColor: ["#2563eb", "#10b981", "#f59e0b", "#7c3aed"][i] }} />
          <div className="w-11 h-5 rounded-md mt-2 -ml-4 border p-0.5" style={{ background: "#f8fafc", borderColor: "#e2e8f0" }}>
            <div className="h-1 rounded mb-0.5" style={{ background: ["#dbeafe", "#dcfce7", "#fef3c7", "#ede9fe"][i] }} />
            <div className="h-1 rounded w-2/3" style={{ background: "#e2e8f0" }} />
          </div>
          {i === 2 && <div className="absolute -top-4 -left-1 w-2 h-2 rotate-45" style={{ background: "#f59e0b" }} />}
        </div>
      ))}
    </div>
  </div>
);

const ThumbRisk = () => (
  <div className="w-full h-full p-3 grid grid-cols-[14px_1fr] grid-rows-[1fr_10px] gap-1.5" style={{ background: "#fff" }}>
    <div className="row-span-1 flex items-center justify-center text-[5px] font-bold -rotate-90 whitespace-nowrap" style={{ color: "#64748b" }}>影响</div>
    <div className="grid grid-cols-3 grid-rows-3 gap-1">
      {["#dcfce7", "#fef3c7", "#fee2e2", "#dcfce7", "#fef3c7", "#fb923c", "#fef3c7", "#fb923c", "#dc2626"].map((c, i) => (
        <div key={i} className="rounded-sm border relative" style={{ background: c, borderColor: "#fff" }}>
          {[2, 5, 7, 8].includes(i) && <span className="absolute inset-0 flex items-center justify-center text-[5px] font-black text-white">R{i}</span>}
        </div>
      ))}
    </div>
    <div />
    <div className="flex items-center justify-center text-[5px] font-bold" style={{ color: "#64748b" }}>概率</div>
  </div>
);

const ThumbMind = () => (
  <div className="w-full h-full p-3 relative" style={{ background: "#f8fafc" }}>
    <div className="absolute left-1/2 top-1/2 h-6 rounded-full -translate-x-1/2 -translate-y-1/2 text-[6px] flex items-center justify-center font-bold shadow-sm" style={{ width: 52, background: "#2563eb", color: "#fff" }}>中心主题</div>
    {[[20, 22, "#10b981", "数据"], [80, 22, "#f59e0b", "流程"], [18, 76, "#7c3aed", "应用"], [82, 76, "#ef4444", "风险"], [50, 14, "#0891b2", "治理"]].map(([x, y, c, label], i) => (
      <div key={i}>
        <div className="absolute h-0.5 origin-left" style={{ left: "50%", top: "50%", width: "27%", transform: `rotate(${Number(y) < 50 ? (Number(x) < 50 ? -144 : -36) : (Number(x) < 50 ? 144 : 36)}deg)`, background: String(c), opacity: 0.58 }} />
        <div className="absolute w-10 h-4 rounded-full text-[5px] flex items-center justify-center border font-semibold" style={{ left: `${x}%`, top: `${y}%`, transform: "translate(-50%,-50%)", background: String(c) + "16", borderColor: String(c) + "55", color: String(c) }}>{label}</div>
        <div className="absolute w-3 h-1 rounded" style={{ left: `${Number(x) + (Number(x) < 50 ? -8 : 5)}%`, top: `${Number(y) + 8}%`, background: String(c) + "55" }} />
        <div className="absolute w-4 h-1 rounded" style={{ left: `${Number(x) + (Number(x) < 50 ? -8 : 4)}%`, top: `${Number(y) + 13}%`, background: String(c) + "33" }} />
      </div>
    ))}
  </div>
);

const ThumbFishbone = () => (
  <div className="w-full h-full p-3 relative overflow-hidden" style={{ background: "#f8fafc" }}>
    <div className="absolute left-3 right-12 top-1/2 h-0.5" style={{ background: "#0891b2" }} />
    <div
      className="absolute top-1/2 -translate-y-1/2"
      style={{
        right: 36,
        width: 0,
        height: 0,
        borderTop: "5px solid transparent",
        borderBottom: "5px solid transparent",
        borderLeft: "9px solid #0891b2",
      }}
    />
    <div
      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg px-1.5 py-1 text-[6px] font-bold leading-tight"
      style={{ background: "#0891b2", color: "#fff", boxShadow: "0 2px 8px rgba(8,145,178,.22)" }}
    >
      延期
    </div>
    {[
      { x: 28, y: 28, rot: -34, label: "人员", color: "#2563eb" },
      { x: 52, y: 28, rot: -34, label: "流程", color: "#10b981" },
      { x: 76, y: 28, rot: -34, label: "依赖", color: "#f59e0b" },
      { x: 28, y: 72, rot: 34, label: "技术", color: "#7c3aed" },
      { x: 52, y: 72, rot: 34, label: "数据", color: "#dc2626" },
      { x: 76, y: 72, rot: 34, label: "外部", color: "#0f766e" },
    ].map((bone) => (
      <div key={`${bone.label}-${bone.y}`}>
        <div
          className="absolute h-0.5 origin-right rounded-full"
          style={{
            left: `${bone.x - 15}%`,
            top: `${bone.y}%`,
            width: "28%",
            transform: `rotate(${bone.rot}deg)`,
            background: bone.color,
            opacity: 0.78,
          }}
        />
        <div
          className="absolute rounded-md border px-1.5 py-0.5 text-[5.5px] font-semibold"
          style={{
            left: `${bone.x - 12}%`,
            top: `${bone.y + (bone.y < 50 ? -16 : 6)}%`,
            background: `${bone.color}14`,
            borderColor: `${bone.color}40`,
            color: bone.color,
          }}
        >
          {bone.label}
        </div>
      </div>
    ))}
    <div className="absolute left-4 bottom-2 right-4 grid grid-cols-3 gap-1">
      {["证据", "5Why", "整改"].map((item, idx) => (
        <div key={item} className="h-2 rounded" style={{ background: ["#cffafe", "#e0f2fe", "#dbeafe"][idx] }} />
      ))}
    </div>
  </div>
);

const ThumbDashboard = () => (
  <div className="w-full h-full p-2.5 flex flex-col gap-1.5" style={{ background: "#0f172a" }}>
    <div className="grid grid-cols-3 gap-1.5">
      {["68%", "12", "4.2"].map((v, i) => <div key={v} className="rounded-md p-1 border" style={{ background: "#1e293b", borderColor: "#334155", color: ["#38bdf8", "#34d399", "#fbbf24"][i], fontSize: 6, fontWeight: 700 }}>{v}</div>)}
    </div>
    <div className="grid grid-cols-[1fr_1fr] gap-1.5 flex-1">
      <div className="rounded-md border relative overflow-hidden" style={{ background: "#1e293b", borderColor: "#334155" }}>
        {[68, 52, 60, 35, 44].map((h, i, arr) => (
          <div key={i} className="absolute w-1.5 rounded-t" style={{ left: `${18 + i * 15}%`, bottom: 7, height: `${h}%`, background: ["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#38bdf8"][i] }}>
            {i < arr.length - 1 && <div className="absolute h-0.5 origin-left" style={{ left: 5, top: `${Math.max(2, 100 - h)}%`, width: 10, transform: "rotate(-18deg)", background: "#e0f2fe" }} />}
          </div>
        ))}
      </div>
      <div className="rounded-md border p-1 grid grid-cols-3 grid-rows-3 gap-0.5" style={{ background: "#1e293b", borderColor: "#334155" }}>
        {["#164e63", "#0e7490", "#38bdf8", "#14532d", "#16a34a", "#86efac", "#713f12", "#f59e0b", "#fde68a"].map((c, i) => <div key={i} className="rounded-sm" style={{ background: c }} />)}
      </div>
    </div>
  </div>
);

const ThumbResourceGantt = () => (
  <div className="w-full h-full p-2.5 grid grid-cols-[30px_1fr] gap-2 relative" style={{ background: "#f8fafc" }}>
    <div className="flex flex-col justify-between py-1">
      {["前端", "后端", "算法", "测试"].map((role, i) => (
        <div key={role} className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ background: ["#0f766e", "#2563eb", "#f59e0b", "#dc2626"][i] }} />
          <span className="text-[5px] font-semibold" style={{ color: "#64748b" }}>{role}</span>
        </div>
      ))}
    </div>
    <div className="relative">
      {[0, 1, 2, 3].map((i) => <div key={i} className="absolute top-0 bottom-0 w-px" style={{ left: `${i * 25}%`, background: "#e2e8f0" }} />)}
      {[
        { top: 8, left: 5, width: 42, c: "#0f766e", load: "80%" },
        { top: 31, left: 23, width: 50, c: "#2563eb", load: "95%" },
        { top: 54, left: 48, width: 34, c: "#f59e0b", load: "70%" },
        { top: 77, left: 60, width: 32, c: "#dc2626", load: "冲突" },
      ].map((item) => (
        <div key={item.top} className="absolute h-3 rounded-full text-[4.5px] font-bold text-white flex items-center justify-center shadow-sm" style={{ top: `${item.top}%`, left: `${item.left}%`, width: `${item.width}%`, background: item.c }}>{item.load}</div>
      ))}
      <div className="absolute right-1 top-6 bottom-2 w-3 grid grid-rows-4 gap-0.5">
        {["#dcfce7", "#fef3c7", "#fed7aa", "#fecaca"].map((c) => <span key={c} className="rounded-sm" style={{ background: c }} />)}
      </div>
    </div>
  </div>
);

type HtmlTemplate = {
  id: string; name: string; desc: string; style: string;
  icon: React.ElementType; accentColor: string; bg: string;
  preview: React.ReactNode; placeholder: string; suggestedTags: string[];
  focus: string;
  layout: string;
  visual: string;
  contentRule: string;
  logic: string;
  category: string;
};

const AUTO_DIRECTION = "自动定义";
const AUTO_TEMPLATE_ID = "auto";
const CATEGORIES = [AUTO_DIRECTION, "进度管理", "敏捷协作", "风险管控", "分析拆解", "数据看板"];
const DIRECTION_SKILLS: Record<string, string[]> = {
  [AUTO_DIRECTION]: ["web-project-view-auto"],
  "进度管理": ["web-progress-management"],
  "敏捷协作": ["web-agile-collaboration"],
  "风险管控": ["web-risk-control"],
  "分析拆解": ["web-analysis-breakdown"],
  "数据看板": ["web-data-dashboard"],
};
const DIRECTION_DESCRIPTIONS: Record<string, string> = {
  [AUTO_DIRECTION]: "根据用户描述自动判断网页处理方向",
  "进度管理": "突出计划、依赖、里程碑、延期和责任动作",
  "敏捷协作": "突出需求流动、迭代燃尽、阻塞和复盘动作",
  "风险管控": "突出风险分级、触发条件、预案和升级路径",
  "分析拆解": "突出主题拆解、根因分析、逻辑关系和整改闭环",
  "数据看板": "突出 KPI、趋势异常、指标口径和行动建议",
};
const CATEGORY_MAP: Record<string, string> = {
  "gantt-pert": "进度管理",
  "resource-gantt": "进度管理",
  "timeline-roadmap": "进度管理",
  "kanban-burndown": "敏捷协作",
  "risk-matrix": "风险管控",
  "mind-map": "分析拆解",
  "fishbone": "分析拆解",
  "data-dashboard": "数据看板",
};

const TEMPLATES: HtmlTemplate[] = [
  { id: "gantt-pert", name: "甘特 / PERT 进度图", desc: "任务多、依赖复杂、要严控关键路径和时间节点", style: "pm-gantt", icon: GitBranch, accentColor: "#2563eb", bg: "#f8fafc", preview: <ThumbGantt />, placeholder: "描述项目任务、起止时间、依赖关系和关键节点，例如：「生成数据治理项目进度页，展示需求、开发、联调、验收依赖」", suggestedTags: [], focus: "把任务、依赖、里程碑和延期风险放在同一张进度视图里", layout: "顶部状态摘要、左侧任务树、右侧时间轴、底部关键路径与阻塞清单", visual: "横向时间条、依赖连线、里程碑菱形、风险色标", contentRule: "每项任务必须给出负责人、周期、依赖、状态、风险和下一动作", logic: "project-template:gantt-pert. Generate a rigorous project-control HTML. Required sections: executive status strip, WBS task tree, Gantt timeline, PERT/dependency list, critical path, milestone gate, delay/risk alerts, owner-action table. Do not produce a generic webpage. Layout must visually prioritize time, dependencies, owners, and control points.", category: "进度管理" },
  { id: "kanban-burndown", name: "看板 / 燃尽图", desc: "敏捷迭代、需求频繁变更、要跟踪吞吐与剩余工作量", style: "pm-kanban", icon: Columns3, accentColor: "#10b981", bg: "#f8fafc", preview: <ThumbKanban />, placeholder: "描述迭代周期、需求池、开发状态和燃尽目标，例如：「生成两周冲刺看板，展示待办、进行中、验收、阻塞和燃尽趋势」", suggestedTags: ["Sprint", "需求变更", "阻塞项"], focus: "让团队一眼看到需求流动、阻塞和交付预测", layout: "迭代目标、三到五列看板、燃尽趋势、变更记录、复盘动作", visual: "列式卡片、WIP 限制、燃尽折线、阻塞红标", contentRule: "每张卡片包含优先级、负责人、工期、验收口径和阻塞原因", logic: "project-template:kanban-burndown. Required sections: sprint goal, Kanban board with WIP constraints, burndown chart data, change log, blocker lane, velocity/throughput metrics, review checklist. The content must be organized around agile iteration control rather than marketing or article structure.", category: "敏捷协作" },
  { id: "timeline-roadmap", name: "时间线 / 里程碑 / 路线图", desc: "向领导或客户汇报整体进展、阶段成果和未来路线", style: "pm-timeline", icon: Milestone, accentColor: "#7c3aed", bg: "#ffffff", preview: <ThumbTimeline />, placeholder: "描述阶段、时间、成果和汇报对象，例如：「生成年度AI平台建设路线图，按季度展示里程碑、交付物和决策事项」", suggestedTags: ["领导汇报", "路线图", "阶段成果"], focus: "用清晰时间叙事交代已经完成、正在推进、下一步决策", layout: "一页总览、横向时间线、里程碑卡、成果证据、下一阶段路线", visual: "时间轴节点、阶段色块、成果徽章、决策标记", contentRule: "每个阶段都要包含目标、交付物、完成度、证据和需要领导决策的事项", logic: "project-template:timeline-roadmap. Required sections: progress narrative, milestone timeline, phase deliverables, proof/evidence cards, upcoming decisions, roadmap risks. Tone must fit executive/client reporting: concise, result-oriented, date-specific.", category: "进度管理" },
  { id: "resource-gantt", name: "资源甘特图", desc: "管理人力/设备/预算负载，避免资源冲突和过度分配", style: "pm-resource", icon: UsersRound, accentColor: "#0f766e", bg: "#f8fafc", preview: <ThumbResourceGantt />, placeholder: "描述团队、资源、任务排期和负载，例如：「生成项目资源排期页，展示前端、后端、算法、测试的负载与冲突」", suggestedTags: ["资源负载", "冲突预警", "人员排期"], focus: "把任务进度和资源负载合在一起，找出过载与空档", layout: "资源总览、人员/设备排期、负载热力、冲突清单、调度建议", visual: "资源行甘特条、负载热力格、过载警戒线、调配箭头", contentRule: "每个资源必须标注占用率、冲突时间、替代方案和调度建议", logic: "project-template:resource-gantt. Required sections: resource capacity summary, allocation timeline, utilization heatmap, over-allocation warnings, rebalancing suggestions, owner/task mapping. Prioritize capacity management and schedule feasibility.", category: "进度管理" },
  { id: "risk-matrix", name: "风险矩阵", desc: "识别项目风险，评估影响/概率，明确预案和责任人", style: "pm-risk", icon: AlertTriangle, accentColor: "#dc2626", bg: "#ffffff", preview: <ThumbRisk />, placeholder: "描述项目风险和约束，例如：「生成核心系统上线风险矩阵，包含数据质量、接口稳定、人员缺口、安全合规」", suggestedTags: ["影响概率", "应对预案", "升级机制"], focus: "把风险从描述变成分级、责任、预案和触发条件", layout: "风险摘要、影响概率矩阵、TOP 风险、缓解措施、升级路径", visual: "3x3 或 5x5 热力矩阵、风险编号、红黄绿分级、责任表", contentRule: "每个风险必须包含触发信号、概率、影响、责任人、缓解措施和截止时间", logic: "project-template:risk-matrix. Required sections: risk register, impact-probability matrix, high-risk cards, mitigation plan, contingency plan, escalation path. Every risk must be actionable and owned.", category: "风险管控" },
  { id: "mind-map", name: "思维导图", desc: "拆解复杂主题、方案架构、汇报提纲和知识结构", style: "pm-mindmap", icon: Brain, accentColor: "#f59e0b", bg: "#fffaf0", preview: <ThumbMind />, placeholder: "描述中心主题和分支，例如：「生成企业数据资产盘点思维导图，包含数据源、治理流程、应用场景、风险合规」", suggestedTags: ["结构拆解", "汇报提纲", "方案架构"], focus: "用中心主题和层级分支表达复杂逻辑，不堆长段文字", layout: "中心主题、一级分支、二级要点、逻辑说明、可执行清单", visual: "放射式节点、分支色彩、关系线、层级标签", contentRule: "每个分支要有明确层级、归属关系和汇报时的一句话口径", logic: "project-template:mind-map. Required sections: central thesis, branch map, hierarchy table, relationship explanation, presentation talking points. Avoid linear article format; preserve tree structure and logic depth.", category: "分析拆解" },
  { id: "fishbone", name: "鱼骨图 / 根因分析", desc: "定位问题根因，适合质量、流程、交付和经营异常分析", style: "pm-fishbone", icon: Workflow, accentColor: "#0891b2", bg: "#f8fafc", preview: <ThumbFishbone />, placeholder: "描述问题和候选原因，例如：「生成项目延期根因分析鱼骨图，围绕人员、流程、技术、外部依赖、数据质量拆解」", suggestedTags: ["根因分析", "5Why", "整改措施"], focus: "围绕一个核心问题，把原因分类、证据和整改动作串起来", layout: "问题定义、鱼骨主干、原因分类、证据判断、整改闭环", visual: "主干箭头、分类骨架、原因节点、证据标签、整改表", contentRule: "每个原因要区分现象/根因，给出证据、验证方法和整改责任", logic: "project-template:fishbone. Required sections: problem statement, cause categories, fishbone structure, evidence validation, 5-Why notes, corrective action plan. The page must support root-cause review, not generic reporting.", category: "分析拆解" },
  { id: "data-dashboard", name: "数据可视化看板", desc: "从上传内容或数据中抽取指标、维度、趋势和异常，形成管理驾驶舱", style: "dashboard", icon: BarChart3, accentColor: "#38bdf8", bg: "#0f172a", preview: <ThumbDashboard />, placeholder: "描述看板数据和管理目标，例如：「生成项目 PMO 数据看板，展示进度、质量、成本、风险、资源负载」", suggestedTags: ["KPI", "趋势异常", "管理驾驶舱"], focus: "指标、趋势、异常、原因和行动建议一屏闭环", layout: "KPI 总览、趋势区、维度对比、异常告警、行动建议", visual: "深色看板、指标卡、折线/柱状/矩阵组合、告警条", contentRule: "每个指标都要给出口径、趋势、异常解释和动作建议", logic: "project-template:data-dashboard. Required sections: KPI cards, trend panels, dimension breakdown, anomaly alerts, insight/action list, metric definitions. Use management dashboard logic and avoid decorative page sections.", category: "数据看板" },
];

const AUTO_TEMPLATE: HtmlTemplate = {
  id: AUTO_TEMPLATE_ID,
  name: "自动选择",
  desc: "根据描述自动匹配最合适的项目视图模板",
  style: "report",
  icon: Wand2,
  accentColor: "#2563eb",
  bg: "#f8fafc",
  preview: <ThumbDashboard />,
  placeholder: "描述你想生成的项目网页，例如：展示项目延期原因、关键里程碑、风险和下一步动作",
  suggestedTags: [],
  focus: "根据用户描述自动判断应使用甘特、看板、风险矩阵、鱼骨图、路线图或数据看板",
  layout: "自动匹配",
  visual: "自动匹配",
  contentRule: "根据需求自动选择最能表达项目状态和行动闭环的页面结构",
  logic: "",
  category: AUTO_DIRECTION,
};

// ── Preview pane ──────────────────────────────────────────────────────────────

function HtmlPreviewPane({ html, onClose }: { html: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(html);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${Date.now()}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: "var(--bg)" }}>
      <div className="h-12 border-b flex items-center gap-3 px-4 flex-shrink-0"
        style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}>
        <Eye size={14} style={{ color: "var(--ink-400)" }} />
        <span className="text-[13px] font-semibold" style={{ color: "var(--ink-800)" }}>HTML 预览</span>
        <div className="flex-1" />
        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12px] font-medium hover:bg-gray-50 transition-colors"
          style={{ borderColor: "var(--border)", color: "var(--ink-600)" }} onClick={handleCopy}>
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? "已复制" : "复制代码"}
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold text-white"
          style={{ background: "var(--brand, #2563eb)" }} onClick={handleDownload}>
          <Download size={13} /> 下载 HTML
        </button>
        <button className="px-3 py-1.5 rounded-lg border text-[12px] hover:bg-gray-50 transition-colors"
          style={{ borderColor: "var(--border)", color: "var(--ink-600)" }} onClick={onClose}>
          关闭
        </button>
      </div>
      <iframe className="flex-1 w-full border-0" srcDoc={html} sandbox="allow-scripts allow-same-origin" title="HTML Preview" />
    </div>
  );
}

function suggestedMaterialTagsForTemplate(template: HtmlTemplate) {
  const fallback: Record<string, string[]> = {
    "gantt-pert": ["任务清单", "里程碑", "依赖关系", "延期风险"],
    "resource-gantt": ["资源清单", "占用率", "冲突预警", "调配建议"],
    "timeline-roadmap": ["阶段成果", "关键节点", "决策事项", "下一阶段"],
    "risk-matrix": ["风险清单", "影响概率", "应对预案", "升级机制"],
    "mind-map": ["中心主题", "一级分支", "二级要点", "汇报口径"],
    "fishbone": ["核心问题", "原因分类", "证据判断", "整改措施"],
    "data-dashboard": ["KPI", "趋势异常", "维度对比", "行动建议"],
  };
  return fallback[template.id] || ["页面目标", "关键数据", "风险动作"];
}

function inferTemplateForRequest(text: string, direction: string) {
  const normalized = (text || "").toLowerCase().replace(/\s+/g, "");
  const scoped = direction && direction !== AUTO_DIRECTION
    ? TEMPLATES.filter((tpl) => tpl.category === direction)
    : TEMPLATES;
  const rules: Array<{ id: string; keywords: string[] }> = [
    { id: "kanban-burndown", keywords: ["看板", "燃尽", "sprint", "迭代", "需求变更", "阻塞", "wip", "吞吐"] },
    { id: "fishbone", keywords: ["鱼骨", "根因", "5why", "原因分析", "延期原因", "问题原因", "整改"] },
    { id: "risk-matrix", keywords: ["风险", "概率", "影响", "预案", "升级机制", "风险矩阵"] },
    { id: "data-dashboard", keywords: ["看板", "dashboard", "kpi", "指标", "趋势", "异常", "驾驶舱", "数据"] },
    { id: "resource-gantt", keywords: ["资源", "人力", "排期", "负载", "占用率", "冲突"] },
    { id: "timeline-roadmap", keywords: ["路线图", "roadmap", "时间线", "里程碑", "阶段", "季度", "年度"] },
    { id: "gantt-pert", keywords: ["甘特", "pert", "进度", "计划", "任务", "依赖", "关键路径", "排期"] },
    { id: "mind-map", keywords: ["思维导图", "脑图", "结构拆解", "分支", "架构", "提纲"] },
  ];
  for (const rule of rules) {
    const match = rule.keywords.some((kw) => normalized.includes(kw.toLowerCase()));
    const template = scoped.find((tpl) => tpl.id === rule.id);
    if (match && template) return template;
  }
  return scoped[0] || TEMPLATES[0];
}

function materialBlockForTag(tag: string, template: HtmlTemplate) {
  const prompts: Record<string, string[]> = {
    "页面目标": ["页面服务对象：", "希望解决的问题：", "页面核心结论：", "需要推动的动作："],
    "关键数据": ["数据字段/指标：", "数据来源：", "计算口径：", "希望展示的判断："],
    "图示要求": ["图示类型：", "必须体现的关系：", "视觉质量要求：", "不希望出现的样式："],
    Sprint: ["迭代周期：", "Sprint 目标：", "团队容量：", "验收口径："],
    "需求变更": ["变更项：", "变更原因：", "影响范围：", "处理状态："],
    "阻塞项": ["阻塞事项：", "负责人：", "影响：", "解除动作与时间："],
    "资源负载": ["资源/角色：", "当前占用率：", "冲突时段：", "调配建议："],
    "冲突预警": ["冲突对象：", "发生时间：", "影响任务：", "缓解方案："],
    "人员排期": ["人员/角色：", "任务：", "起止时间：", "可用容量："],
    "领导汇报": ["汇报对象：", "核心结论：", "需决策事项：", "风险提示："],
    "路线图": ["阶段：", "时间范围：", "交付物：", "下一步："],
    "阶段成果": ["阶段：", "已完成成果：", "证据/数据：", "待推进事项："],
    "影响概率": ["风险项：", "发生概率：", "影响程度：", "评分依据："],
    "应对预案": ["风险项：", "预防措施：", "应急动作：", "责任人/截止时间："],
    "升级机制": ["触发条件：", "升级对象：", "响应时限：", "闭环标准："],
    "结构拆解": ["中心主题：", "一级分支：", "二级要点：", "关系说明："],
    "汇报提纲": ["开场结论：", "核心论据：", "风险/分歧：", "行动请求："],
    "方案架构": ["模块：", "职责：", "依赖：", "输出物："],
    "根因分析": ["问题现象：", "直接原因：", "根因判断：", "验证方法："],
    "5Why": ["Why 1：", "Why 2：", "Why 3：", "Why 4：", "Why 5："],
    "整改措施": ["问题/根因：", "整改动作：", "负责人：", "完成时间与验收标准："],
    KPI: ["指标名称：", "指标口径：", "当前值/目标值：", "趋势判断："],
    "趋势异常": ["异常指标：", "异常时间：", "可能原因：", "建议动作："],
    "管理驾驶舱": ["核心指标：", "展示维度：", "告警规则：", "管理动作："],
    "任务清单": ["任务：", "负责人：", "起止时间：", "状态："],
    "里程碑": ["里程碑：", "计划时间：", "完成标准：", "当前风险："],
    "依赖关系": ["前置任务：", "后置任务：", "依赖类型：", "风险说明："],
    "延期风险": ["延期任务：", "延期原因：", "影响范围：", "追赶计划："],
    "资源清单": ["资源名称：", "角色/用途：", "可用容量：", "约束条件："],
    "占用率": ["资源/人员：", "占用率：", "峰值时段：", "优化建议："],
    "调配建议": ["待调配资源：", "调配目标：", "替代方案：", "决策点："],
    "关键节点": ["节点：", "时间：", "输出物：", "责任人："],
    "决策事项": ["事项：", "背景：", "可选方案：", "建议结论："],
    "下一阶段": ["阶段目标：", "关键动作：", "依赖/风险：", "需要支持："],
    "风险清单": ["风险：", "概率/影响：", "责任人：", "应对动作："],
    "中心主题": ["主题：", "目标受众：", "核心结论：", "展示重点："],
    "一级分支": ["分支名称：", "包含内容：", "与主题关系：", "汇报口径："],
    "二级要点": ["所属分支：", "要点：", "证据/例子：", "下一步："],
    "核心问题": ["问题定义：", "发生场景：", "影响范围：", "判断依据："],
    "原因分类": ["分类：", "原因：", "证据：", "是否根因："],
    "证据判断": ["证据：", "来源：", "支持的判断：", "置信度："],
    "维度对比": ["维度：", "对比对象：", "差异：", "解释："],
    "行动建议": ["发现：", "建议动作：", "负责人：", "预期效果："],
  };
  const lines = prompts[tag] || ["素材要点：", "数据/证据：", "风险或约束：", "希望页面如何呈现："];
  return [`## ${tag}`, `模板：${template.name}`, ...lines.map((line) => `- ${line}`)].join("\n");
}

function materialPlaceholderForTag(tag: string, template: HtmlTemplate) {
  const block = materialBlockForTag(tag, template);
  return block
    .split("\n")
    .filter((line) => line.startsWith("- "))
    .map((line) => line.replace(/^- /, ""))
    .join("\n");
}

function buildStructuredMaterial(values: Record<string, string>, template: HtmlTemplate) {
  return Object.entries(values)
    .filter(([, value]) => value.trim())
    .map(([tag, value]) => [`## ${tag}`, `模板：${template.name}`, value.trim()].join("\n"))
    .join("\n\n");
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function HtmlPage({
  onOpenTechIntro: _onOpenTechIntro,
}: {
  onOpenTechIntro?: (techId: string) => void;
}) {
  const [selectedTpl, setSelectedTpl] = useState<HtmlTemplate>(AUTO_TEMPLATE);
  const [prompt, setPrompt] = useState("");
  const [content, setContent] = useState("");
  const [showContentInput, setShowContentInput] = useState(false);
  const [materialValues, setMaterialValues] = useState<Record<string, string>>({});
  const [activeMaterialTag, setActiveMaterialTag] = useState("页面目标");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [generatedHtml, setGeneratedHtml] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [error, setError] = useState("");
  const [analyzingHtml, setAnalyzingHtml] = useState(false);
  const [uploadedHtmlName, setUploadedHtmlName] = useState("");
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [showDirectionSelector, setShowDirectionSelector] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(AUTO_DIRECTION);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<number | null>(() => {
    const saved = localStorage.getItem("da_current_project_id");
    return saved ? Number(saved) : null;
  });
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [showCreateProjectModal, setShowCreateProjectModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [createProjectError, setCreateProjectError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const directionSelectorRef = useRef<HTMLDivElement>(null);
  const projectDropdownRef = useRef<HTMLDivElement>(null);

  const filteredTemplates = useMemo(() => {
    if (selectedCategory === AUTO_DIRECTION) return TEMPLATES;
    return TEMPLATES.filter(t => t.category === selectedCategory);
  }, [selectedCategory]);

  const accentColor = "#2563eb";
  const accentGradient = "linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)";
  const titleGradient = "linear-gradient(90deg, #2563eb, #7c3aed, #3b82f6, #2563eb)";

  useEffect(() => {
    api.listProjects().then(res => setProjects(res.items || [])).catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!showDirectionSelector && !projectDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (directionSelectorRef.current && !directionSelectorRef.current.contains(target)) {
        setShowDirectionSelector(false);
      }
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(target)) {
        setProjectDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showDirectionSelector, projectDropdownOpen]);

  const materialTags = useMemo(() => {
    const base = selectedTpl.suggestedTags.length
      ? selectedTpl.suggestedTags
      : suggestedMaterialTagsForTemplate(selectedTpl);
    return Array.from(new Set(["页面目标", "关键数据", "图示要求", ...base]));
  }, [selectedTpl]);

  const structuredMaterial = useMemo(
    () => buildStructuredMaterial(materialValues, selectedTpl),
    [materialValues, selectedTpl],
  );

  const combinedContent = useMemo(
    () => [content.trim(), structuredMaterial.trim()].filter(Boolean).join("\n\n"),
    [content, structuredMaterial],
  );

  const hasSupplementalMaterial = Boolean(combinedContent.trim() || title.trim());

  useEffect(() => {
    if (!materialTags.includes(activeMaterialTag)) {
      setActiveMaterialTag(materialTags[0] || "页面目标");
    }
  }, [activeMaterialTag, materialTags]);

  const handleGenerate = async () => {
    if (!prompt.trim() && !combinedContent.trim()) { setError("请输入描述或内容"); return; }
    setLoading(true); setError("");
    const effectiveTpl = selectedTpl.id === AUTO_TEMPLATE_ID
      ? inferTemplateForRequest(`${prompt}\n${combinedContent}`, selectedCategory)
      : selectedTpl;
    try {
      const res = await api.post<{ html: string }>("/api/html/generate", {
        prompt: prompt || `生成一份${effectiveTpl.name}风格的HTML页面`,
        content: combinedContent, title: title || prompt.slice(0, 30) || "DataAgent 报告",
        template_style: effectiveTpl.style,
        template_logic: effectiveTpl.logic,
        processing_direction: selectedCategory,
        skills: DIRECTION_SKILLS[selectedCategory] || [],
        project_id: currentProjectId,
        kb_ids: [], include_system_kb: true,
      });
      setGeneratedHtml(res.html); setShowPreview(true);
    } catch {
      setGeneratedHtml(buildDemoHtml(title || prompt.slice(0, 40) || "DataAgent 报告", combinedContent || prompt, effectiveTpl.style));
      setShowPreview(true);
    } finally { setLoading(false); }
  };

  const handleDirectionSelect = (category: string) => {
    setSelectedCategory(category);
    const list = category === AUTO_DIRECTION ? TEMPLATES : TEMPLATES.filter(t => t.category === category);
    if (selectedTpl.id !== AUTO_TEMPLATE_ID && list.length > 0 && !list.find(t => t.id === selectedTpl.id)) {
      setSelectedTpl(AUTO_TEMPLATE);
    }
    setShowDirectionSelector(false);
  };

  const handleSelectProject = (projectId: number | null) => {
    setCurrentProjectId(projectId);
    if (projectId != null) {
      localStorage.setItem("da_current_project_id", String(projectId));
    } else {
      localStorage.removeItem("da_current_project_id");
    }
    setProjectDropdownOpen(false);
  };

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    if (!name) return;
    setCreatingProject(true);
    setCreateProjectError("");
    try {
      const newProject = await api.createProject(name);
      setProjects((prev) => [newProject, ...prev.filter((item) => item.id !== newProject.id)]);
      handleSelectProject(newProject.id);
      setShowCreateProjectModal(false);
      setNewProjectName("");
    } catch {
      setCreateProjectError("创建项目失败，请重试");
    } finally {
      setCreatingProject(false);
    }
  };

  const handleMaterialTag = (tag: string) => {
    setShowContentInput(true);
    setActiveMaterialTag(tag);
  };

  const handleHtmlUpload = async (file: File | null) => {
    if (!file) return;
    if (!/\.html?$/i.test(file.name)) {
      setError("请上传 .html 或 .htm 文件");
      return;
    }
    setAnalyzingHtml(true);
    setError("");
    try {
      const html = await file.text();
      const effectiveTpl = selectedTpl.id === AUTO_TEMPLATE_ID
        ? inferTemplateForRequest(`${prompt}\n${combinedContent}\n${file.name}`, selectedCategory)
        : selectedTpl;
      const res = await api.post<{ analysis: string; title?: string }>("/api/html/analyze", {
        title: file.name.replace(/\.html?$/i, ""),
        html,
        template_logic: effectiveTpl.logic,
      });
      setUploadedHtmlName(file.name);
      setContent(res.analysis);
      setShowContentInput(true);
      if (!title.trim() && res.title) setTitle(res.title);
      setPrompt(p => p || `参考上传 HTML「${file.name}」的结构、数据看板、思维导图、逻辑结构和汇报口径，生成${selectedTpl.id === AUTO_TEMPLATE_ID ? "自动匹配模板的" : selectedTpl.name}网页`);
    } catch {
      setError("HTML 解析失败，请检查文件内容或后端服务");
    } finally {
      setAnalyzingHtml(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  function buildDemoHtml(docTitle: string, text: string, style: string): string {
    const palettes: Record<string, Record<string, string>> = {
      dashboard:    { bg:"#0f172a", bg2:"#1e293b", accent:"#38bdf8", accent2:"#818cf8", text:"#f1f5f9", text2:"#94a3b8", card:"#1e293b", border:"#334155", ar:"56,189,248", a2r:"129,140,248" },
      report:       { bg:"#ffffff", bg2:"#f8fafc", accent:"#2563eb", accent2:"#7c3aed", text:"#0f172a", text2:"#64748b", card:"#f1f5f9", border:"#e2e8f0", ar:"37,99,235", a2r:"124,58,237" },
      minimal:      { bg:"#fafafa", bg2:"#ffffff", accent:"#18181b", accent2:"#71717a", text:"#18181b", text2:"#71717a", card:"#ffffff", border:"#e4e4e7", ar:"24,24,27", a2r:"113,113,122" },
      vivid:        { bg:"#0d0d0d", bg2:"#1a1a1a", accent:"#ff6b35", accent2:"#ffd166", text:"#ffffff", text2:"#a1a1aa", card:"#1a1a1a", border:"#2a2a2a", ar:"255,107,53", a2r:"255,209,102" },
      "pm-gantt":   { bg:"#f8fafc", bg2:"#ffffff", accent:"#2563eb", accent2:"#10b981", text:"#0f172a", text2:"#475569", card:"#ffffff", border:"#dbe3ef", ar:"37,99,235", a2r:"16,185,129" },
      "pm-kanban":  { bg:"#f8fafc", bg2:"#ffffff", accent:"#10b981", accent2:"#2563eb", text:"#0f172a", text2:"#475569", card:"#ffffff", border:"#dbe3ef", ar:"16,185,129", a2r:"37,99,235" },
      "pm-timeline":{ bg:"#ffffff", bg2:"#f8fafc", accent:"#7c3aed", accent2:"#f59e0b", text:"#111827", text2:"#4b5563", card:"#f8fafc", border:"#e5e7eb", ar:"124,58,237", a2r:"245,158,11" },
      "pm-resource":{ bg:"#f8fafc", bg2:"#ffffff", accent:"#0f766e", accent2:"#f59e0b", text:"#0f172a", text2:"#475569", card:"#ffffff", border:"#dbe3ef", ar:"15,118,110", a2r:"245,158,11" },
      "pm-risk":    { bg:"#ffffff", bg2:"#f8fafc", accent:"#dc2626", accent2:"#f59e0b", text:"#111827", text2:"#4b5563", card:"#f8fafc", border:"#e5e7eb", ar:"220,38,38", a2r:"245,158,11" },
      "pm-mindmap": { bg:"#fffaf0", bg2:"#ffffff", accent:"#f59e0b", accent2:"#2563eb", text:"#111827", text2:"#57534e", card:"#ffffff", border:"#fde68a", ar:"245,158,11", a2r:"37,99,235" },
      "pm-fishbone":{ bg:"#f8fafc", bg2:"#ffffff", accent:"#0891b2", accent2:"#7c3aed", text:"#0f172a", text2:"#475569", card:"#ffffff", border:"#dbe3ef", ar:"8,145,178", a2r:"124,58,237" },
    };
    const p = palettes[style] || palettes.report;
    const cssVars = `--bg:${p.bg};--bg2:${p.bg2};--accent:${p.accent};--accent2:${p.accent2};--text:${p.text};--text2:${p.text2};--card:${p.card};--border:${p.border};--ar:${p.ar};--a2r:${p.a2r}`;
    const lines = text.split("\n");
    let html = ""; let inUl = false; let olN = 0;
    for (const l of lines) {
      if (!l.trim()) { if (inUl) { html += "</ul>"; inUl = false; } olN = 0; continue; }
      const inline = (s: string) => s
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/~~(.+?)~~/g, "<del>$1</del>")
        .replace(/`([^`]+)`/g, "<code style='background:rgba(var(--ar),.1);color:var(--accent);padding:1px 5px;border-radius:4px;font-size:.875em'>$1</code>");
      const hm = l.match(/^(#{1,4})\s+(.*)/);
      if (hm) {
        if (inUl) { html += "</ul>"; inUl = false; }
        const lvl = hm[1].length;
        const sz = lvl <= 2 ? "1.2rem" : "1.02rem";
        const lw = lvl <= 2 ? "4px" : "3px";
        html += `<h${Math.min(lvl+1,4)} style="font-size:${sz};font-weight:700;color:var(--text);border-left:${lw} solid var(--accent);padding-left:14px;margin:28px 0 12px;line-height:1.3">${inline(hm[2])}</h${Math.min(lvl+1,4)}>`;
        continue;
      }
      if (l.match(/^\d+[.)]\s+/)) {
        if (inUl) { html += "</ul>"; inUl = false; }
        olN++;
        const item = l.replace(/^\d+[.)]\s+/, "");
        html += `<div style="display:flex;gap:10px;padding:8px 14px 8px 10px;margin-bottom:4px;border-radius:8px;background:rgba(var(--ar),.04);border:1px solid rgba(var(--ar),.08)"><span style="min-width:20px;height:20px;border-radius:50%;background:rgba(var(--ar),.14);color:var(--accent);font-size:.72rem;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px">${olN}</span><span style="color:var(--text2);font-size:.93rem;line-height:1.65">${inline(item)}</span></div>`;
        continue;
      }
      if (l.trim().startsWith("- ") || l.trim().startsWith("* ")) {
        if (!inUl) { html += '<ul style="list-style:none;padding:0;margin:10px 0">'; inUl = true; }
        const item = l.replace(/^\s*[-*]\s+/, "");
        html += `<li style="padding:7px 14px 7px 32px;margin-bottom:4px;border-radius:8px;background:rgba(var(--ar),.03);border:1px solid rgba(var(--ar),.06);color:var(--text2);font-size:.93rem;line-height:1.65;position:relative"><span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);width:6px;height:6px;border-radius:50%;background:var(--accent)"></span>${inline(item)}</li>`;
        continue;
      }
      if (l.startsWith("> ")) {
        if (inUl) { html += "</ul>"; inUl = false; }
        html += `<blockquote style="margin:16px 0;padding:14px 18px 14px 22px;background:rgba(var(--a2r),.06);border-left:4px solid var(--accent2);border-radius:0 10px 10px 0;color:var(--text2);font-style:italic">${inline(l.slice(2))}</blockquote>`;
        continue;
      }
      if (/^---+$/.test(l.trim())) {
        if (inUl) { html += "</ul>"; inUl = false; }
        html += `<hr style="border:none;height:1px;background:linear-gradient(90deg,transparent,var(--border),transparent);margin:28px 0">`;
        continue;
      }
      if (inUl) { html += "</ul>"; inUl = false; }
      html += `<p style="color:var(--text2);margin-bottom:12px;line-height:1.78;font-size:.95rem">${inline(l)}</p>`;
    }
    if (inUl) html += "</ul>";
    const today = new Date().toLocaleDateString("zh-CN");
    return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${docTitle}</title>
<style>:root{${cssVars}}*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}html{scroll-behavior:smooth}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:0 24px 80px}
.hero{padding:52px 0 36px;text-align:center;position:relative}
.hero::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 50% 0%,rgba(var(--ar),.07) 0%,transparent 70%);pointer-events:none}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 12px;border-radius:100px;font-size:.72rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;background:rgba(var(--ar),.1);color:var(--accent);border:1px solid rgba(var(--ar),.2);margin-bottom:16px}
.hero h1{font-size:clamp(1.8rem,4vw,2.8rem);font-weight:800;letter-spacing:-.03em;line-height:1.15;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:12px}
.hero-sub{color:var(--text2);font-size:1rem;max-width:600px;margin:0 auto}
.divider{height:1px;background:linear-gradient(90deg,transparent,var(--border),transparent);margin-top:36px}
.footer{text-align:center;padding:32px 0 16px;border-top:1px solid var(--border);margin-top:52px;font-size:.8rem;color:var(--text2)}
.footer strong{font-weight:700;font-size:.88rem;color:var(--text)}
.footer strong span{background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
#btt{position:fixed;bottom:24px;right:24px;width:38px;height:38px;border-radius:50%;background:var(--accent);color:#fff;border:none;cursor:pointer;font-size:14px;display:none;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(var(--ar),.4);transition:all .25s;z-index:100}
#btt.vis{display:flex}#btt:hover{transform:translateY(-2px)}
code{font-size:.875em}</style></head>
<body><div class="wrap"><div class="hero">
<div class="badge">&#128196; DataAgent Studio</div>
<h1>${docTitle}</h1>
<p class="hero-sub">由 DataAgent Studio 生成</p>
<div class="divider"></div>
</div>
<div style="margin-top:32px">${html}</div>
<div class="footer"><strong>Data<span>Agent</span> Studio</strong><br>${today} · 本报告由 AI 生成，仅供参考</div>
</div>
<button id="btt" onclick="window.scrollTo({top:0,behavior:'smooth'})" title="返回顶部">&#8679;</button>
<script>var b=document.getElementById('btt');window.addEventListener('scroll',function(){b&&(window.scrollY>300?b.classList.add('vis'):b.classList.remove('vis'))});</script>
</body></html>`;
  }

  if (showPreview && generatedHtml) {
    return <HtmlPreviewPane html={generatedHtml} onClose={() => setShowPreview(false)} />;
  }

  return (
    <div className="min-h-full flex flex-col items-center px-6 py-8 pb-20 relative" style={{ background: "var(--bg)" }}>
      {/* Subtle background */}
      <div
        className="absolute inset-x-0 top-0 h-[45vh] pointer-events-none"
        style={{ background: `radial-gradient(ellipse 45% 35% at 50% 0%, ${accentColor}04 0%, transparent 70%)` }}
      />

      <div className="w-full max-w-[820px] flex flex-col items-center relative mt-36 flex-1">
        <style>{`
          @keyframes html-gradient-flow {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
          }
          .animated-gradient-html {
            background: ${titleGradient};
            background-size: 200% 100%;
            animation: html-gradient-flow 3s ease infinite;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }
          @keyframes html-page-rise {
            from { opacity: 0; transform: translateY(18px) scale(.985); }
            to { opacity: 1; transform: translateY(0) scale(1); }
          }
          @keyframes html-soft-float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
          }
          @keyframes html-card-in {
            from { opacity: 0; transform: translateY(14px); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes html-sheen {
            from { transform: translateX(-120%) skewX(-18deg); opacity: 0; }
            35% { opacity: .55; }
            to { transform: translateX(320%) skewX(-18deg); opacity: 0; }
          }
          .html-hero-in { animation: html-page-rise .48s cubic-bezier(.22,1,.36,1) both; }
          .html-input-in { animation: html-page-rise .52s .08s cubic-bezier(.22,1,.36,1) both; }
          .html-gallery-in { animation: html-page-rise .5s .16s cubic-bezier(.22,1,.36,1) both; }
          .html-template-card { animation: html-card-in .44s cubic-bezier(.22,1,.36,1) both; }
          .html-template-card:hover .html-thumb-motion { transform: scale(1.018); }
          .html-thumb-motion { transition: transform .35s cubic-bezier(.22,1,.36,1); }
          .html-template-card:hover .html-card-sheen { background: linear-gradient(90deg, transparent, rgba(255,255,255,.68), transparent); animation: html-sheen 1.25s ease-out; }
          .html-send-ready { animation: html-soft-float 2s ease-in-out infinite; }
          @media (prefers-reduced-motion: reduce) {
            .html-hero-in, .html-input-in, .html-gallery-in, .html-template-card, .html-send-ready,
            .html-template-card:hover .html-card-sheen { animation: none !important; }
            .html-template-card:hover .html-thumb-motion { transform: none !important; }
          }
        `}</style>

        {/* Hero */}
        <div className="text-center mb-6 html-hero-in">
          <h1 style={{ fontSize: "30px", lineHeight: 1.35, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--ink-900)" }}>
            欢迎来到 <span className="animated-gradient-html">DataAgent WebSite</span>
          </h1>
          <p style={{ marginTop: 8, fontSize: "14px", color: "var(--ink-400)", lineHeight: 1.6, maxWidth: 520, margin: "8px auto 0" }}>
            选择项目视图模板，描述需求，生成可直接交付的独立 HTML 页面
          </p>
        </div>

        {/* Input card */}
        <div className="w-full relative z-40 html-input-in">
          <div
            className="transition-all rounded-[22px] px-4 pt-4 pb-3"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              boxShadow: "0 10px 34px rgba(15, 23, 42, 0.07), 0 1px 2px rgba(15, 23, 42, 0.05)",
            }}
            onFocus={(e) => {
              const hex = accentColor.replace('#', '');
              const r = parseInt(hex.substring(0, 2), 16);
              const g = parseInt(hex.substring(2, 4), 16);
              const b = parseInt(hex.substring(4, 6), 16);
              e.currentTarget.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.22)`;
              e.currentTarget.style.boxShadow = `0 12px 32px -8px rgba(${r}, ${g}, ${b}, 0.22)`;
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "0 10px 34px rgba(15, 23, 42, 0.07), 0 1px 2px rgba(15, 23, 42, 0.05)";
            }}
          >
            {/* Uploaded HTML reference */}
            {uploadedHtmlName && (
              <div className="flex items-center gap-2 px-2 pt-1.5 pb-2">
                <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                  <FileCode2 size={14} style={{ color: accentColor }} />
                  <div style={{ maxWidth: 200 }}>
                    <div className="truncate text-[12.5px]" style={{ color: "var(--ink-900)", fontWeight: 500 }}>{uploadedHtmlName}</div>
                    <div style={{ fontSize: "11px", color: "var(--ink-400)" }}>已解析为参考内容</div>
                  </div>
                  <button onClick={() => { setUploadedHtmlName(""); setContent(""); }} className="h-4 w-4 flex items-center justify-center flex-shrink-0" style={{ color: "var(--ink-400)" }}>
                    <X size={12} />
                  </button>
                </div>
              </div>
            )}

            {/* Prompt textarea */}
            <textarea
              ref={textRef}
              className="w-full bg-transparent border-0 outline-none resize-none text-[15px] px-1 py-2"
              rows={3}
              placeholder={selectedTpl.placeholder}
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              style={{ color: "var(--ink-900)", lineHeight: 1.7 }}
            />

            {/* Optional material paste area */}
            {showContentInput ? (
              <div className="mt-1 mb-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] font-medium" style={{ color: "var(--ink-600)" }}>
                    补充素材
                    <span className="ml-1 text-[11px]" style={{ color: "var(--ink-400)" }}>
                      {Object.values(materialValues).filter((value) => value.trim()).length}/{materialTags.length}
                    </span>
                  </span>
                  <button className="h-6 w-6 rounded-full inline-flex items-center justify-center hover:bg-[var(--hover)]" onClick={() => { setShowContentInput(false); setMaterialValues({}); setTitle(""); }} title="移除补充素材">
                    <X size={13} />
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 mb-2">
                  {materialTags.map(tag => {
                    const filled = Boolean(materialValues[tag]?.trim());
                    const active = activeMaterialTag === tag;
                    return (
                      <button key={tag}
                        className="px-2 py-0.5 rounded-full border text-[11px] whitespace-nowrap transition-all hover:shadow-sm inline-flex items-center gap-1"
                        style={{
                          borderColor: filled ? "#22c55e" : active ? selectedTpl.accentColor + "70" : "var(--border)",
                          color: filled ? "#15803d" : active ? selectedTpl.accentColor : "var(--ink-500)",
                          background: filled ? "#dcfce7" : active ? selectedTpl.accentColor + "10" : "var(--bg-subtle)",
                        }}
                        onClick={() => handleMaterialTag(tag)}>
                        {filled ? <Check size={10} /> : <Plus size={10} />}
                        {tag}
                      </button>
                    );
                  })}
                </div>
                <input
                  className="w-full rounded-xl border px-3 py-2.5 text-[12.5px] focus:outline-none transition-all mb-2"
                  placeholder="页面标题（选填）"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  style={{ borderColor: "var(--border)", background: "var(--bg-subtle, #f9fafb)", color: "var(--ink-800)" }}
                />
                <div className="rounded-xl border overflow-hidden" style={{ borderColor: materialValues[activeMaterialTag]?.trim() ? "#22c55e" : "var(--border)", background: "var(--bg-subtle, #f9fafb)" }}>
                  <div className="px-3 py-2 flex items-center justify-between" style={{ borderBottom: "1px solid var(--border)" }}>
                    <span className="text-[12px] font-semibold" style={{ color: materialValues[activeMaterialTag]?.trim() ? "#15803d" : "var(--ink-700)" }}>
                      {activeMaterialTag}
                    </span>
                    {materialValues[activeMaterialTag]?.trim() && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium" style={{ color: "#15803d" }}>
                        <Check size={11} /> 已填写
                      </span>
                    )}
                  </div>
                  <textarea
                    className="w-full border-0 px-3 py-2.5 text-[12.5px] resize-none focus:outline-none transition-all bg-transparent"
                    rows={4}
                    placeholder={materialPlaceholderForTag(activeMaterialTag, selectedTpl)}
                    value={materialValues[activeMaterialTag] || ""}
                    onChange={e => setMaterialValues((prev) => ({ ...prev, [activeMaterialTag]: e.target.value }))}
                    style={{ color: "var(--ink-700)", fontFamily: "monospace", fontSize: 12 }}
                  />
                </div>
                {content.trim() && (
                  <div className="mt-2 rounded-xl border px-3 py-2 text-[11px] leading-5" style={{ borderColor: "var(--border)", background: "var(--bg-subtle)", color: "var(--ink-500)" }}>
                    已包含上传 HTML 解析素材，将与上方补充元素一起提交。
                  </div>
                )}
              </div>
            ) : null}

            {error && <div className="text-[12px] text-red-500 px-1 mb-2">{error}</div>}

            {/* Toolbar row */}
            <div className="flex items-center gap-1.5 pt-2 min-w-0 flex-nowrap" style={{ borderTop: "1px solid rgba(15, 23, 42, 0.06)" }}>
              {/* HTML upload */}
              <input ref={fileInputRef} type="file" accept=".html,.htm,text/html" className="hidden" onChange={e => handleHtmlUpload(e.target.files?.[0] || null)} />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="h-9 w-9 inline-flex items-center justify-center rounded-full transition hover:bg-[var(--hover)] flex-shrink-0"
                style={{ color: "var(--ink-500)" }}
                title="上传并解析 HTML 参考"
              >
                <Paperclip size={18} />
              </button>

              {/* Template selector */}
              <div className="relative min-w-0 max-w-[200px] flex-shrink-0">
                <button
                  onClick={() => setShowTemplateSelector(!showTemplateSelector)}
                  className="inline-flex items-center gap-1 h-7 px-2.5 rounded-full transition hover:bg-[var(--hover)] whitespace-nowrap flex-shrink-0"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
                >
                  <span style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)" }} className="truncate">{selectedTpl.name}</span>
                  <ChevronDown size={12} style={{ color: "var(--ink-500)", flexShrink: 0 }} />
                </button>

                {showTemplateSelector && (
                  <>
                    <div className="fixed inset-0 z-20" onClick={() => setShowTemplateSelector(false)} />
                    <div
                      className="absolute top-full mt-1.5 left-0 rounded-lg overflow-hidden min-w-[200px] max-h-[360px] overflow-y-auto z-30 custom-scrollbar"
                      style={{
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                      }}
                    >
                      <div className="py-1">
                        <button
                          key={AUTO_TEMPLATE.id}
                          onClick={() => { setSelectedTpl(AUTO_TEMPLATE); setShowTemplateSelector(false); }}
                          className="w-full px-3 py-2 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                          style={{ fontSize: "13px", color: selectedTpl.id === AUTO_TEMPLATE_ID ? accentColor : "var(--ink-700)" }}
                        >
                          <Wand2 size={14} style={{ color: accentColor, flexShrink: 0 }} />
                          <span className="truncate">自动选择</span>
                        </button>
                        {filteredTemplates.map((tpl) => {
                          const Icon = tpl.icon;
                          return (
                            <button
                              key={tpl.id}
                              onClick={() => { setSelectedTpl(tpl); setShowTemplateSelector(false); setPrompt(""); }}
                              className="w-full px-3 py-2 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                              style={{ fontSize: "13px", color: "var(--ink-700)" }}
                            >
                              <Icon size={14} style={{ color: tpl.accentColor, flexShrink: 0 }} />
                              <span className="truncate">{tpl.name}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Processing direction selector */}
              <div className="relative min-w-0 max-w-[132px] flex-shrink-0" ref={directionSelectorRef}>
                <button
                  onClick={() => setShowDirectionSelector(!showDirectionSelector)}
                  className="inline-flex items-center gap-1 h-7 px-2.5 rounded-full transition hover:bg-[var(--hover)] whitespace-nowrap flex-shrink-0"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
                  title={DIRECTION_DESCRIPTIONS[selectedCategory]}
                >
                  <span style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)" }} className="truncate">{selectedCategory}</span>
                  <ChevronDown size={12} style={{ color: "var(--ink-500)", flexShrink: 0 }} />
                </button>

                {showDirectionSelector && (
                  <div
                    className="absolute top-full mt-1.5 left-0 rounded-lg overflow-hidden min-w-[220px] max-h-[320px] overflow-y-auto z-30 custom-scrollbar"
                    style={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border)",
                      boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                    }}
                  >
                    <div className="py-1">
                      {CATEGORIES.map((cat) => {
                        const selected = selectedCategory === cat;
                        return (
                          <button
                            key={cat}
                            onClick={() => handleDirectionSelect(cat)}
                            className="w-full px-3 py-2 text-left transition hover:bg-[var(--hover)] flex items-start gap-2"
                            style={{ fontSize: "13px", color: selected ? accentColor : "var(--ink-700)" }}
                            title={`启用 ${DIRECTION_SKILLS[cat]?.join(", ") || "web skill"}`}
                          >
                            <span className="mt-1 h-2 w-2 rounded-full flex-shrink-0" style={{ background: selected ? accentColor : "var(--border-strong, #cbd5e1)" }} />
                            <span className="min-w-0">
                              <span className="block font-medium">{cat}</span>
                              <span className="block text-[11px] leading-4" style={{ color: "var(--ink-400)" }}>{DIRECTION_DESCRIPTIONS[cat]}</span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Project selector */}
              <div className="relative min-w-0 max-w-[160px] flex-shrink-0" ref={projectDropdownRef}>
                <button
                  onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
                  className="inline-flex items-center gap-1 h-7 px-2.5 rounded-full transition hover:bg-[var(--hover)] whitespace-nowrap flex-shrink-0"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
                >
                  <FolderOpen size={12} style={{ color: "var(--ink-500)", flexShrink: 0 }} />
                  <span style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)" }} className="truncate">
                    {projects.find((project) => project.id === currentProjectId)?.name || "不使用项目"}
                  </span>
                  <ChevronDown size={12} style={{ color: "var(--ink-500)", flexShrink: 0 }} />
                </button>

                {projectDropdownOpen && (
                  <div
                    className="absolute top-full mt-1.5 left-0 rounded-lg overflow-hidden w-[260px] max-h-[320px] overflow-y-auto z-30 custom-scrollbar"
                    style={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border)",
                      boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                    }}
                  >
                    <div className="p-2" style={{ borderBottom: "1px solid var(--border)" }}>
                      <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg" style={{ background: "var(--bg-subtle)" }}>
                        <Search size={12} style={{ color: "var(--ink-400)" }} />
                        <input
                          type="text"
                          placeholder="搜索项目"
                          value={projectSearch}
                          onChange={(e) => setProjectSearch(e.target.value)}
                          className="bg-transparent text-[12px] outline-none w-full"
                          style={{ color: "var(--ink-700)" }}
                        />
                      </div>
                    </div>
                    <div className="p-1.5">
                      {projects
                        .filter((project) => !projectSearch || project.name.toLowerCase().includes(projectSearch.toLowerCase()))
                        .map((project) => (
                          <button
                            key={project.id}
                            onClick={() => handleSelectProject(project.id)}
                            className="w-full px-2 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2 rounded-lg"
                            style={{ fontSize: "12px", color: "var(--ink-700)" }}
                          >
                            <FolderOpen size={13} style={{ color: "var(--ink-500)", flexShrink: 0 }} />
                            <span className="truncate flex-1">{project.name}</span>
                            {currentProjectId === project.id && <Check size={12} style={{ color: accentColor }} />}
                          </button>
                        ))}
                      {projects.filter((project) => !projectSearch || project.name.toLowerCase().includes(projectSearch.toLowerCase())).length === 0 && (
                        <div className="px-2 py-2 text-[11px]" style={{ color: "var(--ink-400)" }}>无匹配项目</div>
                      )}
                    </div>
                    <div className="p-1.5 space-y-0.5" style={{ borderTop: "1px solid var(--border)" }}>
                      <button
                        onClick={() => {
                          setProjectDropdownOpen(false);
                          setNewProjectName("");
                          setCreateProjectError("");
                          setShowCreateProjectModal(true);
                        }}
                        className="w-full px-2 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2 rounded-lg"
                        style={{ fontSize: "12px", color: "var(--ink-700)" }}
                      >
                        <Plus size={13} style={{ color: "var(--ink-500)" }} />
                        添加新项目
                      </button>
                      <button
                        onClick={() => handleSelectProject(null)}
                        className="w-full px-2 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2 rounded-lg"
                        style={{ fontSize: "12px", color: "var(--ink-700)" }}
                      >
                        <X size={13} style={{ color: "var(--ink-500)" }} />
                        不使用项目
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Supplemental material */}
              <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
                <button
                  className="px-2 py-0.5 rounded-full border text-[11px] whitespace-nowrap flex-shrink-0 transition-all hover:shadow-sm"
                  style={{
                    borderColor: (showContentInput || hasSupplementalMaterial) ? selectedTpl.accentColor + "60" : "var(--border)",
                    color: (showContentInput || hasSupplementalMaterial) ? selectedTpl.accentColor : "var(--ink-500)",
                    background: (showContentInput || hasSupplementalMaterial) ? selectedTpl.accentColor + "10" : "transparent",
                  }}
                  onClick={() => setShowContentInput((open) => !open)}
                >
                  <Plus size={10} className="inline mr-1" /> 补充素材
                </button>
              </div>

              <div className="flex-1 min-w-2" />

              {/* Generate button */}
              <button
                onClick={handleGenerate}
                disabled={loading || (!prompt.trim() && !combinedContent.trim())}
                className={`h-9 w-9 inline-flex items-center justify-center rounded-full transition-all active:scale-95 disabled:cursor-not-allowed flex-shrink-0 ${prompt.trim() || combinedContent.trim() ? "html-send-ready" : ""}`}
                style={{
                  background: prompt.trim() || combinedContent.trim() ? accentColor : "var(--bg-subtle)",
                  color: prompt.trim() || combinedContent.trim() ? "#fff" : "var(--ink-400)",
                  boxShadow: prompt.trim() || combinedContent.trim() ? "var(--shadow-sm)" : "none",
                }}
                title="生成网页"
              >
                {loading ? <span className="animate-spin text-[12px]">⏳</span> : <ArrowUp size={18} />}
              </button>
            </div>
          </div>
          <p className="text-center text-[11px] mt-2.5" style={{ color: "var(--ink-400)" }}>
            DataAgent 可能会出错，请仔细核对
          </p>
        </div>

        {/* Template gallery */}
        <div className="w-full mt-10 html-gallery-in">
          <div className="flex items-center justify-between mb-4">
            <div>
              <span style={{ fontWeight: 700, fontSize: "14px", color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
                项目视图模板
              </span>
              <span className="ml-2" style={{ fontSize: "11.5px", color: "var(--ink-400)" }}>点击选择，填写描述后生成</span>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold" style={{ background: accentColor + "12", color: accentColor }}>
              {filteredTemplates.length} 个
            </span>
          </div>

          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {filteredTemplates.map((tpl, index) => {
              const Icon = tpl.icon;
              const sel = selectedTpl.id === tpl.id;
              return (
                <button key={tpl.id}
                  className="html-template-card text-left relative overflow-hidden rounded-2xl transition-all duration-200 hover:-translate-y-0.5"
                  style={{
                    animationDelay: `${index * 55}ms`,
                    border: sel ? `2px solid ${tpl.accentColor}` : "1.5px solid var(--border)",
                    boxShadow: sel
                      ? `0 0 0 3px ${tpl.accentColor}18, 0 8px 24px rgba(0,0,0,0.08)`
                      : "0 1px 4px rgba(0,0,0,0.05)",
                    background: sel ? tpl.bg : "var(--bg-panel)",
                  }}
                  onClick={() => { setSelectedTpl(tpl); setPrompt(""); }}
                >
                  {/* Sheen effect */}
                  <div className="html-card-sheen absolute inset-0 pointer-events-none z-10" />

                  {/* Thumbnail — increased to 130px */}
                  <div className="h-[130px] w-full overflow-hidden flex-shrink-0 relative rounded-t-2xl">
                    <div className="html-thumb-motion w-full h-full">{tpl.preview}</div>
                    {/* Selected checkmark overlay */}
                    {sel && (
                      <div className="absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center z-20"
                        style={{ background: tpl.accentColor, boxShadow: `0 2px 8px ${tpl.accentColor}60` }}>
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="px-3 pt-2.5 pb-3">
                    <div className="flex items-start gap-1.5 mb-1">
                      <div className="w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5"
                        style={{ background: tpl.accentColor + "18" }}>
                        <Icon size={11} style={{ color: tpl.accentColor }} />
                      </div>
                      <span className="text-[13px] font-semibold leading-tight" style={{ color: "var(--ink-900)" }}>{tpl.name}</span>
                    </div>
                    <p className="text-[11px] leading-[1.55] line-clamp-2 mb-2.5" style={{ color: "var(--ink-400)" }}>{tpl.desc}</p>
                    {/* Focus badge */}
                    <div className="flex items-center gap-1 text-[10px] leading-[1.4]" style={{ color: "var(--ink-500)" }}>
                      <Layers size={9} style={{ color: tpl.accentColor, flexShrink: 0 }} />
                      <span className="line-clamp-1">{tpl.focus}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="w-full text-center mt-auto pt-10 pb-6" style={{ color: "var(--ink-400)", fontSize: "11px" }}>
          2026 大数据应用部 | Brdc.AI人工智能小组
        </div>
      </div>

      {showCreateProjectModal && (
        <div className="fixed inset-0 z-[300] flex items-center justify-center" style={{ background: "rgba(0,0,0,0.48)" }}>
          <div className="w-[360px] rounded-2xl p-6" style={{ background: "var(--bg-elevated)", boxShadow: "0 24px 64px rgba(0,0,0,0.25)" }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[16px] font-semibold" style={{ color: "var(--ink-900)" }}>添加新项目</h3>
              <button
                className="h-7 w-7 rounded-full inline-flex items-center justify-center hover:bg-[var(--hover)]"
                onClick={() => setShowCreateProjectModal(false)}
                style={{ color: "var(--ink-500)" }}
              >
                <X size={14} />
              </button>
            </div>
            <input
              className="w-full rounded-xl border px-3 py-2.5 text-[14px] outline-none mb-3"
              placeholder="输入项目名称"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void handleCreateProject(); }}
              style={{ borderColor: "var(--border)", background: "var(--bg-subtle)", color: "var(--ink-900)" }}
              autoFocus
            />
            {createProjectError && <div className="text-[12px] text-red-500 mb-3">{createProjectError}</div>}
            <div className="flex justify-end gap-2">
              <button
                className="h-9 px-4 rounded-xl text-[13px] font-medium hover:bg-[var(--hover)]"
                style={{ color: "var(--ink-600)" }}
                onClick={() => setShowCreateProjectModal(false)}
              >
                取消
              </button>
              <button
                className="h-9 px-4 rounded-xl text-[13px] font-semibold text-white disabled:opacity-50"
                style={{ background: "var(--ink-900)" }}
                disabled={!newProjectName.trim() || creatingProject}
                onClick={handleCreateProject}
              >
                {creatingProject ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
