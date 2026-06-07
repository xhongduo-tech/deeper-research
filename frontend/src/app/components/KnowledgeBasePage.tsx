/**
 * KnowledgeBasePage — 三合一知识库中心 (世界观10层架构版)
 *
 * 标签页:
 *   1) 数据图谱    — 10层世界观架构可视化 + 领域覆盖
 *   2) 系统数据库  — 按10层分组的官方数据源卡片
 *   3) 用户数据库  — 用户自建知识库 (上传/管理)
 */
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Database, Plus, Upload, FileText, Trash2, Loader2, X,
  CheckCircle2, AlertCircle, Layers, FileStack, HardDrive,
  Globe, Server, FolderOpen, Search, BarChart3, ChevronRight,
  TrendingUp, Shield, Brain, Workflow, Clock, Eye, Zap, BookOpen,
  Cpu, Microscope, Anchor, Radio, Activity, Target, Compass,
} from "lucide-react";
import { api, KnowledgeBase, KBDocument, OfficialDataSource } from "../lib/api";

type TabKey = "graph" | "system" | "user";

// ═══════════════════════════════════════════════════════════════════════════════
// 10层世界观架构配置
// ═══════════════════════════════════════════════════════════════════════════════

export interface WorldviewLayer {
  id: string;
  name: string;
  nameEn: string;
  budgetGb: number;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ElementType;
  description: string;
  sourceCount: number;
}

const WORLDVIEW_LAYERS: WorldviewLayer[] = [
  {
    id: "L0", name: "元知识层", nameEn: "Meta-Knowledge",
    budgetGb: 50, color: "#8b5cf6", bgColor: "#f5f3ff", borderColor: "#c4b5fd",
    icon: Anchor, description: "本体定义、Schema、概念体系、版本控制",
    sourceCount: 5,
  },
  {
    id: "L1", name: "基础事实层", nameEn: "Ground Facts",
    budgetGb: 800, color: "#3b82f6", bgColor: "#eff6ff", borderColor: "#93c5fd",
    icon: BookOpen, description: "原始事实、观测数据、统计数据、年报财报",
    sourceCount: 11,
  },
  {
    id: "L2", name: "关系网络层", nameEn: "Relation Networks",
    budgetGb: 600, color: "#06b6d4", bgColor: "#ecfeff", borderColor: "#67e8f9",
    icon: Globe, description: "实体关系、知识图谱、社交网络、供应链",
    sourceCount: 6,
  },
  {
    id: "L3", name: "因果机制层", nameEn: "Causal & Mechanistic",
    budgetGb: 400, color: "#10b981", bgColor: "#ecfdf5", borderColor: "#6ee7b7",
    icon: Workflow, description: "因果关系、物理机制、经济模型、推理链",
    sourceCount: 6,
  },
  {
    id: "L4", name: "价值规范层", nameEn: "Normative",
    budgetGb: 100, color: "#84cc16", bgColor: "#f7fee7", borderColor: "#bef264",
    icon: Shield, description: "法律法规、伦理准则、行业标准、政策导向",
    sourceCount: 6,
  },
  {
    id: "L5", name: "认知思维层", nameEn: "Cognitive",
    budgetGb: 150, color: "#f59e0b", bgColor: "#fffbeb", borderColor: "#fcd34d",
    icon: Brain, description: "认知框架、思维模型、决策理论、心理学",
    sourceCount: 6,
  },
  {
    id: "L6", name: "程序实用层", nameEn: "Procedural",
    budgetGb: 300, color: "#f97316", bgColor: "#fff7ed", borderColor: "#fdba74",
    icon: Cpu, description: "算法代码、工程实践、操作手册、最佳实践",
    sourceCount: 6,
  },
  {
    id: "L7", name: "多模态对齐层", nameEn: "Multimodal",
    budgetGb: 800, color: "#ef4444", bgColor: "#fef2f2", borderColor: "#fca5a5",
    icon: Eye, description: "图像、音频、视频、跨模态语义对齐",
    sourceCount: 4,
  },
  {
    id: "L8", name: "时序演化层", nameEn: "Temporal",
    budgetGb: 200, color: "#ec4899", bgColor: "#fdf2f8", borderColor: "#f9a8d4",
    icon: Clock, description: "历史演变、趋势预测、版本追踪、时间序列",
    sourceCount: 5,
  },
  {
    id: "L9", name: "不确定性层", nameEn: "Uncertainty",
    budgetGb: 100, color: "#6b7280", bgColor: "#f9fafb", borderColor: "#d1d5db",
    icon: Microscope, description: "误差范围、置信区间、边界条件、反面证据",
    sourceCount: 5,
  },
];

const TOTAL_BUDGET_GB = WORLDVIEW_LAYERS.reduce((s, l) => s + l.budgetGb, 0);

// 模拟各层已下载量（后续接入后端API）
function getLayerActualGb(layerId: string): number {
  const actuals: Record<string, number> = {
    L0: 2.1, L1: 45.2, L2: 18.5, L3: 12.3, L4: 8.7,
    L5: 5.4, L6: 35.8, L7: 2.1, L8: 6.2, L9: 1.8,
  };
  return actuals[layerId] || 0;
}

// ── 领域分类（与后端 type_labels 对齐）───────────────────────────────────────
const KB_TYPES: { value: string; label: string; icon: string }[] = [
  { value: "finance", label: "金融数据", icon: "💹" },
  { value: "banking", label: "银行年报", icon: "🏦" },
  { value: "policy", label: "政策法规", icon: "📜" },
  { value: "gov", label: "政府报告", icon: "🏛️" },
  { value: "news", label: "新闻舆情", icon: "📰" },
  { value: "academic", label: "学术论文", icon: "🎓" },
  { value: "code", label: "代码工程", icon: "💻" },
  { value: "math", label: "数学知识", icon: "➗" },
  { value: "statistics", label: "统计数据", icon: "📊" },
  { value: "research", label: "研究报告", icon: "🔬" },
  { value: "general", label: "通用", icon: "📁" },
];

function typeIcon(t?: string) {
  return KB_TYPES.find((k) => k.value === t)?.icon ?? "📁";
}

// ═══════════════════════════════════════════════════════════════════════════════
// 资产总览横幅
// ═══════════════════════════════════════════════════════════════════════════════

function WorldviewOverviewBanner() {
  const totalActual = WORLDVIEW_LAYERS.reduce((s, l) => s + getLayerActualGb(l.id), 0);
  const totalPct = Math.min((totalActual / TOTAL_BUDGET_GB) * 100, 100);
  const totalSources = WORLDVIEW_LAYERS.reduce((s, l) => s + l.sourceCount, 0);

  return (
    <div className="px-6 py-4 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center backdrop-blur">
            <Compass size={20} className="text-emerald-400" />
          </div>
          <div>
            <h2 className="text-[15px] font-bold text-white">世界观知识库 · Worldview Knowledge Base</h2>
            <p className="text-[12px] text-slate-400">10层架构 · 60个数据源 · 3.5TB存储预算</p>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right">
            <p className="text-[11px] text-slate-400">已下载</p>
            <p className="text-[18px] font-bold text-emerald-400">{totalActual.toFixed(1)} <span className="text-[12px] font-normal text-slate-500">GB</span></p>
          </div>
          <div className="text-right">
            <p className="text-[11px] text-slate-400">总预算</p>
            <p className="text-[18px] font-bold text-white">{TOTAL_BUDGET_GB} <span className="text-[12px] font-normal text-slate-500">GB</span></p>
          </div>
          <div className="text-right">
            <p className="text-[11px] text-slate-400">覆盖率</p>
            <p className="text-[18px] font-bold text-amber-400">{totalPct.toFixed(1)}%</p>
          </div>
          <div className="text-right">
            <p className="text-[11px] text-slate-400">数据源</p>
            <p className="text-[18px] font-bold text-blue-400">{totalSources} <span className="text-[12px] font-normal text-slate-500">个</span></p>
          </div>
        </div>
      </div>
      {/* 总体进度条 */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2.5 rounded-full bg-white/10 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000"
            style={{
              width: `${totalPct}%`,
              background: "linear-gradient(90deg, #10b981, #3b82f6, #8b5cf6)",
            }}
          />
        </div>
        <span className="text-[11px] text-slate-400 w-12 text-right">{totalPct.toFixed(1)}%</span>
      </div>
      {/* 各层小进度条 */}
      <div className="flex items-center gap-1 mt-2">
        {WORLDVIEW_LAYERS.map((layer) => {
          const actual = getLayerActualGb(layer.id);
          const pct = Math.min((actual / layer.budgetGb) * 100, 100);
          return (
            <div key={layer.id} className="flex-1 group relative">
              <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, backgroundColor: layer.color }}
                />
              </div>
              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
                <div className="bg-slate-800 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap shadow-lg">
                  {layer.id} {layer.name}: {actual.toFixed(1)}/{layer.budgetGb}GB ({pct.toFixed(0)}%)
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════════

export default function KnowledgeBasePage() {
  const [activeTab, setActiveTab] = useState<TabKey>("graph");

  return (
    <div className="flex flex-col h-full bg-[#f8f9fb] overflow-hidden">
      {/* 世界观资产总览横幅 */}
      <WorldviewOverviewBanner />

      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-3 bg-white border-b border-gray-100">
        <div className="flex-1">
          <p className="text-[12px] text-gray-500">数据图谱、系统数据库与用户知识库的统一入口</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-6 py-2 bg-white border-b border-gray-100">
        {([
          { key: "graph" as TabKey, label: "数据图谱", icon: BarChart3 },
          { key: "system" as TabKey, label: "系统数据库", icon: Server },
          { key: "user" as TabKey, label: "用户数据库", icon: FolderOpen },
        ]).map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-colors ${
                active
                  ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                  : "text-gray-500 hover:bg-gray-50"
              }`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "graph" && <DataGraphTab />}
        {activeTab === "system" && <SystemDBTab />}
        {activeTab === "user" && <UserDBTab />}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 1: 数据图谱 — 10层世界观架构可视化
// ═══════════════════════════════════════════════════════════════════════════════

function DataGraphTab() {
  const [selectedLayer, setSelectedLayer] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<{
    nodes: Array<{
      id: string; label: string; type: string; coverage_score: number;
      color: string; status: string; parent?: string; kb_ids?: string[];
      actual_kbs?: number; planned_kbs?: number; actual_files?: number;
    }>;
    edges: Array<{ source: string; target: string; strength: number }>;
    summary?: any;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDataGraph()
      .then((d) => setGraphData(d))
      .catch(() => setGraphData(null))
      .finally(() => setLoading(false));
  }, []);

  const summary = graphData?.summary || {};

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-gray-300" />
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: 10层架构 + 领域覆盖 */}
      <div className="flex-1 overflow-auto p-6">
        {/* 10层架构金字塔 */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[14px] font-semibold text-gray-900">10层世界观架构</h3>
            <span className="text-[11px] text-gray-400">点击层查看详情</span>
          </div>
          <div className="space-y-2">
            {WORLDVIEW_LAYERS.map((layer) => {
              const actual = getLayerActualGb(layer.id);
              const pct = Math.min((actual / layer.budgetGb) * 100, 100);
              const isSelected = selectedLayer === layer.id;
              const LayerIcon = layer.icon;

              return (
                <button
                  key={layer.id}
                  onClick={() => setSelectedLayer(isSelected ? null : layer.id)}
                  className={`w-full text-left rounded-xl border transition-all ${
                    isSelected
                      ? "ring-2 shadow-md"
                      : "hover:shadow-sm"
                  }`}
                  style={{
                    backgroundColor: layer.bgColor,
                    borderColor: isSelected ? layer.color : layer.borderColor,
                    ringColor: layer.color,
                  }}
                >
                  <div className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {/* 图标 */}
                      <div
                        className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                        style={{ backgroundColor: layer.color + "20" }}
                      >
                        <LayerIcon size={18} style={{ color: layer.color }} />
                      </div>

                      {/* 信息 */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-bold px-1.5 py-0.5 rounded"
                            style={{ backgroundColor: layer.color, color: "white" }}>
                            {layer.id}
                          </span>
                          <span className="text-[13px] font-semibold text-gray-900">{layer.name}</span>
                          <span className="text-[11px] text-gray-400">{layer.nameEn}</span>
                        </div>
                        <p className="text-[11px] text-gray-500 mt-0.5 truncate">{layer.description}</p>
                      </div>

                      {/* 数据指标 */}
                      <div className="flex items-center gap-4 shrink-0">
                        <div className="text-right">
                          <p className="text-[11px] text-gray-400">预算</p>
                          <p className="text-[13px] font-semibold text-gray-700">{layer.budgetGb}GB</p>
                        </div>
                        <div className="text-right">
                          <p className="text-[11px] text-gray-400">已下载</p>
                          <p className="text-[13px] font-semibold" style={{ color: layer.color }}>
                            {actual.toFixed(1)}GB
                          </p>
                        </div>
                        <div className="text-right w-14">
                          <p className="text-[11px] text-gray-400">覆盖率</p>
                          <p className="text-[13px] font-bold" style={{ color: pct >= 50 ? "#10b981" : pct >= 20 ? "#f59e0b" : "#ef4444" }}>
                            {pct.toFixed(0)}%
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* 进度条 */}
                    <div className="mt-2.5 flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-white/60 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${pct}%`, backgroundColor: layer.color }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-400 w-10 text-right">{layer.sourceCount} 数据源</span>
                    </div>
                  </div>

                  {/* 展开详情 */}
                  {isSelected && <LayerDetailPanel layer={layer} actualGb={actual} />}
                </button>
              );
            })}
          </div>
        </div>

        {/* 传统领域覆盖卡片 */}
        <LayerCoverageCards summary={summary} />
      </div>

      {/* Right: 选中层的详情 */}
      {selectedLayer && !WORLDVIEW_LAYERS.find(l => l.id === selectedLayer) && (
        <div className="w-80 border-l border-gray-200 bg-white overflow-auto">
          <GraphNodeDetailPanel
            nodes={graphData?.nodes || []}
            selectedId={selectedLayer}
            onClose={() => setSelectedLayer(null)}
          />
        </div>
      )}
    </div>
  );
}

// 层详情面板
function LayerDetailPanel({ layer, actualGb }: { layer: WorldviewLayer; actualGb: number }) {
  const pct = Math.min((actualGb / layer.budgetGb) * 100, 100);
  const status = pct >= 50 ? "良好" : pct >= 20 ? "一般" : "需补充";
  const statusColor = pct >= 50 ? "#10b981" : pct >= 20 ? "#f59e0b" : "#ef4444";

  // 该层的关键数据源（示例数据）
  const keySources: Record<string, string[]> = {
    L0: ["Wikidata Schema本体", "Schema.org本体", "DBpedia Ontology", "OpenKG schema"],
    L1: ["巨潮资讯A股年报", "国家统计局", "世界银行数据", "联合国数据", "中国人民银行"],
    L2: ["Wikidata实体关系", "OpenKG知识图谱", "供应链数据", "社交网络关系"],
    L3: ["arXiv因果推断", "经济机制模型", "物理机制论文", "医学机制文献"],
    L4: ["法律法规库", "证监会规章", "行业标准", "国际条约"],
    L5: ["认知科学论文", "决策理论", "思维模型库", "心理学研究"],
    L6: ["GitHub工程代码", "算法实现", "技术文档", "最佳实践指南"],
    L7: ["多模态数据集", "图文对齐数据", "视频理解数据"],
    L8: ["A股历史序列", "宏观经济时序", "政策演变轨迹"],
    L9: ["误差分析数据", "反面证据库", "边界条件案例"],
  };

  const sources = keySources[layer.id] || [];

  return (
    <div className="px-4 pb-4 border-t border-gray-100/50">
      <div className="pt-3 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-gray-500">状态:</span>
          <span className="text-[12px] font-medium px-2 py-0.5 rounded-full"
            style={{ backgroundColor: statusColor + "15", color: statusColor }}>
            {status}
          </span>
          <span className="text-[11px] text-gray-400 ml-auto">
            剩余空间: {(layer.budgetGb - actualGb).toFixed(1)}GB
          </span>
        </div>

        <div>
          <p className="text-[11px] font-semibold text-gray-500 mb-1.5">关键数据源</p>
          <div className="flex flex-wrap gap-1.5">
            {sources.map((s) => (
              <span
                key={s}
                className="px-2 py-1 rounded-lg text-[11px] border"
                style={{
                  backgroundColor: layer.bgColor,
                  borderColor: layer.borderColor,
                  color: "#374151",
                }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="bg-white/60 rounded-lg p-2 text-center">
            <p className="text-[10px] text-gray-400">置信度范围</p>
            <p className="text-[12px] font-semibold text-gray-700">0.7 - 1.0</p>
          </div>
          <div className="bg-white/60 rounded-lg p-2 text-center">
            <p className="text-[10px] text-gray-400">来源优先级</p>
            <p className="text-[12px] font-semibold text-gray-700">P0 - P2</p>
          </div>
          <div className="bg-white/60 rounded-lg p-2 text-center">
            <p className="text-[10px] text-gray-400">时间范围</p>
            <p className="text-[12px] font-semibold text-gray-700">2020-2026</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// 传统领域覆盖卡片
function LayerCoverageCards({ summary }: { summary: any }) {
  const domainNodes = summary?.domain_nodes || [];
  if (!domainNodes.length) return null;

  return (
    <div>
      <h3 className="text-[14px] font-semibold text-gray-900 mb-3">领域覆盖详情</h3>
      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          { label: "计划知识库", value: summary?.total_planned_kbs || 0, unit: "个" },
          { label: "实际知识库", value: summary?.total_actual_kbs || 0, unit: "个" },
          { label: "实际文档", value: summary?.total_actual_files || 0, unit: "篇" },
          { label: "覆盖率", value: `${summary?.total_kb_coverage_pct || 0}%`, unit: "" },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-[11px] text-gray-400 font-medium">{s.label}</p>
            <p className="text-[22px] font-bold text-gray-900 mt-1">
              {s.value}
              <span className="text-[12px] font-normal text-gray-400 ml-0.5">{s.unit}</span>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function GraphNodeDetailPanel({ nodes, selectedId, onClose }: { nodes: any[]; selectedId: string; onClose: () => void }) {
  const node = nodes.find((n) => n.id === selectedId);
  if (!node) return null;

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[14px] font-semibold text-gray-900">{node.label}</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
          <X size={14} className="text-gray-400" />
        </button>
      </div>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-gray-500">覆盖率</span>
          <span className="text-[13px] font-medium" style={{ color: node.color }}>{node.coverage_score}%</span>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 2: 系统数据库 — 按10层分组
// ═══════════════════════════════════════════════════════════════════════════════

function SystemDBTab() {
  const [sources, setSources] = useState<OfficialDataSource[]>([]);
  const [systemKbs, setSystemKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedLayerFilter, setSelectedLayerFilter] = useState<string | "all">("all");
  const [detailSource, setDetailSource] = useState<OfficialDataSource | null>(null);

  useEffect(() => {
    Promise.all([
      api.listOfficialSources(),
      api.listKBs("corp"),
    ])
      .then(([srcRes, kbRes]) => {
        setSources(srcRes.sources || []);
        setSystemKbs(kbRes.items || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = sources.filter((s) => {
    const matchLayer = selectedLayerFilter === "all" || s.domain_tags?.some((t) => t.includes(selectedLayerFilter));
    const matchSearch =
      !search ||
      s.name.includes(search) ||
      s.description?.includes(search) ||
      s.domain_tags?.some((t) => t.includes(search));
    return matchLayer && matchSearch;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-gray-300" />
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main grid */}
      <div className="flex-1 overflow-auto p-6">
        {/* Search + layer filter */}
        <div className="flex items-center gap-3 mb-5">
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white border border-gray-200 flex-1 max-w-md">
            <Search size={14} className="text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索系统数据库…"
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-gray-300"
            />
          </div>
        </div>

        {/* 10层过滤标签 */}
        <div className="flex items-center gap-1.5 mb-4 flex-wrap">
          <button
            onClick={() => setSelectedLayerFilter("all")}
            className={`px-3 py-1.5 rounded-lg text-[11px] transition-colors ${
              selectedLayerFilter === "all"
                ? "bg-slate-800 text-white"
                : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            全部
          </button>
          {WORLDVIEW_LAYERS.map((layer) => {
            const isActive = selectedLayerFilter === layer.id;
            return (
              <button
                key={layer.id}
                onClick={() => setSelectedLayerFilter(isActive ? "all" : layer.id)}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] transition-colors border ${
                  isActive
                    ? "text-white"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
                style={{
                  backgroundColor: isActive ? layer.color : layer.bgColor,
                  borderColor: isActive ? layer.color : layer.borderColor,
                }}
              >
                <layer.icon size={12} />
                {layer.id} {layer.name}
              </button>
            );
          })}
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 mb-4 text-[12px] text-gray-500">
          <span>共 {sources.length} 个数据源</span>
          <span>·</span>
          <span>{systemKbs.length} 个已入库系统知识库</span>
          <span>·</span>
          <span>筛选后 {filtered.length} 个</span>
        </div>

        {/* Card grid */}
        <div className="grid grid-cols-3 gap-4">
          {filtered.map((src) => {
            const matchedKb = systemKbs.find(
              (kb) =>
                kb.name.includes(src.key) ||
                src.name.includes(kb.name) ||
                kb.kb_type === src.source_type
            );
            // 查找该数据源所属的世界观层
            const layer = WORLDVIEW_LAYERS.find((l) =>
              src.domain_tags?.some((t) => t.includes(l.id))
            ) || WORLDVIEW_LAYERS[1];

            return (
              <button
                key={src.key}
                onClick={() => setDetailSource(src)}
                className="text-left bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md hover:border-emerald-200 transition-all group"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold text-white shrink-0"
                      style={{ background: layer.color }}
                    >
                      {layer.id}
                    </span>
                    <span className="text-[13px] font-semibold text-gray-900 truncate">{src.name}</span>
                  </div>
                  {matchedKb && (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 text-[10px] font-medium">
                      已入库
                    </span>
                  )}
                </div>
                <p className="text-[12px] text-gray-500 line-clamp-2 mb-3">{src.description}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  {src.domain_tags?.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="px-1.5 py-0.5 rounded text-[10px]"
                      style={{
                        backgroundColor: layer.bgColor,
                        color: layer.color,
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-50">
                  <span className="text-[11px] text-gray-400">{src.coverage}</span>
                  <ChevronRight
                    size={14}
                    className="text-gray-300 group-hover:text-emerald-500 transition-colors"
                  />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Detail drawer */}
      {detailSource && (
        <div className="w-96 border-l border-gray-200 bg-white overflow-auto">
          <SystemSourceDetail
            source={detailSource}
            matchedKb={systemKbs.find(
              (kb) =>
                kb.name.includes(detailSource.key) ||
                detailSource.name.includes(kb.name)
            )}
            onClose={() => setDetailSource(null)}
          />
        </div>
      )}
    </div>
  );
}

function SystemSourceDetail({
  source,
  matchedKb,
  onClose,
}: {
  source: OfficialDataSource;
  matchedKb?: KnowledgeBase;
  onClose: () => void;
}) {
  const [samples, setSamples] = useState<Array<{ kb_id: number; kb_name: string; content: string }>>([]);

  useEffect(() => {
    api.getOfficialSourceSample(source.key)
      .then((r) => setSamples(r.samples || []))
      .catch(() => setSamples([]));
  }, [source.key]);

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-white font-bold"
            style={{ background: source.icon_color, fontSize: 13 }}
          >
            {source.name.charAt(0)}
          </span>
          <span className="text-[15px] font-semibold text-gray-900">{source.name}</span>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100">
          <X size={16} className="text-gray-400" />
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1">描述</p>
          <p className="text-[13px] text-gray-700 leading-relaxed">{source.description}</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-[11px] text-gray-400">分类</p>
            <p className="text-[13px] font-medium text-gray-800 mt-0.5">{source.category}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-[11px] text-gray-400">数据范围</p>
            <p className="text-[13px] font-medium text-gray-800 mt-0.5">{source.coverage}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-[11px] text-gray-400">文档数</p>
            <p className="text-[13px] font-medium text-gray-800 mt-0.5">{(source.doc_count || 0).toLocaleString()}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-[11px] text-gray-400">状态</p>
            <p className="text-[13px] font-medium mt-0.5">
              {matchedKb ? (
                <span className="text-emerald-600">已入库 ({matchedKb.chunk_count || 0} 切片)</span>
              ) : (
                <span className="text-gray-400">未入库</span>
              )}
            </p>
          </div>
        </div>

        {source.sample_queries && source.sample_queries.length > 0 && (
          <div>
            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-2">示例查询</p>
            <div className="space-y-1.5">
              {source.sample_queries.map((q, i) => (
                <div
                  key={i}
                  className="px-3 py-2 rounded-lg bg-gray-50 text-[12px] text-gray-600"
                >
                  {q}
                </div>
              ))}
            </div>
          </div>
        )}

        {samples.length > 0 && (
          <div>
            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-2">内容预览</p>
            <div className="space-y-2">
              {samples.map((s, i) => (
                <div key={i} className="p-3 rounded-lg bg-gray-50 border border-gray-100">
                  <p className="text-[10px] text-gray-400 mb-1">{s.kb_name}</p>
                  <p className="text-[12px] text-gray-600 line-clamp-4">{s.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 3: 用户数据库 (preserved from original)
// ═══════════════════════════════════════════════════════════════════════════════

function UserDBTab() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const selected = kbs.find((k) => k.id === selectedId) || null;

  const loadKBs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listKBs();
      setKbs(res.items || []);
      if (res.items?.length && selectedId == null) setSelectedId(res.items[0].id);
    } catch (e) {
      setMsg({ type: "err", text: String((e as Error)?.message || e) });
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  const loadDocs = useCallback(async (kbId: number) => {
    try {
      const res = await api.listKBDocuments(kbId);
      setDocs(res.items || []);
    } catch {
      setDocs([]);
    }
  }, []);

  useEffect(() => {
    loadKBs();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (selectedId != null) loadDocs(selectedId);
  }, [selectedId, loadDocs]);

  const handleUpload = useCallback(
    async (files: FileList | File[]) => {
      if (selectedId == null) return;
      setUploading(true);
      setMsg(null);
      let ok = 0, fail = 0;
      for (const file of Array.from(files)) {
        try {
          await api.uploadKBDocument(selectedId, file);
          ok++;
        } catch {
          fail++;
        }
      }
      setUploading(false);
      setMsg({
        type: fail ? "err" : "ok",
        text: `入库完成：成功 ${ok}${fail ? `，失败 ${fail}` : ""}`,
      });
      await loadDocs(selectedId);
      await loadKBs();
    },
    [selectedId, loadDocs, loadKBs]
  );

  const handleDeleteDoc = useCallback(
    async (docId: number) => {
      if (selectedId == null) return;
      try {
        await api.deleteKBDocument(selectedId, docId);
        await loadDocs(selectedId);
        await loadKBs();
      } catch (e) {
        setMsg({ type: "err", text: String((e as Error)?.message || e) });
      }
    },
    [selectedId, loadDocs, loadKBs]
  );

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: KB list */}
      <div className="w-72 shrink-0 border-r border-gray-100 bg-white overflow-auto">
        <div className="p-3 border-b border-gray-100">
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center justify-center gap-1.5 w-full px-3 py-2 rounded-lg bg-emerald-500 text-white text-[13px] font-medium hover:bg-emerald-600 transition-colors"
          >
            <Plus size={15} /> 新建知识库
          </button>
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-32 text-gray-400">
            <Loader2 size={20} className="animate-spin" />
          </div>
        ) : kbs.length === 0 ? (
          <div className="text-center mt-12 px-6">
            <Layers size={32} className="mx-auto text-gray-300 mb-2" />
            <p className="text-[13px] text-gray-400">还没有知识库</p>
            <p className="text-[11px] text-gray-300 mt-1">点击「新建知识库」开始构造你的语义库</p>
          </div>
        ) : (
          <div className="p-2">
            {kbs.map((kb) => (
              <button
                key={kb.id}
                onClick={() => setSelectedId(kb.id)}
                className={`w-full text-left rounded-xl px-3 py-2.5 mb-1 transition-colors ${
                  selectedId === kb.id
                    ? "bg-emerald-50 ring-1 ring-emerald-200"
                    : "hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-[16px]">{typeIcon(kb.kb_type)}</span>
                  <span className="text-[13px] font-medium text-gray-800 truncate flex-1">
                    {kb.name}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1 text-[11px] text-gray-400">
                  <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                    {kb.type_label || kb.kb_type}
                  </span>
                  <span>{kb.doc_count || 0} 篇</span>
                  <span>·</span>
                  <span>{kb.size_display || "0 B"}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right: KB detail */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selected ? (
          <>
            {/* KB summary */}
            <div className="px-6 py-4 border-b border-gray-100 bg-white">
              <div className="flex items-center gap-2">
                <span className="text-[20px]">{typeIcon(selected.kb_type)}</span>
                <h2 className="text-[15px] font-semibold text-gray-900">{selected.name}</h2>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600">
                  {selected.type_label || selected.kb_type}
                </span>
              </div>
              <div className="flex items-center gap-4 mt-2 text-[12px] text-gray-500">
                <span className="flex items-center gap-1">
                  <FileStack size={13} /> {selected.doc_count || 0} 篇文档
                </span>
                <span className="flex items-center gap-1">
                  <Layers size={13} /> {selected.chunk_count || 0} 切片
                </span>
                <span className="flex items-center gap-1">
                  <HardDrive size={13} /> {selected.size_display || "0 B"}
                </span>
              </div>
            </div>

            <div className="flex-1 overflow-auto p-6 space-y-4">
              {/* Upload zone */}
              <div
                onDrop={(e) => {
                  e.preventDefault();
                  if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files);
                }}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => fileInput.current?.click()}
                className="border-2 border-dashed border-emerald-200 rounded-2xl p-8 text-center cursor-pointer hover:border-emerald-400 hover:bg-emerald-50/50 transition-all"
              >
                {uploading ? (
                  <Loader2
                    size={28}
                    className="mx-auto text-emerald-500 animate-spin mb-2"
                  />
                ) : (
                  <Upload size={28} className="mx-auto text-emerald-400 mb-2" />
                )}
                <p className="text-[13px] text-gray-600 font-medium">
                  {uploading ? "正在入库（分块 + embedding）…" : "拖拽或点击上传文档"}
                </p>
                <p className="text-[11px] text-gray-400 mt-1">
                  PDF / DOCX / TXT / MD / Excel / CSV — 支持多选批量入库
                </p>
                <input
                  ref={fileInput}
                  type="file"
                  multiple
                  className="hidden"
                  accept=".pdf,.docx,.doc,.txt,.md,.markdown,.xlsx,.xls,.csv,.json"
                  onChange={(e) => {
                    if (e.target.files?.length) handleUpload(e.target.files);
                    e.target.value = "";
                  }}
                />
              </div>

              {msg && (
                <div
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-[12px] ${
                    msg.type === "ok"
                      ? "bg-green-50 text-green-700"
                      : "bg-red-50 text-red-600"
                  }`}
                >
                  {msg.type === "ok" ? (
                    <CheckCircle2 size={13} />
                  ) : (
                    <AlertCircle size={13} />
                  )}
                  {msg.text}
                </div>
              )}

              {/* Document list */}
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50 text-[12px] font-semibold text-gray-600">
                  文档列表（{docs.length}）
                </div>
                {docs.length === 0 ? (
                  <div className="text-center py-10 text-gray-400">
                    <FileText size={28} className="mx-auto text-gray-300 mb-2" />
                    <p className="text-[12px]">该知识库暂无文档，上传后将分块入库</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-50">
                    {docs.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 group"
                      >
                        <FileText size={15} className="text-gray-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] text-gray-800 truncate">{doc.title}</p>
                          <p className="text-[11px] text-gray-400">
                            {doc.file_type?.toUpperCase()} · {doc.chunk_count || 0} 切片
                            {doc.status === "error" && (
                              <span className="text-red-500 ml-1">· 解析失败</span>
                            )}
                            {doc.status === "indexed" && (
                              <span className="text-green-500 ml-1">· 已索引</span>
                            )}
                          </p>
                        </div>
                        <button
                          onClick={() => handleDeleteDoc(doc.id)}
                          className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-all"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Database size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-[13px] text-gray-400">选择或新建一个知识库</p>
            </div>
          </div>
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <CreateKBModal
          onClose={() => setShowCreate(false)}
          onCreated={async (kb) => {
            setShowCreate(false);
            await loadKBs();
            setSelectedId(kb.id);
          }}
        />
      )}
    </div>
  );
}

function CreateKBModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (kb: KnowledgeBase) => void;
}) {
  const [name, setName] = useState("");
  const [kbType, setKbType] = useState("finance");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!name.trim()) {
      setErr("请填写知识库名称");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const kb = await api.createKB(name.trim(), {
        kb_type: kbType,
        description: desc.trim(),
      });
      onCreated(kb);
    } catch (e) {
      setErr(String((e as Error)?.message || e));
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl w-[440px] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[15px] font-semibold text-gray-900">新建知识库</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>

        <label className="block text-[12px] font-medium text-gray-600 mb-1">名称</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          placeholder="例如：2024 银行业年报库"
          className="w-full text-[13px] border border-gray-200 rounded-lg px-3 py-2 mb-3 focus:outline-none focus:border-emerald-400"
        />

        <label className="block text-[12px] font-medium text-gray-600 mb-1.5">
          领域分类
        </label>
        <div className="grid grid-cols-3 gap-1.5 mb-3">
          {KB_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => setKbType(t.value)}
              className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-[12px] border transition-colors ${
                kbType === t.value
                  ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                  : "border-gray-200 text-gray-600 hover:border-gray-300"
              }`}
            >
              <span>{t.icon}</span> {t.label}
            </button>
          ))}
        </div>

        <label className="block text-[12px] font-medium text-gray-600 mb-1">
          描述（可选）
        </label>
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          rows={2}
          placeholder="这个库收录什么内容…"
          className="w-full text-[13px] border border-gray-200 rounded-lg px-3 py-2 mb-3 resize-none focus:outline-none focus:border-emerald-400"
        />

        {err && <p className="text-[12px] text-red-500 mb-2">{err}</p>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg text-[13px] text-gray-600 hover:bg-gray-100"
          >
            取消
          </button>
          <button
            onClick={submit}
            disabled={busy}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 text-white text-[13px] font-medium hover:bg-emerald-600 disabled:opacity-40"
          >
            {busy ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Plus size={14} />
            )}{" "}
            创建
          </button>
        </div>
      </div>
    </div>
  );
}
