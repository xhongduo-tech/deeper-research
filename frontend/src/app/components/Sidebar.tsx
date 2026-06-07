import { useState, useRef, useEffect } from "react";
import {
  Plus, Presentation, FileText, Table2, Code2,
  Layers, Database,
  PanelLeftClose, ChevronDown, Search, LogOut,
  Pin, Trash2, User, MessageSquare,
} from "lucide-react";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { ScrollArea } from "./ui/scroll-area";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "./ui/tooltip";
import logoImg from "../../imports/deep-research.png";
import { ImageWithFallback } from "./figma/ImageWithFallback";
import type { Conversation } from "../App";
import type { UserInfo } from "../lib/api";

export type PageKey =
  | "home"
  | "docs"
  | "ppt"
  | "html"
  | "sheet"
  | "datalab"           // Table-Agent 数据交互实验室（场景 B/C）
  | "knowledge";        // 知识库管理（持久化 Vector RAG）

const LOCKED_PAGES = new Set<PageKey>(["ppt", "sheet"]);

const NAV_STUDIO: { key: PageKey; label: string; icon: React.ElementType; badge?: string }[] = [
  { key: "docs",  label: "文档",  icon: FileText },
  { key: "ppt",   label: "PPT",   icon: Presentation, badge: "即将上线" },
  { key: "html",  label: "网页",  icon: Code2 },
  { key: "sheet", label: "表格",  icon: Table2,        badge: "即将上线" },
];

const NAV_EXPLORE: { key: PageKey; label: string; icon: React.ElementType }[] = [
  { key: "knowledge", label: "知识库",  icon: Database },
  { key: "datalab",   label: "DataLab", icon: Layers },
];

const EXPANDED_W  = 256;
const EASE = "cubic-bezier(0.4, 0, 0.2, 1)";
const DUR  = "0.24s";

// ─── Tooltip wrapper ──────────────────────────────────────────────────────────

function SidebarTip({ label, children, show }: { label: string; children: React.ReactNode; show: boolean }) {
  if (!show) return <>{children}</>;
  return (
    <Tooltip delayDuration={80}>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right" sideOffset={10}
        className="z-50 text-[12px] font-medium px-2.5 py-1.5 rounded-lg"
        style={{ background: "var(--ink-900)", color: "#fff", border: "none",
                 boxShadow: "0 4px 16px rgba(0,0,0,0.2)" }}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

// ─── Main Sidebar ─────────────────────────────────────────────────────────────

export function Sidebar({
  active, onSelect, collapsed, onToggle,
  isLoggedIn, onLogout, onNeedLogin, user, onSearchHistory,
  onNewConversation, onSelectConversation,
  searchHistoryOpen = false,
  conversations = [], onPinConversation, onDeleteConversation,
}: {
  active: PageKey;
  onSelect: (k: PageKey) => void;
  onNewConversation?: () => void;
  onSelectConversation?: (id: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  isLoggedIn: boolean;
  onLogout: () => void;
  onNeedLogin: () => void;
  user?: UserInfo | null;
  onSearchHistory: () => void;
  searchHistoryOpen?: boolean;
  conversations?: Conversation[];
  onPinConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
}) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [hoveredId, setHoveredId]       = useState<string | null>(null);
  const [showAllRecent, setShowAllRecent] = useState(false);
  const menuRef       = useRef<HTMLDivElement>(null);
  const recentScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showUserMenu) return;
    const h = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node))
        setShowUserMenu(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [showUserMenu]);

  useEffect(() => {
    if (!showAllRecent) return;
    const t = window.setTimeout(() => {
      const vp = recentScrollRef.current?.querySelector<HTMLElement>("[data-slot='scroll-area-viewport']");
      vp?.scrollBy({ top: 96, behavior: "smooth" });
    }, 80);
    return () => window.clearTimeout(t);
  }, [showAllRecent]);

  const fade: React.CSSProperties = {
    opacity: collapsed ? 0 : 1,
    transition: `opacity ${DUR} ${EASE}`,
    whiteSpace: "nowrap",
    overflow: "hidden",
    pointerEvents: collapsed ? "none" : "auto",
  };

  const displayName = user?.username || user?.auth_id || "用户";
  const department  = user?.department || (user?.role === "admin" ? "管理员" : "研究员");
  const initial     = displayName.slice(0, 1).toUpperCase();

  // ─── Section label ───────────────────────────────────────────────────────────

  function SectionLabel({ children, englishSub }: { children: string; englishSub?: string }) {
    return (
      <div className="px-3 mb-0.5" style={{ height: 28, display: "flex", alignItems: "flex-end",
          opacity: collapsed ? 0 : 0.7, transition: `opacity ${DUR} ${EASE}`,
          pointerEvents: collapsed ? "none" : "auto" }}>
        <span className="text-[10.5px] font-bold uppercase tracking-[0.08em]"
          style={{ color: "var(--ink-400)" }}>{children}</span>
        {englishSub && (
          <span style={{
            fontSize: 9.5, fontWeight: 500, marginLeft: 5, letterSpacing: "0.04em",
            color: "var(--ink-300)",
            opacity: collapsed ? 0 : 1,
            transition: `opacity ${DUR} ${EASE}`,
            whiteSpace: "nowrap",
          }}>{englishSub}</span>
        )}
      </div>
    );
  }

  // ─── Nav button ──────────────────────────────────────────────────────────────

  function NavBtn({
    icon: Icon, label, pageKey, badge, onClick, forceActive,
  }: {
    icon: React.ElementType; label: string;
    pageKey?: PageKey; badge?: string;
    onClick?: () => void; forceActive?: boolean;
  }) {
    const isActive = forceActive ?? (!searchHistoryOpen && !!pageKey && active === pageKey);
    const isLocked = !!pageKey && LOCKED_PAGES.has(pageKey);

    return (
      <div className="relative" style={{ padding: "0 8px" }}>
        {isActive && !collapsed && (
          <span className="absolute left-2 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full"
            style={{ background: "var(--brand, #2563eb)" }} />
        )}
        <SidebarTip label={label} show={collapsed}>
          <button
            onClick={isLocked ? undefined : (onClick ?? (pageKey ? () => onSelect(pageKey) : undefined))}
            className="rounded-xl flex items-center gap-2.5 transition-all duration-150"
            style={{
              width: collapsed ? 40 : "100%",
              height: 36,
              paddingLeft: 12,
              paddingRight: collapsed ? 12 : 10,
              justifyContent: collapsed ? "center" : "flex-start",
              background: isActive ? "rgba(37,99,235,0.10)" : "transparent",
              cursor: isLocked ? "default" : "pointer",
              opacity: isLocked ? 0.45 : 1,
            }}
            onMouseEnter={e => { if (!isActive && !isLocked) e.currentTarget.style.background = "var(--hover, rgba(0,0,0,0.04))"; }}
            onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
            aria-disabled={isLocked}
          >
            <Icon style={{
              width: 16, height: 16, flexShrink: 0,
              color: isActive ? "var(--brand, #2563eb)" : "var(--ink-500)",
              transition: "color 0.15s",
            }} />
            {!collapsed && (
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
                <span style={{
                  fontSize: 13.5, fontWeight: isActive ? 600 : 500,
                  color: isActive ? "var(--ink-900)" : "var(--ink-700)",
                }}>{label}</span>
                {badge && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0"
                    style={{ background: "var(--border)", color: "var(--ink-400)" }}>
                    {badge}
                  </span>
                )}
              </div>
            )}
          </button>
        </SidebarTip>
      </div>
    );
  }

  const pinnedItems   = conversations.filter(c =>  c.pinned);
  const unpinnedItems = conversations.filter(c => !c.pinned);
  const maxRecent     = 8;
  const visiblePinned   = showAllRecent ? pinnedItems   : pinnedItems.slice(0, 2);
  const remainingSlots  = Math.max(0, maxRecent - visiblePinned.length);
  const visibleUnpinned = showAllRecent ? unpinnedItems : unpinnedItems.slice(0, remainingSlots);
  const hiddenCount     = Math.max(0, pinnedItems.length + unpinnedItems.length - visiblePinned.length - visibleUnpinned.length);

  return (
    <TooltipProvider>
      <aside
        className="h-full flex flex-col flex-shrink-0 relative z-20"
        style={{
          width: collapsed ? 56 : EXPANDED_W,
          transition: `width ${DUR} ${EASE}`,
          overflow: "hidden",
          background: "var(--bg-sidebar, var(--bg-panel))",
          borderRight: "1px solid var(--border)",
        }}
      >
        <div style={{ width: EXPANDED_W, display: "flex", flexDirection: "column", height: "100%" }}>

          {/* ── Header ── */}
          <div className="flex items-center flex-shrink-0"
            style={{ height: 52, paddingLeft: 12, paddingRight: 10, borderBottom: "1px solid var(--border)" }}>
            <SidebarTip label="DataAgent" show={collapsed}>
	              <button
	                onClick={onToggle}
	                className="flex items-center justify-center rounded-[10px] flex-shrink-0 transition-colors"
	                style={{ width: 30, height: 30, background: "#18181b", flexShrink: 0, lineHeight: 0 }}
	              >
	                <ImageWithFallback src={logoImg} alt="DataAgent"
	                  style={{ width: 16, height: 16, objectFit: "contain", display: "block" }} />
	              </button>
            </SidebarTip>

            <div style={{ ...fade, flex: 1, paddingLeft: 10, display: "flex", alignItems: "center",
                          justifyContent: "space-between" }}>
              <span style={{ fontWeight: 700, fontSize: 14.5, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
                DataAgent
              </span>
              <button
                onClick={onToggle}
                className="h-7 w-7 inline-flex items-center justify-center rounded-lg transition-colors"
	                style={{ color: "var(--ink-400)", lineHeight: 0 }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--hover)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
	                <PanelLeftClose style={{ width: 15, height: 15, display: "block", flexShrink: 0 }} />
	              </button>
            </div>
          </div>

          {/* ── Body ── */}
          <div className="flex flex-col flex-1 min-h-0" style={{ paddingTop: 8 }}>

            {/* New conversation */}
            <div style={{ padding: "0 8px 4px", display: "flex" }}>
              <SidebarTip label="新建会话" show={collapsed}>
                <button
                  onClick={onNewConversation ?? (() => onSelect("home"))}
                  className="flex items-center gap-2.5 rounded-xl transition-all active:scale-[0.98]"
                  style={{
                    width: collapsed ? 40 : "100%",
                    height: 36,
                    paddingLeft: 12,
                    paddingRight: collapsed ? 12 : 12,
                    justifyContent: collapsed ? "center" : "flex-start",
                    background: "var(--ink-900)", color: "#fff",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                  }}
                >
                  <Plus style={{ width: 16, height: 16, flexShrink: 0 }} />
                  {!collapsed && (
                    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 550, fontSize: 13.5 }}>新建会话</span>
                      <span style={{ fontSize: 10.5, padding: "2px 5px", borderRadius: 4,
                                     background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)" }}>
                        ⌘K
                      </span>
                    </div>
                  )}
                </button>
              </SidebarTip>
            </div>

            <NavBtn icon={Search} label="搜索历史" onClick={onSearchHistory} forceActive={searchHistoryOpen} />

            {/* Divider */}
            <div style={{ margin: "6px 12px", height: 1, background: "var(--border)", flexShrink: 0 }} />

	            {/* Studio section */}
	            {NAV_STUDIO.map(n => (
	              <NavBtn key={n.key} icon={n.icon} label={n.label} pageKey={n.key} badge={n.badge} />
	            ))}
	
	            {/* Divider */}
	            <div style={{ margin: "8px 12px 7px", height: 1, background: "var(--border)", flexShrink: 0 }} />
	
	            {/* Explore section */}
	            {NAV_EXPLORE.map(n => (
	              <NavBtn key={n.key} icon={n.icon} label={n.label} pageKey={n.key} />
	            ))}

            {/* Divider */}
            <div style={{ margin: "6px 12px", height: 1, background: "var(--border)", flexShrink: 0 }} />

            {/* Recent conversations */}
            <div className="flex flex-col flex-1 min-h-0">
              <div style={{ height: 26, paddingLeft: 12, display: "flex", alignItems: "flex-end",
                            marginBottom: 2,
                            opacity: collapsed ? 0 : 0.7, transition: `opacity ${DUR} ${EASE}`,
                            pointerEvents: collapsed ? "none" : "auto" }}>
                <MessageSquare style={{ width: 10.5, height: 10.5, color: "var(--ink-400)", marginRight: 5, flexShrink: 0 }} />
                <span className="text-[10.5px] font-bold uppercase tracking-[0.08em]"
                  style={{ color: "var(--ink-400)" }}>最近对话</span>
              </div>

              <div ref={recentScrollRef} className="flex-1 min-h-0">
                <ScrollArea className="h-full px-2">
                  <div style={{ paddingBottom: 80 }}>
                    {visiblePinned.length > 0 && (
                      <>
                        <div style={{ paddingLeft: 12, paddingBottom: 2, paddingTop: 2,
                                      opacity: collapsed ? 0 : 0.6, transition: `opacity ${DUR} ${EASE}`,
                                      pointerEvents: collapsed ? "none" : "auto" }}>
                          <span className="text-[10px] font-bold uppercase tracking-wide"
                            style={{ color: "var(--ink-400)" }}>置顶</span>
                        </div>
                        {visiblePinned.map(c => (
                          <ConversationItem key={c.id} item={c} collapsed={collapsed}
                            hovered={hoveredId === c.id} onHover={setHoveredId}
                            onSelect={onSelectConversation}
                            onPin={onPinConversation} onDelete={onDeleteConversation} />
                        ))}
                        <div style={{ margin: "4px 8px", height: 1, background: "var(--border)" }} />
                      </>
                    )}
                    {visibleUnpinned.map(c => (
                      <ConversationItem key={c.id} item={c} collapsed={collapsed}
                        hovered={hoveredId === c.id} onHover={setHoveredId}
                        onSelect={onSelectConversation}
                        onPin={onPinConversation} onDelete={onDeleteConversation} />
                    ))}
                    {!showAllRecent && hiddenCount > 0 && (
                      <button
                        onClick={() => setShowAllRecent(true)}
                        className="w-full h-8 rounded-xl flex items-center px-3 text-[12px] transition-colors"
                        style={{ color: "var(--ink-500)", opacity: collapsed ? 0 : 1,
                                 pointerEvents: collapsed ? "none" : "auto" }}
                        onMouseEnter={e => e.currentTarget.style.background = "var(--hover)"}
                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                      >
                        查看更多 {hiddenCount} 条…
                      </button>
                    )}
                    {showAllRecent && conversations.length > maxRecent && (
                      <button
                        onClick={() => setShowAllRecent(false)}
                        className="w-full h-8 rounded-xl flex items-center px-3 text-[12px] transition-colors"
                        style={{ color: "var(--ink-500)", opacity: collapsed ? 0 : 1,
                                 pointerEvents: collapsed ? "none" : "auto" }}
                        onMouseEnter={e => e.currentTarget.style.background = "var(--hover)"}
                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                      >
                        收起
                      </button>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </div>

            {/* ── User footer ── */}
            <div ref={menuRef} style={{ borderTop: "1px solid var(--border)", position: "relative" }}>
              {showUserMenu && (
                <div className="absolute bottom-full left-2 right-2 mb-1.5 rounded-2xl overflow-hidden"
                  style={{ background: "var(--bg-elevated, var(--bg-panel))",
                           border: "1px solid var(--border)",
                           boxShadow: "0 8px 32px rgba(0,0,0,0.12)" }}>
                  <button
                    onClick={() => { setShowUserMenu(false); onLogout(); }}
                    className="w-full h-10 px-4 flex items-center gap-2.5 text-[13px] font-medium transition-colors"
                    style={{ color: "#ef4444" }}
                    onMouseEnter={e => e.currentTarget.style.background = "rgba(239,68,68,0.06)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <LogOut style={{ width: 15, height: 15 }} />
                    退出登录
                  </button>
                </div>
              )}
              <div style={{ padding: "8px 8px", display: "flex" }}>
                <SidebarTip label={isLoggedIn ? `${displayName} · ${department}` : "点击登录"} show={collapsed}>
                  <button
                    onClick={() => isLoggedIn ? setShowUserMenu(v => !v) : onNeedLogin()}
                    className="flex items-center gap-2.5 rounded-xl transition-all"
                    style={{
                      width: collapsed ? 40 : "100%",
                      height: 40,
                      paddingLeft: 4,
                      paddingRight: collapsed ? 4 : 8,
                      justifyContent: collapsed ? "center" : "flex-start",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--hover)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    {isLoggedIn ? (
                      <Avatar className="h-8 w-8 flex-shrink-0">
                        <AvatarFallback className="text-white text-[11.5px] font-semibold"
                          style={{ background: "linear-gradient(135deg,#f59e0b,#ef4444)" }}>
                          {initial}
                        </AvatarFallback>
                      </Avatar>
                    ) : (
                      <div className="h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0"
                        style={{ background: "var(--bg, #f4f4f5)", border: "1px solid var(--border)" }}>
                        <User style={{ width: 14, height: 14, color: "var(--ink-400)" }} />
                      </div>
                    )}
                    {!collapsed && (
                      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        {isLoggedIn ? (
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: 13.5, color: "var(--ink-900)", fontWeight: 600,
                                          textAlign: "left", lineHeight: 1.3 }}>{displayName}</div>
                            <div style={{ fontSize: 11, color: "var(--ink-400)", textAlign: "left",
                                          marginTop: 1, lineHeight: 1.2 }}>{department}</div>
                          </div>
                        ) : (
                          <span style={{ fontSize: 13.5, color: "var(--ink-700)", fontWeight: 500 }}>
                            未登录
                          </span>
                        )}
                        <ChevronDown style={{
                          width: 14, height: 14, flexShrink: 0, color: "var(--ink-400)",
                          transform: showUserMenu ? "rotate(180deg)" : "rotate(0deg)",
                          transition: "transform 0.2s ease",
                        }} />
                      </div>
                    )}
                  </button>
                </SidebarTip>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
}

// ─── Conversation item ────────────────────────────────────────────────────────

function ConversationItem({
  item, hovered, onHover, onSelect, onPin, onDelete, collapsed,
}: {
  item: Conversation; hovered: boolean;
  onHover: (id: string | null) => void;
  onSelect?: (id: string) => void;
  onPin?: (id: string) => void;
  onDelete?: (id: string) => void;
  collapsed?: boolean;
}) {
  const groupColor: Record<string, string> = {
    "今天": "#2563eb", "昨天": "#7c3aed", "7 天内": "#059669", "更早": "#94a3b8",
  };
  const dot = groupColor[item.group] || "#94a3b8";

  return (
    <div className="relative px-1"
      onMouseEnter={() => onHover(item.id)}
      onMouseLeave={() => onHover(null)}>
      <div
        role="button"
        tabIndex={collapsed ? -1 : 0}
        onClick={() => onSelect?.(item.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect?.(item.id);
          }
        }}
        className="w-full text-left rounded-xl transition-colors"
        style={{
          display: "grid",
          gridTemplateColumns: "6px minmax(0, 1fr) 58px",
          alignItems: "center",
          columnGap: 8,
          padding: "9px 10px",
          background: hovered ? "var(--hover, rgba(0,0,0,0.04))" : "transparent",
          opacity: collapsed ? 0 : 1,
          transition: `opacity 0.24s ease, background 0.12s ease`,
          pointerEvents: collapsed ? "none" : "auto",
          cursor: "pointer",
        }}
      >
        <span className="mt-[1px] w-1.5 h-1.5 rounded-full" style={{ background: dot }} />
        <div
          style={{
            minWidth: 0,
          }}
        >
          <div className="text-[13px] font-medium truncate"
            style={{ color: "var(--ink-800)", lineHeight: 1.4, whiteSpace: "nowrap" }}>
            {item.title || "无标题对话"}
          </div>
        </div>
        <div
          className="flex items-center justify-end gap-0.5"
          style={{
            width: 58,
            minWidth: 58,
            height: 24,
            borderRadius: 10,
          }}
        >
          {hovered && !collapsed ? (
            <>
              {onPin && (
                <button
	                  onClick={e => { e.stopPropagation(); onPin(item.id); }}
	                  className="w-6 h-6 rounded-lg flex items-center justify-center transition-colors"
	                  style={{ background: "transparent", border: "none" }}
	                  title={item.pinned ? "取消置顶" : "置顶"}
	                >
                  <Pin style={{ width: 11, height: 11, color: item.pinned ? "var(--brand)" : "var(--ink-500)" }} />
                </button>
              )}
              {onDelete && (
                <button
	                  onClick={e => { e.stopPropagation(); onDelete(item.id); }}
	                  className="w-6 h-6 rounded-lg flex items-center justify-center transition-colors"
	                  style={{ background: "transparent", border: "none" }}
	                  title="删除"
                >
                  <Trash2 style={{ width: 11, height: 11, color: "#ef4444" }} />
                </button>
              )}
            </>
          ) : (
            <span
              className="text-[12px] truncate"
              style={{
                width: "100%",
                textAlign: "right",
                color: "var(--ink-400)",
                lineHeight: 1.3,
              }}
            >
              {item.time}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
