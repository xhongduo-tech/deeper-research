import { useState, useRef, useEffect, useCallback } from "react";
import { Paperclip, ArrowUp, AtSign, Presentation, FileText, Table2, X, FileImage, File } from "lucide-react";
import { ModelSelector, EffortLevel } from "./ModelSelector";
import { ScenarioSuggestion } from "./SuggestionChips";
import { DatabaseSelector, DBSelection } from "./DatabaseSelector";

const AGENTS = [
  { key: "ppt",   icon: Presentation, label: "Agent PPT",  desc: "生成演示文稿，自动排版设计", color: "#f59e0b", bg: "rgba(245,158,11,0.10)" },
  { key: "docs",  icon: FileText,     label: "Agent 文档", desc: "撰写报告、分析文档、整理内容", color: "#2563eb", bg: "rgba(37,99,235,0.10)" },
  { key: "sheet", icon: Table2,       label: "Agent 表格", desc: "处理数据、生成图表、统计分析", color: "#059669", bg: "rgba(5,150,105,0.10)" },
];

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
}: {
  isLoggedIn?: boolean;
  onNeedLogin?: () => void;
  onSubmit?: (payload: { prompt: string; outputFormat: "word" | "pptx" | "xlsx"; files?: File[]; scenario?: string | null; modelId?: string | null; effort?: EffortLevel; mode?: "chat" | "agent"; kb_ids?: number[]; include_system_kb?: boolean }) => void;
  busy?: boolean;
  selectedScenario?: ScenarioSuggestion | null;
  onClearScenario?: () => void;
  prefillText?: string;
  onPrefillConsumed?: () => void;
}) {
  const [value, setValue] = useState("");
  const [showAgents, setShowAgents] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<(typeof AGENTS)[number] | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [model, setModel] = useState("dataagent-2");
  const [effort, setEffort] = useState<EffortLevel>("low");
  const [dbSelection, setDbSelection] = useState<DBSelection>({ kb_ids: [], include_system: true });
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const atBtnRef = useRef<HTMLButtonElement>(null);
  const agentPopRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasValue = value.trim().length > 0 || files.length > 0 || !!selectedAgent;

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
    const outputFormat = selectedAgent?.key === "ppt" ? "pptx" : selectedAgent?.key === "sheet" ? "xlsx" : "word";
    onSubmit?.({
      prompt: value.trim() || selectedScenario?.placeholder || "请根据上传文件生成分析报告",
      outputFormat,
      files: files.map((f) => f.file),
      scenario: selectedScenario?.label || selectedAgent?.label || null,
      modelId: model,
      effort,
      mode: selectedAgent ? "agent" : "chat",
      kb_ids: dbSelection.kb_ids,
      include_system_kb: dbSelection.include_system,
    });
    setValue("");
    setFiles([]);
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
  };

  return (
    <div className="w-full">
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

        {/* Chips row (agent + scenario) — shown above textarea */}
        {(selectedAgent || selectedScenario) && (
          <div className="flex flex-wrap gap-1.5 px-3 pt-2.5 pb-0">
            {selectedAgent && (() => {
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
            {selectedScenario && (() => {
              const Icon = selectedScenario.icon;
              return (
                <span className="ci-chip" style={{ background: selectedScenario.bg, color: selectedScenario.color, border: `1px solid ${selectedScenario.color}25` }}>
                  <Icon style={{ width: 11, height: 11 }} />
                  {selectedScenario.label}
                  <button className="ci-chip-close" style={{ color: selectedScenario.color }} onClick={() => onClearScenario?.()}>
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
                  bottom: "calc(100% + 8px)",
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

          <div style={{ flex: 1 }} />

          {/* Hint */}
          <span style={{ fontSize: "11px", color: "var(--ink-300, #d1d5db)", userSelect: "none", whiteSpace: "nowrap" }}>
            Shift ↵ 换行
          </span>
          <div style={{ width: 1, height: 14, background: "rgba(0,0,0,.1)", margin: "0 6px" }} />

          {/* Database selector */}
          <DatabaseSelector selection={dbSelection} onChange={setDbSelection} />

          <div style={{ width: 1, height: 14, background: "rgba(0,0,0,.1)", margin: "0 4px 0 2px" }} />

          {/* Model selector */}
          <ModelSelector selectedModel={model} onSelect={setModel} selectedEffort={effort} onSelectEffort={setEffort} placement="top" align="right" />

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
    </div>
  );
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
