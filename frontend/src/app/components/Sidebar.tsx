import { useState, useRef, useEffect, useCallback } from "react";
import {
  Plus, Presentation, FileText, Table2, Code2,
  Database, FolderOpen, ChevronRight,
  PanelLeftClose, ChevronDown, LogOut,
  Pin, Trash2, User, MessageSquare, MoreHorizontal,
  Clock, Pencil, GitGraph,
} from "lucide-react";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { ScrollArea } from "./ui/scroll-area";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "./ui/tooltip";
import logoImg from "../../imports/deep-research.png";
import { ImageWithFallback } from "./figma/ImageWithFallback";
import type { Conversation } from "../App";
import { api, type UserInfo, type Project } from "../lib/api";

export type PageKey =
  | "home"
  | "docs"
  | "ppt"
  | "html"
  | "sheet"
  | "knowledge";        // 数据库管理（持久化 Vector RAG）

const LOCKED_PAGES = new Set<PageKey>(["ppt", "sheet"]);

const NAV_STUDIO: { key: PageKey; label: string; icon: React.ElementType; badge?: string }[] = [
  { key: "docs",  label: "文档",  icon: FileText },
  { key: "ppt",   label: "PPT",   icon: Presentation, badge: "即将开放" },
  { key: "html",  label: "网页",  icon: Code2 },
  { key: "sheet", label: "表格",  icon: Table2, badge: "即将开放" },
];

const NAV_EXPLORE: { key: PageKey; label: string; icon: React.ElementType }[] = [
  { key: "knowledge", label: "数据库", icon: Database },
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
  isLoggedIn, onLogout, onNeedLogin, user,
  onNewConversation, onSelectConversation,
  conversations = [], onPinConversation, onDeleteConversation,
  currentProjectId,
  onSelectProject,
  onOpenHistory,
  onOpenProjectDB,
  onOpenProjectGraph,
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
  conversations?: Conversation[];
  onPinConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
  currentProjectId?: number | null;
  onSelectProject?: (projectId: number | null) => void;
  onOpenHistory?: () => void;
  onOpenProjectDB?: (projectId: number) => void;
  onOpenProjectGraph?: (projectId: number) => void;
}) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [hoveredId, setHoveredId]       = useState<string | null>(null);
  const [projects, setProjects]         = useState<Project[]>([]);
  const [expandedProjectIds, setExpandedProjectIds] = useState<Set<number>>(new Set());
  const [projectsSectionExpanded, setProjectsSectionExpanded] = useState(true);
  const [hoveredProjectId, setHoveredProjectId] = useState<number | null>(null);
  const [activeProjectMenuId, setActiveProjectMenuId] = useState<number | null>(null);
  const [editingProjectId, setEditingProjectId] = useState<number | null>(null);
  const [editingProjectName, setEditingProjectName] = useState("");
  const [pinnedProjectIds, setPinnedProjectIds] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState<{ open: boolean; project: Project | null }>({ open: false, project: null });
  const menuRef       = useRef<HTMLDivElement>(null);
  const projectMenuRef = useRef<HTMLDivElement>(null);
  const projectRowRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Load projects
  const loadProjects = useCallback(async () => {
    try {
      const res = await api.listProjects();
      setProjects(res.items || []);
    } catch {
      setProjects([]);
    }
  }, []);

  useEffect(() => {
    if (isLoggedIn) loadProjects();
  }, [isLoggedIn, loadProjects]);

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
    if (activeProjectMenuId == null) return;
    const h = (e: MouseEvent) => {
      if (projectMenuRef.current && !projectMenuRef.current.contains(e.target as Node))
        setActiveProjectMenuId(null);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [activeProjectMenuId]);

  const toggleProject = (projectId: number) => {
    setExpandedProjectIds(prev => {
      const next = new Set(prev);
      if (next.has(projectId)) next.delete(projectId);
      else next.add(projectId);
      return next;
    });
  };

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
      <div className="px-3 mb-0.5" style={{ height: 28, display: "flex", alignItems: "center",
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
    const isActive = forceActive ?? (!!pageKey && active === pageKey);
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

  const generalConversations = conversations.filter(c => c.project_id == null);

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

            {/* History button */}
            <div style={{ padding: "0 8px 4px", display: "flex" }}>
              <SidebarTip label="历史记录" show={collapsed}>
                <button
                  onClick={onOpenHistory}
                  className="flex items-center gap-2.5 rounded-xl transition-all"
                  style={{
                    width: collapsed ? 40 : "100%",
                    height: 36,
                    paddingLeft: 12,
                    paddingRight: collapsed ? 12 : 10,
                    justifyContent: collapsed ? "center" : "flex-start",
                    background: "transparent",
                    cursor: "pointer",
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--hover, rgba(0,0,0,0.04))"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  <Clock style={{ width: 16, height: 16, flexShrink: 0, color: "var(--ink-500)" }} />
                  {!collapsed && (
                    <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--ink-700)" }}>
                      历史记录
                    </span>
                  )}
                </button>
              </SidebarTip>
            </div>

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

            {/* Project + Conversation list */}
            <div className="flex flex-col flex-1 min-h-0">
              <ScrollArea className="h-full px-2">
                <div style={{ paddingBottom: 80 }}>
                  {/* 项目区域 */}
                  {projects.length > 0 && (
                    <>
                      {/* Section header with expand/collapse toggle */}
                      <div
                        className="flex items-center justify-between px-3 mb-0.5 cursor-pointer"
                        style={{ height: 28, opacity: collapsed ? 0 : 0.7, transition: `opacity ${DUR} ${EASE}`, pointerEvents: collapsed ? "none" : "auto" }}
                        onClick={() => setProjectsSectionExpanded(v => !v)}
                      >
                        <span className="text-[10.5px] font-bold uppercase tracking-[0.08em]" style={{ color: "var(--ink-400)" }}>项目</span>
                        <ChevronRight
                          size={12}
                          style={{
                            color: "var(--ink-400)",
                            transform: projectsSectionExpanded ? "rotate(90deg)" : "rotate(0deg)",
                            transition: "transform 0.2s",
                          }}
                        />
                      </div>
                      {projectsSectionExpanded && (
                        <>
                          {[...projects]
                            .sort((a, b) => {
                              const aPinned = pinnedProjectIds.has(a.id) ? 1 : 0;
                              const bPinned = pinnedProjectIds.has(b.id) ? 1 : 0;
                              return bPinned - aPinned;
                            })
                            .map((project) => {
                              const projectConvs = conversations
                                .filter((c) => c.project_id === project.id)
                                .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());
                              const isExpanded = expandedProjectIds.has(project.id);
                              const hasConvs = projectConvs.length > 0;
                              const isHovered = hoveredProjectId === project.id;
                              const isMenuOpen = activeProjectMenuId === project.id;
                              const isEditing = editingProjectId === project.id;

                              return (
                                <div key={project.id} style={{ position: "relative" }}>
                                  {/* Project row */}
                                  <div
                                    ref={(el) => { if (el) projectRowRefs.current.set(project.id, el); else projectRowRefs.current.delete(project.id); }}
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-colors relative"
                                    style={{ opacity: collapsed ? 0 : 1, transition: `opacity ${DUR} ${EASE}`, pointerEvents: collapsed ? "none" : "auto" }}
                                    onClick={() => hasConvs && toggleProject(project.id)}
                                    onMouseEnter={(e) => {
                                      e.currentTarget.style.background = "var(--hover, rgba(0,0,0,0.04))";
                                      setHoveredProjectId(project.id);
                                    }}
                                    onMouseLeave={(e) => {
                                      e.currentTarget.style.background = "transparent";
                                      setHoveredProjectId(null);
                                    }}
                                  >
                                    <FolderOpen size={14} style={{ color: "var(--ink-500)", flexShrink: 0 }} />
                                    {isEditing ? (
                                      <input
                                        autoFocus
                                        value={editingProjectName}
                                        onChange={(e) => setEditingProjectName(e.target.value)}
                                        onKeyDown={async (e) => {
                                          if (e.key === "Enter") {
                                            if (editingProjectName.trim()) {
                                              try {
                                                await api.updateProject(project.id, { name: editingProjectName.trim() });
                                                setProjects(prev => prev.map(p => p.id === project.id ? { ...p, name: editingProjectName.trim() } : p));
                                              } catch {}
                                            }
                                            setEditingProjectId(null);
                                          } else if (e.key === "Escape") {
                                            setEditingProjectId(null);
                                          }
                                        }}
                                        onBlur={() => setEditingProjectId(null)}
                                        onClick={(e) => e.stopPropagation()}
                                        className="flex-1 text-[13px] font-medium truncate rounded px-1.5 py-0.5"
                                        style={{ color: "var(--ink-800)", background: "var(--bg-elevated)", border: "1px solid var(--border)", outline: "none" }}
                                      />
                                    ) : (
                                      <span className="text-[13px] font-medium truncate" style={{ color: "var(--ink-800)", flex: 1 }}>
                                        {project.name}
                                      </span>
                                    )}
                                    {/* Expand/collapse chevron — fixed position */}
                                    {hasConvs && (
                                      <ChevronRight
                                        size={12}
                                        style={{
                                          color: "var(--ink-400)",
                                          flexShrink: 0,
                                          transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                                          transition: "transform 0.2s",
                                        }}
                                      />
                                    )}
                                    {/* Hover action buttons — absolute so chevron stays aligned */}
                                    {!isEditing && (
                                      <div
                                        className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-0.5 rounded-md"
                                        style={{
                                          opacity: isHovered ? 1 : 0,
                                          transition: "opacity 0.15s",
                                          pointerEvents: isHovered ? "auto" : "none",
                                          background: "var(--bg-sidebar, var(--bg-panel))",
                                          padding: "0 2px",
                                        }}
                                      >
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setActiveProjectMenuId(isMenuOpen ? null : project.id);
                                          }}
                                          className="w-6 h-6 rounded-lg flex items-center justify-center transition-colors"
                                          style={{ background: "transparent", border: "none" }}
                                          title="更多"
                                        >
                                          <MoreHorizontal size={13} style={{ color: "var(--ink-500)" }} />
                                        </button>
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setEditingProjectId(project.id);
                                            setEditingProjectName(project.name);
                                          }}
                                          className="w-6 h-6 rounded-lg flex items-center justify-center transition-colors"
                                          style={{ background: "transparent", border: "none" }}
                                          title="重命名"
                                        >
                                          <Pencil size={11} style={{ color: "var(--ink-500)" }} />
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                  {/* Dropdown menu */}
                                  {isMenuOpen && (
                                    <div
                                      ref={projectMenuRef}
                                      className="absolute right-2 z-40 rounded-lg overflow-hidden"
                                      style={{
                                        top: 32,
                                        minWidth: 140,
                                        background: "var(--bg-elevated, #fff)",
                                        border: "1px solid var(--border)",
                                        boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                                      }}
                                    >
                                      <div className="py-1">
                                        <button
                                          onClick={() => {
                                            setPinnedProjectIds(prev => {
                                              const next = new Set(prev);
                                              if (next.has(project.id)) next.delete(project.id);
                                              else next.add(project.id);
                                              return next;
                                            });
                                            setActiveProjectMenuId(null);
                                          }}
                                          className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                                          style={{ fontSize: "12.5px", color: "var(--ink-700)" }}
                                        >
                                          <Pin size={12} style={{ color: "var(--ink-500)" }} />
                                          {pinnedProjectIds.has(project.id) ? "取消置顶" : "置顶项目"}
                                        </button>
                                        <button
                                          onClick={() => {
                                            onOpenProjectDB?.(project.id);
                                            setActiveProjectMenuId(null);
                                          }}
                                          className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                                          style={{ fontSize: "12.5px", color: "var(--ink-700)" }}
                                        >
                                          <Database size={12} style={{ color: "var(--ink-500)" }} />
                                          项目数据库
                                        </button>
                                        <button
                                          onClick={() => {
                                            onOpenProjectGraph?.(project.id);
                                            setActiveProjectMenuId(null);
                                          }}
                                          className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                                          style={{ fontSize: "12.5px", color: "var(--ink-700)" }}
                                        >
                                          <GitGraph size={12} style={{ color: "var(--ink-500)" }} />
                                          数据图谱
                                        </button>
                                        <button
                                          onClick={() => {
                                            setEditingProjectId(project.id);
                                            setEditingProjectName(project.name);
                                            setActiveProjectMenuId(null);
                                          }}
                                          className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                                          style={{ fontSize: "12.5px", color: "var(--ink-700)" }}
                                        >
                                          <Pencil size={12} style={{ color: "var(--ink-500)" }} />
                                          重命名项目
                                        </button>
                                        <div className="h-px mx-2 my-1" style={{ background: "var(--border)" }} />
                                        <button
                                          onClick={() => {
                                            setActiveProjectMenuId(null);
                                            setConfirmDelete({ open: true, project });
                                          }}
                                          className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                                          style={{ fontSize: "12.5px", color: "#ef4444" }}
                                        >
                                          <Trash2 size={12} style={{ color: "#ef4444" }} />
                                          移除
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                  {/* Conversations under project */}
                                  {isExpanded && projectConvs.map((c) => (
                                    <div key={c.id} style={{ paddingLeft: 20 }}>
                                      <ConversationItem
                                        item={c}
                                        collapsed={collapsed}
                                        hovered={hoveredId === c.id}
                                        onHover={setHoveredId}
                                        onSelect={onSelectConversation}
                                        onPin={onPinConversation}
                                        onDelete={onDeleteConversation}
                                      />
                                    </div>
                                  ))}
                                </div>
                              );
                            })}
                        </>
                      )}
                    </>
                  )}

                  {/* 对话区域（无项目） */}
                  {generalConversations.length > 0 && (
                    <>
                      <SectionLabel>对话</SectionLabel>
                      {generalConversations.map((c) => (
                        <ConversationItem
                          key={c.id}
                          item={c}
                          collapsed={collapsed}
                          hovered={hoveredId === c.id}
                          onHover={setHoveredId}
                          onSelect={onSelectConversation}
                          onPin={onPinConversation}
                          onDelete={onDeleteConversation}
                        />
                      ))}
                    </>
                  )}
                </div>
              </ScrollArea>
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

      {/* Project delete confirm popup */}
      {confirmDelete.open && confirmDelete.project && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center"
          style={{ background: "rgba(0,0,0,0.25)", paddingTop: 160 }}
          onClick={() => setConfirmDelete({ open: false, project: null })}
        >
          <div
            className="rounded-2xl p-6 w-[320px]"
            style={{
              background: "var(--bg-elevated, #fff)",
              border: "1px solid var(--border)",
              boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div
                className="h-9 w-9 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ background: "rgba(239,68,68,0.1)" }}
              >
                <Trash2 size={16} style={{ color: "#ef4444" }} />
              </div>
              <div>
                <p style={{ fontSize: 14.5, fontWeight: 600, color: "var(--ink-900)" }}>
                  确认移除项目
                </p>
                <p style={{ fontSize: 12.5, color: "var(--ink-500)", marginTop: 2 }}>
                  项目「{confirmDelete.project.name}」将被删除，此操作不可恢复。
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setConfirmDelete({ open: false, project: null })}
                className="h-8 px-3 rounded-lg text-[13px] font-medium transition-colors"
                style={{ color: "var(--ink-600)", background: "var(--bg-subtle)" }}
              >
                取消
              </button>
              <button
                onClick={async () => {
                  const project = confirmDelete.project;
                  if (!project) return;
                  setConfirmDelete({ open: false, project: null });
                  try {
                    await api.deleteProject(project.id);
                    setProjects((prev) => prev.filter((p) => p.id !== project.id));
                    if (currentProjectId === project.id) {
                      onSelectProject?.(null);
                    }
                  } catch {}
                }}
                className="h-8 px-3 rounded-lg text-[13px] font-medium transition-colors"
                style={{ color: "#fff", background: "#ef4444" }}
              >
                确认移除
              </button>
            </div>
          </div>
        </div>
      )}
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
  return (
    <div className="relative"
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
          gridTemplateColumns: "minmax(0, 1fr) 58px",
          alignItems: "center",
          columnGap: 8,
          padding: "6px 10px",
          background: hovered ? "var(--hover, rgba(0,0,0,0.04))" : "transparent",
          opacity: collapsed ? 0 : 1,
          transition: `opacity 0.24s ease, background 0.12s ease`,
          pointerEvents: collapsed ? "none" : "auto",
          cursor: "pointer",
        }}
      >
        <div style={{ minWidth: 0 }}>
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
