import { useState, useEffect, useCallback } from "react";
import { Database, Check, ChevronDown, X, Layers, Server, FolderOpen } from "lucide-react";
import { api, KnowledgeBase, OfficialDataSource } from "../lib/api";

export type DBSelection = {
  kb_ids: number[];
  include_system: boolean;
};

export function DatabaseSelector({
  selection,
  onChange,
  children,
}: {
  selection: DBSelection;
  onChange: (s: DBSelection) => void;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [userKbs, setUserKbs] = useState<KnowledgeBase[]>([]);
  const [systemSources, setSystemSources] = useState<OfficialDataSource[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [kbRes, srcRes] = await Promise.all([
        api.listKBs(),
        api.listOfficialSources(),
      ]);
      setUserKbs(kbRes.items || []);
      setSystemSources(srcRes.sources || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadData();
  }, [open, loadData]);

  const toggleUserKb = (id: number) => {
    const ids = new Set(selection.kb_ids);
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    onChange({ ...selection, kb_ids: Array.from(ids) });
  };

  const selectedCount =
    (selection.include_system ? systemSources.length : 0) +
    selection.kb_ids.length;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium transition-colors hover:bg-gray-100"
        style={{ color: "var(--ink-700)" }}
      >
        <Database size={14} />
        <span>数据库</span>
        {selectedCount > 0 && (
          <span className="ml-0.5 px-1.5 py-0 rounded-full bg-emerald-500 text-white text-[10px]">
            {selectedCount}
          </span>
        )}
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {children}

      {open && (
        <>
          <div className="fixed inset-0 z-[110]" onClick={() => setOpen(false)} />
          <div
            className="absolute right-0 top-full mt-2 w-[360px] max-h-[480px] overflow-y-auto rounded-xl border shadow-xl z-[120] bg-white"
            style={{ borderColor: "var(--border)" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
              <div className="flex items-center gap-2">
                <Layers size={15} style={{ color: "var(--ink-600)" }} />
                <span className="text-[13px] font-semibold" style={{ color: "var(--ink-900)" }}>知识库选择</span>
              </div>
              <button onClick={() => setOpen(false)} className="p-1 rounded hover:bg-gray-100">
                <X size={14} style={{ color: "var(--ink-400)" }} />
              </button>
            </div>

            {loading ? (
              <div className="p-6 text-center text-[12px] text-gray-400">加载中…</div>
            ) : (
              <div className="p-3 space-y-3">
                {/* System KBs Toggle */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5">
                      <Server size={13} style={{ color: "var(--ink-500)" }} />
                      <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">系统数据库</span>
                    </div>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <span className="text-[11px] text-gray-500">使用全部</span>
                      <div
                        className={`w-8 h-4.5 rounded-full transition-colors relative ${selection.include_system ? "bg-emerald-500" : "bg-gray-300"}`}
                        onClick={() => onChange({ ...selection, include_system: !selection.include_system })}
                      >
                        <div className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white transition-transform ${selection.include_system ? "translate-x-4" : "translate-x-0.5"}`} />
                      </div>
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {systemSources.slice(0, 8).map((src) => (
                      <span
                        key={src.key}
                        className={`px-2 py-0.5 rounded-md text-[10px] border transition-colors ${
                          selection.include_system
                            ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                            : "bg-gray-50 border-gray-200 text-gray-400"
                        }`}
                      >
                        {src.name}
                      </span>
                    ))}
                    {systemSources.length > 8 && (
                      <span className="px-2 py-0.5 rounded-md text-[10px] bg-gray-50 text-gray-400">
                        +{systemSources.length - 8}
                      </span>
                    )}
                  </div>
                </div>

                {/* Divider */}
                <div className="h-px bg-gray-100" />

                {/* User KBs */}
                <div>
                  <div className="flex items-center gap-1.5 mb-2">
                    <FolderOpen size={13} style={{ color: "var(--ink-500)" }} />
                    <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">用户数据库</span>
                  </div>
                  {userKbs.length === 0 ? (
                    <p className="text-[11px] text-gray-400 px-1">暂无用户知识库</p>
                  ) : (
                    <div className="space-y-1">
                      {userKbs.map((kb) => {
                        const checked = selection.kb_ids.includes(kb.id);
                        return (
                          <button
                            key={kb.id}
                            onClick={() => toggleUserKb(kb.id)}
                            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors ${
                              checked ? "bg-emerald-50" : "hover:bg-gray-50"
                            }`}
                          >
                            <div
                              className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                checked ? "bg-emerald-500 border-emerald-500" : "border-gray-300"
                              }`}
                            >
                              {checked && <Check size={10} className="text-white" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-[12px] font-medium truncate" style={{ color: "var(--ink-800)" }}>
                                {kb.name}
                              </p>
                              <p className="text-[10px] text-gray-400">
                                {kb.doc_count || 0} 篇 · {kb.size_display || "0 B"}
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
