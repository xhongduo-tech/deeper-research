/**
 * KnowledgeBasePage — 数据库中心 v3
 *
 * 变更：
 * - SystemKBTab 使用新公开接口 /api/kb/system，展示真实 28K+ 文档数据
 * - ProjectKBTab 支持直接新建项目，不再提示去主界面
 * - 页面内容居中（max-w 1160px，mx-auto）
 * - 结构化数据 vs 知识文档 双通道上传
 */
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Database, Plus, Upload, FileText, Trash2, Loader2, X,
  CheckCircle2, AlertCircle, Search, RefreshCw,
  Network, GitBranch, CircleDot,
  Globe, ChevronDown, HardDrive,
  FolderOpen, BookOpen, Zap, BarChart3,
  Table2, Brain, Sheet,
} from "lucide-react";
import { api, KnowledgeBase, KBDocument, OfficialDataSource, Project, UploadedFileRecord } from "../lib/api";
import OntologyEditor from "./OntologyEditor";

type TabKey = "system" | "project" | "ontology";

// ─── helpers ──────────────────────────────────────────────────────────────────

async function safeCall<T>(promise: Promise<T>, fallback: T, timeoutMs = 8000): Promise<T> {
  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, rej) => setTimeout(() => rej(new Error("timeout")), timeoutMs)),
    ]);
  } catch {
    return fallback;
  }
}

function fmt(n: number | undefined | null): string {
  if (!n) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
function fmtSize(bytes: number | undefined | null): string {
  if (!bytes) return "—";
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(1)} KB`;
  return `${bytes} B`;
}
function isStructured(n: string) { return /\.(csv|xlsx|xls|parquet|tsv|ods)$/i.test(n); }

const CAT_COLORS: Record<string, { bg: string; text: string }> = {
  "金融数据":  { bg: "#fef9c3", text: "#854d0e" },
  "行政政务":  { bg: "#dbeafe", text: "#1e40af" },
  "学术研究":  { bg: "#f3e8ff", text: "#6b21a8" },
  "法律法规":  { bg: "#fce7f3", text: "#9d174d" },
  "产业数据":  { bg: "#d1fae5", text: "#065f46" },
  "企业信息":  { bg: "#e0f2fe", text: "#0369a1" },
  "新闻舆情":  { bg: "#fef3c7", text: "#92400e" },
  "健康医疗":  { bg: "#dcfce7", text: "#15803d" },
  "科技创新":  { bg: "#ede9fe", text: "#5b21b6" },
};
function CatBadge({ category }: { category: string }) {
  const c = CAT_COLORS[category] || { bg: "var(--bg-subtle)", text: "var(--ink-600)" };
  return (
    <span style={{ display:"inline-flex", alignItems:"center", height:18, padding:"0 7px", borderRadius:99,
      background:c.bg, color:c.text, fontSize:10.5, fontWeight:650, whiteSpace:"nowrap" }}>
      {category}
    </span>
  );
}

const KB_TYPE_LABELS: Record<string, string> = {
  general:"通用", policy:"政策法规", research:"研究报告",
  finance:"金融数据", tech:"技术文档", news:"新闻舆情",
  academic:"学术论文", code:"代码工程", math:"数学知识",
  statistics:"统计数据", law:"法律法规", trade:"贸易数据",
  gov:"政府报告", banking:"银行年报",
};
const KB_TYPE_COLORS: Record<string, string> = {
  academic:"#6366f1", code:"#0ea5e9", statistics:"#10b981",
  policy:"#f59e0b", law:"#8b5cf6", finance:"#ec4899",
  news:"#f97316", math:"#14b8a6", trade:"#64748b",
};

// ─── Main ──────────────────────────────────────────────────────────────────────

export default function KnowledgeBasePage({
  initialTab, initialProjectSubTab, initialProjectId,
}: { initialTab?: TabKey; initialProjectSubTab?: "tables" | "graph"; initialProjectId?: number; }) {
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab ?? "project");

  const TABS = [
    { key: "system" as TabKey,   label: "系统知识库", icon: Globe },
    { key: "project" as TabKey,  label: "项目数据库", icon: FolderOpen },
    { key: "ontology" as TabKey, label: "本体建模",   icon: Network },
  ];

  return (
    <div className="min-h-full w-full flex flex-col items-center px-6 py-6 pb-20">
      <style>{`
        @keyframes kb-in { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        .kb-in { animation: kb-in .35s cubic-bezier(.22,1,.36,1) both; }
        .kb-row:hover { background: var(--hover) !important; }
        .kb-card:hover { border-color:rgba(91,78,232,.3)!important; box-shadow:0 2px 8px rgba(91,78,232,.06)!important; }
        .drop-zone-active { border-color:var(--brand)!important; background:rgba(91,78,232,.04)!important; }
      `}</style>

      <div className="w-full" style={{ maxWidth: 1160 }}>
        <div className="mb-6 kb-in">
          <h1 style={{ fontSize:22, fontWeight:720, letterSpacing:"-.02em", color:"var(--ink-900)" }}>数据库</h1>
          <p style={{ fontSize:13, color:"var(--ink-400)", marginTop:4 }}>系统知识库 · 项目数据库 · 本体建模</p>
        </div>

        <div className="flex items-center gap-1 mb-6 kb-in"
          style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)", borderRadius:12, padding:4, width:"fit-content" }}>
          {TABS.map(({ key, label, icon: Icon }) => {
            const active = activeTab === key;
            return (
              <button key={key} onClick={() => setActiveTab(key)}
                className="flex items-center gap-1.5 transition-all"
                style={{ height:32, padding:"0 14px", borderRadius:9, fontSize:13,
                  fontWeight: active ? 650 : 500,
                  background: active ? "var(--ink-900)" : "transparent",
                  color: active ? "#fff" : "var(--ink-500)" }}>
                <Icon size={14} />{label}
              </button>
            );
          })}
        </div>

        <div className="kb-in">
          {activeTab === "system"   && <SystemKBTab />}
          {activeTab === "project"  && <ProjectKBTab initialSubTab={initialProjectSubTab} initialProjectId={initialProjectId} />}
          {activeTab === "ontology" && <OntologyTab />}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 1: 系统知识库
// 使用 /api/kb/system（公开接口）+ /api/v1/official-sources（公开接口）
// ═══════════════════════════════════════════════════════════════════════════════

type SystemKBItem = KnowledgeBase & { type_label: string };

function SystemKBTab() {
  const [sources, setSources]   = useState<OfficialDataSource[]>([]);
  const [kbs, setKBs]           = useState<SystemKBItem[]>([]);
  const [sysStats, setSysStats] = useState<{ total_docs: number; total_size: number } | null>(null);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState("");
  const [activeCat, setActiveCat] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [activeKbType, setActiveKbType] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [srcRes, kbRes] = await Promise.all([
      safeCall(api.listOfficialSources(), { sources: [], categories: [], by_category: {} }),
      safeCall(api.listSystemKBs(), { items: [], total: 0, total_docs: 0, total_size: 0, size_display: "—" }),
    ]);
    setSources(srcRes.sources || []);
    setKBs((kbRes.items || []) as SystemKBItem[]);
    setSysStats({ total_docs: kbRes.total_docs || 0, total_size: kbRes.total_size || 0 });
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const offlineDocs  = sources.reduce((a, s) => a + (s.offline_doc_count || 0), 0);
  const activeSrcs   = sources.filter((s) => s.is_active).length;
  const kbTypes      = Array.from(new Set(kbs.map((k) => k.kb_type).filter(Boolean)));
  const categories   = Array.from(new Set(sources.map((s) => s.category).filter(Boolean)));

  const filteredSrcs = sources.filter((s) => {
    const mc = !activeCat  || s.category === activeCat;
    const ms = !search || s.name.includes(search) || (s.description || "").includes(search);
    return mc && ms;
  });
  const filteredKBs = kbs.filter((k) => !activeKbType || k.kb_type === activeKbType);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 gap-2">
        <Loader2 size={18} className="animate-spin" style={{ color:"var(--ink-300)" }} />
        <span style={{ fontSize:13, color:"var(--ink-400)" }}>加载中…</span>
      </div>
    );
  }

  return (
    <div>
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {[
          { label:"数据源",    value:fmt(sources.length),            sub:`${activeSrcs} 已激活`,       icon:Globe,    color:"#6366f1" },
          { label:"官方数据量", value:fmt(sources.reduce((a,s)=>a+(s.doc_count||0),0)), sub:"各源累计", icon:FileText, color:"#0ea5e9" },
          { label:"离线预载",  value:fmt(offlineDocs),               sub:"可离线使用",                  icon:HardDrive, color:"#10b981" },
          { label:"系统 KB",   value:fmt(kbs.length),                sub:`${fmt(sysStats?.total_docs)} 文档`, icon:Database, color:"#f59e0b" },
          { label:"语料体积",  value:fmtSize(sysStats?.total_size), sub:"已入库文本",                  icon:BarChart3, color:"#8b5cf6" },
        ].map((s) => (
          <div key={s.label} className="rounded-xl p-4 kb-card transition-all"
            style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)" }}>
            <div className="flex items-center gap-1.5 mb-1.5">
              <s.icon size={13} style={{ color:s.color }} />
              <span style={{ fontSize:11, color:"var(--ink-400)", fontWeight:500 }}>{s.label}</span>
            </div>
            <div style={{ fontSize:20, fontWeight:720, color:"var(--ink-900)", lineHeight:1.2 }}>{s.value}</div>
            <div style={{ fontSize:10.5, color:"var(--ink-400)", marginTop:2 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* ── Section 1: System KBs ───────────────────────────────── */}
      {kbs.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <h3 className="flex items-center gap-2" style={{ fontSize:14, fontWeight:650, color:"var(--ink-700)" }}>
              <Database size={14} style={{ color:"var(--ink-400)" }} />
              已入库知识库
              <span style={{ fontSize:10.5, padding:"1px 7px", borderRadius:99, background:"var(--bg-subtle)", color:"var(--ink-400)", fontWeight:500 }}>
                {kbs.length}
              </span>
            </h3>
            {/* KB type filter */}
            <div className="flex flex-wrap gap-1.5 ml-2">
              {kbTypes.map((t) => (
                <button key={t} onClick={() => setActiveKbType(activeKbType === t ? null : t)}
                  style={{ height:22, padding:"0 8px", borderRadius:99, fontSize:11, fontWeight:550,
                    background: activeKbType === t ? (KB_TYPE_COLORS[t!] || "var(--ink-900)") : "var(--bg-subtle)",
                    color: activeKbType === t ? "#fff" : "var(--ink-600)",
                    border: `1px solid ${activeKbType === t ? (KB_TYPE_COLORS[t!] || "var(--ink-900)") : "var(--border)"}`,
                    transition:"all .15s" }}>
                  {KB_TYPE_LABELS[t!] || t}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl overflow-hidden" style={{ border:"1px solid var(--border)" }}>
            {/* Header */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 100px 80px 90px 70px",
              background:"var(--bg-subtle)", padding:"7px 16px", borderBottom:"1px solid var(--border)",
              fontSize:11, fontWeight:650, color:"var(--ink-500)" }}>
              <span>知识库名称</span><span>类型</span>
              <span className="text-right">文档数</span><span className="text-right">语料体积</span><span className="text-center">向量状态</span>
            </div>
            {filteredKBs.map((kb) => {
              const typeColor = KB_TYPE_COLORS[kb.kb_type || ""] || "#6b7280";
              const hasVectors = (kb.doc_count || 0) > 0;
              return (
                <div key={kb.id} className="kb-row" style={{
                  display:"grid", gridTemplateColumns:"1fr 100px 80px 90px 70px",
                  padding:"9px 16px", alignItems:"center", borderBottom:"1px solid var(--border)",
                  background:"var(--bg-elevated)", fontSize:13, transition:"background .12s",
                }}>
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="h-6 w-6 rounded flex items-center justify-center flex-shrink-0 text-[10px] font-bold"
                      style={{ background:`${typeColor}18`, color:typeColor }}>
                      {(kb.name || "").slice(0, 1)}
                    </span>
                    <p className="truncate font-medium" style={{ color:"var(--ink-900)" }}>{kb.name}</p>
                  </div>
                  <div>
                    <span style={{ fontSize:10.5, padding:"2px 6px", borderRadius:99,
                      background:`${typeColor}12`, color:typeColor, fontWeight:600 }}>
                      {KB_TYPE_LABELS[kb.kb_type || ""] || kb.kb_type}
                    </span>
                  </div>
                  <span className="text-right" style={{ fontSize:12.5, fontWeight:650, fontVariantNumeric:"tabular-nums",
                    color: (kb.doc_count || 0) > 0 ? "var(--ink-800)" : "var(--ink-300)" }}>
                    {fmt(kb.doc_count)}
                  </span>
                  <span className="text-right" style={{ fontSize:12, color:"var(--ink-500)", fontVariantNumeric:"tabular-nums" }}>
                    {fmtSize(kb.total_size)}
                  </span>
                  <div className="flex justify-center items-center gap-1">
                    <span style={{ width:7, height:7, borderRadius:999,
                      background: hasVectors ? "#10b981" : "#d1d5db", display:"inline-block" }} />
                    <span style={{ fontSize:10, color: hasVectors ? "#059669" : "var(--ink-300)" }}>
                      {hasVectors ? "已入库" : "空"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Section 2: Official Data Sources ───────────────────── */}
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <h3 className="flex items-center gap-2" style={{ fontSize:14, fontWeight:650, color:"var(--ink-700)" }}>
            <Globe size={14} style={{ color:"var(--ink-400)" }} />
            官方数据源
            <span style={{ fontSize:10.5, padding:"1px 7px", borderRadius:99, background:"var(--bg-subtle)", color:"var(--ink-400)", fontWeight:500 }}>
              {sources.length}
            </span>
          </h3>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg ml-2"
            style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)" }}>
            <Search size={12} style={{ color:"var(--ink-400)" }} />
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索数据源…" className="bg-transparent text-[12px] outline-none w-36"
              style={{ color:"var(--ink-700)" }} />
            {search && <button onClick={() => setSearch("")}><X size={12} style={{ color:"var(--ink-400)" }} /></button>}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {categories.map((cat) => (
              <button key={cat} onClick={() => setActiveCat(activeCat === cat ? null : cat)}
                style={{ height:26, padding:"0 9px", borderRadius:8, fontSize:11.5, fontWeight:550,
                  background: activeCat === cat ? "var(--ink-900)" : "var(--bg-elevated)",
                  color: activeCat === cat ? "#fff" : "var(--ink-600)",
                  border:`1px solid ${activeCat === cat ? "var(--ink-900)" : "var(--border)"}`,
                  transition:"all .15s" }}>
                {cat}
              </button>
            ))}
          </div>
          <button onClick={load} className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
            style={{ fontSize:11.5, color:"var(--ink-400)", border:"1px solid var(--border)", background:"var(--bg-elevated)" }}>
            <RefreshCw size={11} /> 刷新
          </button>
        </div>

        {filteredSrcs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center rounded-xl"
            style={{ border:"1.5px dashed var(--border)" }}>
            <Globe size={28} style={{ color:"var(--ink-200)", marginBottom:10 }} />
            <p style={{ fontSize:13, color:"var(--ink-400)" }}>暂无官方数据源</p>
            <p style={{ fontSize:11.5, color:"var(--ink-300)", marginTop:3 }}>通过管理后台导入后显示</p>
          </div>
        ) : (
          <div className="rounded-xl overflow-hidden" style={{ border:"1px solid var(--border)" }}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 110px 100px 80px 80px 64px 28px",
              background:"var(--bg-subtle)", padding:"7px 16px", borderBottom:"1px solid var(--border)",
              fontSize:11, fontWeight:650, color:"var(--ink-500)" }}>
              <span>数据源</span><span>分类</span><span>覆盖范围</span>
              <span className="text-right">文档数</span><span className="text-right">离线索引</span>
              <span className="text-center">状态</span><span />
            </div>
            {filteredSrcs.map((src) => {
              const expanded = expandedKey === src.key;
              return (
                <div key={src.key} style={{ borderBottom:"1px solid var(--border)" }}>
                  <button className="kb-row w-full text-left"
                    onClick={() => setExpandedKey(expanded ? null : src.key)}
                    style={{ display:"grid", gridTemplateColumns:"1fr 110px 100px 80px 80px 64px 28px",
                      padding:"9px 16px", alignItems:"center",
                      background: expanded ? "rgba(91,78,232,.03)" : "var(--bg-elevated)", fontSize:13 }}>
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="h-7 w-7 rounded-lg flex items-center justify-center flex-shrink-0 text-[11px] font-bold"
                        style={{ background:src.icon_bg||"#eef2ff", color:src.icon_color||"#6366f1" }}>
                        {src.name.slice(0,1)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate font-medium" style={{ color:"var(--ink-900)" }}>{src.name}</p>
                        {src.description && <p className="truncate" style={{ color:"var(--ink-400)", fontSize:11, marginTop:1 }}>{src.description}</p>}
                      </div>
                    </div>
                    <div><CatBadge category={src.category} /></div>
                    <span style={{ fontSize:11.5, color:"var(--ink-500)" }}>{src.coverage||"—"}</span>
                    <span className="text-right" style={{ fontSize:12.5, fontWeight:600, color:"var(--ink-700)", fontVariantNumeric:"tabular-nums" }}>
                      {fmt(src.doc_count)}
                    </span>
                    <span className="text-right" style={{ fontSize:12, fontVariantNumeric:"tabular-nums",
                      fontWeight: src.offline_available ? 650 : 400,
                      color: src.offline_available ? "#059669" : "var(--ink-300)" }}>
                      {src.offline_available ? fmt(src.offline_doc_count) : "—"}
                    </span>
                    <div className="flex justify-center">
                      <span style={{ width:7, height:7, borderRadius:999, background:src.is_active?"#10b981":"#d1d5db", display:"inline-block" }} />
                    </div>
                    <ChevronDown size={13} style={{ color:"var(--ink-300)", transform:expanded?"rotate(180deg)":"rotate(0)", transition:"transform .2s" }} />
                  </button>
                  {expanded && (
                    <div style={{ padding:"10px 16px 14px 56px", background:"rgba(91,78,232,.025)", borderTop:"1px solid var(--border)" }}>
                      {src.description && <p style={{ fontSize:12, color:"var(--ink-600)", marginBottom:8 }}>{src.description}</p>}
                      {(src.sample_queries as string[]|undefined)?.length ? (
                        <div>
                          <p style={{ fontSize:11, fontWeight:650, color:"var(--ink-400)", marginBottom:5 }}>示例查询</p>
                          <div className="flex flex-wrap gap-1.5">
                            {(src.sample_queries as string[]).slice(0,4).map((q,i) => (
                              <span key={i} style={{ fontSize:11.5, padding:"2px 8px", borderRadius:6,
                                background:"var(--bg-subtle)", border:"1px solid var(--border)", color:"var(--ink-600)" }}>{q}</span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      <div className="flex gap-4 mt-2" style={{ fontSize:11, color:"var(--ink-400)" }}>
                        {src.source_type && <span>类型：{src.source_type}</span>}
                        {src.requires_api_key && <span style={{ color:"#f59e0b" }}>⚠ 需要 API Key</span>}
                        {src.last_synced_at && <span>同步：{new Date(src.last_synced_at).toLocaleDateString()}</span>}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 2: 项目数据库
// 三栏布局：项目列表 | 数据模式选择 | 文件/文档列表
// ═══════════════════════════════════════════════════════════════════════════════

type DataMode = "structured" | "documents";

const DATA_MODE_CONFIG = {
  structured: {
    label: "结构化数据",
    icon: Table2,
    color: "#2563eb",
    bg: "#eff6ff",
    border: "#bfdbfe",
    desc: "CSV · Excel · Parquet",
    hint: "自动注册为 DuckDB 数据表，支持自然语言查询",
    accept: ".csv,.xlsx,.xls,.parquet,.tsv",
    emptyText: "拖拽 CSV / Excel 文件到此处",
  },
  documents: {
    label: "知识文档",
    icon: Brain,
    color: "#7c3aed",
    bg: "#faf5ff",
    border: "#e9d5ff",
    desc: "PDF · Word · TXT · MD",
    hint: "向量化入库，参与 RAG 检索与本体建模",
    accept: ".pdf,.docx,.doc,.txt,.md,.pptx,.html",
    emptyText: "拖拽文档到此处上传",
  },
} as const;

function ProjectKBTab({ initialProjectId }: { initialSubTab?: "tables"|"graph"; initialProjectId?: number; }) {
  const [projects, setProjects]         = useState<Project[]>([]);
  const [selProjectId, setSelProjectId] = useState<number|null>(initialProjectId ?? null);
  const [dataMode, setDataMode]         = useState<DataMode>("structured");
  const [loading, setLoading]           = useState(true);
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [newProjectName, setNewProjectName]       = useState("");
  const [newProjectDesc, setNewProjectDesc]       = useState("");
  const [creatingProject, setCreatingProject]     = useState(false);

  // Structured files
  const [structFiles, setStructFiles]   = useState<UploadedFileRecord[]>([]);
  const [structLoading, setStructLoading] = useState(false);

  // KB / docs
  const [projectKBs, setProjectKBs]     = useState<KnowledgeBase[]>([]);
  const [selKbId, setSelKbId]           = useState<number|null>(null);
  const [docs, setDocs]                 = useState<KBDocument[]>([]);
  const [docsLoading, setDocsLoading]   = useState(false);
  const [showCreateKb, setShowCreateKb] = useState(false);
  const [newKbName, setNewKbName]       = useState("");

  const [uploading, setUploading]   = useState(false);
  const [dragging, setDragging]     = useState(false);
  const [msg, setMsg]               = useState<{type:"ok"|"err"; text:string}|null>(null);
  const structRef = useRef<HTMLInputElement>(null);
  const docRef    = useRef<HTMLInputElement>(null);

  const selKb = projectKBs.find((k) => k.id === selKbId);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    const res = await safeCall(api.listProjects(), { items:[], total:0 });
    const items = res.items || [];
    setProjects(items);
    if (!selProjectId && items[0]) setSelProjectId(items[0].id);
    setLoading(false);
  }, [selProjectId]);

  const loadStructured = useCallback(async () => {
    setStructLoading(true);
    const res = await safeCall(api.listFiles(), { files:[] });
    const all = (res.files || []) as UploadedFileRecord[];
    setStructFiles(all.filter((f) => isStructured(f.original_name || f.filename || "")));
    setStructLoading(false);
  }, []);

  const loadKBs = useCallback(async (pid: number) => {
    const res = await safeCall(api.listProjectKBs(pid), { items:[], total:0 });
    setProjectKBs(res.items || []);
    setSelKbId(null); setDocs([]);
  }, []);

  const loadDocs = useCallback(async (kbId: number) => {
    setDocsLoading(true);
    const res = await safeCall(api.listKBDocuments(kbId), { items:[], total:0 });
    setDocs(res.items || []);
    setDocsLoading(false);
  }, []);

  useEffect(() => { loadProjects(); }, []); // eslint-disable-line
  useEffect(() => { if (dataMode === "structured") loadStructured(); }, [dataMode, loadStructured]);
  useEffect(() => { if (selProjectId) loadKBs(selProjectId); }, [selProjectId, loadKBs]);
  useEffect(() => { if (selKbId) loadDocs(selKbId); }, [selKbId, loadDocs]);

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    setCreatingProject(true);
    try {
      const res = await api.createProject(newProjectName.trim(), newProjectDesc.trim());
      setNewProjectName(""); setNewProjectDesc(""); setShowCreateProject(false);
      await loadProjects();
      setSelProjectId((res as any).id);
      setMsg({ type:"ok", text:`项目「${(res as any).name}」已创建` });
    } catch {
      setMsg({ type:"err", text:"创建项目失败，请先登录" });
    }
    setCreatingProject(false);
  };

  const uploadStructured = async (file: File) => {
    if (!isStructured(file.name)) {
      setMsg({ type:"err", text:`格式不支持：${file.name.split(".").pop()?.toUpperCase()}。请上传 CSV / Excel / Parquet` });
      return;
    }
    setUploading(true);
    try {
      const up = await api.uploadFile(file);
      await api.duckdbRegister("project-" + (selProjectId || "0"), up.id);
      await loadStructured();
      setMsg({ type:"ok", text:`${file.name} 已上传并注册为数据表` });
    } catch { setMsg({ type:"err", text:`${file.name} 上传失败` }); }
    setUploading(false);
  };

  const uploadDoc = async (file: File) => {
    if (!selKbId) { setMsg({ type:"err", text:"请先选择或新建知识库" }); return; }
    setUploading(true);
    try {
      await api.uploadKBDocument(selKbId, file);
      await loadDocs(selKbId);
      setMsg({ type:"ok", text:`${file.name} 已加入知识库` });
    } catch { setMsg({ type:"err", text:`${file.name} 上传失败` }); }
    setUploading(false);
  };

  const createKB = async () => {
    if (!newKbName.trim()) return;
    try {
      const kb = await api.createKB(newKbName.trim(), { scope:"personal" });
      setNewKbName(""); setShowCreateKb(false);
      if (selProjectId) await loadKBs(selProjectId);
      setSelKbId(kb.id);
      setMsg({ type:"ok", text:"知识库已创建" });
    } catch { setMsg({ type:"err", text:"创建失败，请先登录" }); }
  };

  const deleteDoc = async (docId: number) => {
    if (!selKbId) return;
    try { await api.deleteKBDocument(selKbId, docId); await loadDocs(selKbId); }
    catch { setMsg({ type:"err", text:"删除失败" }); }
  };

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    for (const f of Array.from(e.dataTransfer.files)) {
      if (dataMode === "structured") await uploadStructured(f);
      else await uploadDoc(f);
    }
  };

  const cfg = DATA_MODE_CONFIG[dataMode];
  const ModeIcon = cfg.icon;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 gap-2">
        <Loader2 size={18} className="animate-spin" style={{ color:"var(--ink-300)" }} />
        <span style={{ fontSize:13, color:"var(--ink-400)" }}>加载项目…</span>
      </div>
    );
  }

  return (
    <div>
      {/* Toast */}
      {msg && (
        <div className="flex items-center gap-2 rounded-xl px-4 py-3 mb-5 text-[12.5px]"
          style={{ background:msg.type==="ok"?"#f0fdf4":"#fef2f2",
            border:`1px solid ${msg.type==="ok"?"#86efac":"#fca5a5"}`,
            color:msg.type==="ok"?"#15803d":"#dc2626" }}>
          {msg.type==="ok" ? <CheckCircle2 size={14}/> : <AlertCircle size={14}/>}
          <span>{msg.text}</span>
          <button className="ml-auto p-0.5 rounded hover:bg-black/5" onClick={() => setMsg(null)}>
            <X size={13}/>
          </button>
        </div>
      )}

      <div className="flex gap-5" style={{ minHeight: 520 }}>

        {/* ══ Col 1: Projects (220px) ══════════════════════════ */}
        <div style={{ width: 220, flexShrink: 0 }}>
          <div className="flex items-center justify-between mb-3">
            <span style={{ fontSize:11, fontWeight:700, color:"var(--ink-400)",
              textTransform:"uppercase", letterSpacing:".08em" }}>项目</span>
            <button onClick={() => setShowCreateProject((v) => !v)}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11.5px] font-semibold transition-all"
              style={{ color: showCreateProject ? "#fff" : "var(--brand)",
                background: showCreateProject ? "var(--brand)" : "rgba(91,78,232,.08)",
                border: "1px solid transparent" }}>
              <Plus size={11}/> 新建
            </button>
          </div>

          {/* Create project form */}
          {showCreateProject && (
            <div className="rounded-xl mb-3 overflow-hidden"
              style={{ border:"1px solid var(--brand)", boxShadow:"0 0 0 3px rgba(91,78,232,.1)" }}>
              <div className="px-3 py-2.5" style={{ background:"rgba(91,78,232,.04)" }}>
                <input value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="项目名称*" onKeyDown={(e) => e.key==="Enter" && createProject()}
                  className="w-full text-[13px] font-medium bg-transparent outline-none"
                  style={{ color:"var(--ink-900)" }} autoFocus />
                <input value={newProjectDesc} onChange={(e) => setNewProjectDesc(e.target.value)}
                  placeholder="描述（可选）"
                  className="w-full text-[12px] bg-transparent outline-none mt-1.5"
                  style={{ color:"var(--ink-500)" }} />
              </div>
              <div className="flex items-center gap-2 px-3 py-2"
                style={{ borderTop:"1px solid rgba(91,78,232,.15)", background:"var(--bg-elevated)" }}>
                <button onClick={createProject} disabled={creatingProject || !newProjectName.trim()}
                  className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-[12px] font-semibold transition"
                  style={{ background:"var(--brand)", color:"#fff",
                    opacity: (creatingProject || !newProjectName.trim()) ? .5 : 1 }}>
                  {creatingProject ? <Loader2 size={11} className="animate-spin"/> : null}
                  创建项目
                </button>
                <button onClick={() => { setShowCreateProject(false); setNewProjectName(""); setNewProjectDesc(""); }}
                  className="px-3 py-1 rounded-lg text-[12px] transition"
                  style={{ color:"var(--ink-500)", background:"var(--bg-subtle)" }}>取消</button>
              </div>
            </div>
          )}

          {/* Project list */}
          {projects.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-center gap-2">
              <div className="h-10 w-10 rounded-xl flex items-center justify-center"
                style={{ background:"var(--bg-subtle)" }}>
                <FolderOpen size={18} style={{ color:"var(--ink-300)" }}/>
              </div>
              <p style={{ fontSize:12.5, color:"var(--ink-400)", fontWeight:500 }}>暂无项目</p>
              <p style={{ fontSize:11, color:"var(--ink-300)" }}>点击「新建」创建第一个项目</p>
            </div>
          ) : (
            <div className="space-y-1">
              {projects.map((p, i) => {
                const active = selProjectId === p.id;
                const hues = ["#6366f1","#0ea5e9","#10b981","#f59e0b","#ec4899","#8b5cf6"];
                const color = hues[i % hues.length];
                return (
                  <button key={p.id} onClick={() => setSelProjectId(p.id)}
                    className="w-full text-left rounded-xl px-3 py-2.5 transition-all group"
                    style={{ background: active ? color : "var(--bg-elevated)",
                      border: `1px solid ${active ? color : "var(--border)"}`,
                      boxShadow: active ? `0 2px 8px ${color}30` : "none" }}>
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 rounded-lg flex items-center justify-center flex-shrink-0 text-[10px] font-bold"
                        style={{ background: active ? "rgba(255,255,255,.2)" : `${color}18`,
                          color: active ? "#fff" : color }}>
                        {p.name.slice(0,1)}
                      </div>
                      <p className="font-semibold truncate text-[13px]"
                        style={{ color: active ? "#fff" : "var(--ink-800)" }}>
                        {p.name}
                      </p>
                    </div>
                    {p.description && (
                      <p className="truncate mt-0.5 ml-8 text-[11px]"
                        style={{ color: active ? "rgba(255,255,255,.75)" : "var(--ink-400)" }}>
                        {p.description}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* ══ Col 2: Data type cards (200px) ═══════════════════ */}
        <div style={{ width: 196, flexShrink: 0 }}>
          <span style={{ fontSize:11, fontWeight:700, color:"var(--ink-400)",
            textTransform:"uppercase", letterSpacing:".08em", display:"block", marginBottom:12 }}>
            数据类型
          </span>
          <div className="flex flex-col gap-3">
            {(Object.entries(DATA_MODE_CONFIG) as [DataMode, typeof cfg][]).map(([mode, c]) => {
              const Icon = c.icon;
              const active = dataMode === mode;
              return (
                <button key={mode} onClick={() => setDataMode(mode)}
                  className="text-left rounded-xl p-3.5 transition-all"
                  style={{ background: active ? c.bg : "var(--bg-elevated)",
                    border: `1.5px solid ${active ? c.border : "var(--border)"}`,
                    boxShadow: active ? `0 2px 12px ${c.color}15` : "none" }}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <div className="h-7 w-7 rounded-lg flex items-center justify-center"
                      style={{ background: active ? c.color : `${c.color}15`,
                        color: active ? "#fff" : c.color }}>
                      <Icon size={14}/>
                    </div>
                    <span style={{ fontSize:13, fontWeight:650,
                      color: active ? c.color : "var(--ink-800)" }}>{c.label}</span>
                  </div>
                  <p style={{ fontSize:11, color: active ? c.color : "var(--ink-400)",
                    opacity: active ? .8 : 1, lineHeight: 1.5 }}>
                    {c.desc}
                  </p>
                  <p style={{ fontSize:10.5, color:"var(--ink-400)", marginTop:4, lineHeight:1.4 }}>
                    {c.hint}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        {/* ══ Col 3: Content area (flex-1) ═════════════════════ */}
        <div className="flex-1 min-w-0">
          {/* Header with upload button */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 style={{ fontSize:14, fontWeight:650, color:"var(--ink-900)" }}>
                {cfg.label}
                {dataMode === "documents" && selKb && (
                  <span style={{ fontSize:12, fontWeight:400, color:"var(--ink-400)", marginLeft:8 }}>
                    · {selKb.name}
                  </span>
                )}
              </h3>
              <p style={{ fontSize:11.5, color:"var(--ink-400)", marginTop:2 }}>
                {dataMode === "structured"
                  ? `${structFiles.length} 个数据表已注册`
                  : selKb
                    ? `${fmt(selKb.doc_count)} 文档 · ${fmtSize(selKb.total_size)}`
                    : "选择知识库后上传文档"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {dataMode === "documents" && (
                <div className="flex items-center gap-1.5">
                  {/* KB quick select */}
                  {projectKBs.length > 0 && (
                    <select value={selKbId ?? ""} onChange={(e) => setSelKbId(Number(e.target.value))}
                      className="text-[12px] rounded-lg px-2.5 py-1.5 outline-none"
                      style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)", color:"var(--ink-700)" }}>
                      <option value="">选择知识库</option>
                      {projectKBs.map((kb) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
                    </select>
                  )}
                  <button onClick={() => setShowCreateKb((v) => !v)}
                    className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] font-medium"
                    style={{ color:"var(--ink-600)", background:"var(--bg-elevated)", border:"1px solid var(--border)" }}>
                    <Plus size={12}/> 新建 KB
                  </button>
                </div>
              )}
              <input ref={dataMode==="structured" ? structRef : docRef} type="file" className="hidden"
                accept={cfg.accept}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  if (dataMode==="structured") uploadStructured(f);
                  else uploadDoc(f);
                }}/>
              <button
                onClick={() => (dataMode==="structured" ? structRef : docRef).current?.click()}
                disabled={uploading || (dataMode==="documents" && !selKbId)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-[12.5px] font-semibold transition"
                style={{ background: "var(--ink-900)", color:"#fff",
                  opacity: (uploading || (dataMode==="documents" && !selKbId)) ? .45 : 1 }}>
                {uploading ? <Loader2 size={13} className="animate-spin"/> : <Upload size={13}/>}
                上传{dataMode==="structured" ? "数据" : "文档"}
              </button>
            </div>
          </div>

          {/* Create KB inline form */}
          {dataMode === "documents" && showCreateKb && (
            <div className="rounded-xl p-3 mb-3 flex items-center gap-2"
              style={{ background:"rgba(91,78,232,.04)", border:"1px solid rgba(91,78,232,.2)" }}>
              <input value={newKbName} onChange={(e) => setNewKbName(e.target.value)}
                placeholder="知识库名称" onKeyDown={(e) => e.key==="Enter" && createKB()}
                className="flex-1 text-[13px] bg-transparent outline-none" style={{ color:"var(--ink-800)" }} autoFocus/>
              <button onClick={createKB} className="px-3 py-1 rounded-lg text-[12px] font-medium"
                style={{ background:"var(--brand)", color:"#fff" }}>创建</button>
              <button onClick={() => { setShowCreateKb(false); setNewKbName(""); }}
                className="p-1 rounded" style={{ color:"var(--ink-400)" }}><X size={13}/></button>
            </div>
          )}

          {/* Drop zone + file list */}
          <div
            className={`rounded-2xl transition-all ${dragging ? "drop-zone-active" : ""}`}
            style={{ border:`1.5px dashed ${dragging ? "var(--brand)" : "var(--border)"}`,
              background: dragging ? "rgba(91,78,232,.03)" : "transparent",
              minHeight: 320, padding: "16px" }}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}>

            {/* Loading */}
            {(dataMode==="structured" ? structLoading : docsLoading) ? (
              <div className="flex items-center justify-center h-40 gap-2">
                <Loader2 size={16} className="animate-spin" style={{ color:"var(--ink-300)" }}/>
                <span style={{ fontSize:13, color:"var(--ink-400)" }}>加载中…</span>
              </div>
            ) : (dataMode==="structured" ? structFiles : docs).length === 0 ? (
              /* Empty drop zone */
              <div className="flex flex-col items-center justify-center h-52 text-center gap-3">
                <div className="h-12 w-12 rounded-2xl flex items-center justify-center"
                  style={{ background: cfg.bg, border:`1.5px dashed ${cfg.border}` }}>
                  <ModeIcon size={20} style={{ color: cfg.color }}/>
                </div>
                <div>
                  <p style={{ fontSize:13.5, fontWeight:600, color:"var(--ink-600)" }}>{cfg.emptyText}</p>
                  <p style={{ fontSize:12, color:"var(--ink-400)", marginTop:4 }}>
                    支持 {cfg.desc}
                  </p>
                </div>
              </div>
            ) : dataMode === "structured" ? (
              /* Structured file list */
              <div className="space-y-2">
                <p style={{ fontSize:11, fontWeight:700, color:"var(--ink-400)", marginBottom:10,
                  textTransform:"uppercase", letterSpacing:".07em" }}>
                  已注册数据表 · {structFiles.length}
                </p>
                {structFiles.map((f) => {
                  const ext = (f.original_name||f.filename||"").split(".").pop()?.toUpperCase()||"?";
                  const isCSV = ["CSV","TSV"].includes(ext);
                  return (
                    <div key={f.id} className="flex items-center gap-3 rounded-xl px-4 py-3 group transition"
                      style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)" }}>
                      <div className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0 text-[10px] font-bold"
                        style={{ background:isCSV?"#dcfce7":"#dbeafe", color:isCSV?"#15803d":"#1d4ed8" }}>
                        {ext.slice(0,4)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold truncate" style={{ fontSize:13, color:"var(--ink-800)" }}>
                          {f.original_name||f.filename}
                        </p>
                        <p style={{ fontSize:11, color:"var(--ink-400)", marginTop:1.5 }}>
                          {fmtSize(f.file_size)}
                          {f.created_at && ` · ${new Date(f.created_at).toLocaleDateString()}`}
                        </p>
                      </div>
                      <span className="flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-lg"
                        style={{ background:"#f0fdf4", color:"#15803d", border:"1px solid #86efac" }}>
                        <CheckCircle2 size={11}/> 已注册
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              /* Document list */
              <div className="space-y-2">
                <p style={{ fontSize:11, fontWeight:700, color:"var(--ink-400)", marginBottom:10,
                  textTransform:"uppercase", letterSpacing:".07em" }}>
                  知识库文档 · {docs.length}
                </p>
                {docs.map((doc) => {
                  const ext = doc.title.split(".").pop()?.toUpperCase() || "DOC";
                  const extColors: Record<string, {bg:string;text:string}> = {
                    PDF:{bg:"#fef2f2",text:"#dc2626"}, DOCX:{bg:"#eff6ff",text:"#2563eb"},
                    DOC:{bg:"#eff6ff",text:"#2563eb"}, TXT:{bg:"#f9fafb",text:"#6b7280"},
                    MD:{bg:"#f5f3ff",text:"#7c3aed"},
                  };
                  const ec = extColors[ext] || {bg:"var(--bg-subtle)",text:"var(--ink-500)"};
                  return (
                    <div key={doc.id} className="flex items-center gap-3 rounded-xl px-4 py-3 group transition"
                      style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)" }}>
                      <div className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0 text-[9.5px] font-bold"
                        style={{ background:ec.bg, color:ec.text }}>
                        {ext.slice(0,4)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold" style={{ fontSize:13, color:"var(--ink-800)" }}>
                          {doc.title}
                        </p>
                        <p style={{ fontSize:11, color:"var(--ink-400)", marginTop:1.5 }}>
                          {fmt(doc.chunk_count)} chunks · {fmtSize(doc.file_size)}
                          {doc.status && (
                            <span style={{ marginLeft:6, padding:"1px 6px", borderRadius:99,
                              background: doc.status==="indexed"?"#f0fdf4":"#fff7ed",
                              color: doc.status==="indexed"?"#15803d":"#c2410c", fontSize:10 }}>
                              {doc.status}
                            </span>
                          )}
                        </p>
                      </div>
                      <button onClick={() => deleteDoc(doc.id)}
                        className="opacity-0 group-hover:opacity-100 transition p-1.5 rounded-lg"
                        style={{ color:"#ef4444", background:"#fef2f2" }}>
                        <Trash2 size={12}/>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 3: 本体建模
// ═══════════════════════════════════════════════════════════════════════════════

function OntologyTab() {
  const [projects, setProjects]   = useState<Project[]>([]);
  const [selProjectId, setSelProjectId] = useState<number|null>(null);
  const [graphData, setGraphData] = useState<{
    nodes:any[]; edges:any[]; kb_count:number; ontology_count:number;
  }|null>(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    Promise.all([
      safeCall(api.getOntologyDataGraph(), null),
      safeCall(api.listProjects(), { items:[], total:0 }),
    ]).then(([graph, projs]) => {
      if (graph) setGraphData(graph);
      const items = projs?.items || [];
      setProjects(items);
      if (items[0]) {
        const saved = localStorage.getItem("da_ontology_project_id");
        const savedId = saved ? Number(saved) : null;
        setSelProjectId(savedId && items.find((p:Project) => p.id === savedId) ? savedId : items[0].id);
      }
    }).finally(() => setLoading(false));
  }, []);

  const ontologyNodes = graphData?.nodes.filter((n) => n.type === "ontology_domain") || [];
  const kbNodes       = graphData?.nodes.filter((n) => n.type === "knowledge_base") || [];
  const totalChunks   = kbNodes.reduce((a:number,n:any) => a+(n.chunk_count||0), 0);
  const totalDocs     = kbNodes.reduce((a:number,n:any) => a+(n.doc_count||0), 0);

  return (
    <div>
      {loading ? (
        <div className="flex items-center gap-2 h-20">
          <Loader2 size={18} className="animate-spin" style={{ color:"var(--ink-300)" }}/>
          <span style={{ fontSize:13, color:"var(--ink-400)" }}>加载本体数据…</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {[
              { label:"本体领域",    value:fmt(graphData?.ontology_count||ontologyNodes.length), icon:Brain,    color:"#6366f1" },
              { label:"系统 KB",     value:fmt(graphData?.kb_count||kbNodes.length),             icon:Database, color:"#0ea5e9" },
              { label:"已索引文档",  value:fmt(totalDocs),                                       icon:FileText, color:"#10b981" },
              { label:"向量 Chunks", value:fmt(totalChunks),                                     icon:Zap,      color:"#f59e0b" },
            ].map((s) => (
              <div key={s.label} className="rounded-xl p-4 kb-card"
                style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)" }}>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <s.icon size={13} style={{ color:s.color }}/>
                  <span style={{ fontSize:11, color:"var(--ink-400)", fontWeight:500 }}>{s.label}</span>
                </div>
                <div style={{ fontSize:22, fontWeight:720, color:"var(--ink-900)" }}>{s.value}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-5 mb-8">
            {/* Ontology domains */}
            <div className="rounded-xl p-4" style={{ border:"1px solid var(--border)", background:"var(--bg-elevated)" }}>
              <h3 className="flex items-center gap-2 mb-3" style={{ fontSize:13, fontWeight:650, color:"var(--ink-700)" }}>
                <Brain size={13} style={{ color:"var(--ink-400)" }}/>
                系统本体领域
                <span style={{ fontSize:10.5, padding:"1px 6px", borderRadius:99, background:"var(--bg-subtle)", color:"var(--ink-400)" }}>
                  {ontologyNodes.length}
                </span>
              </h3>
              {ontologyNodes.length === 0 ? (
                <div className="text-center py-8">
                  <Network size={24} style={{ color:"var(--ink-200)", margin:"0 auto 8px" }}/>
                  <p style={{ fontSize:12, color:"var(--ink-400)" }}>暂无本体节点</p>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {ontologyNodes.slice(0,14).map((node:any) => (
                    <div key={node.id} className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                      style={{ background:"var(--bg-subtle)", fontSize:12 }}>
                      <CircleDot size={10} style={{ color:"var(--brand)", flexShrink:0, opacity:.7 }}/>
                      <span className="font-medium truncate" style={{ color:"var(--ink-800)", flex:1 }}>{node.label}</span>
                      {node.domain && <span style={{ fontSize:10.5, color:"var(--ink-400)" }}>{node.domain}</span>}
                      {node.importance != null && (
                        <div style={{ width:28, height:4, borderRadius:99, background:"var(--border)", overflow:"hidden", flexShrink:0 }}>
                          <div style={{ width:`${(node.importance*100)}%`, height:"100%", background:"var(--brand)", borderRadius:99 }}/>
                        </div>
                      )}
                    </div>
                  ))}
                  {ontologyNodes.length > 14 && (
                    <p style={{ fontSize:11, color:"var(--ink-400)", textAlign:"center", paddingTop:4 }}>
                      + {ontologyNodes.length - 14} 更多
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* KB nodes */}
            <div className="rounded-xl p-4" style={{ border:"1px solid var(--border)", background:"var(--bg-elevated)" }}>
              <h3 className="flex items-center gap-2 mb-3" style={{ fontSize:13, fontWeight:650, color:"var(--ink-700)" }}>
                <Database size={13} style={{ color:"var(--ink-400)" }}/>
                已连接知识库
                <span style={{ fontSize:10.5, padding:"1px 6px", borderRadius:99, background:"var(--bg-subtle)", color:"var(--ink-400)" }}>
                  {kbNodes.length}
                </span>
              </h3>
              {kbNodes.length === 0 ? (
                <div className="text-center py-8">
                  <Database size={24} style={{ color:"var(--ink-200)", margin:"0 auto 8px" }}/>
                  <p style={{ fontSize:12, color:"var(--ink-400)" }}>暂无系统知识库</p>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {kbNodes.slice(0,14).map((kb:any) => (
                    <div key={kb.id} className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                      style={{ background:"var(--bg-subtle)", fontSize:12 }}>
                      <BookOpen size={10} style={{ color:"#0ea5e9", flexShrink:0 }}/>
                      <span className="font-medium truncate" style={{ color:"var(--ink-800)", flex:1 }}>{kb.label}</span>
                      <span style={{ fontSize:10.5, color:"var(--ink-400)", fontVariantNumeric:"tabular-nums" }}>
                        {fmt(kb.chunk_count)} c
                      </span>
                    </div>
                  ))}
                  {kbNodes.length > 14 && (
                    <p style={{ fontSize:11, color:"var(--ink-400)", textAlign:"center", paddingTop:4 }}>
                      + {kbNodes.length - 14} 更多
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Project ontology editor */}
      <div style={{ borderTop:"1px solid var(--border)", paddingTop:24 }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="flex items-center gap-2" style={{ fontSize:14, fontWeight:650, color:"var(--ink-700)" }}>
            <GitBranch size={14} style={{ color:"var(--ink-400)" }}/>
            项目本体编辑
          </h3>
          {projects.length > 0 && (
            <select value={selProjectId ?? ""}
              onChange={(e) => {
                const id = Number(e.target.value);
                setSelProjectId(id);
                localStorage.setItem("da_ontology_project_id", String(id));
              }}
              className="text-[12px] rounded-lg px-2.5 py-1.5 outline-none"
              style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)", color:"var(--ink-700)" }}>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
        </div>
        <OntologyEditor projectId={selProjectId ?? undefined} defaultToSystem={true} />
      </div>
    </div>
  );
}
