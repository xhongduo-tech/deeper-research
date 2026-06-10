import { useState, useEffect, useCallback } from "react";
import { Database, Check, ChevronDown, X, Layers, Server, FolderOpen, Briefcase } from "lucide-react";
import { api, KnowledgeBase, OfficialDataSource, Project } from "../lib/api";

export type DBSelection = {
  kb_ids: number[];
  include_system: boolean;
};

export function DatabaseSelector({
  selection,
  onChange,
  children,
  variant = "default",
}: {
  selection: DBSelection;
  onChange: (s: DBSelection) => void;
  children?: React.ReactNode;
  variant?: "default" | "pill" | "icon";
}) {
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [projectKBs, setProjectKBs] = useState<KnowledgeBase[]>([]);
  const [userKbs, setUserKbs] = useState<KnowledgeBase[]>([]);
  const [systemSources, setSystemSources] = useState<OfficialDataSource[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [projectRes, kbRes, srcRes] = await Promise.all([
        api.listProjects(),
        api.listKBs(),
        api.listOfficialSources(),
      ]);
      setProjects(projectRes.items || []);
      setUserKbs(kbRes.items || []);
      setSystemSources(srcRes.sources || []);

      // Try to restore selected project from localStorage
      const savedProjectId = localStorage.getItem("da_selected_project_id");
      if (savedProjectId) {
        const pid = Number(savedProjectId);
        const exists = (projectRes.items || []).some((p) => p.id === pid);
        if (exists) {
          setSelectedProjectId(pid);
        }
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadData();
  }, [open, loadData]);

  // Load project KBs when selected project changes
  useEffect(() => {
    if (selectedProjectId == null) {
      setProjectKBs([]);
      return;
    }
    api.listProjectKBs(selectedProjectId)
      .then((res) => setProjectKBs(res.items || []))
      .catch(() => setProjectKBs([]));
  }, [selectedProjectId]);

  const toggleUserKb = (id: number) => {
    const ids = new Set(selection.kb_ids);
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    onChange({ ...selection, kb_ids: Array.from(ids) });
  };

  const handleSelectProject = (projectId: number | null) => {
    setSelectedProjectId(projectId);
    if (projectId != null) {
      localStorage.setItem("da_selected_project_id", String(projectId));
    } else {
      localStorage.removeItem("da_selected_project_id");
    }
  };

  const displayedKbs = selectedProjectId != null ? projectKBs : userKbs;

  const selectedCount =
    (selection.include_system ? systemSources.length : 0) +
    selection.kb_ids.length;

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <div className="relative">
      {/* ── icon variant: home-page ChatInput toolbar ── */}
      {variant === "icon" && (
        <button
          onClick={() => setOpen(!open)}
          title="数据库"
          style={{
            height: 34, width: 34, position: "relative",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            borderRadius: "50%", border: "none", background: "transparent",
            cursor: "pointer",
            color: selectedCount > 0 ? "var(--brand, #5b4ee8)" : "var(--ink-500, #6b7280)",
            transition: "background 0.14s ease, color 0.14s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(0,0,0,.06)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
        >
          <Database style={{ width: 16, height: 16 }} />
          {selectedCount > 0 && (
            <span style={{
              position: "absolute", top: 3, right: 3,
              fontSize: 8, lineHeight: "12px", fontWeight: 700,
              background: "#10b981", color: "#fff",
              borderRadius: 999, padding: "0 2.5px",
            }}>
              {selectedCount}
            </span>
          )}
        </button>
      )}

      {/* ── pill variant: docs/HTML toolbar ── */}
      {variant === "pill" && (
        <button
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1 h-7 px-2.5 rounded-full transition hover:bg-[var(--hover)] whitespace-nowrap flex-shrink-0"
          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
        >
          <Database size={13} style={{ color: "var(--ink-500)" }} />
          <span style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)" }}>数据库</span>
          {selectedCount > 0 && (
            <span style={{ fontSize: "10px", background: "#10b981", color: "#fff", borderRadius: 999, padding: "0 5px", marginLeft: 1 }}>
              {selectedCount}
            </span>
          )}
          <ChevronDown size={11} className={`transition-transform ${open ? "rotate-180" : ""}`} style={{ color: "var(--ink-500)" }} />
        </button>
      )}

      {/* ── default variant ── */}
      {variant === "default" && (
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
      )}

      {children}

      {open && (
        <>
          <div className="fixed inset-0 z-[110]" onClick={() => setOpen(false)} />
          <div
            className={`absolute ${variant === "default" ? "right-0" : "left-0"} top-full mt-2 w-[380px] max-h-[520px] overflow-y-auto rounded-xl border shadow-xl z-[120] bg-white`}
            style={{ borderColor: "var(--border)" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
              <div className="flex items-center gap-2">
                <Layers size={15} style={{ color: "var(--ink-600)" }} />
                <span className="text-[13px] font-semibold" style={{ color: "var(--ink-900)" }}>数据库选择</span>
              </div>
              <button onClick={() => setOpen(false)} className="p-1 rounded hover:bg-gray-100">
                <X size={14} style={{ color: "var(--ink-400)" }} />
              </button>
            </div>

            {loading ? (
              <div className="p-6 text-center text-[12px] text-gray-400">加载中…</div>
            ) : (
              <div className="p-3 space-y-3">
                {/* Project Selector */}
                {projects.length > 0 && (
                  <div>
                    <div className="flex items-center gap-1.5 mb-2">
                      <Briefcase size={13} style={{ color: "var(--ink-500)" }} />
                      <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">项目维度</span>
                    </div>
                    <div className="space-y-1">
                      <button
                        onClick={() => handleSelectProject(null)}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors ${
                          selectedProjectId == null ? "bg-indigo-50" : "hover:bg-gray-50"
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                            selectedProjectId == null ? "bg-indigo-500 border-indigo-500" : "border-gray-300"
                          }`}
                        >
                          {selectedProjectId == null && <Check size={10} className="text-white" />}
                        </div>
                        <span className="text-[12px] font-medium" style={{ color: "var(--ink-800)" }}>
                          全部项目
                        </span>
                      </button>
                      {projects.map((project) => {
                        const checked = selectedProjectId === project.id;
                        return (
                          <button
                            key={project.id}
                            onClick={() => handleSelectProject(project.id)}
                            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors ${
                              checked ? "bg-indigo-50" : "hover:bg-gray-50"
                            }`}
                          >
                            <div
                              className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                checked ? "bg-indigo-500 border-indigo-500" : "border-gray-300"
                              }`}
                            >
                              {checked && <Check size={10} className="text-white" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-[12px] font-medium truncate" style={{ color: "var(--ink-800)" }}>
                                {project.name}
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Divider */}
                <div className="h-px bg-gray-100" />

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
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5">
                      <FolderOpen size={13} style={{ color: "var(--ink-500)" }} />
                      <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                        {selectedProject ? `「${selectedProject.name}」数据库` : "用户数据库"}
                      </span>
                    </div>
                    {selectedProjectId != null && (
                      <span className="text-[10px] text-gray-400">
                        {displayedKbs.length} 个知识库
                      </span>
                    )}
                  </div>
                  {displayedKbs.length === 0 ? (
                    <p className="text-[11px] text-gray-400 px-1">
                      {selectedProjectId != null
                        ? "该项目暂无知识库，请在数据库页面创建"
                        : "暂无用户数据库"}
                    </p>
                  ) : (
                    <div className="space-y-1">
                      {displayedKbs.map((kb) => {
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
