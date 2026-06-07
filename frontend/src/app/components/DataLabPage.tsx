/**
 * DataLabPage — Table-Agent 数据交互实验室 (场景 B/C)
 *
 * 功能：
 *   1. 上传 Excel/CSV → 自动注册 DuckDB 内存表 + 显示 Schema
 *   2. 自然语言查询 → SQL → 结果表格
 *   3. 一键生成 ECharts 交互 Widget
 *   4. 代码沙箱（Python/Node.js/Shell）执行
 */
import { useState, useRef, useCallback } from "react";
import {
  Upload, Database, Play, Sparkles, Code2, Table2,
  BarChart3, Loader2, ChevronRight, FileSpreadsheet,
  Terminal, AlertCircle, CheckCircle2, X,
} from "lucide-react";
import { api } from "../lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type TableRow = Record<string, unknown>;

type QueryResult = {
  success: boolean;
  sql?: string;
  error?: string;
  columns: string[];
  rows: TableRow[];
  row_count: number;
  exec_ms: number;
  markdown?: string;
};

type SandboxResult = {
  success: boolean;
  language: string;
  stdout: string;
  stderr: string;
  error?: string;
  exec_ms: number;
  figures: Array<{ format: string; base64: string }>;
};

type Tab = "query" | "sandbox" | "widget";

// ── DataLabPage ────────────────────────────────────────────────────────────────

export default function DataLabPage() {
  const [sessionId]          = useState(() => `lab_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  const [tableNames, setTableNames] = useState<string[]>([]);
  const [schema, setSchema]  = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const [tab, setTab]        = useState<Tab>("query");

  // Query
  const [nlQuery, setNlQuery]   = useState("");
  const [sqlMode, setSqlMode]   = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [querying, setQuerying] = useState(false);

  // Widget
  const [widgetQuestion, setWidgetQuestion] = useState("");
  const [widgetHtml, setWidgetHtml]         = useState("");
  const [genWidget, setGenWidget]           = useState(false);

  // Sandbox
  const [sbCode, setSbCode]     = useState("import pandas as pd\nprint('Hello from DataLab!')");
  const [sbLang, setSbLang]     = useState("python");
  const [sbResult, setSbResult] = useState<SandboxResult | null>(null);
  const [running, setRunning]   = useState(false);

  const fileInput = useRef<HTMLInputElement>(null);

  // ── Upload ─────────────────────────────────────────────────────────────────

  const handleUpload = useCallback(async (file: File) => {
    setUploading(true);
    setUploadMsg(null);
    try {
      // 1. Upload via ingress (get file_id)
      const ingest = await api.ingestUpload(file);
      const fileId = ingest.file_id;

      // 2. Register in DuckDB
      const reg = await api.duckdbRegister(sessionId, fileId);
      setTableNames(prev => [...new Set([...prev, reg.table_name])]);
      setSchema(reg.schema);
      setUploadMsg({ type: "ok", text: `已注册表 "${reg.table_name}"，共 ${ingest.vfs_summary.total_files} 个文件` });

      // Prefill query textarea
      setNlQuery(`分析 ${reg.table_name} 表，返回前10行数据`);
    } catch (err) {
      setUploadMsg({ type: "err", text: String((err as Error)?.message || err) });
    } finally {
      setUploading(false);
    }
  }, [sessionId]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  // ── Query ──────────────────────────────────────────────────────────────────

  const runQuery = useCallback(async () => {
    if (!nlQuery.trim()) return;
    setQuerying(true);
    setQueryResult(null);
    try {
      const r = await api.duckdbQuery(sessionId, nlQuery.trim(), !sqlMode);
      setQueryResult(r as QueryResult);
    } catch (err) {
      setQueryResult({ success: false, error: String((err as Error)?.message || err), columns: [], rows: [], row_count: 0, exec_ms: 0 });
    } finally {
      setQuerying(false);
    }
  }, [sessionId, nlQuery, sqlMode]);

  // ── Widget ─────────────────────────────────────────────────────────────────

  const generateWidget = useCallback(async () => {
    if (!queryResult?.rows?.length || !widgetQuestion.trim()) return;
    setGenWidget(true);
    setWidgetHtml("");
    try {
      const r = await api.generateWidget(widgetQuestion, queryResult.rows as Record<string, unknown>[]);
      setWidgetHtml(r.html);
    } catch (err) {
      alert("Widget 生成失败: " + String((err as Error)?.message || err));
    } finally {
      setGenWidget(false);
    }
  }, [queryResult, widgetQuestion]);

  // ── Sandbox ────────────────────────────────────────────────────────────────

  const runSandbox = useCallback(async () => {
    if (!sbCode.trim()) return;
    setRunning(true);
    setSbResult(null);
    try {
      const r = await api.sandboxRun(sbCode, sbLang);
      setSbResult(r as SandboxResult);
    } catch (err) {
      setSbResult({ success: false, language: sbLang, stdout: "", stderr: "", error: String((err as Error)?.message || err), exec_ms: 0, figures: [] });
    } finally {
      setRunning(false);
    }
  }, [sbCode, sbLang]);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full bg-[#f8f9fb] overflow-hidden">

      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
          <Database size={18} className="text-white" />
        </div>
        <div>
          <h1 className="text-[15px] font-semibold text-gray-900">DataLab · 数据交互实验室</h1>
          <p className="text-[12px] text-gray-500">上传 Excel/CSV → DuckDB 分析 → 自然语言查询 → 可视化 Widget</p>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">

        {/* Left: Upload + Schema */}
        <div className="w-72 shrink-0 border-r border-gray-100 bg-white flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-[12px] font-semibold text-gray-700 mb-2">上传数据文件</p>

            {/* Drop zone */}
            <div
              onDrop={onDrop}
              onDragOver={e => e.preventDefault()}
              onClick={() => fileInput.current?.click()}
              className="border-2 border-dashed border-blue-200 rounded-xl p-4 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all"
            >
              {uploading ? (
                <Loader2 size={24} className="mx-auto text-blue-500 animate-spin mb-1" />
              ) : (
                <Upload size={24} className="mx-auto text-blue-400 mb-1" />
              )}
              <p className="text-[12px] text-gray-600">
                {uploading ? "正在解析…" : "拖入或点击上传"}
              </p>
              <p className="text-[11px] text-gray-400 mt-0.5">Excel / CSV / Parquet / JSON</p>
            </div>
            <input
              ref={fileInput} type="file"
              accept=".xlsx,.xls,.csv,.xlsb,.parquet,.json,.zip"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = ""; }}
            />

            {uploadMsg && (
              <div className={`mt-2 flex items-start gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] ${uploadMsg.type === "ok" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
                {uploadMsg.type === "ok" ? <CheckCircle2 size={12} className="mt-0.5 shrink-0" /> : <AlertCircle size={12} className="mt-0.5 shrink-0" />}
                {uploadMsg.text}
              </div>
            )}
          </div>

          {/* Schema */}
          <div className="flex-1 overflow-auto px-4 py-3">
            {tableNames.length > 0 && (
              <>
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  已注册表 ({tableNames.length})
                </p>
                {tableNames.map(t => (
                  <div key={t} className="flex items-center gap-1.5 mb-1.5">
                    <FileSpreadsheet size={13} className="text-blue-500" />
                    <span className="text-[12px] font-medium text-gray-800">{t}</span>
                  </div>
                ))}
                <div className="mt-3">
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Schema</p>
                  <pre className="text-[10px] text-gray-600 bg-gray-50 rounded-lg p-2 overflow-x-auto whitespace-pre-wrap leading-relaxed font-mono">
                    {schema || "—"}
                  </pre>
                </div>
              </>
            )}
            {tableNames.length === 0 && (
              <div className="text-center mt-8">
                <Table2 size={32} className="mx-auto text-gray-300 mb-2" />
                <p className="text-[12px] text-gray-400">上传数据文件后，表 Schema 将显示在此处</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Tabs */}
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Tab Bar */}
          <div className="flex border-b border-gray-100 bg-white px-4 overflow-x-auto">
            {([
              { key: "query" as Tab,   icon: <Sparkles size={14} />,  label: "自然语言查询" },
              { key: "widget" as Tab,  icon: <BarChart3 size={14} />, label: "可视化 Widget" },
              { key: "sandbox" as Tab, icon: <Terminal size={14} />,  label: "代码沙箱" },
            ] as { key: Tab; icon: React.ReactNode; label: string }[]).map(({ key, icon, label }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`flex items-center gap-1.5 px-4 py-3 text-[13px] font-medium border-b-2 transition-colors whitespace-nowrap shrink-0 ${
                  tab === key
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {icon}{label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-auto p-4 space-y-4">

            {/* ── Query Tab ── */}
            {tab === "query" && (
              <>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <label className="text-[12px] font-semibold text-gray-700">查询输入</label>
                    <button
                      onClick={() => setSqlMode(m => !m)}
                      className={`ml-auto flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                        sqlMode ? "bg-gray-800 text-white border-gray-800" : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
                      }`}
                    >
                      <Code2 size={10} />
                      {sqlMode ? "SQL 模式" : "自然语言模式"}
                    </button>
                  </div>
                  <textarea
                    value={nlQuery}
                    onChange={e => setNlQuery(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) runQuery(); }}
                    placeholder={sqlMode
                      ? "SELECT category, SUM(value) as total FROM data GROUP BY category"
                      : "用自然语言描述你想查什么，例如：各类别销售额排名前5"}
                    rows={3}
                    className="w-full text-[13px] font-mono bg-gray-50 border border-gray-200 rounded-lg p-3 resize-none focus:outline-none focus:border-blue-400 focus:bg-white transition-colors"
                  />
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-[11px] text-gray-400">
                      {sqlMode ? "直接执行 SQL" : "LLM 将自动生成 SQL 并执行"} · ⌘Enter 运行
                    </span>
                    <button
                      onClick={runQuery}
                      disabled={querying || !nlQuery.trim() || tableNames.length === 0}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500 text-white text-[12px] font-medium hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {querying ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                      {querying ? "执行中…" : "运行查询"}
                    </button>
                  </div>
                </div>

                {/* Result */}
                {queryResult && (
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100 bg-gray-50">
                      {queryResult.success ? (
                        <CheckCircle2 size={13} className="text-green-500" />
                      ) : (
                        <AlertCircle size={13} className="text-red-500" />
                      )}
                      <span className="text-[12px] font-medium text-gray-700">
                        {queryResult.success
                          ? `${queryResult.row_count} 行 · ${queryResult.exec_ms.toFixed(0)}ms`
                          : "查询失败"}
                      </span>
                      {queryResult.sql && (
                        <code className="ml-auto text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded font-mono truncate max-w-xs">
                          {queryResult.sql}
                        </code>
                      )}
                    </div>

                    {queryResult.success && queryResult.columns.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-[12px]">
                          <thead>
                            <tr className="bg-gray-50 border-b border-gray-100">
                              {queryResult.columns.map(c => (
                                <th key={c} className="text-left px-3 py-2 font-semibold text-gray-600 whitespace-nowrap">{c}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {queryResult.rows.slice(0, 50).map((row, i) => (
                              <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                                {queryResult.columns.map(c => (
                                  <td key={c} className="px-3 py-1.5 text-gray-700 whitespace-nowrap font-mono">
                                    {row[c] == null ? <span className="text-gray-300">null</span> : String(row[c])}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : queryResult.error ? (
                      <p className="px-4 py-3 text-[12px] text-red-600 font-mono">{queryResult.error}</p>
                    ) : null}

                    {/* Widget shortcut */}
                    {queryResult.success && queryResult.rows.length > 0 && (
                      <div className="px-4 py-2.5 border-t border-gray-100 bg-gray-50 flex items-center gap-2">
                        <BarChart3 size={13} className="text-blue-500" />
                        <span className="text-[12px] text-gray-600">想看图表？</span>
                        <button
                          onClick={() => setTab("widget")}
                          className="text-[12px] text-blue-500 hover:underline flex items-center gap-0.5"
                        >
                          切换到 Widget 标签 <ChevronRight size={11} />
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {/* ── Widget Tab ── */}
            {tab === "widget" && (
              <>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <p className="text-[12px] font-semibold text-gray-700 mb-2">描述你想看的图表</p>
                  <div className="flex gap-2">
                    <input
                      value={widgetQuestion}
                      onChange={e => setWidgetQuestion(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") generateWidget(); }}
                      placeholder='例如："按类别画饼图" / "画各月份销售额折线图"'
                      className="flex-1 text-[13px] border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400 transition-colors"
                    />
                    <button
                      onClick={generateWidget}
                      disabled={genWidget || !widgetQuestion.trim() || !queryResult?.rows?.length}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-500 text-white text-[12px] font-medium hover:bg-blue-600 disabled:opacity-40 transition-colors"
                    >
                      {genWidget ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                      {genWidget ? "生成中…" : "生成图表"}
                    </button>
                  </div>
                  {!queryResult?.rows?.length && (
                    <p className="mt-2 text-[11px] text-amber-600">请先在「自然语言查询」标签执行一条查询，然后回到这里生成图表</p>
                  )}
                </div>

                {widgetHtml && (
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100 bg-gray-50">
                      <BarChart3 size={13} className="text-blue-500" />
                      <span className="text-[12px] font-medium text-gray-700">交互图表</span>
                      <button
                        onClick={() => setWidgetHtml("")}
                        className="ml-auto text-gray-400 hover:text-gray-600"
                      >
                        <X size={13} />
                      </button>
                    </div>
                    <iframe
                      srcDoc={widgetHtml}
                      style={{ width: "100%", height: 440, border: "none" }}
                      sandbox="allow-scripts"
                    />
                  </div>
                )}

                {!widgetHtml && !genWidget && (
                  <div className="text-center py-12">
                    <BarChart3 size={40} className="mx-auto text-gray-300 mb-3" />
                    <p className="text-[13px] text-gray-400">先查询数据，再用自然语言描述图表类型</p>
                    <p className="text-[11px] text-gray-300 mt-1">支持折线图、柱状图、饼图、散点图、热力图、树图等</p>
                  </div>
                )}
              </>
            )}

            {/* ── Sandbox Tab ── */}
            {tab === "sandbox" && (
              <>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <p className="text-[12px] font-semibold text-gray-700">代码沙箱</p>
                    <select
                      value={sbLang}
                      onChange={e => setSbLang(e.target.value)}
                      className="ml-auto text-[12px] border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:border-blue-400"
                    >
                      <option value="python">Python</option>
                      <option value="javascript">Node.js</option>
                      <option value="shell">Shell</option>
                      <option value="java">Java</option>
                      <option value="go">Go</option>
                    </select>
                  </div>
                  <textarea
                    value={sbCode}
                    onChange={e => setSbCode(e.target.value)}
                    rows={10}
                    className="w-full text-[12px] font-mono bg-gray-50 border border-gray-200 rounded-lg p-3 resize-none focus:outline-none focus:border-blue-400 transition-colors"
                    placeholder="输入代码…"
                  />
                  <button
                    onClick={runSandbox}
                    disabled={running || !sbCode.trim()}
                    className="mt-2 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gray-900 text-white text-[12px] font-medium hover:bg-gray-700 disabled:opacity-40 transition-colors"
                  >
                    {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                    {running ? "执行中…" : `运行 ${sbLang}`}
                  </button>
                </div>

                {sbResult && (
                  <div className="bg-[#1a1a2e] rounded-xl overflow-hidden font-mono">
                    <div className="flex items-center gap-2 px-4 py-2 border-b border-white/10">
                      {sbResult.success ? (
                        <CheckCircle2 size={12} className="text-green-400" />
                      ) : (
                        <AlertCircle size={12} className="text-red-400" />
                      )}
                      <span className="text-[11px] text-white/60">
                        {sbResult.language} · {sbResult.exec_ms.toFixed(0)}ms
                      </span>
                    </div>
                    {sbResult.stdout && (
                      <pre className="px-4 py-3 text-[12px] text-green-300 whitespace-pre-wrap">{sbResult.stdout}</pre>
                    )}
                    {sbResult.stderr && (
                      <pre className="px-4 py-3 text-[12px] text-yellow-300 whitespace-pre-wrap">{sbResult.stderr}</pre>
                    )}
                    {sbResult.error && !sbResult.success && (
                      <pre className="px-4 py-3 text-[12px] text-red-400 whitespace-pre-wrap">Error: {sbResult.error}</pre>
                    )}
                    {sbResult.figures?.map((fig, i) => (
                      <div key={i} className="px-4 pb-3">
                        <img src={`data:image/${fig.format};base64,${fig.base64}`} alt={`figure-${i}`} className="max-w-full rounded" />
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
