import { useEffect, useRef, useState } from "react";
import {
  Plus, FileSpreadsheet, Database, CheckCircle2, Trash2, RefreshCw,
  ChevronRight, AlertTriangle, ArrowLeft, Table, Search, X, Key, Upload, FileText,
} from "lucide-react";
import { api, KnowledgeBase, OfficialDataSource } from "../lib/api";
import { DatabaseQueryCard } from "./DatabaseQueryCard";

/* ── Official source mock data (shown when API is unavailable) ── */
const OFFICIAL_SOURCES: OfficialDataSource[] = [
  { key: "fin_stock_cn", name: "中国A股行情数据", category: "金融数据", description: "沪深A股实时行情、历史K线、涨跌停板数据", domain_tags: ["金融", "股票", "A股"], icon_color: "#e53e3e", icon_bg: "#fff5f5", coverage: "2020-至今", is_active: true },
  { key: "fin_annual_report", name: "上市公司年度报告", category: "金融数据", description: "A股上市公司历年财报、业绩披露、分红数据", domain_tags: ["金融", "财报", "年报"], icon_color: "#e53e3e", icon_bg: "#fff5f5", coverage: "2020-至今", is_active: true },
  { key: "fin_macro_cn", name: "中国宏观经济指标", category: "金融数据", description: "GDP/CPI/PPI/PMI等核心宏观经济数据", domain_tags: ["金融", "宏观", "统计"], icon_color: "#e53e3e", icon_bg: "#fff5f5", coverage: "2020-至今", is_active: true },
  { key: "fin_bond", name: "债券市场数据", category: "金融数据", description: "国债/企业债收益率曲线、债券发行数据", domain_tags: ["金融", "债券"], icon_color: "#e53e3e", icon_bg: "#fff5f5", coverage: "2020-至今", is_active: true },
  { key: "acad_arxiv", name: "ArXiv预印本数据库", category: "学术研究", description: "物理/数学/计算机科学/经济学预印本论文", domain_tags: ["学术", "论文", "科研"], icon_color: "#7c3aed", icon_bg: "#f5f3ff", coverage: "2020-至今", is_active: true },
  { key: "acad_pubmed", name: "PubMed生物医学文献", category: "学术研究", description: "生物医学、临床研究、基础科学文献", domain_tags: ["学术", "医学", "生命科学"], icon_color: "#7c3aed", icon_bg: "#f5f3ff", coverage: "2020-至今", is_active: true },
  { key: "gov_report_cn", name: "政府工作报告", category: "政府数据", description: "历年国务院政府工作报告全文及解读", domain_tags: ["政府", "政策", "宏观"], icon_color: "#b45309", icon_bg: "#fffbeb", coverage: "2020-至今", is_active: true },
  { key: "gov_stats_cn", name: "国家统计局数据", category: "政府数据", description: "人口/工业/农业/贸易统计公报和数据", domain_tags: ["政府", "统计", "宏观"], icon_color: "#b45309", icon_bg: "#fffbeb", coverage: "2020-至今", is_active: true },
  { key: "gov_policy_cn", name: "中央政策文件", category: "政府数据", description: "国发/国办文件、部委规章、重要政策", domain_tags: ["政府", "政策", "法规"], icon_color: "#b45309", icon_bg: "#fffbeb", coverage: "2020-至今", is_active: true },
  { key: "corp_esg", name: "企业ESG报告", category: "企业信息", description: "上市公司ESG评级与社会责任报告", domain_tags: ["企业", "ESG", "可持续"], icon_color: "#059669", icon_bg: "#ecfdf5", coverage: "2020-至今", is_active: true },
  { key: "news_financial", name: "财经新闻数据库", category: "新闻舆情", description: "证券时报/上证报/第一财经等财经媒体", domain_tags: ["新闻", "财经", "舆情"], icon_color: "#0284c7", icon_bg: "#f0f9ff", coverage: "2020-至今", is_active: true },
  { key: "news_politics", name: "时政新闻数据库", category: "新闻舆情", description: "新华社/人民日报等权威媒体新闻报道", domain_tags: ["新闻", "政治", "时事"], icon_color: "#0284c7", icon_bg: "#f0f9ff", coverage: "2020-至今", is_active: true },
  { key: "news_sports", name: "体育新闻数据库", category: "新闻舆情", description: "国内外赛事成绩/转会/排名实时数据", domain_tags: ["新闻", "体育", "赛事"], icon_color: "#0284c7", icon_bg: "#f0f9ff", coverage: "2020-至今", is_active: true },
  { key: "industry_agri", name: "农业与粮食数据", category: "行业数据", description: "粮食产量/农产品价格/农业政策数据", domain_tags: ["农业", "粮食", "行业"], icon_color: "#65a30d", icon_bg: "#f7fee7", coverage: "2020-至今", is_active: true },
  { key: "industry_energy", name: "能源数据库", category: "行业数据", description: "电力/煤炭/天然气/油价/新能源数据", domain_tags: ["能源", "电力", "行业"], icon_color: "#65a30d", icon_bg: "#f7fee7", coverage: "2020-至今", is_active: true },
  { key: "industry_realestate", name: "房地产数据库", category: "行业数据", description: "房价指数/土地成交/库存/开发商数据", domain_tags: ["房地产", "行业", "房价"], icon_color: "#65a30d", icon_bg: "#f7fee7", coverage: "2020-至今", is_active: true },
  { key: "env_weather_cn", name: "中国气象数据", category: "气象环境", description: "全国城市天气预报、历史气候、极端天气", domain_tags: ["气象", "天气", "气候"], icon_color: "#0891b2", icon_bg: "#ecfeff", coverage: "2020-至今", is_active: true },
  { key: "env_carbon", name: "碳排放双碳数据", category: "气象环境", description: "碳排放数据/碳市场/双碳政策追踪", domain_tags: ["碳排放", "双碳", "环境"], icon_color: "#0891b2", icon_bg: "#ecfeff", coverage: "2020-至今", is_active: true },
  { key: "law_statute_cn", name: "中国法律法规库", category: "法律法规", description: "现行有效法律、行政法规、司法解释全文", domain_tags: ["法律", "法规", "合规"], icon_color: "#dc2626", icon_bg: "#fef2f2", coverage: "2020-至今", is_active: true },
  { key: "intl_worldbank", name: "世界银行数据库", category: "国际数据", description: "全球宏观经济、人口、发展指标数据", domain_tags: ["国际", "世界银行", "宏观"], icon_color: "#4f46e5", icon_bg: "#eef2ff", coverage: "2020-至今", is_active: true },
  { key: "intl_imf", name: "IMF国际货币基金", category: "国际数据", description: "世界经济展望/金融稳定/国际收支数据", domain_tags: ["国际", "IMF", "金融"], icon_color: "#4f46e5", icon_bg: "#eef2ff", coverage: "2020-至今", is_active: true },
  { key: "health_disease", name: "疾病与公卫数据", category: "医疗健康", description: "疾病流行病学/传染病/卫生统计数据", domain_tags: ["医疗", "疾病", "公卫"], icon_color: "#be185d", icon_bg: "#fdf2f8", coverage: "2020-至今", is_active: true },
];

/* ── KB types ── */
interface KBItem {
  id: string;
  name: string;
  type: string;
  status: "connected" | "disconnected" | "error";
  docCount: number;
  chunkCount: number;
  sizeMB: number;
  lastUpdated: string;
}

/* ── Preview API response ── */
interface PreviewResult {
  source_key: string;
  source_name: string;
  result_type: "table" | "financial" | "articles" | "stats" | "text";
  data: any;
  row_count: number;
  error: string | null;
  offline: boolean;
}

/* ── KB Document from API ── */
interface KBDocument {
  id: number;
  filename?: string;
  original_name?: string;
  file_type?: string;
  file_size?: number;
  chunk_count?: number;
  status?: string;
  created_at?: string;
}

export function DataSourcePage({ sidebarCollapsed }: { sidebarCollapsed?: boolean }) {
  const [tab, setTab] = useState<"official" | "kb">("official");
  const [drawerSource, setDrawerSource] = useState<OfficialDataSource | null>(null);
  const [drawerKB, setDrawerKB] = useState<KBItem | null>(null);

  const containerStyle = sidebarCollapsed
    ? { paddingLeft: 190, paddingRight: 190 }
    : { paddingLeft: 40, paddingRight: 40, maxWidth: 1060, marginLeft: "auto", marginRight: "auto" };

  return (
    <div className="min-h-full pt-20 pb-10" style={containerStyle}>
      {/* Header */}
      <div className="mb-6">
        <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink-900)" }}>数据源管理</h1>
        <p style={{ color: "var(--ink-500)", fontSize: 13.5, marginTop: 4 }}>
          管理官方数据库接入与本地知识库，用于研究报告生成
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6" style={{ borderBottom: "1px solid var(--border)", paddingBottom: 0 }}>
        {(["official", "kb"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 18px",
              fontSize: 14,
              fontWeight: tab === t ? 650 : 500,
              color: tab === t ? "var(--brand)" : "var(--ink-500)",
              borderBottom: tab === t ? "2px solid var(--brand)" : "2px solid transparent",
              background: "none",
              cursor: "pointer",
              transition: "color 0.15s",
              marginBottom: -1,
            }}
          >
            {t === "official" ? "官方数据库" : "我的知识库"}
          </button>
        ))}
      </div>

      {tab === "official"
        ? <OfficialTab onCardClick={setDrawerSource} />
        : <KBTab onCardClick={setDrawerKB} />}

      <div className="mt-8 text-center" style={{ color: "var(--ink-400)", fontSize: 11 }}>
        2026 大数据应用部 | Brdc.AI人工智能小组
      </div>

      {/* Official source drawer */}
      {drawerSource && (
        <OfficialSourceDrawer source={drawerSource} onClose={() => setDrawerSource(null)} />
      )}

      {/* KB drawer */}
      {drawerKB && (
        <KBDrawer kb={drawerKB} onClose={() => setDrawerKB(null)} />
      )}
    </div>
  );
}

/* ════════════════════════════════ OFFICIAL TAB ══════════════════════════════ */
function OfficialTab({ onCardClick }: { onCardClick: (src: OfficialDataSource) => void }) {
  const [sources, setSources] = useState<OfficialDataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("全部");

  useEffect(() => {
    let alive = true;
    api.listOfficialSources()
      .then((res) => { if (alive) { setSources(res.sources || []); setLoading(false); } })
      .catch(() => { if (alive) { setSources(OFFICIAL_SOURCES); setLoading(false); } });
    return () => { alive = false; };
  }, []);

  const filtered = sources.filter((s) => {
    const matchCat = category === "全部" || s.category === category;
    const q = search.toLowerCase();
    const matchSearch = !q || s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.domain_tags.some((t) => t.includes(q));
    return matchCat && matchSearch;
  });

  const categories = ["全部", ...Array.from(new Set(sources.map((s) => s.category)))];

  return (
    <div>
      {/* Search + category filters */}
      <div className="flex flex-col gap-3 mb-5">
        <div className="relative" style={{ maxWidth: 360 }}>
          <Search style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 15, height: 15, color: "var(--ink-400)" }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索数据库名称或标签…"
            style={{
              width: "100%", height: 36, paddingLeft: 32, paddingRight: search ? 30 : 10,
              borderRadius: 10, border: "1px solid var(--border)", background: "var(--bg-subtle)",
              fontSize: 13.5, color: "var(--ink-900)", outline: "none",
            }}
          />
          {search && (
            <button onClick={() => setSearch("")} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", padding: 0, color: "var(--ink-400)" }}>
              <X style={{ width: 14, height: 14 }} />
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              style={{
                height: 28, padding: "0 12px", borderRadius: 999, fontSize: 12.5, fontWeight: 500,
                border: "1px solid var(--border)", cursor: "pointer", transition: "all 0.12s",
                background: category === cat ? "var(--ink-900)" : "var(--bg-subtle)",
                color: category === cat ? "#fff" : "var(--ink-600)",
              }}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20" style={{ border: "1.5px dashed var(--border)", borderRadius: 16 }}>
          <Database style={{ width: 36, height: 36, color: "var(--ink-300)", marginBottom: 12 }} />
          <p style={{ color: "var(--ink-400)", fontSize: 14 }}>未找到匹配的数据库</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((src) => <OfficialSourceCard key={src.key} source={src} onClick={() => onCardClick(src)} />)}
        </div>
      )}
    </div>
  );
}

function OfficialSourceCard({ source: s, onClick }: { source: OfficialDataSource; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="rounded-xl p-5 flex flex-col transition hover:-translate-y-0.5"
      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "var(--shadow-xs)", cursor: "pointer" }}
    >
      {/* Icon + name */}
      <div className="flex items-start gap-3 mb-3">
        <div style={{ width: 40, height: 40, borderRadius: 10, background: s.icon_bg, border: `1px solid ${s.icon_color}22`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Database style={{ width: 18, height: 18, color: s.icon_color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div style={{ fontWeight: 650, fontSize: 14, color: "var(--ink-900)", lineHeight: 1.3 }}>{s.name}</div>
          <div style={{ fontSize: 12, color: "var(--ink-400)", marginTop: 2 }}>{s.category}</div>
        </div>
        {s.is_active && (
          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11.5, color: "#16a34a", flexShrink: 0 }}>
            <CheckCircle2 style={{ width: 13, height: 13 }} /> 已启用
          </div>
        )}
      </div>

      {/* Description */}
      <p style={{ fontSize: 12.5, color: "var(--ink-600)", lineHeight: 1.6, margin: "0 0 10px", flex: 1 }}>
        {s.description}
      </p>

      {/* Tags */}
      <div className="flex flex-wrap gap-1 mb-3">
        {s.domain_tags.map((tag) => (
          <span key={tag} style={{ fontSize: 11, padding: "1px 7px", borderRadius: 999, background: `${s.icon_color}12`, color: s.icon_color, border: `1px solid ${s.icon_color}28`, fontWeight: 500 }}>
            {tag}
          </span>
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between" style={{ fontSize: 11.5, color: "var(--ink-400)" }}>
        {s.coverage && <span>覆盖：{s.coverage}</span>}
        {s.doc_count != null && <span>{s.doc_count.toLocaleString()} 条</span>}
      </div>
    </div>
  );
}

/* ── Official Source Drawer ── */
function OfficialSourceDrawer({ source: s, onClose }: { source: OfficialDataSource; onClose: () => void }) {
  const [previewState, setPreviewState] = useState<"loading" | "done" | "error">("loading");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [mounted, setMounted] = useState(false);

  // Slide-in animation
  useEffect(() => {
    const t = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(t);
  }, []);

  // Escape key closes drawer
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Load preview when drawer opens
  useEffect(() => {
    let alive = true;
    setPreviewState("loading");
    setPreview(null);

    const firstQuery = s.sample_queries?.[0] || s.name;
    api.request<PreviewResult>(`/api/v1/official-sources/${encodeURIComponent(s.key)}/preview?q=${encodeURIComponent(firstQuery)}`)
      .then((res) => {
        if (!alive) return;
        setPreview(res);
        setPreviewState(res.error ? "error" : "done");
      })
      .catch(() => {
        if (!alive) return;
        setPreviewState("error");
      });

    return () => { alive = false; };
  }, [s.key, s.name, s.sample_queries]);

  const isOffline = previewState === "done" && preview?.offline === true;
  const hasError = previewState === "error" || (previewState === "done" && preview?.error);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)",
          zIndex: 1000, transition: "opacity 0.2s",
          opacity: mounted ? 1 : 0,
        }}
      />
      {/* Drawer panel */}
      <div
        style={{
          position: "fixed", right: 0, top: 0, bottom: 0,
          width: "min(480px, 90vw)",
          background: "var(--bg-elevated)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "-4px 0 32px rgba(0,0,0,0.12)",
          zIndex: 1001,
          transform: mounted ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.25s cubic-bezier(0.4,0,0.2,1)",
          display: "flex", flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* Drawer header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "16px 18px",
          borderBottom: "1px solid var(--border)", position: "sticky", top: 0,
          background: "var(--bg-elevated)", zIndex: 1,
        }}>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: s.icon_bg, border: `1px solid ${s.icon_color}22`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <Database style={{ width: 16, height: 16, color: s.icon_color }} />
          </div>
          <div className="flex-1 min-w-0">
            <div style={{ fontWeight: 700, fontSize: 15, color: "var(--ink-900)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.name}</div>
            <div style={{ fontSize: 12, color: "var(--ink-400)", marginTop: 1 }}>{s.category}</div>
          </div>
          <button
            onClick={onClose}
            style={{ width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 8, border: "none", background: "none", cursor: "pointer", color: "var(--ink-400)", flexShrink: 0 }}
            className="hover:bg-[var(--hover)]"
          >
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>

        {/* Drawer body */}
        <div style={{ flex: 1, padding: "18px 18px 28px", display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Meta row */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12.5, color: "var(--ink-500)" }}>
              分类：<strong style={{ color: "var(--ink-700)" }}>{s.category}</strong>
            </span>
            {s.coverage && (
              <>
                <span style={{ color: "var(--border)", fontSize: 12 }}>|</span>
                <span style={{ fontSize: 12.5, color: "var(--ink-500)" }}>
                  覆盖：<strong style={{ color: "var(--ink-700)" }}>{s.coverage}</strong>
                </span>
              </>
            )}
          </div>

          {/* Tags */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {s.domain_tags.map((tag) => (
              <span key={tag} style={{ fontSize: 11.5, padding: "2px 9px", borderRadius: 999, background: `${s.icon_color}12`, color: s.icon_color, border: `1px solid ${s.icon_color}28`, fontWeight: 500 }}>
                {tag}
              </span>
            ))}
          </div>

          {/* Availability chip */}
          <div>
            {isOffline ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 999, background: "rgba(22,163,74,0.1)", color: "#16a34a", fontSize: 12.5, fontWeight: 600, border: "1px solid rgba(22,163,74,0.2)" }}>
                <CheckCircle2 style={{ width: 13, height: 13 }} /> 离线可用
              </span>
            ) : hasError ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 999, background: "rgba(217,119,6,0.1)", color: "#d97706", fontSize: 12.5, fontWeight: 600, border: "1px solid rgba(217,119,6,0.2)" }}>
                <Key style={{ width: 13, height: 13 }} /> 需配置API密钥
              </span>
            ) : s.is_active ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 999, background: "rgba(22,163,74,0.1)", color: "#16a34a", fontSize: 12.5, fontWeight: 600, border: "1px solid rgba(22,163,74,0.2)" }}>
                <CheckCircle2 style={{ width: 13, height: 13 }} /> 离线可用
              </span>
            ) : (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 999, background: "rgba(217,119,6,0.1)", color: "#d97706", fontSize: 12.5, fontWeight: 600, border: "1px solid rgba(217,119,6,0.2)" }}>
                <Key style={{ width: 13, height: 13 }} /> 需配置API密钥
              </span>
            )}
          </div>

          {/* Description */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-400)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 7 }}>描述</div>
            <p style={{ fontSize: 13.5, color: "var(--ink-700)", lineHeight: 1.7, margin: 0 }}>{s.description}</p>
          </div>

          {/* Data preview */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-400)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>数据预览</div>
            {previewState === "loading" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[...Array(3)].map((_, i) => (
                  <div key={i} style={{
                    height: i === 0 ? 40 : 24,
                    borderRadius: 8,
                    background: "var(--bg-subtle)",
                    animation: "drawerPulse 1.4s ease-in-out infinite",
                    animationDelay: `${i * 0.15}s`,
                    width: i === 2 ? "70%" : "100%",
                  }} />
                ))}
                <style>{`@keyframes drawerPulse{0%,100%{opacity:1}50%{opacity:0.5}}`}</style>
              </div>
            )}
            {previewState === "done" && preview && !preview.error && (
              <DatabaseQueryCard
                sourceKey={s.key}
                sourceName={s.name}
                state="done"
                resultType={preview.result_type}
                data={preview.data}
                rowCount={preview.row_count}
              />
            )}
            {(previewState === "error" || (previewState === "done" && preview?.error)) && (
              <div style={{ padding: "14px 16px", borderRadius: 10, background: "var(--bg-subtle)", border: "1px solid var(--border)", fontSize: 13, color: "var(--ink-500)", lineHeight: 1.6 }}>
                预览数据加载中，请稍后
              </div>
            )}
          </div>

          {/* Sample queries */}
          {s.sample_queries && s.sample_queries.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-400)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>示例查询</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                {s.sample_queries.map((q) => (
                  <span key={q} style={{ padding: "4px 11px", borderRadius: 999, background: "var(--bg-subtle)", border: "1px solid var(--border)", fontSize: 12.5, color: "var(--ink-600)", cursor: "default" }}>
                    · {q}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-xl p-5" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "var(--shadow-xs)" }}>
      <div className="flex items-start gap-3 mb-3">
        <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--bg-subtle)" }} />
        <div className="flex-1">
          <div style={{ height: 14, background: "var(--bg-subtle)", borderRadius: 6, width: "60%", marginBottom: 6 }} />
          <div style={{ height: 11, background: "var(--bg-subtle)", borderRadius: 6, width: "35%" }} />
        </div>
      </div>
      <div style={{ height: 12, background: "var(--bg-subtle)", borderRadius: 6, width: "90%", marginBottom: 6 }} />
      <div style={{ height: 12, background: "var(--bg-subtle)", borderRadius: 6, width: "70%" }} />
    </div>
  );
}

/* ════════════════════════════════ KB TAB ════════════════════════════════════ */
function KBTab({ onCardClick }: { onCardClick: (kb: KBItem) => void }) {
  const [kbs, setKbs] = useState<KBItem[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [nameInput, setNameInput] = useState("");

  useEffect(() => {
    let alive = true;
    api.listKBs()
      .then((data) => { if (alive) setKbs((data.items || []).map(kbToItem)); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const handleAdd = async () => {
    if (!nameInput.trim()) return;
    try {
      const kb = await api.createKB(nameInput.trim(), "");
      setKbs((prev) => [...prev, kbToItem(kb)]);
    } catch {
      setKbs((prev) => [...prev, {
        id: `local-${Date.now()}`, name: nameInput.trim(), type: "知识库",
        status: "connected", docCount: 0, chunkCount: 0, sizeMB: 0, lastUpdated: "刚刚",
      }]);
    }
    setNameInput(""); setShowAdd(false);
  };

  const handleDelete = (id: string) => setKbs((prev) => prev.filter((k) => k.id !== id));

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <p style={{ fontSize: 13.5, color: "var(--ink-500)" }}>管理你的私有知识库，上传文档用于 RAG 检索</p>
        <button
          onClick={() => setShowAdd(true)}
          className="h-9 px-4 rounded-lg inline-flex items-center gap-1.5 transition active:scale-[0.99]"
          style={{ background: "var(--ink-900)", color: "#fff", fontWeight: 600, fontSize: 13.5 }}
        >
          <Plus className="h-4 w-4" />新建知识库
        </button>
      </div>

      {kbs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20" style={{ border: "1.5px dashed var(--border)", borderRadius: 16 }}>
          <Database style={{ width: 36, height: 36, color: "var(--ink-300)", marginBottom: 12 }} />
          <p style={{ color: "var(--ink-400)", fontSize: 14 }}>暂无知识库</p>
          <button
            onClick={() => setShowAdd(true)}
            className="mt-4 h-9 px-4 rounded-lg inline-flex items-center gap-1.5"
            style={{ background: "var(--brand-soft)", color: "var(--brand)", fontWeight: 600, fontSize: 13.5, border: "1px solid var(--brand-border)" }}
          >
            <Plus className="h-4 w-4" />创建第一个知识库
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {kbs.map((kb) => (
            <div
              key={kb.id}
              className="rounded-xl p-5 flex flex-col transition hover:-translate-y-0.5 cursor-pointer group relative overflow-hidden"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "var(--shadow-xs)" }}
              onClick={() => onCardClick(kb)}
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t-xl" style={{ background: kb.status === "connected" ? "#16a34a" : "#ef4444" }} />
              <div className="flex items-start justify-between mb-3">
                <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--brand-soft)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Database style={{ width: 18, height: 18, color: "var(--brand)" }} />
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(kb.id); }}
                  className="h-7 w-7 inline-flex items-center justify-center rounded-lg opacity-0 group-hover:opacity-100 transition hover:bg-red-50"
                  style={{ color: "var(--ink-400)" }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
              <div style={{ fontWeight: 650, fontSize: 15, color: "var(--ink-900)", marginBottom: 4 }}>{kb.name}</div>
              <div className="flex items-center gap-2 mb-3" style={{ fontSize: 12.5, color: "var(--ink-500)" }}>
                <CheckCircle2 style={{ width: 12, height: 12, color: "#16a34a" }} />
                <span>{kb.type}</span>
                <span>·</span>
                <span>{kb.docCount} 文档</span>
                {kb.sizeMB > 0 && <><span>·</span><span>{kb.sizeMB} MB</span></>}
              </div>
              <div style={{ fontSize: 12, color: "var(--ink-400)", marginBottom: 12 }}>更新于 {kb.lastUpdated}</div>
              <button
                onClick={(e) => { e.stopPropagation(); onCardClick(kb); }}
                className="h-9 w-full rounded-lg inline-flex items-center justify-center gap-1.5 mt-auto transition hover:bg-[var(--hover)] text-[13px]"
                style={{ color: "var(--ink-700)", border: "1px solid var(--border)", fontWeight: 500 }}
              >
                管理文档 <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowAdd(false)} />
          <div className="relative rounded-2xl p-7 w-[440px]" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "0 24px 64px rgba(0,0,0,0.16)" }}>
            <h2 style={{ fontWeight: 700, fontSize: 17, color: "var(--ink-900)", marginBottom: 20 }}>新建知识库</h2>
            <label className="block mb-1.5 text-[12.5px]" style={{ color: "var(--ink-500)", fontWeight: 600 }}>知识库名称</label>
            <input
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              placeholder="例如：行业研究报告库"
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              style={{ width: "100%", height: 40, padding: "0 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--bg-subtle)", fontSize: 13.5, color: "var(--ink-900)", outline: "none", marginBottom: 20 }}
            />
            <div className="flex gap-2.5">
              <button onClick={() => { setShowAdd(false); setNameInput(""); }} className="flex-1 h-10 rounded-xl text-[14px] transition hover:bg-[var(--hover)]" style={{ border: "1px solid var(--border)", color: "var(--ink-700)", fontWeight: 500 }}>取消</button>
              <button onClick={handleAdd} className="flex-1 h-10 rounded-xl text-[14px] transition active:scale-[0.99]" style={{ background: "var(--ink-900)", color: "#fff", fontWeight: 600 }}>创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── KB Drawer ── */
function KBDrawer({ kb, onClose }: { kb: KBItem; onClose: () => void }) {
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(t);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    let alive = true;
    setDocsLoading(true);
    const kbId = parseInt(kb.id.replace(/\D/g, "")) || 0;
    if (!kbId) { setDocsLoading(false); return; }
    api.request<{ documents: KBDocument[]; total: number }>(`/api/kb/${kbId}/documents`)
      .then((res) => { if (alive) { setDocs(res.documents || []); setDocsLoading(false); } })
      .catch(() => { if (alive) setDocsLoading(false); });
    return () => { alive = false; };
  }, [kb.id]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const kbId = parseInt(kb.id.replace(/\D/g, "")) || 0;
    try {
      await api.uploadKBDocument(kbId, file);
      // Reload docs
      const res = await api.request<{ documents: KBDocument[]; total: number }>(`/api/kb/${kbId}/documents`);
      setDocs(res.documents || []);
    } catch {
      // Append locally as fallback
      setDocs((prev) => [...prev, {
        id: Date.now(),
        original_name: file.name,
        file_size: file.size,
        status: "error",
        created_at: new Date().toISOString(),
      }]);
    } finally {
      setUploading(false);
      // Reset input
      e.target.value = "";
    }
  };

  const fmtSize = (bytes?: number) => {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  const fileExt = (name?: string) => {
    if (!name) return "file";
    const m = name.match(/\.([^.]+)$/);
    return m ? m[1].toLowerCase() : "file";
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)",
          zIndex: 1000, transition: "opacity 0.2s",
          opacity: mounted ? 1 : 0,
        }}
      />
      {/* Drawer panel */}
      <div
        style={{
          position: "fixed", right: 0, top: 0, bottom: 0,
          width: "min(480px, 90vw)",
          background: "var(--bg-elevated)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "-4px 0 32px rgba(0,0,0,0.12)",
          zIndex: 1001,
          transform: mounted ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.25s cubic-bezier(0.4,0,0.2,1)",
          display: "flex", flexDirection: "column",
        }}
      >
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "16px 18px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-elevated)",
        }}>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: "var(--brand-soft)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <Database style={{ width: 16, height: 16, color: "var(--brand)" }} />
          </div>
          <div className="flex-1 min-w-0">
            <div style={{ fontWeight: 700, fontSize: 15, color: "var(--ink-900)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{kb.name}</div>
            <div style={{ fontSize: 12, color: "var(--ink-400)", marginTop: 1 }}>{kb.type} · {kb.docCount} 个文档</div>
          </div>
          <button
            onClick={onClose}
            style={{ width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 8, border: "none", background: "none", cursor: "pointer", color: "var(--ink-400)", flexShrink: 0 }}
            className="hover:bg-[var(--hover)]"
          >
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>

        {/* Upload button */}
        <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--border)" }}>
          <label style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            height: 36, padding: "0 14px", borderRadius: 9,
            background: "var(--ink-900)", color: "#fff", fontWeight: 600, fontSize: 13, cursor: "pointer",
          }}>
            {uploading ? <RefreshCw style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} /> : <Upload style={{ width: 14, height: 14 }} />}
            上传文档
            <input type="file" style={{ display: "none" }} onChange={handleUpload} accept=".pdf,.docx,.txt,.md,.csv,.xlsx" />
          </label>
          <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
        </div>

        {/* Document list */}
        <div style={{ flex: 1, overflowY: "auto", padding: "14px 18px", display: "flex", flexDirection: "column", gap: 8 }}>
          {docsLoading ? (
            [...Array(4)].map((_, i) => (
              <div key={i} style={{ height: 56, borderRadius: 10, background: "var(--bg-subtle)", animation: "drawerPulse 1.4s ease-in-out infinite", animationDelay: `${i * 0.12}s` }} />
            ))
          ) : docs.length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "48px 0", gap: 10 }}>
              <FileText style={{ width: 32, height: 32, color: "var(--ink-300)" }} />
              <p style={{ color: "var(--ink-400)", fontSize: 13.5 }}>暂无文档，上传后可用于 RAG 检索</p>
            </div>
          ) : (
            docs.map((doc) => {
              const name = doc.original_name || doc.filename || "未知文件";
              const ext = fileExt(name);
              const status = doc.status || "ready";
              return (
                <div key={doc.id} style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "10px 14px", borderRadius: 10,
                  background: "var(--bg-subtle)", border: "1px solid var(--border)",
                }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--bg-elevated)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <FileText style={{ width: 14, height: 14, color: "var(--ink-400)" }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, color: "var(--ink-900)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</div>
                    <div style={{ fontSize: 11.5, color: "var(--ink-400)", marginTop: 2, display: "flex", gap: 8 }}>
                      <span>{ext.toUpperCase()}</span>
                      <span>{fmtSize(doc.file_size)}</span>
                      {doc.chunk_count != null && <span>{doc.chunk_count} 块</span>}
                      {doc.created_at && <span>{new Date(doc.created_at).toLocaleDateString("zh-CN")}</span>}
                    </div>
                  </div>
                  {status === "ready" || status === "indexed" || status === "completed"
                    ? <CheckCircle2 style={{ width: 15, height: 15, color: "#16a34a", flexShrink: 0 }} />
                    : status === "error"
                      ? <AlertTriangle style={{ width: 15, height: 15, color: "#ef4444", flexShrink: 0 }} />
                      : <RefreshCw style={{ width: 15, height: 15, color: "var(--brand)", flexShrink: 0, animation: "spin 1s linear infinite" }} />}
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}

/* ── KB Detail: document list + upload (legacy full-page view, kept for back-compat) ── */
function KBDetail({ kb, onBack }: { kb: KBItem; onBack: () => void }) {
  const [docs, setDocs] = useState<{ id: string; name: string; size: string; status: string; date: string }[]>([]);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const kbId = parseInt(kb.id.replace(/\D/g, "")) || 0;
    try {
      await api.uploadKBDocument(kbId, file);
      setDocs((prev) => [...prev, { id: Date.now().toString(), name: file.name, size: `${(file.size / 1024).toFixed(0)} KB`, status: "ready", date: "刚刚" }]);
    } catch {
      setDocs((prev) => [...prev, { id: Date.now().toString(), name: file.name, size: `${(file.size / 1024).toFixed(0)} KB`, status: "error", date: "刚刚" }]);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        <button onClick={onBack} className="h-9 w-9 rounded-lg inline-flex items-center justify-center transition hover:bg-[var(--hover)]" style={{ color: "var(--ink-600)" }}>
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1">
          <div style={{ fontWeight: 700, fontSize: 20, color: "var(--ink-900)" }}>{kb.name}</div>
          <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 2 }}>{kb.type} · {kb.docCount} 个文档</div>
        </div>
        <label style={{ height: 36, padding: "0 16px", borderRadius: 10, background: "var(--ink-900)", color: "#fff", fontWeight: 600, fontSize: 13.5, display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          {uploading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          上传文档
          <input type="file" className="hidden" onChange={handleUpload} accept=".pdf,.docx,.txt,.md,.csv,.xlsx" />
        </label>
      </div>

      {docs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16" style={{ border: "1.5px dashed var(--border)", borderRadius: 16 }}>
          <FileSpreadsheet style={{ width: 32, height: 32, color: "var(--ink-300)", marginBottom: 10 }} />
          <p style={{ color: "var(--ink-400)", fontSize: 13.5 }}>暂无文档，上传后可用于 RAG 检索</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {docs.map((doc) => (
            <div key={doc.id} className="rounded-xl px-5 py-3.5 flex items-center gap-4" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "var(--shadow-xs)" }}>
              <Table className="h-5 w-5 flex-shrink-0" style={{ color: "var(--ink-400)" }} />
              <div className="flex-1 min-w-0">
                <div style={{ fontWeight: 600, fontSize: 14, color: "var(--ink-900)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.name}</div>
                <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 2 }}>{doc.size} · {doc.date}</div>
              </div>
              {doc.status === "ready"
                ? <CheckCircle2 className="h-4 w-4 flex-shrink-0" style={{ color: "#16a34a" }} />
                : doc.status === "error"
                  ? <AlertTriangle className="h-4 w-4 flex-shrink-0" style={{ color: "#ef4444" }} />
                  : <RefreshCw className="h-4 w-4 flex-shrink-0 animate-spin" style={{ color: "var(--brand)" }} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── helpers ── */
function kbToItem(kb: KnowledgeBase): KBItem {
  return {
    id: String(kb.id),
    name: kb.name,
    type: kb.kb_type || "知识库",
    status: "connected",
    docCount: kb.doc_count || 0,
    chunkCount: kb.chunk_count || 0,
    sizeMB: Math.round((kb.total_size || 0) / 1024 / 1024),
    lastUpdated: kb.updated_at ? new Date(kb.updated_at).toLocaleString("zh-CN") : "刚刚",
  };
}
