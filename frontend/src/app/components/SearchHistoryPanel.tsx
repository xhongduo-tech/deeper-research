import { useState, useEffect, useRef } from "react";
import { Search, MessageSquare, Pin, PinOff, Trash2, FileText, BarChart2, Presentation, Plus, Clock } from "lucide-react";
import type { Conversation } from "../App";

// Ordered groups — must stay in sync with Conversation["group"] union in App.tsx
const GROUPS = ["今天", "昨天", "7 天内", "30 天内", "更早"] as const;
type GroupLabel = typeof GROUPS[number];
type TabType = "chat" | "create";

function isChatItem(c: Conversation) {
  return !!c.tags?.includes("问答");
}

function stripMarkdown(text: string) {
  return text
    .replace(/```[\s\S]*?```/g, "代码片段")
    .replace(/!\[[^\]]*\]\([^)]+\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/#{1,6}\s+/g, "")
    .replace(/[*_`~>]+/g, "")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

function getCreateIcon(tags?: string[]) {
  if (!tags) return <FileText style={{ width: 14, height: 14 }} />;
  if (tags.includes("PPT")) return <Presentation style={{ width: 14, height: 14 }} />;
  if (tags.includes("数据分析")) return <BarChart2 style={{ width: 14, height: 14 }} />;
  return <FileText style={{ width: 14, height: 14 }} />;
}

export function SearchHistoryPanel({
  open,
  onClose,
  onNewConversation,
  onSelectConversation,
  conversations = [],
  onPinConversation,
  onDeleteConversation,
}: {
  open: boolean;
  onClose: () => void;
  onNewConversation?: () => void;
  onSelectConversation: (id: string) => void;
  conversations?: Conversation[];
  onPinConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("chat");
  const [searchFocused, setSearchFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setMounted(true);
      setTimeout(() => inputRef.current?.focus(), 60);
    } else {
      const t = setTimeout(() => { setMounted(false); setQuery(""); }, 240);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!mounted) return null;

  const isSearching = query.trim().length > 0;
  const filtered = isSearching
    ? conversations.filter((c) =>
        c.title.toLowerCase().includes(query.toLowerCase()) ||
        c.preview.toLowerCase().includes(query.toLowerCase())
      )
    : conversations;

  const chatItems = filtered.filter(isChatItem);
  const createItems = filtered.filter((c) => !isChatItem(c));
  const activeItems = activeTab === "chat" ? chatItems : createItems;

  const pinned = activeItems.filter((c) => c.pinned);
  const groupedItems: Array<{ label: GroupLabel; items: Conversation[] }> = isSearching
    ? []
    : GROUPS.map((g) => ({
        label: g,
        items: activeItems.filter((c) => !c.pinned && c.group === g),
      })).filter((g) => g.items.length > 0);

  const searchResults = isSearching ? activeItems.filter((c) => !c.pinned) : [];

  return (
    <div
      className="absolute inset-0 flex flex-col"
      style={{
        background: "var(--bg, #f7f7f5)",
        opacity: open ? 1 : 0,
        transform: open ? "translateX(0)" : "translateX(20px)",
        transition: "opacity 0.2s ease, transform 0.2s cubic-bezier(0.4,0,0.2,1)",
        zIndex: 80,
        pointerEvents: open ? "auto" : "none",
      }}
    >
      <style>{`
        .shp-row {
          position: relative;
          display: flex;
          align-items: center;
          padding: 9px 136px 9px 10px;
          border-radius: 10px;
          cursor: pointer;
          gap: 12px;
          transition: background 0.12s ease;
        }
        .shp-row:hover { background: rgba(0,0,0,.05); }
        .shp-row-actions {
          position: absolute;
          right: 10px;
          top: 50%;
          transform: translateY(-50%);
          width: 58px;
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 2px;
          visibility: hidden;
          border-radius: 10px;
          background: var(--bg-elevated, #fff);
        }
        .shp-row:hover .shp-row-actions { visibility: visible; }
        .shp-icon-btn {
          height: 28px;
          width: 28px;
          border-radius: 8px;
          border: none;
          background: transparent;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--ink-400);
          transition: background 0.12s ease, color 0.12s ease;
        }
        .shp-icon-btn:hover { background: rgba(0,0,0,.07); color: var(--ink-700); }
        .shp-icon-btn.danger:hover { background: rgba(239,68,68,.08); color: #ef4444; }
        .shp-section-label {
          font-size: 12px;
          font-weight: 600;
          color: var(--ink-400);
          padding: 12px 10px 4px;
        }
        .shp-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 80px 0;
          gap: 12px;
          color: var(--ink-400);
          font-size: 14px;
        }
        .shp-artifact-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
          gap: 12px;
          margin-top: 4px;
        }
        .shp-artifact-card {
          border-radius: 14px;
          border: 1px solid var(--border);
          background: var(--bg-elevated, #fff);
          cursor: pointer;
          overflow: hidden;
          transition: box-shadow 0.15s ease, transform 0.15s ease, border-color 0.15s ease;
        }
        .shp-artifact-card:hover {
          box-shadow: 0 4px 16px rgba(0,0,0,.08);
          transform: translateY(-2px);
          border-color: rgba(0,0,0,.15);
        }
        /* Tab pills */
        .shp-tab {
          height: 30px;
          padding: 0 12px;
          border-radius: 8px;
          border: none;
          background: transparent;
          cursor: pointer;
          font-size: 13px;
          font-weight: 500;
          transition: background 0.12s ease, color 0.12s ease;
          color: var(--ink-400);
          display: flex;
          align-items: center;
          gap: 5px;
        }
        .shp-tab.active {
          background: rgba(0,0,0,.07);
          color: var(--ink-900);
          font-weight: 600;
        }
        .shp-tab:not(.active):hover { background: rgba(0,0,0,.04); color: var(--ink-700); }
        /* Search input focus — blue border like Claude */
        .shp-search-wrap {
          display: flex;
          align-items: center;
          gap: 9px;
          height: 42px;
          padding: 0 13px;
          border-radius: 12px;
          border: 1.5px solid rgba(0,0,0,.1);
          background: #fff;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .shp-search-wrap.focused {
          border-color: rgba(91,78,232,.5);
          box-shadow: 0 0 0 3px rgba(91,78,232,.08);
        }
        .shp-search-input {
          flex: 1;
          border: none;
          outline: none;
          background: transparent;
          font-size: 14px;
          color: var(--ink-900);
        }
        .shp-search-input::placeholder { color: var(--ink-400); }
        /* New chat button */
        .shp-new-btn {
          height: 34px;
          padding: 0 14px;
          border-radius: 8px;
          border: 1px solid rgba(0,0,0,.12);
          background: var(--ink-900, #111);
          color: #fff;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
          transition: opacity 0.12s;
          white-space: nowrap;
        }
        .shp-new-btn:hover { opacity: 0.85; }
        @keyframes shp-pulse { 0%,100%{opacity:.4;transform:scale(.85)} 50%{opacity:1;transform:scale(1.1)} }
      `}</style>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div style={{ maxWidth: 800, margin: "0 auto", padding: "36px 20px 48px" }}>

          {/* ── Header row: [title] [tabs] [spacer] [+ 新建对话] ── */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-900)", letterSpacing: "-0.02em", flexShrink: 0 }}>
              历史记录
            </h1>
            {/* Inline tabs */}
            <div style={{ display: "flex", gap: 3, marginLeft: 10 }}>
              <button
                className={`shp-tab${activeTab === "chat" ? " active" : ""}`}
                onClick={() => setActiveTab("chat")}
              >
                对话
                {chatItems.length > 0 && (
                  <span style={{ fontSize: 11, opacity: 0.65 }}>{chatItems.length}</span>
                )}
              </button>
              <button
                className={`shp-tab${activeTab === "create" ? " active" : ""}`}
                onClick={() => setActiveTab("create")}
              >
                创作
                {createItems.length > 0 && (
                  <span style={{ fontSize: 11, opacity: 0.65 }}>{createItems.length}</span>
                )}
              </button>
            </div>
            <div style={{ flex: 1 }} />
            <button
              className="shp-new-btn"
              onClick={() => onNewConversation ? onNewConversation() : onClose()}
            >
              <Plus style={{ width: 14, height: 14 }} />
              新建对话
            </button>
          </div>

          {/* ── Search bar with Claude-style blue focus ── */}
          <div className={`shp-search-wrap${searchFocused ? " focused" : ""}`} style={{ marginBottom: 18 }}>
            <Search style={{ width: 15, height: 15, color: searchFocused ? "var(--brand, #5b4ee8)" : "var(--ink-400)", flexShrink: 0, transition: "color .15s" }} />
            <input
              ref={inputRef}
              className="shp-search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              placeholder={activeTab === "chat" ? "搜索对话…" : "搜索创作…"}
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                style={{ border: "none", background: "none", cursor: "pointer", color: "var(--ink-400)", fontSize: 18, lineHeight: 1, display: "flex", alignItems: "center" }}
              >
                ×
              </button>
            )}
          </div>

          {/* ── Content ── */}
          {activeItems.length === 0 ? (
            <div className="shp-empty">
              <MessageSquare style={{ width: 36, height: 36, opacity: 0.3 }} />
              <span>{isSearching ? "没有找到相关记录" : activeTab === "chat" ? "暂无对话记录" : "暂无创作记录"}</span>
            </div>
          ) : activeTab === "chat" ? (
            <div>
              {pinned.length > 0 && (
                <>
                  <div className="shp-section-label">📌 已置顶</div>
                  {pinned.map((item) => (
                    <ChatRow key={item.id} item={item}
                      onSelect={() => { onSelectConversation(item.id); onClose(); }}
                      onPin={() => onPinConversation?.(item.id)}
                      onDelete={() => onDeleteConversation?.(item.id)}
                    />
                  ))}
                </>
              )}
              {isSearching ? (
                <>
                  {pinned.length > 0 && searchResults.length > 0 && <div className="shp-section-label">其他结果</div>}
                  {searchResults.map((item) => (
                    <ChatRow key={item.id} item={item}
                      onSelect={() => { onSelectConversation(item.id); onClose(); }}
                      onPin={() => onPinConversation?.(item.id)}
                      onDelete={() => onDeleteConversation?.(item.id)}
                    />
                  ))}
                </>
              ) : (
                groupedItems.map((group) => (
                  <div key={group.label}>
                    <div className="shp-section-label">{group.label}</div>
                    {group.items.map((item) => (
                      <ChatRow key={item.id} item={item}
                        onSelect={() => { onSelectConversation(item.id); onClose(); }}
                        onPin={() => onPinConversation?.(item.id)}
                        onDelete={() => onDeleteConversation?.(item.id)}
                      />
                    ))}
                  </div>
                ))
              )}
            </div>
          ) : (
            <div>
              {pinned.length > 0 && (
                <>
                  <div className="shp-section-label">📌 已置顶</div>
                  <div className="shp-artifact-grid" style={{ marginBottom: 20 }}>
                    {pinned.map((item) => (
                      <ArtifactCard key={item.id} item={item}
                        onSelect={() => { onSelectConversation(item.id); onClose(); }}
                        onPin={() => onPinConversation?.(item.id)}
                        onDelete={() => onDeleteConversation?.(item.id)}
                      />
                    ))}
                  </div>
                </>
              )}
              {isSearching ? (
                <div className="shp-artifact-grid">
                  {searchResults.map((item) => (
                    <ArtifactCard key={item.id} item={item}
                      onSelect={() => { onSelectConversation(item.id); onClose(); }}
                      onPin={() => onPinConversation?.(item.id)}
                      onDelete={() => onDeleteConversation?.(item.id)}
                    />
                  ))}
                </div>
              ) : (
                groupedItems.map((group) => (
                  <div key={group.label}>
                    <div className="shp-section-label">{group.label}</div>
                    <div className="shp-artifact-grid" style={{ marginBottom: 20 }}>
                      {group.items.map((item) => (
                        <ArtifactCard key={item.id} item={item}
                          onSelect={() => { onSelectConversation(item.id); onClose(); }}
                          onPin={() => onPinConversation?.(item.id)}
                          onDelete={() => onDeleteConversation?.(item.id)}
                        />
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

// ── Chat row ───────────────────────────────────────────────────────────────

function ChatRow({ item, onSelect, onPin, onDelete }: {
  item: Conversation; onSelect: () => void; onPin: () => void; onDelete: () => void;
}) {
  return (
    <div className="shp-row" onClick={onSelect}>
      {item.running && (
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--brand, #5b4ee8)", flexShrink: 0, animation: "shp-pulse 1.4s ease-in-out infinite" }} />
      )}
      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 14.5, color: "var(--ink-900)", fontWeight: 500 }}>
        {item.pinned && <Pin style={{ width: 10, height: 10, color: "var(--brand)", display: "inline", marginRight: 6, transform: "rotate(45deg)" }} />}
        {item.title}
      </span>
      <span
        style={{
          position: "absolute",
          right: 78,
          top: "50%",
          transform: "translateY(-50%)",
          width: 48,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          textAlign: "right",
          fontSize: 12.5,
          color: "var(--ink-400)",
        }}
      >
        {item.time}
      </span>
      <span className="shp-row-actions" onClick={(e) => e.stopPropagation()}>
        <button className="shp-icon-btn" title={item.pinned ? "取消置顶" : "置顶"} onClick={onPin}>
          {item.pinned ? <PinOff style={{ width: 13, height: 13 }} /> : <Pin style={{ width: 13, height: 13 }} />}
        </button>
        <button className="shp-icon-btn danger" title="删除" onClick={onDelete}>
          <Trash2 style={{ width: 13, height: 13 }} />
        </button>
      </span>
    </div>
  );
}

// ── Artifact card ──────────────────────────────────────────────────────────

function ArtifactCard({ item, onSelect, onPin, onDelete }: {
  item: Conversation; onSelect: () => void; onPin: () => void; onDelete: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const previewText = stripMarkdown(item.preview || "");
  const tag = item.tags?.[0];

  return (
    <div
      className="shp-artifact-card"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onSelect}
    >
      <div style={{ position: "relative", padding: "14px 14px 10px", background: "rgba(0,0,0,.02)", minHeight: 120 }}>
        {tag && (
          <div style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "2px 7px", borderRadius: 6, marginBottom: 8, background: "rgba(0,0,0,.06)", fontSize: 11, fontWeight: 600, color: "var(--ink-500)" }}>
            {getCreateIcon(item.tags)}
            {tag}
          </div>
        )}
        <p style={{ fontSize: 12, lineHeight: 1.6, color: "var(--ink-500)", display: "-webkit-box", WebkitLineClamp: 5, WebkitBoxOrient: "vertical", overflow: "hidden", whiteSpace: "pre-line" }}>
          {previewText || "暂无内容预览"}
        </p>
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 28, background: "linear-gradient(transparent, rgba(0,0,0,.02))", pointerEvents: "none" }} />
        {hovered && (
          <div style={{ position: "absolute", top: 8, right: 8, display: "flex", gap: 3 }} onClick={(e) => e.stopPropagation()}>
            <button className="shp-icon-btn" style={{ background: "#fff", border: "1px solid rgba(0,0,0,.1)" }} title={item.pinned ? "取消置顶" : "置顶"} onClick={onPin}>
              {item.pinned ? <PinOff style={{ width: 12, height: 12 }} /> : <Pin style={{ width: 12, height: 12 }} />}
            </button>
            <button className="shp-icon-btn danger" style={{ background: "#fff", border: "1px solid rgba(0,0,0,.1)" }} title="删除" onClick={onDelete}>
              <Trash2 style={{ width: 12, height: 12 }} />
            </button>
          </div>
        )}
      </div>
      <div style={{ padding: "9px 14px 11px", borderTop: "1px solid var(--border)" }}>
        <p style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink-900)", marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {item.title}
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--ink-400)", fontSize: 11.5 }}>
          <Clock style={{ width: 10, height: 10 }} />
          <span>{item.time}</span>
        </div>
      </div>
    </div>
  );
}
