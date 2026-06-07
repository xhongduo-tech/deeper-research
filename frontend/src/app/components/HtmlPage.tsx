/**
 * HtmlPage — HTML report generation with 4 template styles.
 * Generates self-contained HTML files downloadable directly from the browser.
 */
import { useState, useRef } from "react";
import { Code2, Download, Eye, Wand2, LayoutDashboard, FileText, Map, Rocket, Copy, Check } from "lucide-react";
import { api } from "../lib/api";
import { TechIntroBadge } from "./TechIntroModal";
import { DatabaseSelector, DBSelection } from "./DatabaseSelector";

// ── Template definitions ──────────────────────────────────────────────────────

type HtmlTemplate = {
  id: string;
  name: string;
  desc: string;
  style: string;   // backend template_style
  icon: React.ElementType;
  accentColor: string;
  bg: string;
  preview: React.ReactNode;
  placeholder: string;
  suggestedTags: string[];
};

const ThumbDashboard = () => (
  <div className="w-full h-full p-3 flex flex-col gap-1.5" style={{ background: "#0f172a" }}>
    <div className="flex gap-1.5">
      {["#38bdf8", "#818cf8", "#34d399"].map((c, i) => (
        <div key={i} className="flex-1 rounded p-1.5" style={{ background: "#1e293b" }}>
          <div className="text-[6px] font-bold" style={{ color: c }}>{ ["2.4M", "68%", "142"][i] }</div>
          <div className="h-0.5 rounded mt-0.5" style={{ background: "#334155" }} />
        </div>
      ))}
    </div>
    <div className="flex gap-1.5 flex-1">
      <div className="flex-[2] rounded" style={{ background: "#1e293b" }}>
        <div className="h-full p-1.5 flex flex-col justify-end gap-0.5">
          {[60, 45, 80, 55, 70, 40, 75].map((h, i) => (
            <div key={i} className="w-full rounded-sm" style={{ height: `${h}%`, background: "#38bdf8", opacity: 0.7, maxHeight: 6 }} />
          ))}
        </div>
      </div>
      <div className="flex-1 rounded flex items-center justify-center" style={{ background: "#1e293b" }}>
        <div className="w-6 h-6 rounded-full border-4" style={{ borderColor: "#38bdf8", borderTopColor: "#1e293b" }} />
      </div>
    </div>
  </div>
);

const ThumbReport = () => (
  <div className="w-full h-full p-3 flex flex-col gap-1.5" style={{ background: "#fff" }}>
    <div className="h-1 w-1/2 rounded" style={{ background: "#2563eb" }} />
    <div className="h-0.5 w-3/4 rounded" style={{ background: "#e2e8f0" }} />
    <div className="h-0.5 w-full rounded" style={{ background: "#e2e8f0" }} />
    <div className="h-0.5 w-5/6 rounded" style={{ background: "#e2e8f0" }} />
    <div className="flex gap-1.5 mt-1">
      {["#2563eb", "#7c3aed"].map((c, i) => (
        <div key={i} className="flex-1 rounded p-1" style={{ background: c + "10" }}>
          <div className="h-0.5 rounded w-full" style={{ background: c, opacity: 0.5 }} />
          <div className="h-0.5 rounded w-3/4 mt-0.5" style={{ background: "#e2e8f0" }} />
        </div>
      ))}
    </div>
    <div className="h-0.5 w-full rounded" style={{ background: "#e2e8f0" }} />
    <div className="h-0.5 w-2/3 rounded" style={{ background: "#e2e8f0" }} />
  </div>
);

const ThumbMinimal = () => (
  <div className="w-full h-full p-3 flex flex-col gap-1.5" style={{ background: "#fafafa" }}>
    <div className="h-2 w-2/3 rounded" style={{ background: "#18181b" }} />
    <div className="h-0.5 w-full rounded" style={{ background: "#e4e4e7" }} />
    <div className="h-0.5 w-5/6 rounded" style={{ background: "#e4e4e7" }} />
    <div className="h-0.5 w-full rounded" style={{ background: "#e4e4e7" }} />
    <div className="h-0.5 w-3/4 rounded" style={{ background: "#e4e4e7" }} />
    <div className="flex gap-1.5 mt-1">
      {[0, 1, 2].map(i => (
        <span key={i} className="px-1 py-0.5 rounded text-[5px]"
          style={{ background: "#18181b12", color: "#71717a" }}>tag</span>
      ))}
    </div>
  </div>
);

const ThumbVivid = () => (
  <div className="w-full h-full p-3 flex flex-col gap-1.5" style={{ background: "#0d0d0d" }}>
    <div className="h-2 w-2/3 rounded" style={{ background: "linear-gradient(90deg,#ff6b35,#ffd166)" }} />
    <div className="h-0.5 w-full rounded" style={{ background: "#2a2a2a" }} />
    <div className="grid grid-cols-2 gap-1 mt-1">
      {[["#ff6b35", "84K"], ["#ffd166", "2.1M"], ["#34d399", "99%"], ["#a78bfa", "↑18"]].map(([c, v]) => (
        <div key={v} className="rounded p-1" style={{ background: "#1a1a1a" }}>
          <div className="text-[6px] font-bold" style={{ color: c }}>{v}</div>
        </div>
      ))}
    </div>
  </div>
);

const TEMPLATES: HtmlTemplate[] = [
  {
    id: "dashboard",
    name: "数据大屏",
    desc: "深色科技风，适合数据可视化展示、汇报大屏",
    style: "dashboard",
    icon: LayoutDashboard,
    accentColor: "#38bdf8",
    bg: "#0f172a",
    preview: <ThumbDashboard />,
    placeholder: "描述你的数据大屏内容，例如：「生成2026年Q1销售数据大屏，包含营收、增长率、区域分布」",
    suggestedTags: ["销售大屏", "运营监控", "财务看板", "用户分析"],
  },
  {
    id: "report",
    name: "研究报告网页版",
    desc: "专业白色风格，长文阅读友好，适合研究报告、分析文档",
    style: "report",
    icon: FileText,
    accentColor: "#2563eb",
    bg: "#ffffff",
    preview: <ThumbReport />,
    placeholder: "描述你的报告内容，例如：「将以下市场分析报告转成网页版，要求层次清晰、有数据卡片」",
    suggestedTags: ["市场分析", "行业报告", "竞品研究", "投资备忘"],
  },
  {
    id: "minimal",
    name: "极简知识文档",
    desc: "简洁中性风格，专注内容，适合知识整理、产品文档",
    style: "minimal",
    icon: Map,
    accentColor: "#18181b",
    bg: "#fafafa",
    preview: <ThumbMinimal />,
    placeholder: "描述文档内容，例如：「整理团队规范文档、产品 FAQ、项目说明」",
    suggestedTags: ["操作手册", "FAQ", "项目说明", "团队规范"],
  },
  {
    id: "vivid",
    name: "活力展示页",
    desc: "深色彩色风格，视觉冲击力强，适合产品介绍、成果展示",
    style: "vivid",
    icon: Rocket,
    accentColor: "#ff6b35",
    bg: "#0d0d0d",
    preview: <ThumbVivid />,
    placeholder: "描述展示内容，例如：「生成AI产品发布页，突出三大核心功能和用户数据」",
    suggestedTags: ["产品发布", "成果展示", "项目汇报", "品牌推广"],
  },
];

// ── Preview pane ──────────────────────────────────────────────────────────────

function HtmlPreviewPane({ html, onClose }: { html: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(html);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${Date.now()}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: "var(--bg)" }}>
      {/* Toolbar */}
      <div className="h-12 border-b flex items-center gap-3 px-4 flex-shrink-0"
        style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}>
        <Eye size={14} style={{ color: "var(--ink-400)" }} />
        <span className="text-[13px] font-semibold" style={{ color: "var(--ink-800)" }}>HTML 预览</span>
        <div className="flex-1" />
        <button
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12px] font-medium hover:bg-gray-50 transition-colors"
          style={{ borderColor: "var(--border)", color: "var(--ink-600)" }}
          onClick={handleCopy}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? "已复制" : "复制代码"}
        </button>
        <button
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold text-white"
          style={{ background: "var(--brand, #2563eb)" }}
          onClick={handleDownload}
        >
          <Download size={13} />
          下载 HTML
        </button>
        <button
          className="px-3 py-1.5 rounded-lg border text-[12px] hover:bg-gray-50 transition-colors"
          style={{ borderColor: "var(--border)", color: "var(--ink-600)" }}
          onClick={onClose}
        >
          关闭
        </button>
      </div>
      {/* iframe preview */}
      <iframe
        className="flex-1 w-full border-0"
        srcDoc={html}
        sandbox="allow-scripts allow-same-origin"
        title="HTML Preview"
      />
    </div>
  );
}

// ── Template card ─────────────────────────────────────────────────────────────

function TemplateCard({
  tpl, selected, onSelect,
}: {
  tpl: HtmlTemplate;
  selected: boolean;
  onSelect: () => void;
}) {
  const Icon = tpl.icon;
  return (
    <button
      className="w-full text-left rounded-2xl border overflow-hidden transition-all duration-200 hover:shadow-md"
      style={{
        borderColor: selected ? tpl.accentColor : "var(--border)",
        boxShadow: selected ? `0 0 0 2px ${tpl.accentColor}30` : undefined,
        background: "var(--bg-panel)",
      }}
      onClick={onSelect}
    >
      {/* Thumbnail */}
      <div className="h-[80px] w-full overflow-hidden">
        {tpl.preview}
      </div>
      {/* Info */}
      <div className="p-3">
        <div className="flex items-center gap-2 mb-1">
          <Icon size={13} style={{ color: tpl.accentColor, flexShrink: 0 }} />
          <span className="text-[13px] font-semibold" style={{ color: "var(--ink-900)" }}>{tpl.name}</span>
          {selected && (
            <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full"
              style={{ background: tpl.accentColor + "18", color: tpl.accentColor }}>
              ✓ 已选
            </span>
          )}
        </div>
        <p className="text-[11px] leading-4" style={{ color: "var(--ink-400)" }}>{tpl.desc}</p>
      </div>
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function HtmlPage({
  onOpenTechIntro,
}: {
  onOpenTechIntro?: (techId: string) => void;
}) {
  const [selectedTpl, setSelectedTpl] = useState<HtmlTemplate>(TEMPLATES[0]);
  const [prompt, setPrompt] = useState("");
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [generatedHtml, setGeneratedHtml] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [error, setError] = useState("");
  const [dbSelection, setDbSelection] = useState<DBSelection>({ kb_ids: [], include_system: true });
  const textRef = useRef<HTMLTextAreaElement>(null);

  const handleGenerate = async () => {
    if (!prompt.trim() && !content.trim()) {
      setError("请输入描述或内容");
      return;
    }
    setLoading(true);
    setError("");
    try {
      // Use the backend HTML generation API
      const res = await api.post<{ html: string }>("/api/html/generate", {
        prompt: prompt || `生成一份${selectedTpl.name}风格的HTML页面`,
        content: content,
        title: title || prompt.slice(0, 30) || "DataAgent 报告",
        template_style: selectedTpl.style,
        kb_ids: dbSelection.kb_ids,
        include_system_kb: dbSelection.include_system,
      });
      setGeneratedHtml(res.html);
      setShowPreview(true);
    } catch {
      // Fallback: generate client-side demo HTML
      const demoHtml = buildDemoHtml(
        title || prompt.slice(0, 40) || "DataAgent 报告",
        content || prompt,
        selectedTpl.style,
      );
      setGeneratedHtml(demoHtml);
      setShowPreview(true);
    } finally {
      setLoading(false);
    }
  };

  // Client-side demo HTML builder (used as fallback)
  function buildDemoHtml(docTitle: string, text: string, style: string): string {
    const palettes: Record<string, Record<string, string>> = {
      dashboard: { bg: "#0f172a", accent: "#38bdf8", accent2: "#818cf8", text: "#f1f5f9", text2: "#94a3b8", card: "#1e293b", border: "#334155" },
      report:    { bg: "#ffffff", accent: "#2563eb", accent2: "#7c3aed", text: "#0f172a", text2: "#64748b", card: "#f1f5f9", border: "#e2e8f0" },
      minimal:   { bg: "#fafafa", accent: "#18181b", accent2: "#71717a", text: "#18181b", text2: "#71717a", card: "#ffffff", border: "#e4e4e7" },
      vivid:     { bg: "#0d0d0d", accent: "#ff6b35", accent2: "#ffd166", text: "#ffffff", text2: "#a1a1aa", card: "#1a1a1a", border: "#2a2a2a" },
    };
    const p = palettes[style] || palettes.report;
    const cssVars = Object.entries(p).map(([k, v]) => `--${k}:${v}`).join(";");

    const lines = text.split("\n").filter(Boolean);
    const bodyLines = lines.map(l => {
      if (l.startsWith("## ") || l.startsWith("# ")) return `<h2 style="font-size:1.2rem;font-weight:700;color:var(--accent);border-left:3px solid var(--accent);padding-left:14px;margin:24px 0 12px">${l.replace(/^#+\s/, "")}</h2>`;
      if (l.startsWith("- ")) return `<li style="margin:4px 0;color:var(--text2)">${l.slice(2)}</li>`;
      return `<p style="color:var(--text2);margin-bottom:10px;line-height:1.7">${l}</p>`;
    }).join("\n");

    return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${docTitle}</title>
<style>:root{${cssVars}}*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,'PingFang SC',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.wrap{max-width:900px;margin:0 auto;padding:48px 24px}.hero{padding:48px 0 32px;text-align:center;border-bottom:1px solid var(--border);margin-bottom:40px}
.hero h1{font-size:clamp(1.8rem,4vw,2.6rem);font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}
.footer{text-align:center;padding:32px 0 16px;border-top:1px solid var(--border);margin-top:48px;font-size:.8rem;color:var(--text2)}</style></head>
<body><div class="wrap"><div class="hero"><h1>${docTitle}</h1><p style="color:var(--text2);font-size:1rem">由 DataAgent Studio 生成</p></div>
<div>${bodyLines}</div><div class="footer">Generated by DataAgent Studio · ${new Date().toLocaleDateString("zh-CN")}</div></div></body></html>`;
  }

  if (showPreview && generatedHtml) {
    return <HtmlPreviewPane html={generatedHtml} onClose={() => setShowPreview(false)} />;
  }

  return (
    <div className="flex h-full overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* Left: template gallery */}
      <div className="w-[280px] flex-shrink-0 border-r flex flex-col overflow-y-auto"
        style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}>
        <div className="px-4 pt-4 pb-3 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-2 mb-2">
            <Code2 size={18} style={{ color: "var(--brand, #2563eb)" }} />
            <span className="font-semibold text-[15px]" style={{ color: "var(--ink-900)" }}>HTML 网页</span>
          </div>
          <TechIntroBadge techId="insight_fusion" onOpen={id => onOpenTechIntro?.(id ?? "insight_fusion")} />
        </div>
        <div className="p-3 flex flex-col gap-2.5">
          <div className="text-[11px] font-semibold uppercase tracking-wide px-1" style={{ color: "var(--ink-400)" }}>
            选择模板风格
          </div>
          {TEMPLATES.map(tpl => (
            <TemplateCard
              key={tpl.id}
              tpl={tpl}
              selected={selectedTpl.id === tpl.id}
              onSelect={() => {
                setSelectedTpl(tpl);
                setPrompt("");
              }}
            />
          ))}
        </div>
      </div>

      {/* Right: input + generate */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="h-14 border-b flex items-center gap-3 px-6 flex-shrink-0"
          style={{ borderColor: "var(--border)", background: "var(--bg-panel)" }}>
          <selectedTpl.icon size={18} style={{ color: selectedTpl.accentColor }} />
          <div>
            <span className="text-[14px] font-semibold" style={{ color: "var(--ink-900)" }}>{selectedTpl.name}</span>
            <span className="ml-2 text-[12px]" style={{ color: "var(--ink-400)" }}>{selectedTpl.desc}</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-5 max-w-3xl mx-auto w-full">
          {/* Title */}
          <div>
            <label className="text-[12px] font-semibold mb-1.5 block" style={{ color: "var(--ink-600)" }}>
              页面标题
            </label>
            <input
              className="w-full rounded-xl border px-4 py-2.5 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              placeholder="例如：2026年Q1销售数据大屏"
              value={title}
              onChange={e => setTitle(e.target.value)}
              style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--ink-900)" }}
            />
          </div>

          {/* Prompt */}
          <div>
            <label className="text-[12px] font-semibold mb-1.5 block" style={{ color: "var(--ink-600)" }}>
              描述需求（AI 生成内容）
            </label>
            <textarea
              ref={textRef}
              className="w-full rounded-xl border px-4 py-3 text-[14px] resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              rows={3}
              placeholder={selectedTpl.placeholder}
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--ink-900)" }}
            />
            {/* Suggestion chips */}
            <div className="flex flex-wrap gap-2 mt-2">
              {selectedTpl.suggestedTags.map(tag => (
                <button key={tag}
                  className="px-3 py-1 rounded-full border text-[12px] transition-all hover:shadow-sm"
                  style={{ borderColor: selectedTpl.accentColor + "50", color: selectedTpl.accentColor, background: selectedTpl.accentColor + "08" }}
                  onClick={() => setPrompt(p => p ? p + "，" + tag : tag)}>
                  + {tag}
                </button>
              ))}
            </div>
          </div>

          {/* Content */}
          <div>
            <label className="text-[12px] font-semibold mb-1.5 flex items-center gap-2" style={{ color: "var(--ink-600)" }}>
              粘贴内容（可选）
              <span className="font-normal" style={{ color: "var(--ink-400)" }}>把已有的报告/数据/文字粘贴进来，AI 转换为网页</span>
            </label>
            <textarea
              className="w-full rounded-xl border px-4 py-3 text-[13px] resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              rows={8}
              placeholder="粘贴 Markdown、纯文本、数据等……"
              value={content}
              onChange={e => setContent(e.target.value)}
              style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--ink-900)", fontFamily: "monospace" }}
            />
          </div>

          {error && <div className="text-[13px] text-red-500">{error}</div>}

          {/* Database selector */}
          <div className="flex justify-end">
            <DatabaseSelector selection={dbSelection} onChange={setDbSelection} />
          </div>

          {/* Generate button */}
          <button
            className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-[14px] font-semibold text-white disabled:opacity-50 transition-all hover:opacity-90"
            style={{ background: `linear-gradient(135deg, ${selectedTpl.accentColor}, ${selectedTpl.accentColor}cc)` }}
            onClick={handleGenerate}
            disabled={loading}
          >
            {loading ? (
              <><span className="animate-spin">⏳</span> 生成中...</>
            ) : (
              <><Wand2 size={16} /> 生成 HTML 网页</>
            )}
          </button>

          {/* How it works hint */}
          <div className="rounded-xl p-4 flex gap-3"
            style={{ background: selectedTpl.accentColor + "08", border: `1px solid ${selectedTpl.accentColor}20` }}>
            <div className="text-lg">💡</div>
            <div>
              <div className="text-[12px] font-semibold mb-1" style={{ color: selectedTpl.accentColor }}>生成说明</div>
              <div className="text-[12px] leading-5" style={{ color: "var(--ink-600)" }}>
                生成的 HTML 文件完全自包含（CSS 内嵌），无需联网即可在浏览器中打开。
                可以直接分享给他人、嵌入 iframe，或上传到内网服务器。
              </div>
              <div className="flex items-center gap-1.5 mt-2 text-[11px]" style={{ color: "var(--ink-400)" }}>
                {["AI生成内容", "→", "Markdown解析", "→", "样式内嵌", "→", "单文件HTML"].map((s, i) => (
                  <span key={i} style={{ color: i % 2 === 1 ? "var(--ink-300)" : selectedTpl.accentColor }}>{s}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
