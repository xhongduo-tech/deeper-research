/**
 * OntologyEditor — 可视化本体编辑器
 *
 * 功能：
 * 1. 画布渲染节点（概念/实体/事件/流程/属性）和关系边
 * 2. 拖拽移动节点
 * 3. 添加节点 / 连接节点 / 删除选中项
 * 4. 属性面板编辑
 * 5. 从项目知识库自动抽取本体
 */
import { useState, useRef, useEffect, useCallback } from "react";
import {
  MousePointer2, Plus, GitBranch, Trash2, Wand2, RotateCcw,
  Move, X, Check, Loader2, AlertCircle, ChevronRight, Sparkles,
} from "lucide-react";
import { api, Project, KnowledgeBase } from "../lib/api";

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

export interface VisualNode {
  id: number;
  name: string;
  node_type: string;
  domain: string;
  description?: string;
  importance?: number;
  aliases?: string[];
  x: number;
  y: number;
}

export interface VisualEdge {
  id: number;
  source: number;
  target: number;
  relation_type: string;
  relation_label?: string;
  weight?: number;
  confidence?: number;
}

type EditorMode = "select" | "add_node" | "connect";

const NODE_TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  concept:    { bg: "#eff6ff", border: "#93c5fd", text: "#1d4ed8" },
  entity:     { bg: "#f0fdf4", border: "#86efac", text: "#15803d" },
  event:      { bg: "#fffbeb", border: "#fcd34d", text: "#b45309" },
  process:    { bg: "#f5f3ff", border: "#c4b5fd", text: "#6d28d9" },
  attribute:  { bg: "#f3f4f6", border: "#d1d5db", text: "#4b5563" },
};

const NODE_TYPE_LABELS: Record<string, string> = {
  concept: "概念", entity: "实体", event: "事件", process: "流程", attribute: "属性",
};

function getNodeColor(nodeType: string) {
  return NODE_TYPE_COLORS[nodeType] || NODE_TYPE_COLORS.concept;
}

function getNodeLabel(nodeType: string) {
  return NODE_TYPE_LABELS[nodeType] || nodeType;
}

/** Simple grid layout for nodes without positions */
function autoLayout(nodes: Omit<VisualNode, "x" | "y">[]): VisualNode[] {
  const cols = Math.max(3, Math.ceil(Math.sqrt(nodes.length)));
  return nodes.map((n, i) => ({
    ...n,
    x: 140 + (i % cols) * 200,
    y: 80 + Math.floor(i / cols) * 120,
  }));
}

let _nextLocalId = -1;
function nextLocalId() {
  return _nextLocalId--;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════════════

export default function OntologyEditor({ projectId, defaultToSystem = false }: { projectId?: number; defaultToSystem?: boolean }) {
  const [nodes, setNodes] = useState<VisualNode[]>([]);
  const [edges, setEdges] = useState<VisualEdge[]>([]);
  const [mode, setMode] = useState<EditorMode>("select");
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<number | null>(null);
  const [connectingFrom, setConnectingFrom] = useState<number | null>(null);
  const [dragging, setDragging] = useState<{ id: number; dx: number; dy: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [projectKBs, setProjectKBs] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<number | null>(null);

  const canvasRef = useRef<HTMLDivElement>(null);

  // ── Load project KBs ──
  useEffect(() => {
    if (projectId == null) {
      // No project — show system ontology nodes by default
      if (defaultToSystem) loadGraph(undefined);
      return;
    }
    api.listProjectKBs(projectId)
      .then((res) => {
        const kbs = res.items || [];
        setProjectKBs(kbs);
        if (kbs.length > 0) {
          setSelectedKbId(kbs[0].id);
        } else {
          // Project has no KBs yet — fall back to system nodes
          loadGraph(undefined);
        }
      })
      .catch(() => {
        setProjectKBs([]);
        loadGraph(undefined);
      });
  }, [projectId]); // eslint-disable-line

  // ── Load ontology graph ──
  const loadGraph = useCallback(async (kbId?: number) => {
    setLoading(true);
    setError("");
    try {
      const graph = await api.getOntologyGraph(kbId || undefined);
      const hasPositions = graph.nodes.some((n: any) => n.x != null && n.y != null);
      const visualNodes = hasPositions
        ? graph.nodes.map((n: any) => ({ ...n, x: n.x ?? 100, y: n.y ?? 100 }))
        : autoLayout(graph.nodes);
      setNodes(visualNodes);
      setEdges(graph.edges);
    } catch (e) {
      setError(String((e as Error)?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-load when kb selected
  useEffect(() => {
    if (selectedKbId != null) {
      loadGraph(selectedKbId);
    }
  }, [selectedKbId, loadGraph]);

  // ── Extract from KB ──
  const handleExtract = useCallback(async () => {
    if (selectedKbId == null) return;
    setExtracting(true);
    setError("");
    try {
      const result = await api.extractOntologyFromKB(selectedKbId);
      await loadGraph(selectedKbId);
      // Show a brief success state — nodes/edges already reloaded
    } catch (e) {
      setError(String((e as Error)?.message || e));
    } finally {
      setExtracting(false);
    }
  }, [selectedKbId, loadGraph]);

  // ── Canvas interactions ──
  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    if (mode !== "add_node") return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left + canvasRef.current!.scrollLeft;
    const y = e.clientY - rect.top + canvasRef.current!.scrollTop;
    const newNode: VisualNode = {
      id: nextLocalId(),
      name: "新概念",
      node_type: "concept",
      domain: "general",
      x,
      y,
    };
    setNodes((prev) => [...prev, newNode]);
    setSelectedNodeId(newNode.id);
    setMode("select");
  }, [mode]);

  const handleNodeMouseDown = useCallback((e: React.MouseEvent, nodeId: number) => {
    e.stopPropagation();
    if (mode === "connect") {
      if (connectingFrom == null) {
        setConnectingFrom(nodeId);
        setSelectedNodeId(nodeId);
      } else if (connectingFrom !== nodeId) {
        // Create edge
        const newEdge: VisualEdge = {
          id: nextLocalId(),
          source: connectingFrom,
          target: nodeId,
          relation_type: "related_to",
          relation_label: "关联",
          weight: 1.0,
          confidence: 0.8,
        };
        setEdges((prev) => [...prev, newEdge]);
        setConnectingFrom(null);
        setMode("select");
        setSelectedEdgeId(newEdge.id);
      }
      return;
    }
    if (mode === "select") {
      setSelectedNodeId(nodeId);
      setSelectedEdgeId(null);
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      const canvasX = e.clientX - rect.left + canvasRef.current!.scrollLeft;
      const canvasY = e.clientY - rect.top + canvasRef.current!.scrollTop;
      setDragging({ id: nodeId, dx: canvasX - node.x, dy: canvasY - node.y });
    }
  }, [mode, connectingFrom, nodes]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const canvasX = e.clientX - rect.left + canvasRef.current!.scrollLeft;
    const canvasY = e.clientY - rect.top + canvasRef.current!.scrollTop;
    const x = canvasX - dragging.dx;
    const y = canvasY - dragging.dy;
    setNodes((prev) =>
      prev.map((n) => (n.id === dragging.id ? { ...n, x: Math.max(40, x), y: Math.max(30, y) } : n))
    );
  }, [dragging]);

  const handleMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  const handleEdgeClick = useCallback((e: React.MouseEvent, edgeId: number) => {
    e.stopPropagation();
    setSelectedEdgeId(edgeId);
    setSelectedNodeId(null);
  }, []);

  const handleDelete = useCallback(() => {
    if (selectedNodeId != null) {
      setNodes((prev) => prev.filter((n) => n.id !== selectedNodeId));
      setEdges((prev) => prev.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
      setSelectedNodeId(null);
    } else if (selectedEdgeId != null) {
      setEdges((prev) => prev.filter((e) => e.id !== selectedEdgeId));
      setSelectedEdgeId(null);
    }
  }, [selectedNodeId, selectedEdgeId]);

  // Keyboard delete
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Delete" || e.key === "Backspace") {
        handleDelete();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleDelete]);

  // ── Property updates ──
  const updateNode = (id: number, patch: Partial<VisualNode>) => {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, ...patch } : n)));
  };

  const updateEdge = (id: number, patch: Partial<VisualEdge>) => {
    setEdges((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);

  // ── Render helpers ──
  const getEdgePath = (edge: VisualEdge) => {
    const src = nodes.find((n) => n.id === edge.source);
    const tgt = nodes.find((n) => n.id === edge.target);
    if (!src || !tgt) return "";
    // Node dimensions
    const nw = 128;
    const nh = 52;
    const sx = src.x + nw / 2;
    const sy = src.y + nh / 2;
    const tx = tgt.x + nw / 2;
    const ty = tgt.y + nh / 2;
    // Simple straight line (nodes rendered on top will cover the ends)
    return `M ${sx} ${sy} L ${tx} ${ty}`;
  };

  const canvasWidth = Math.max(1200, nodes.length > 0 ? Math.max(...nodes.map((n) => n.x)) + 300 : 1200);
  const canvasHeight = Math.max(700, nodes.length > 0 ? Math.max(...nodes.map((n) => n.y)) + 200 : 700);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
        <div className="flex items-center gap-1">
          {([
            { key: "select" as EditorMode, label: "选择", icon: MousePointer2 },
            { key: "add_node" as EditorMode, label: "添加节点", icon: Plus },
            { key: "connect" as EditorMode, label: "连接", icon: GitBranch },
          ]).map((m) => {
            const Icon = m.icon;
            const active = mode === m.key;
            return (
              <button
                key={m.key}
                onClick={() => { setMode(m.key); setConnectingFrom(null); }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all"
                style={{
                  background: active ? "var(--ink-900)" : "transparent",
                  color: active ? "#fff" : "var(--ink-500)",
                }}
              >
                <Icon size={13} />
                {m.label}
              </button>
            );
          })}

          <div className="w-px h-5 mx-2" style={{ background: "var(--border)" }} />

          <button
            onClick={handleDelete}
            disabled={selectedNodeId == null && selectedEdgeId == null}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all disabled:opacity-30"
            style={{ color: "#ef4444" }}
          >
            <Trash2 size={13} />
            删除
          </button>

          <button
            onClick={() => { setNodes([]); setEdges([]); setSelectedNodeId(null); setSelectedEdgeId(null); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all"
            style={{ color: "var(--ink-400)" }}
          >
            <RotateCcw size={13} />
            清空
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* KB selector for extraction */}
          {projectKBs.length > 0 && (
            <select
              value={selectedKbId ?? ""}
              onChange={(e) => setSelectedKbId(Number(e.target.value) || null)}
              className="text-[12px] rounded-lg px-2 py-1 outline-none"
              style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-700)" }}
            >
              {projectKBs.map((kb) => (
                <option key={kb.id} value={kb.id}>{kb.name}</option>
              ))}
            </select>
          )}

          <button
            onClick={handleExtract}
            disabled={extracting || selectedKbId == null}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-white transition-all disabled:opacity-40"
            style={{ background: "var(--ink-900)" }}
          >
            {extracting ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />}
            自动抽取
          </button>
        </div>
      </div>

      {mode === "connect" && connectingFrom != null && (
        <div className="px-4 py-1.5 text-[11px] flex items-center gap-1.5"
          style={{ background: "#fef3c7", color: "#92400e", borderBottom: "1px solid #fde68a" }}>
          <Sparkles size={12} />
          连接模式：点击目标节点完成连接，或按 ESC 取消
          <button onClick={() => { setConnectingFrom(null); setMode("select"); }}
            className="ml-2 underline text-[10px]">取消</button>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-1.5 px-4 py-2 text-[11px]"
          style={{ background: "#fef2f2", color: "#991b1b", borderBottom: "1px solid #fecaca" }}>
          <AlertCircle size={12} />
          {error}
          <button onClick={() => setError("")} className="ml-auto underline">关闭</button>
        </div>
      )}

      {/* Main canvas + property panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Canvas */}
        <div className="flex-1 overflow-auto relative" style={{ background: "var(--bg)" }}>
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 size={24} className="animate-spin" style={{ color: "var(--ink-300)" }} />
            </div>
          ) : (
            <div
              ref={canvasRef}
              className="relative"
              style={{
                width: canvasWidth,
                height: canvasHeight,
                backgroundImage:
                  "radial-gradient(circle, var(--border-strong) 1px, transparent 1px)",
                backgroundSize: "20px 20px",
                cursor: mode === "add_node" ? "crosshair" : mode === "connect" ? "crosshair" : "default",
              }}
              onClick={handleCanvasClick}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              {/* SVG edges layer */}
              <svg
                className="absolute inset-0 pointer-events-none"
                width={canvasWidth}
                height={canvasHeight}
                style={{ zIndex: 1 }}
              >
                <defs>
                  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
                  </marker>
                  <marker id="arrowhead-selected" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#6366f1" />
                  </marker>
                </defs>
                {edges.map((edge) => {
                  const d = getEdgePath(edge);
                  if (!d) return null;
                  const isSelected = selectedEdgeId === edge.id;
                  return (
                    <g key={edge.id} style={{ pointerEvents: "stroke" }} onClick={(e) => handleEdgeClick(e as any, edge.id)}>
                      <path
                        d={d}
                        stroke={isSelected ? "#6366f1" : "#9ca3af"}
                        strokeWidth={isSelected ? 2.5 : 1.5}
                        fill="none"
                        markerEnd={isSelected ? "url(#arrowhead-selected)" : "url(#arrowhead)"}
                        style={{ cursor: "pointer", transition: "stroke 0.15s" }}
                      />
                      {/* Edge label */}
                      {edge.relation_label && (() => {
                        const src = nodes.find((n) => n.id === edge.source);
                        const tgt = nodes.find((n) => n.id === edge.target);
                        if (!src || !tgt) return null;
                        const mx = (src.x + 64 + tgt.x + 64) / 2;
                        const my = (src.y + 26 + tgt.y + 26) / 2;
                        return (
                          <g>
                            <rect x={mx - 24} y={my - 9} width={48} height={16} rx={4}
                              fill={isSelected ? "#e0e7ff" : "#f3f4f6"}
                              stroke={isSelected ? "#c7d2fe" : "#e5e7eb"}
                              strokeWidth={1}
                            />
                            <text x={mx} y={my + 3} textAnchor="middle"
                              fontSize={9} fill={isSelected ? "#4338ca" : "#6b7280"}>
                              {edge.relation_label}
                            </text>
                          </g>
                        );
                      })()}
                    </g>
                  );
                })}
              </svg>

              {/* Nodes layer */}
              {nodes.map((node) => {
                const colors = getNodeColor(node.node_type);
                const isSelected = selectedNodeId === node.id;
                const isConnectingSource = connectingFrom === node.id;
                return (
                  <div
                    key={node.id}
                    className="absolute rounded-xl flex flex-col items-center justify-center select-none transition-shadow"
                    style={{
                      left: node.x,
                      top: node.y,
                      width: 128,
                      minHeight: 52,
                      background: colors.bg,
                      border: `2px solid ${isSelected ? "#6366f1" : isConnectingSource ? "#f59e0b" : colors.border}`,
                      boxShadow: isSelected
                        ? "0 0 0 3px rgba(99,102,241,0.15), 0 2px 8px rgba(0,0,0,0.08)"
                        : "0 1px 3px rgba(0,0,0,0.06)",
                      zIndex: isSelected ? 10 : 2,
                      cursor: mode === "connect" ? "crosshair" : mode === "select" ? "move" : "pointer",
                      padding: "6px 8px",
                    }}
                    onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                  >
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded mb-1"
                      style={{ background: colors.border + "40", color: colors.text }}>
                      {getNodeLabel(node.node_type)}
                    </span>
                    <span className="text-[12px] font-semibold text-center leading-tight"
                      style={{ color: "#1f2937" }}>
                      {node.name}
                    </span>
                  </div>
                );
              })}

              {nodes.length === 0 && !loading && (
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <Move size={32} className="mb-2" style={{ color: "var(--ink-300)" }} />
                  <p className="text-[13px] font-medium" style={{ color: "var(--ink-400)" }}>
                    {mode === "add_node" ? "点击画布空白处添加节点" : "画布为空，点击「添加节点」或「自动抽取」开始构建本体"}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Property Panel */}
        <div className="w-64 shrink-0 overflow-auto"
          style={{ borderLeft: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
          {selectedNode ? (
            <div className="p-4 space-y-3">
              <h4 className="text-[13px] font-semibold flex items-center gap-2" style={{ color: "var(--ink-800)" }}>
                <ChevronRight size={14} />
                节点属性
              </h4>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>名称</label>
                <input
                  value={selectedNode.name}
                  onChange={(e) => updateNode(selectedNode.id, { name: e.target.value })}
                  className="w-full text-[12px] rounded-lg px-2 py-1.5 outline-none"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)" }}
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>类型</label>
                <select
                  value={selectedNode.node_type}
                  onChange={(e) => updateNode(selectedNode.id, { node_type: e.target.value })}
                  className="w-full text-[12px] rounded-lg px-2 py-1.5 outline-none"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)" }}
                >
                  {Object.entries(NODE_TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>领域</label>
                <input
                  value={selectedNode.domain}
                  onChange={(e) => updateNode(selectedNode.id, { domain: e.target.value })}
                  className="w-full text-[12px] rounded-lg px-2 py-1.5 outline-none"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)" }}
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>描述</label>
                <textarea
                  value={selectedNode.description || ""}
                  onChange={(e) => updateNode(selectedNode.id, { description: e.target.value })}
                  rows={3}
                  className="w-full text-[12px] rounded-lg px-2 py-1.5 outline-none resize-none"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)" }}
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>
                  重要度: {selectedNode.importance?.toFixed(2) ?? "0.50"}
                </label>
                <input
                  type="range"
                  min={0} max={1} step={0.05}
                  value={selectedNode.importance ?? 0.5}
                  onChange={(e) => updateNode(selectedNode.id, { importance: Number(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>
          ) : selectedEdge ? (
            <div className="p-4 space-y-3">
              <h4 className="text-[13px] font-semibold flex items-center gap-2" style={{ color: "var(--ink-800)" }}>
                <GitBranch size={14} />
                关系属性
              </h4>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>关系类型</label>
                <input
                  value={selectedEdge.relation_type}
                  onChange={(e) => updateEdge(selectedEdge.id, { relation_type: e.target.value })}
                  className="w-full text-[12px] rounded-lg px-2 py-1.5 outline-none"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)" }}
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>显示标签</label>
                <input
                  value={selectedEdge.relation_label || ""}
                  onChange={(e) => updateEdge(selectedEdge.id, { relation_label: e.target.value })}
                  className="w-full text-[12px] rounded-lg px-2 py-1.5 outline-none"
                  style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)" }}
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>
                  权重: {selectedEdge.weight?.toFixed(2) ?? "1.00"}
                </label>
                <input
                  type="range"
                  min={0} max={2} step={0.1}
                  value={selectedEdge.weight ?? 1}
                  onChange={(e) => updateEdge(selectedEdge.id, { weight: Number(e.target.value) })}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-500)" }}>
                  置信度: {selectedEdge.confidence?.toFixed(2) ?? "0.80"}
                </label>
                <input
                  type="range"
                  min={0} max={1} step={0.05}
                  value={selectedEdge.confidence ?? 0.8}
                  onChange={(e) => updateEdge(selectedEdge.id, { confidence: Number(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>
          ) : (
            <div className="p-6 text-center">
              <MousePointer2 size={24} className="mx-auto mb-2" style={{ color: "var(--ink-300)" }} />
              <p className="text-[12px]" style={{ color: "var(--ink-400)" }}>
                选择节点或关系边以编辑属性
              </p>
              <div className="mt-4 text-[11px] space-y-1" style={{ color: "var(--ink-400)" }}>
                <p>· 拖拽移动节点</p>
                <p>· 点击「连接」后依次点击两个节点</p>
                <p>· Delete 键删除选中项</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
