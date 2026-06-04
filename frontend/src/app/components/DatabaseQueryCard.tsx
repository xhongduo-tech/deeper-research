import { useState } from "react";
import { Database, ChevronRight, Copy, Download, AlertCircle, Loader2 } from "lucide-react";

export interface DatabaseQueryCardProps {
  sourceKey: string;
  sourceName: string;
  query?: string;
  state: "searching" | "done" | "error";
  resultType?: "table" | "financial" | "articles" | "stats" | "text";
  data?: any;
  rowCount?: number;
  error?: string;
}

export function DatabaseQueryCard(props: DatabaseQueryCardProps) {
  const { sourceName, state, resultType, data, rowCount, error } = props;
  const isSearching = state === "searching";
  const isError = state === "error";

  return (
    <div
      style={{
        borderRadius: 12,
        border: "1px solid var(--border)",
        background: "var(--bg-elevated)",
        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 14px",
          animation: isSearching ? "dbPulse 1.4s ease-in-out infinite" : undefined,
        }}
      >
        {isSearching ? (
          <Loader2 style={{ width: 15, height: 15, color: "var(--brand)", flexShrink: 0 }} className="animate-spin" />
        ) : isError ? (
          <AlertCircle style={{ width: 15, height: 15, color: "#ef4444", flexShrink: 0 }} />
        ) : (
          <Database style={{ width: 15, height: 15, color: "var(--brand)", flexShrink: 0 }} />
        )}
        <span style={{ fontSize: 12.5, color: "var(--ink-500)", fontWeight: 500, flexShrink: 0 }}>
          {isSearching ? "查找相关数据库" : isError ? "查询失败" : "获取数据"}
        </span>
        <div style={{ width: 1, height: 13, background: "var(--border)", flexShrink: 0 }} />
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-900)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {sourceName}
        </span>
        <ChevronRight style={{ width: 14, height: 14, color: "var(--ink-300)", flexShrink: 0 }} />
      </div>

      {/* Error */}
      {isError && (
        <div style={{ padding: "6px 14px 10px", fontSize: 12, color: "#ef4444" }}>
          {error || "数据源查询失败，请稍后重试。"}
        </div>
      )}

      {/* Result */}
      {state === "done" && data && (
        <div style={{ borderTop: "1px solid var(--border)", padding: "10px 14px 12px" }}>
          {resultType === "table" && <TableResult data={data} rowCount={rowCount} />}
          {resultType === "financial" && <FinancialResult data={data} />}
          {resultType === "articles" && <ArticlesResult data={data} />}
          {resultType === "stats" && <StatsResult data={data} />}
          {resultType === "text" && <TextResult data={data} />}
          {!resultType && <TableResult data={data} rowCount={rowCount} />}
        </div>
      )}

      <style>{`
        @keyframes dbPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}

/* ─── Table Result ─── */
function TableResult({ data, rowCount }: { data: any; rowCount?: number }) {
  const rows: Record<string, any>[] = Array.isArray(data) ? data : (data?.rows || data?.data || []);
  const shown = rows.slice(0, 5);
  const cols: string[] = shown.length > 0 ? Object.keys(shown[0]) : (data?.columns || []);
  const total = rowCount ?? rows.length;

  const copyCSV = () => {
    const lines = [cols.join(","), ...shown.map((r) => cols.map((c) => JSON.stringify(r[c] ?? "")).join(","))];
    navigator.clipboard.writeText(lines.join("\n")).catch(() => {});
  };

  const downloadCSV = () => {
    const lines = [cols.join(","), ...rows.map((r) => cols.map((c) => JSON.stringify(r[c] ?? "")).join(","))];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "data.csv"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if (cols.length === 0) return <div style={{ fontSize: 12, color: "var(--ink-500)" }}>暂无数据</div>;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-700)" }}>数据预览</span>
        <div style={{ display: "flex", gap: 4 }}>
          <IconBtn onClick={copyCSV} title="复制 CSV"><Copy style={{ width: 12, height: 12 }} /></IconBtn>
          <IconBtn onClick={downloadCSV} title="下载 CSV"><Download style={{ width: 12, height: 12 }} /></IconBtn>
        </div>
      </div>
      <div style={{ overflowX: "auto", borderRadius: 8, border: "1px solid var(--border)" }}>
        <table style={{ width: "100%", fontSize: 11.5, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "var(--bg-subtle)" }}>
              {cols.map((c) => (
                <th key={c} style={{ padding: "5px 8px", fontWeight: 600, color: "var(--ink-600)", textAlign: "left", whiteSpace: "nowrap", borderBottom: "1px solid var(--border)" }}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, i) => (
              <tr key={i} style={{ borderBottom: i < shown.length - 1 ? "1px solid var(--border)" : undefined }}>
                {cols.map((c) => (
                  <td key={c} style={{ padding: "5px 8px", color: "var(--ink-800)", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {String(row[c] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {total > 0 && (
        <div style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 5, textAlign: "right" }}>
          共 {total} 条记录
        </div>
      )}
    </div>
  );
}

/* ─── Financial Result ─── */
function FinancialResult({ data }: { data: any }) {
  const d = data || {};
  const change = parseFloat(d.change ?? d.price_change ?? "0");
  const changeColor = change > 0 ? "#dc2626" : change < 0 ? "#16a34a" : "var(--ink-500)";
  const changePct = d.change_pct ?? d.change_percent ?? "";
  const changeLabel = `${change > 0 ? "+" : ""}${change.toFixed(2)}${changePct ? ` (${changePct})` : ""}`;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-800)" }}>
          {d.symbol || d.code || ""} {d.name || d.company || ""}
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-400)" }}>{d.date || d.trade_date || ""}</span>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-900)" }}>{d.price ?? d.close ?? "—"}</span>
        {change !== 0 && (
          <span style={{ fontSize: 13, fontWeight: 600, color: changeColor }}>{changeLabel}</span>
        )}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px 12px" }}>
        {[
          ["今开", d.open], ["收盘", d.close ?? d.price], ["最高", d.high],
          ["最低", d.low], ["成交量", d.volume ?? d.vol], ["成交额", d.turnover ?? d.amount],
        ].map(([label, val]) => val != null && (
          <div key={label as string} style={{ display: "flex", gap: 4, fontSize: 11.5 }}>
            <span style={{ color: "var(--ink-400)" }}>{label}</span>
            <span style={{ color: "var(--ink-800)", fontWeight: 500 }}>{String(val)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Articles Result ─── */
function ArticlesResult({ data }: { data: any }) {
  const articles: any[] = Array.isArray(data) ? data : (data?.articles || data?.items || []);
  const shown = articles.slice(0, 3);
  if (shown.length === 0) return <div style={{ fontSize: 12, color: "var(--ink-500)" }}>暂无文章</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {shown.map((a, i) => {
        const title = String(a.title || a.headline || "").slice(0, 40);
        const summary = String(a.summary || a.abstract || a.content || "").slice(0, 80);
        const source = a.source || a.publisher || "";
        const date = a.date || a.published_at || a.publish_date || "";
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "var(--ink-300)" }}>·</span>
              <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-800)", flex: 1 }}>{title}{title.length >= 40 ? "…" : ""}</span>
              {source && <span style={{ fontSize: 11, padding: "1px 5px", borderRadius: 4, background: "var(--bg-subtle)", color: "var(--ink-500)", border: "1px solid var(--border)" }}>{source}</span>}
              {date && <span style={{ fontSize: 11, color: "var(--ink-400)" }}>{String(date).slice(0, 10)}</span>}
            </div>
            {summary && <div style={{ fontSize: 11.5, color: "var(--ink-500)", paddingLeft: 16, lineHeight: 1.5 }}>{summary}{summary.length >= 80 ? "…" : ""}</div>}
          </div>
        );
      })}
      {articles.length > 3 && (
        <div style={{ fontSize: 11, color: "var(--ink-400)", paddingLeft: 16 }}>…共 {articles.length} 篇</div>
      )}
    </div>
  );
}

/* ─── Stats Result ─── */
function StatsResult({ data }: { data: any }) {
  const entries = Array.isArray(data) ? data : Object.entries(data || {}).map(([k, v]) => ({ label: k, value: v }));
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px" }}>
      {entries.slice(0, 8).map((e: any, i: number) => {
        const label = e.label ?? e.key ?? Object.keys(e)[0];
        const value = e.value ?? e.val ?? Object.values(e)[0];
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>{String(label)}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>{String(value ?? "—")}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ─── Text Result ─── */
function TextResult({ data }: { data: any }) {
  const [expanded, setExpanded] = useState(false);
  const text = typeof data === "string" ? data : (data?.text || data?.content || JSON.stringify(data));
  const truncated = text.length > 200;
  const shown = expanded ? text : text.slice(0, 200);
  return (
    <div>
      <p style={{ fontSize: 12.5, color: "var(--ink-700)", lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap" }}>
        {shown}{!expanded && truncated ? "…" : ""}
      </p>
      {truncated && (
        <button
          onClick={() => setExpanded((p) => !p)}
          style={{ fontSize: 11.5, color: "var(--brand)", marginTop: 4, background: "none", border: "none", cursor: "pointer", padding: 0 }}
        >
          {expanded ? "收起" : "展开"}
        </button>
      )}
    </div>
  );
}

/* ─── Icon button helper ─── */
function IconBtn({ onClick, title, children }: { onClick: () => void; title?: string; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 24, height: 24, display: "inline-flex", alignItems: "center", justifyContent: "center",
        borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-subtle)",
        color: "var(--ink-500)", cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}
