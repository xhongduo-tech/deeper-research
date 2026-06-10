import { useState, useRef, useEffect, useCallback } from "react";
import { Paperclip, ArrowUp, AtSign, Presentation, FileText, Table2, X, FileImage, File, FolderOpen, ChevronDown, Check, Plus, Search } from "lucide-react";
import { api, Project } from "../lib/api";
import { ModelSelector, EffortLevel } from "./ModelSelector";
import { ScenarioSuggestion } from "./SuggestionChips";

type AgentKey = "ppt" | "docs" | "sheet";
type OutputFormat = "word" | "pptx" | "xlsx";

const AGENTS = [
  { key: "ppt",   icon: Presentation, label: "Agent PPT",  desc: "生成演示文稿，自动排版设计", color: "#f59e0b", bg: "rgba(245,158,11,0.10)" },
  { key: "docs",  icon: FileText,     label: "Agent 文档", desc: "撰写报告、分析文档、整理内容", color: "#2563eb", bg: "rgba(37,99,235,0.10)" },
  { key: "sheet", icon: Table2,       label: "Agent 表格", desc: "处理数据、生成图表、统计分析", color: "#059669", bg: "rgba(5,150,105,0.10)" },
] as const;

interface UploadedFile { file: File; name: string; size: string; type: string; }

export function ChatInput({
  isLoggedIn = true,
  onNeedLogin,
  onSubmit,
  busy = false,
  selectedScenario,
  onClearScenario,
  prefillText,
  onPrefillConsumed,
  onAgentSelect,
  currentProjectId,
  onSelectProject,
}: {
  isLoggedIn?: boolean;
  onNeedLogin?: () => void;
  onSubmit?: (payload: { prompt: string; outputFormat: OutputFormat; files?: File[]; scenario?: string | null; reportType?: string | null; modelId?: string | null; effort?: EffortLevel; mode?: "chat" | "agent"; skills?: string[]; project_id?: number | null }) => void;
  busy?: boolean;
  selectedScenario?: ScenarioSuggestion | null;
  onClearScenario?: () => void;
  prefillText?: string;
  onPrefillConsumed?: () => void;
  onAgentSelect?: (agentKey: AgentKey) => void;
  currentProjectId?: number | null;
  onSelectProject?: (projectId: number | null) => void;
}) {
  const [value, setValue] = useState("");
  const [showAgents, setShowAgents] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<(typeof AGENTS)[number] | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [model, setModel] = useState("dataagent-2");
  const [effort, setEffort] = useState<EffortLevel>("low");
  const [focused, setFocused] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [createProjectError, setCreateProjectError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const atBtnRef = useRef<HTMLButtonElement>(null);
  const agentPopRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const projectDropdownRef = useRef<HTMLDivElement>(null);

  // Load projects for selector
  useEffect(() => {
    if (!isLoggedIn) return;
    api.listProjects().then(res => setProjects(res.items || [])).catch(() => setProjects([]));
  }, [isLoggedIn]);

  const hasValue = value.trim().length > 0 || files.length > 0 || !!selectedAgent || !!selectedScenario;

  // Auto-resize textarea based on content
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newHeight = Math.min(el.scrollHeight, 260);
    el.style.height = `${newHeight}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleSend = () => {
    if (!isLoggedIn) { onNeedLogin?.(); return; }
    if (!hasValue || busy) return;
    const prompt = value.trim() || selectedScenario?.placeholder || "请根据上传文件生成分析报告";
    const inferred = inferAgentIntent(prompt);
    const agentKey = selectedAgent?.key || selectedScenario?.agent || inferred?.agent;
    const outputFormat = selectedAgent
      ? outputFormatForAgent(selectedAgent.key)
      : selectedScenario?.outputFormat || inferred?.outputFormat || "word";
    const scenarioSkills = selectedScenario?.skills || [];
    const inferredSkills = inferred?.skills || [];
    onSubmit?.({
      prompt,
      outputFormat,
      files: files.map((f) => f.file),
      scenario: selectedScenario?.label || selectedAgent?.label || inferred?.scenario || null,
      reportType: selectedScenario?.reportType || inferred?.reportType || null,
      modelId: model,
      effort,
      mode: agentKey ? "agent" : "chat",
      skills: uniqueSkills([...scenarioSkills, ...inferredSkills]),
      project_id: currentProjectId,
    });
    setValue("");
    setFiles([]);
    onClearScenario?.();
    // Reset height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  useEffect(() => {
    if (!showAgents) return;
    const handler = (e: MouseEvent) => {
      if (
        agentPopRef.current && !agentPopRef.current.contains(e.target as Node) &&
        atBtnRef.current && !atBtnRef.current.contains(e.target as Node)
      ) setShowAgents(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showAgents]);

  useEffect(() => {
    if (!projectDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(e.target as Node)) {
        setProjectDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [projectDropdownOpen]);

  useEffect(() => {
    if (!prefillText) return;
    setValue(prefillText);
    onPrefillConsumed?.();
    setTimeout(() => textareaRef.current?.focus(), 0);
  }, [prefillText]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    setFiles((prev) => [...prev, ...picked.map((f) => ({ file: f, name: f.name, size: formatSize(f.size), type: f.type }))]);
    e.target.value = "";
  };

  const selectAgent = (agent: (typeof AGENTS)[number]) => {
    setSelectedAgent(agent);
    setShowAgents(false);
    onAgentSelect?.(agent.key);
  };

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    if (!name) return;
    setCreatingProject(true);
    setCreateProjectError("");
    try {
      const newProject = await api.createProject(name);
      setProjects((prev) => [...prev, newProject]);
      onSelectProject?.(newProject.id);
      setShowCreateModal(false);
      setNewProjectName("");
    } catch {
      setCreateProjectError("创建项目失败，请重试");
    } finally {
      setCreatingProject(false);
    }
  };

  return (
    <div className="w-full" style={{ position: "relative", zIndex: 10 }}>
      <style>{`
        @keyframes agent-pop-up {
          from { opacity: 0; transform: translateY(4px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .ci-container {
          background: #fff;
          border-radius: 18px;
          border: 1px solid rgba(0,0,0,.12);
          box-shadow: 0 2px 12px rgba(0,0,0,.06), 0 0 0 0 transparent;
          transition: box-shadow 0.18s ease, border-color 0.18s ease;
        }
        .ci-container.ci-focused {
          border-color: rgba(0,0,0,.22);
          box-shadow: 0 4px 20px rgba(0,0,0,.10);
        }
        .ci-textarea {
          width: 100%;
          min-height: 72px;
          max-height: 260px;
          resize: none;
          border: none;
          outline: none;
          padding: 18px 16px 8px;
          background: transparent;
          font-size: 15px;
          line-height: 1.65;
          color: var(--ink-900, #111);
          overflow-y: auto;
          scrollbar-width: none;
          font-family: inherit;
        }
        .ci-textarea::-webkit-scrollbar { display: none; }
        .ci-textarea::placeholder { color: var(--ink-400, #9ca3af); }
        .ci-icon-btn {
          height: 34px;
          width: 34px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          border: none;
          background: transparent;
          cursor: pointer;
          color: var(--ink-500, #6b7280);
          transition: background 0.14s ease, color 0.14s ease;
          flex-shrink: 0;
        }
        .ci-icon-btn:hover { background: rgba(0,0,0,.06); color: var(--ink-800, #1f2937); }
        .ci-send-btn {
          height: 34px;
          width: 34px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          border: none;
          cursor: pointer;
          flex-shrink: 0;
          transition: background 0.14s ease, transform 0.1s ease;
        }
        .ci-send-btn:not(:disabled):active { transform: scale(0.92); }
        .ci-send-btn:disabled { cursor: not-allowed; }
        .ci-chip {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          height: 26px;
          padding: 0 8px 0 7px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 600;
          flex-shrink: 0;
        }
        .ci-chip-close {
          height: 16px;
          width: 16px;
          border-radius: 50%;
          border: none;
          background: transparent;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          margin-left: 1px;
          transition: background 0.12s ease;
        }
        .ci-chip-close:hover { background: rgba(0,0,0,.1); }
        .ci-file-chip {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 6px 10px;
          border-radius: 10px;
          background: rgba(0,0,0,.04);
          border: 1px solid rgba(0,0,0,.07);
          font-size: 12px;
        }
      `}</style>

      <div className={`ci-container${focused ? " ci-focused" : ""}`}>
        {/* Uploaded files */}
        {files.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-3 pt-3 pb-1">
            {files.map((f, i) => (
              <div key={i} className="ci-file-chip">
                <FileIcon type={f.type} />
                <div style={{ maxWidth: 140 }}>
                  <div className="truncate" style={{ color: "var(--ink-900, #111)", fontWeight: 500 }}>{f.name}</div>
                  <div style={{ fontSize: "11px", color: "var(--ink-400, #9ca3af)", marginTop: 1 }}>{f.size}</div>
                </div>
                <button
                  onClick={() => setFiles((p) => p.filter((_, idx) => idx !== i))}
                  className="ci-icon-btn"
                  style={{ height: 18, width: 18, fontSize: 10 }}
                >
                  <X style={{ width: 11, height: 11 }} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Agent chip is still shown above textarea for in-chat context. */}
        {selectedAgent && (
          <div className="flex flex-wrap gap-1.5 px-3 pt-2.5 pb-0">
            {(() => {
              const Icon = selectedAgent.icon;
              return (
                <span className="ci-chip" style={{ background: selectedAgent.bg, color: selectedAgent.color, border: `1px solid ${selectedAgent.color}25` }}>
                  <Icon style={{ width: 11, height: 11 }} />
                  {selectedAgent.label}
                  <button className="ci-chip-close" style={{ color: selectedAgent.color }} onClick={() => setSelectedAgent(null)}>
                    <X style={{ width: 9, height: 9 }} />
                  </button>
                </span>
              );
            })()}
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          className="ci-textarea"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!e.nativeEvent.isComposing) handleSend();
            }
          }}
          placeholder={selectedScenario?.placeholder ?? "向 DataAgent 提问..."}
          rows={1}
        />

        {/* Bottom toolbar */}
        <div className="flex items-center gap-1 px-2.5 pb-2.5 pt-1">
          {/* Attach */}
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileChange} accept="*/*" />
          <button className="ci-icon-btn" onClick={() => fileInputRef.current?.click()} title="上传文件">
            <Paperclip style={{ width: 16, height: 16 }} />
          </button>

          {/* @ agents popup */}
          <div className="relative">
            <button
              ref={atBtnRef}
              className="ci-icon-btn"
              onClick={() => setShowAgents((v) => !v)}
              title="选择智能体"
              style={{
                color: showAgents || selectedAgent ? "var(--brand, #5b4ee8)" : undefined,
                background: showAgents || selectedAgent ? "var(--brand-soft, rgba(91,78,232,0.08))" : undefined,
              }}
            >
              <AtSign style={{ width: 16, height: 16 }} />
            </button>

            {showAgents && (
              <div
                ref={agentPopRef}
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  left: 0,
                  width: 232,
                  background: "#fff",
                  border: "1px solid rgba(0,0,0,.1)",
                  boxShadow: "0 8px 32px rgba(0,0,0,.12)",
                  borderRadius: 14,
                  overflow: "hidden",
                  zIndex: 30,
                  animation: "agent-pop-up 0.15s cubic-bezier(0.34,1.4,0.64,1)",
                }}
              >
                <div style={{ padding: "8px 6px 6px" }}>
                  <div style={{ padding: "0 8px 6px", fontSize: 11, fontWeight: 700, color: "var(--ink-400, #9ca3af)", letterSpacing: "0.05em" }}>
                    选择智能体
                  </div>
                  {AGENTS.map((a) => {
                    const Icon = a.icon;
                    return (
                      <button
                        key={a.key}
                        onClick={() => selectAgent(a)}
                        style={{
                          width: "100%", display: "flex", alignItems: "center", gap: 10,
                          padding: "8px 10px", borderRadius: 10, border: "none", background: "transparent",
                          cursor: "pointer", textAlign: "left", transition: "background .12s",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(0,0,0,.05)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <div style={{ height: 28, width: 28, borderRadius: 8, background: a.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          <Icon style={{ color: a.color, width: 14, height: 14 }} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--ink-900, #111)" }}>{a.label}</div>
                          <div style={{ fontSize: 11.5, color: "var(--ink-400, #9ca3af)", marginTop: 1 }}>{a.desc}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Project selector — pill dropdown */}
          <div className="relative" ref={projectDropdownRef}>
            <button
              onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
              className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full transition hover:bg-[var(--hover)] whitespace-nowrap flex-shrink-0"
              style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
            >
              <FolderOpen size={13} style={{ color: "var(--ink-500)" }} />
              <span style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)" }}>
                {projects.find((p) => p.id === currentProjectId)?.name || "不使用项目"}
              </span>
              <ChevronDown
                size={11}
                className={`transition-transform ${projectDropdownOpen ? "rotate-180" : ""}`}
                style={{ color: "var(--ink-500)" }}
              />
            </button>

            {projectDropdownOpen && (
              <>
                <div className="fixed inset-0 z-[110]" onClick={() => setProjectDropdownOpen(false)} />
                <div
                  className="absolute left-0 top-full mt-2 w-[260px] max-h-[320px] overflow-y-auto rounded-xl border shadow-xl z-[120] bg-white"
                  style={{ borderColor: "var(--border)" }}
                >
                  {/* Search */}
                  <div className="p-2 border-b" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-gray-50">
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
                  {/* Project list */}
                  <div className="p-1.5">
                    {projects
                      .filter((p) => !projectSearch || p.name.toLowerCase().includes(projectSearch.toLowerCase()))
                      .map((project) => (
                        <button
                          key={project.id}
                          onClick={() => {
                            onSelectProject?.(project.id);
                            setProjectDropdownOpen(false);
                          }}
                          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors hover:bg-gray-50"
                        >
                          <FolderOpen size={13} style={{ color: "var(--ink-500)" }} />
                          <span
                            className="text-[12px] font-medium truncate flex-1"
                            style={{ color: "var(--ink-800)" }}
                          >
                            {project.name}
                          </span>
                          {currentProjectId === project.id && (
                            <Check size={12} style={{ color: "var(--brand)" }} />
                          )}
                        </button>
                      ))}
                    {projects.filter((p) =>
                      !projectSearch || p.name.toLowerCase().includes(projectSearch.toLowerCase())
                    ).length === 0 && (
                      <p className="text-[11px] text-gray-400 px-2 py-1">无匹配项目</p>
                    )}
                  </div>
                  {/* Actions */}
                  <div className="border-t p-1.5 space-y-0.5" style={{ borderColor: "var(--border)" }}>
                    <button
                      onClick={() => {
                        setProjectDropdownOpen(false);
                        if (!isLoggedIn) { onNeedLogin?.(); return; }
                        setNewProjectName("");
                        setCreateProjectError("");
                        setShowCreateModal(true);
                      }}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors hover:bg-gray-50"
                    >
                      <Plus size={13} style={{ color: "var(--ink-500)" }} />
                      <span className="text-[12px] font-medium" style={{ color: "var(--ink-700)" }}>
                        添加新项目
                      </span>
                    </button>
                    <button
                      onClick={() => {
                        onSelectProject?.(null);
                        setProjectDropdownOpen(false);
                      }}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors hover:bg-gray-50"
                    >
                      <X size={13} style={{ color: "var(--ink-500)" }} />
                      <span className="text-[12px] font-medium" style={{ color: "var(--ink-700)" }}>
                        不使用项目
                      </span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>


          {selectedScenario && (() => {
            const Icon = selectedScenario.icon;
            return (
              <span className="ci-chip" style={{ background: selectedScenario.bg, color: selectedScenario.color, border: `1px solid ${selectedScenario.color}25`, marginLeft: 2 }}>
                <Icon style={{ width: 11, height: 11 }} />
                {selectedScenario.label}
                <button className="ci-chip-close" style={{ color: selectedScenario.color }} onClick={() => onClearScenario?.()}>
                  <X style={{ width: 9, height: 9 }} />
                </button>
              </span>
            );
          })()}

          <div style={{ flex: 1 }} />


          {/* Model selector */}
          <ModelSelector selectedModel={model} onSelect={setModel} selectedEffort={effort} onSelectEffort={setEffort} align="right" />

          <div style={{ width: 1, height: 14, background: "rgba(0,0,0,.1)", margin: "0 4px 0 2px" }} />

          {/* Send button */}
          <button
            className="ci-send-btn"
            onClick={handleSend}
            disabled={!hasValue || busy}
            style={{
              background: hasValue && !busy ? "var(--ink-900, #111)" : "rgba(0,0,0,.07)",
              color: hasValue && !busy ? "#fff" : "var(--ink-400, #9ca3af)",
            }}
            title="发送"
          >
            <ArrowUp style={{ width: 16, height: 16 }} />
          </button>
        </div>
      </div>

      <p className="text-center" style={{ fontSize: 11, marginTop: 10, color: "var(--ink-400, #9ca3af)" }}>
        DataAgent 可能会出错，请仔细核对重要信息
      </p>

      {/* Create Project Modal */}
      {showCreateModal && (
        <div
          className="fixed inset-0 flex items-center justify-center"
          style={{ zIndex: 200, background: "rgba(0,0,0,0.55)" }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowCreateModal(false);
          }}
        >
          <div
            className="w-[380px] rounded-2xl p-6"
            style={{
              background: "var(--bg-elevated, #fff)",
              border: "1px solid var(--border)",
              boxShadow: "0 24px 48px rgba(0,0,0,0.25)",
              animation: "modal-pop-up 0.2s cubic-bezier(0.34,1.4,0.64,1)",
            }}
          >
            <style>{`
              @keyframes modal-pop-up {
                from { opacity: 0; transform: translateY(16px) scale(0.96); }
                to { opacity: 1; transform: translateY(0) scale(1); }
              }
            `}</style>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-[16px] font-semibold" style={{ color: "var(--ink-900)" }}>为项目命名</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="ci-icon-btn"
                style={{ height: 28, width: 28 }}
              >
                <X size={16} style={{ color: "var(--ink-400)" }} />
              </button>
            </div>
            <p className="text-[13px] mb-4" style={{ color: "var(--ink-400)" }}>保持简短且易识别</p>
            <input
              type="text"
              autoFocus
              placeholder="新项目"
              value={newProjectName}
              onChange={(e) => { setNewProjectName(e.target.value); setCreateProjectError(""); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newProjectName.trim()) handleCreateProject();
              }}
              className="w-full px-3 py-2.5 rounded-xl text-[14px] outline-none"
              style={{
                border: "1px solid var(--border)",
                color: "var(--ink-900)",
                background: "var(--bg)",
              }}
            />
            {createProjectError && (
              <p className="text-[12px] mt-2" style={{ color: "#dc2626" }}>{createProjectError}</p>
            )}
            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 rounded-lg text-[13px] font-medium transition-colors"
                style={{ color: "var(--ink-600)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-subtle)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                取消
              </button>
              <button
                onClick={handleCreateProject}
                disabled={!newProjectName.trim() || creatingProject}
                className="px-4 py-2 rounded-lg text-[13px] font-medium text-white transition-opacity"
                style={{
                  background: "var(--ink-900)",
                  opacity: !newProjectName.trim() || creatingProject ? 0.5 : 1,
                }}
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

function outputFormatForAgent(agentKey: AgentKey): OutputFormat {
  if (agentKey === "ppt") return "pptx";
  if (agentKey === "sheet") return "xlsx";
  return "word";
}

function uniqueSkills(skills: string[]) {
  return Array.from(new Set(skills.filter(Boolean)));
}

function inferAgentIntent(text: string): {
  agent: AgentKey;
  outputFormat: OutputFormat;
  scenario: string;
  reportType: string;
  skills: string[];
} | null {
  const normalized = normalizeIntentText(text);
  const scenario = inferScenarioIntent(normalized);
  const outputIntent = inferOutputIntent(normalized, scenario);
  if (!outputIntent) return null;

  if (outputIntent === "pptx") {
    return {
      agent: "ppt",
      outputFormat: "pptx",
      scenario: scenario?.scenario || "Agent PPT",
      reportType: scenario?.reportType || "演示文稿",
      skills: uniqueSkills([...(scenario?.skills || []), "ppt-director", "ppt-narrative", "ppt-layout"]),
    };
  }

  if (outputIntent === "xlsx") {
    return {
      agent: "sheet",
      outputFormat: "xlsx",
      scenario: scenario?.scenario || "Agent 表格",
      reportType: scenario?.reportType || "数据分析",
      skills: uniqueSkills([...(scenario?.skills || []), "data-grounding", "excel-modeling"]),
    };
  }

  return {
    agent: "docs",
    outputFormat: "word",
    scenario: scenario?.scenario || "Agent 文档",
    reportType: scenario?.reportType || "文档",
    skills: scenario?.skills?.length ? scenario.skills : ["word-authoring"],
  };
}

type ScenarioIntent = {
  scenario: string;
  reportType: string;
  skills: string[];
  aliases: string[];
};

const SCENARIO_INTENTS: ScenarioIntent[] = [
  {
    scenario: "项目复盘",
    reportType: "项目复盘",
    skills: ["project-retrospective-authoring"],
    aliases: ["项目复盘", "复盘报告", "复盘材料", "复盘总结", "项目总结复盘", "postmortem", "post-mortem", "retrospective"],
  },
  {
    scenario: "年终述职",
    reportType: "述职报告",
    skills: ["performance-review-authoring"],
    aliases: ["年终述职", "年度述职", "述职报告", "述职材料", "述职ppt", "述职文档", "年度总结", "工作总结", "绩效总结", "绩效评估", "个人总结"],
  },
  {
    scenario: "季度总结",
    reportType: "述职报告",
    skills: ["performance-review-authoring"],
    aliases: ["季度总结", "季度汇报", "季度复盘", "q1总结", "q2总结", "q3总结", "q4总结", "周报总结", "月度总结", "半年总结"],
  },
  {
    scenario: "竞品调研",
    reportType: "研究报告",
    skills: ["research-report-authoring", "executive-summary"],
    aliases: ["竞品调研", "竞品分析", "竞对分析", "对标分析", "竞争分析", "产品对比", "友商分析"],
  },
  {
    scenario: "研究报告",
    reportType: "研究报告",
    skills: ["research-report-authoring", "executive-summary"],
    aliases: ["研究报告", "调研报告", "行业报告", "专项研究", "白皮书", "趋势报告", "趋势分析", "市场分析报告"],
  },
  {
    scenario: "论文写作",
    reportType: "学术论文",
    skills: ["academic-paper-authoring", "citation-bibliography"],
    aliases: ["论文写作", "学术论文", "期刊论文", "会议论文", "毕业论文", "paper", "relatedwork", "methodsection"],
  },
  {
    scenario: "经营分析",
    reportType: "经营分析",
    skills: ["business-document-authoring", "executive-summary"],
    aliases: ["经营分析", "业务分析", "经营报告", "管理汇报", "商业分析", "商业计划", "业务复盘", "业绩分析"],
  },
  {
    scenario: "预算汇报",
    reportType: "经营分析",
    skills: ["business-document-authoring", "advanced-charting", "table-figure-authoring"],
    aliases: ["预算汇报", "预算报告", "预算执行", "费用分析", "成本分析", "财务汇报", "财务分析"],
  },
  {
    scenario: "会议纪要",
    reportType: "会议纪要",
    skills: ["meeting-minutes-authoring"],
    aliases: ["会议纪要", "会议记录", "会议总结", "纪要", "会议待办", "行动项"],
  },
  {
    scenario: "培训材料",
    reportType: "培训手册",
    skills: ["training-manual-authoring"],
    aliases: ["培训材料", "培训手册", "培训课件", "培训方案", "课程材料", "操作手册", "sop", "教程"],
  },
  {
    scenario: "生成图表",
    reportType: "图表分析",
    skills: ["data-grounding", "advanced-charting", "table-figure-authoring"],
    aliases: ["生成图表", "做图表", "可视化", "数据可视化", "柱状图", "折线图", "饼图", "看板", "dashboard"],
  },
  {
    scenario: "分析数据",
    reportType: "数据分析",
    skills: ["data-grounding", "excel-modeling", "advanced-charting"],
    aliases: ["分析数据", "数据分析", "统计分析", "销售数据", "excel分析", "表格分析", "异常点", "增长趋势"],
  },
];

function normalizeIntentText(text: string) {
  return (text || "")
    .toLowerCase()
    .replace(/\s+/g, "")
    .replace(/[，。！？、；：,.!?;:()[\]{}"'`]/g, "");
}

function inferScenarioIntent(normalized: string): ScenarioIntent | null {
  return SCENARIO_INTENTS.find((item) => item.aliases.some((alias) => normalized.includes(normalizeIntentText(alias)))) || null;
}

function inferOutputIntent(normalized: string, scenario: ScenarioIntent | null): OutputFormat | null {
  const wantsPpt = /(ppt|pptx|powerpoint|幻灯片|演示文稿|汇报胶片|路演材料|演示稿)/.test(normalized)
    || /(做|生成|制作|输出|整理成|转成|形成|弄个|来个|写个).{0,8}(ppt|幻灯片|演示|课件)/.test(normalized);
  if (wantsPpt) return "pptx";

  const wantsSheet = /(excel|xlsx|xls|电子表格|数据表|统计表|明细表|表格版|做表|成表)/.test(normalized)
    || (/(分析|统计|汇总|清洗|处理)/.test(normalized) && /(数据|表格|excel|csv)/.test(normalized));
  if (wantsSheet) return "xlsx";

  const wantsWord = /(word|docx|doc|文档|报告|材料|稿子|正文|word版|文档版)/.test(normalized)
    || /(生成|做成|做一个|制作|输出|整理成|转成|形成|弄个|来个|写个|写一份|生成一份).{0,10}(word|文档|报告|材料|稿子)/.test(normalized);
  if (wantsWord) return "word";

  return scenario && /(生成|做|制作|输出|整理|写|撰写|形成|产出)/.test(normalized) ? "word" : null;
}

function FileIcon({ type }: { type: string }) {
  if (type.startsWith("image/")) return <FileImage style={{ width: 14, height: 14, color: "#2563eb", flexShrink: 0 }} />;
  return <File style={{ width: 14, height: 14, color: "var(--ink-400, #9ca3af)", flexShrink: 0 }} />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
