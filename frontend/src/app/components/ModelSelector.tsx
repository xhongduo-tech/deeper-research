import { useState, useRef, useEffect } from "react";
import { ChevronDown, ChevronRight, Check } from "lucide-react";

// Fallback models when backend is unavailable
const FALLBACK_MODELS = [
  { id: "flash", name: "Flash", desc: "极速问答",  badge: "推荐" },
  { id: "pro",   name: "Pro",   desc: "专业推理", badge: "专业" },
];

export const MODELS = FALLBACK_MODELS;

export type EffortLevel = "low" | "medium" | "high";

export const EFFORT_LEVELS: { id: EffortLevel; label: string; desc: string; isDefault?: boolean }[] = [
  { id: "low",    label: "Low",    desc: "最快速，适合日常问答", isDefault: true },
  { id: "medium", label: "Medium", desc: "更多推理步骤，质量更高" },
  { id: "high",   label: "High",   desc: "深度分析，最慢但最全面" },
];

type BackendModel = {
  id: string;
  name: string;
  description?: string;
  tier?: string;
  active?: boolean;
};

// Fetch the enabled model pool from backend (public endpoint, no auth required)
let _modelCache: BackendModel[] | null = null;
let _fetchPromise: Promise<BackendModel[]> | null = null;

async function fetchBackendModels(): Promise<BackendModel[]> {
  if (_modelCache) return _modelCache;
  if (_fetchPromise) return _fetchPromise;
  _fetchPromise = fetch("/api/system/models")
    .then((r) => r.json())
    .then((data) => {
      const items: BackendModel[] = (data.models || []).map((m: BackendModel) => ({
        id: m.id,
        name: m.name || m.id,
        description: m.description || "",
        tier: m.tier || "standard",
        active: !!m.active,
      }));
      _modelCache = items.length > 0 ? items : null;
      return items;
    })
    .catch(() => {
      _fetchPromise = null;
      return [] as BackendModel[];
    });
  return _fetchPromise;
}

export function ModelSelector({
  selectedModel,
  onSelect,
  selectedEffort = "low",
  onSelectEffort,
  placement = "bottom",
  align = "left",
}: {
  selectedModel: string;
  onSelect: (id: string) => void;
  selectedEffort?: EffortLevel;
  onSelectEffort?: (effort: EffortLevel) => void;
  placement?: "top" | "bottom";
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const [effortOpen, setEffortOpen] = useState(false);
  const [models, setModels] = useState<BackendModel[]>(FALLBACK_MODELS);
  const ref = useRef<HTMLDivElement>(null);

  // Load models from backend on mount
  useEffect(() => {
    fetchBackendModels().then((backendModels) => {
      if (backendModels.length === 0) return;
      setModels(backendModels);
      // Auto-select the active model if the current selection is not in the list
      const exists = backendModels.some((m) => m.id === selectedModel);
      if (!exists) {
        const active = backendModels.find((m) => m.active) || backendModels[0];
        if (active) onSelect(active.id);
      }
    });
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setEffortOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const current = models.find((m) => m.id === selectedModel) ?? models[0];
  const currentEffort = EFFORT_LEVELS.find((e) => e.id === selectedEffort) ?? EFFORT_LEVELS[0];
  const isTop = placement === "top";

  const dropdownStyle: React.CSSProperties = {
    position: "absolute",
    zIndex: 50,
    ...(align === "right" ? { right: 0 } : { left: 0 }),
    ...(isTop ? { bottom: "calc(100% + 6px)" } : { top: "calc(100% + 6px)" }),
    background: "var(--bg-elevated, #fff)",
    border: "1px solid rgba(0,0,0,.1)",
    boxShadow: "0 8px 28px rgba(0,0,0,.12)",
    borderRadius: 14,
    overflow: "visible",
    minWidth: 200,
    animation: `ms-appear 0.15s cubic-bezier(0.34,1.4,0.64,1)`,
  };

  const effortPanelStyle: React.CSSProperties = {
    position: "absolute",
    ...(align === "right" ? { right: "calc(100% + 8px)" } : { left: "calc(100% + 8px)" }),
    ...(isTop ? { bottom: 0 } : { top: 0 }),
    width: 220,
    background: "var(--bg-elevated, #fff)",
    border: "1px solid rgba(0,0,0,.1)",
    boxShadow: "0 8px 28px rgba(0,0,0,.12)",
    borderRadius: 14,
    overflow: "hidden",
    animation: `ms-appear 0.13s cubic-bezier(0.34,1.4,0.64,1)`,
  };

  // Display name for the trigger button
  const displayName = current
    ? (current.name.length > 14 ? current.name.slice(0, 12) + "…" : current.name)
    : "模型";

  return (
    <div className="relative" ref={ref}>
      <style>{`
        @keyframes ms-appear {
          from { opacity:0; transform:translateY(${isTop ? "4" : "-4"}px) scale(0.96); }
          to   { opacity:1; transform:translateY(0) scale(1); }
        }
      `}</style>

      {/* ── Trigger ── */}
      <button
        onClick={() => { setOpen((v) => !v); setEffortOpen(false); }}
        className="h-8 px-2.5 inline-flex items-center gap-1.5 rounded-lg transition-colors hover:bg-[var(--hover)]"
        style={{ color: "var(--ink-600)" }}
      >
        <span style={{ fontSize: "13px", fontWeight: 500, color: "var(--ink-900)" }}>{displayName}</span>
        <span style={{ fontSize: "13px", color: "var(--ink-400)", fontWeight: 500 }}>{currentEffort.label}</span>
        <ChevronDown style={{ width: 11, height: 11, color: "var(--ink-400)", transition: "transform 0.18s ease", transform: open ? "rotate(180deg)" : "rotate(0deg)" }} />
      </button>

      {/* ── Main dropdown ── */}
      {open && (
        <div style={dropdownStyle}>
          {/* Model list */}
          <div style={{ padding: "6px 6px 4px" }}>
            {models.map((m) => {
              const active = selectedModel === m.id;
              return (
                <button
                  key={m.id}
                  onClick={() => { onSelect(m.id); setOpen(false); setEffortOpen(false); }}
                  style={{
                    width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "8px 10px", borderRadius: 9, border: "none", cursor: "pointer", textAlign: "left",
                    background: active ? "rgba(0,0,0,.06)" : "transparent",
                    transition: "background .12s",
                  }}
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "var(--hover, rgba(0,0,0,.04))"; }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--ink-900)" }}>{m.name}</span>
                    </div>
                    {m.description && (
                      <p style={{ fontSize: 11.5, color: "var(--ink-400)", margin: "1px 0 0" }}>{m.description}</p>
                    )}
                  </div>
                  {active && <Check size={13} style={{ color: "var(--ink-900)", flexShrink: 0 }} />}
                </button>
              );
            })}
          </div>

          {/* ── Effort row ── */}
          <div style={{ borderTop: "1px solid rgba(0,0,0,.07)", padding: "4px 6px", position: "relative" }}>
            <button
              onClick={() => setEffortOpen((v) => !v)}
              onMouseEnter={() => setEffortOpen(true)}
              style={{
                width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "8px 10px", borderRadius: 9, border: "none", cursor: "pointer",
                background: effortOpen ? "var(--hover, rgba(0,0,0,.04))" : "transparent",
                transition: "background .12s",
              }}
            >
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-700)" }}>Effort</span>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ fontSize: 12, color: "var(--ink-400)" }}>{currentEffort.label}</span>
                <ChevronRight size={12} style={{ color: "var(--ink-400)" }} />
              </div>
            </button>

            {effortOpen && (
              <div style={effortPanelStyle}>
                <div style={{ padding: "12px 14px 8px", borderBottom: "1px solid rgba(0,0,0,.07)" }}>
                  <p style={{ fontSize: 12, color: "var(--ink-500)", lineHeight: 1.5, margin: 0 }}>
                    更高 Effort = 更深入的回答，但速度更慢。
                  </p>
                </div>
                <div style={{ padding: "6px 6px" }}>
                  {EFFORT_LEVELS.map((e) => {
                    const active = selectedEffort === e.id;
                    return (
                      <button
                        key={e.id}
                        onClick={() => { onSelectEffort?.(e.id); setOpen(false); setEffortOpen(false); }}
                        style={{
                          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                          padding: "8px 10px", borderRadius: 9, border: "none", cursor: "pointer", textAlign: "left",
                          background: active ? "rgba(37,99,235,0.08)" : "transparent",
                          transition: "background .12s",
                        }}
                        onMouseEnter={(ev) => { if (!active) ev.currentTarget.style.background = "var(--hover, rgba(0,0,0,.04))"; }}
                        onMouseLeave={(ev) => { if (!active) ev.currentTarget.style.background = "transparent"; }}
                      >
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontSize: 13.5, fontWeight: 600, color: active ? "#2563eb" : "var(--ink-800)" }}>
                              {e.label}
                            </span>
                            {e.isDefault && (
                              <span style={{ fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 99, background: "rgba(0,0,0,.06)", color: "var(--ink-400)" }}>默认</span>
                            )}
                          </div>
                          <p style={{ fontSize: 11.5, color: "var(--ink-400)", margin: "1px 0 0" }}>{e.desc}</p>
                        </div>
                        {active && <Check size={13} style={{ color: "#2563eb", flexShrink: 0 }} />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
