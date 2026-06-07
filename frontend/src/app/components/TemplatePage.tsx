import { ArrowUp, ChevronDown, ChevronRight, FileText, Presentation, Table2, Paperclip, Sparkles, Star, Upload, Check, X, FileImage, File, Wand2, Calculator, FileSearch, Sparkle, TrendingUp, Target } from "lucide-react";
import { TechIntroBadge } from "./TechIntroModal";
import { Textarea } from "./ui/textarea";
import { useState, useRef, useEffect } from "react";
import { ModelSelector, EffortLevel } from "./ModelSelector";
import { DatabaseSelector, DBSelection } from "./DatabaseSelector";
import { api, UploadedFileRecord } from "../lib/api";
import freeStylePreview from "../../assets/ppt-templates/free-style.png";
import azureImpactPreview from "../../assets/ppt-templates/azure-impact.png";
import graphiteFuturePreview from "../../assets/ppt-templates/graphite-future.png";
import aquaBreezePreview from "../../assets/ppt-templates/aqua-breeze.png";
import emeraldEdgePreview from "../../assets/ppt-templates/emerald-edge.png";
import siliconRhythmPreview from "../../assets/ppt-templates/silicon-rhythm.png";

type Template = { title: string; desc?: string; badge?: string; thumb: React.ReactNode };

type SheetScenario = {
  icon: React.ComponentType<any>;
  label: string;
  color: string;
  bg: string;
};

type TemplateConfig = {
  pageKey: string;
  tag: string;
  tagIcon: React.ComponentType<any>;
  accentColor: string;
  accentGradient: string;
  titleGradient?: string;
  heroTitle: string;
  heroSub: string;
  placeholder: string;
  groups?: string[];
  galleryTitle: string;
  templates: Template[];
  scenarios?: SheetScenario[];
};

/* ── PPT Thumbnails ── */
const PptThumb = ({ bg, accent, title, sub, shapes }: { bg: string; accent: string; title: string; sub?: string; shapes?: React.ReactNode }) => (
  <div className="w-full h-full flex flex-col p-3 relative overflow-hidden" style={{ background: bg }}>
    {shapes}
    <div className="mt-auto relative z-10">
      <div className="h-1.5 rounded-full mb-2 w-8" style={{ background: accent, opacity: 0.9 }} />
      <div className="text-[8.5px] font-bold leading-tight mb-1" style={{ color: accent === "#fff" ? "#fff" : "#1a1a2e", opacity: 0.95 }}>{title}</div>
      {sub && <div className="text-[7px] leading-tight" style={{ color: accent === "#fff" ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.4)" }}>{sub}</div>}
    </div>
    <div className="absolute top-3 right-3 w-8 h-8 rounded" style={{ background: accent, opacity: 0.15 }} />
    <div className="absolute top-6 right-5 w-4 h-4 rounded-full" style={{ background: accent, opacity: 0.1 }} />
  </div>
);

const PptTemplatePreview = ({ src, alt }: { src: string; alt: string }) => (
  <img
    src={src}
    alt={alt}
    className="w-full h-full object-cover"
    draggable={false}
  />
);

/* ── Doc Thumbnails ── */
const DocThumb = ({ accent, bg, tag }: { accent: string; bg: string; tag: string }) => (
  <div className="doc-thumb w-full h-full p-4 flex flex-col gap-2 relative overflow-hidden" style={{ background: bg }}>
    <div className="doc-thumb-sheen absolute inset-y-0 -left-1/2 w-1/2 pointer-events-none" />
    <div className="flex items-center gap-1.5 mb-1">
      <div className="h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
      <div className="h-1.5 rounded w-10" style={{ background: accent, opacity: 0.7 }} />
    </div>
    <div className="doc-line h-2 rounded w-3/4" style={{ background: "rgba(0,0,0,0.14)" }} />
    <div className="doc-line h-2 rounded w-full" style={{ background: "rgba(0,0,0,0.08)" }} />
    <div className="doc-line h-2 rounded w-5/6" style={{ background: "rgba(0,0,0,0.08)" }} />
    <div className="doc-line h-2 rounded w-4/5" style={{ background: "rgba(0,0,0,0.08)" }} />
    <div className="mt-1 h-10 rounded-lg flex items-center justify-center" style={{ background: `${accent}18`, border: `1px solid ${accent}30` }}>
      <div className="text-[8px] font-semibold" style={{ color: accent }}>{tag}</div>
    </div>
    <div className="doc-line h-2 rounded w-full" style={{ background: "rgba(0,0,0,0.06)" }} />
    <div className="doc-line h-2 rounded w-2/3" style={{ background: "rgba(0,0,0,0.06)" }} />
  </div>
);

/* ── Sheet Thumbnails ── */
const SheetThumb = ({ accent, bg, rows }: { accent: string; bg: string; rows: string[][] }) => (
  <div className="w-full h-full p-3 flex flex-col" style={{ background: bg }}>
    <div className="h-5 rounded-t flex items-center px-2 gap-1.5 mb-0.5" style={{ background: accent }}>
      <div className="h-1.5 w-1.5 rounded-full bg-white opacity-80" />
      <div className="h-1 rounded w-10 bg-white opacity-60" />
    </div>
    <div className="flex-1 flex flex-col border rounded-b overflow-hidden" style={{ borderColor: `${accent}30` }}>
      {rows.map((row, ri) => (
        <div key={ri} className="flex flex-1" style={{ borderBottom: ri < rows.length - 1 ? `1px solid ${accent}18` : "none", background: ri === 0 ? `${accent}12` : "transparent" }}>
          {row.map((cell, ci) => (
            <div
              key={ci}
              className="flex-1 flex items-center px-1.5"
              style={{
                borderRight: ci < row.length - 1 ? `1px solid ${accent}18` : "none",
                fontSize: "6.5px",
                fontWeight: ri === 0 ? 700 : 400,
                color: ri === 0 ? accent : "rgba(0,0,0,0.55)",
              }}
            >
              {cell}
            </div>
          ))}
        </div>
      ))}
    </div>
  </div>
);

/* ── Config ── */
export const pptConfig: TemplateConfig = {
  pageKey: "ppt",
  tag: "Agent PPT",
  tagIcon: Presentation,
  accentColor: "#f59e0b",
  accentGradient: "linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)",
  titleGradient: "linear-gradient(90deg, #f59e0b, #ef4444, #fb923c, #f59e0b)",
  heroTitle: "欢迎来到 DataAgent PowerPoint",
  heroSub: "描述主题，AI 自动生成专业演示文稿",
  placeholder: "输入你想创作的 PPT 主题，例如：2026 年 AI 行业趋势报告",
  groups: ["通用", "学术研究", "商业洞察", "宣传推广", "战略规划", "工作汇报", "教育培训"],
  galleryTitle: "精选风格模板",
  templates: [
    {
      title: "自由风格",
      desc: "由 AI 自动匹配最佳设计",
      badge: "推荐",
      thumb: <PptTemplatePreview src={freeStylePreview} alt="自由风格 PPT 模板预览" />,
    },
    {
      title: "蔚蓝冲击",
      desc: "深蓝科技感，适合发布会",
      thumb: <PptTemplatePreview src={azureImpactPreview} alt="蔚蓝冲击 PPT 模板预览" />,
    },
    {
      title: "铅灰未来",
      desc: "沉稳中性，商务首选",
      thumb: <PptTemplatePreview src={graphiteFuturePreview} alt="铅灰未来 PPT 模板预览" />,
    },
    {
      title: "清风水蓝",
      desc: "清爽明亮，医疗健康类",
      thumb: <PptTemplatePreview src={aquaBreezePreview} alt="清风水蓝 PPT 模板预览" />,
    },
    {
      title: "墨草锋线",
      desc: "自然生态，环保可持续",
      thumb: <PptTemplatePreview src={emeraldEdgePreview} alt="墨草锋线 PPT 模板预览" />,
    },
    {
      title: "矽岩律动",
      desc: "工业风，制造与工程领域",
      thumb: <PptTemplatePreview src={siliconRhythmPreview} alt="矽岩律动 PPT 模板预览" />,
    },
  ],
};

export const docsConfig: TemplateConfig = {
  pageKey: "docs",
  tag: "Agent 文档",
  tagIcon: FileText,
  accentColor: "#2563eb",
  accentGradient: "linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)",
  titleGradient: "linear-gradient(90deg, #2563eb, #7c3aed, #3b82f6, #2563eb)",
  heroTitle: "欢迎来到 DataAgent Word",
  heroSub: "从大纲到全文，AI 帮你撰写任何文档",
  placeholder: "输入 / 可快捷使用技能，或描述你想写的文档内容",
  groups: ["学术论文", "实验报告", "教学材料", "述职报告", "商业计划", "会议总结", "个人简历", "法定公文", "企业制度", "产品文档", "测试报告", "运维报告", "文学创作"],
  galleryTitle: "参考示例",
  templates: [
    {
      title: "2026年AI行业趋势分析报告",
      desc: "深度市场分析与前景展望",
      badge: "示例",
      thumb: <DocThumb accent="#2563eb" bg="linear-gradient(160deg,#eff6ff,#fff)" tag="📊 市场研究" />,
    },
    {
      title: "大数据平台技术方案书",
      desc: "企业级数据平台建设方案",
      badge: "示例",
      thumb: <DocThumb accent="#059669" bg="linear-gradient(160deg,#f0fdf4,#fff)" tag="💻 技术方案" />,
    },
  ],
};

export const sheetConfig: TemplateConfig = {
  pageKey: "sheet",
  tag: "Agent 表格",
  tagIcon: Table2,
  accentColor: "#059669",
  accentGradient: "linear-gradient(135deg, #059669 0%, #0284c7 100%)",
  titleGradient: "linear-gradient(90deg, #059669, #0284c7, #10b981, #059669)",
  heroTitle: "欢迎来到 DataAgent Excel",
  heroSub: "上传数据或描述需求，AI 帮你整理与可视化",
  placeholder: "输入 / 可快捷使用技能，或粘贴数据开始分析",
  galleryTitle: "参考示例",
  scenarios: [
    { icon: Wand2, label: "智能处理", color: "#059669", bg: "rgba(5,150,105,0.10)" },
    { icon: Calculator, label: "公式计算", color: "#2563eb", bg: "rgba(37,99,235,0.10)" },
    { icon: FileSearch, label: "信息提取", color: "#8b5cf6", bg: "rgba(139,92,246,0.10)" },
    { icon: Sparkle, label: "智能补全", color: "#f59e0b", bg: "rgba(245,158,11,0.10)" },
    { icon: TrendingUp, label: "图表洞察", color: "#ec4899", bg: "rgba(236,72,153,0.10)" },
    { icon: Target, label: "归因分析", color: "#06b6d4", bg: "rgba(6,182,212,0.10)" },
  ],
  templates: [
    {
      title: "2023-2025 年销售数据趋势分析",
      desc: "多维度销售数据与增长预测",
      badge: "热门",
      thumb: <SheetThumb accent="#2563eb" bg="linear-gradient(160deg,#eff6ff,#fff)" rows={[["季度","营收","增长","客户"],["Q1'23","¥285万","↑18%","142"],["Q2'23","¥312万","↑22%","168"],["Q3'23","¥298万","↑15%","159"]]} />,
    },
    {
      title: "团队绩效考核对比表",
      desc: "跨部门绩效数据可视化对比",
      badge: "示例",
      thumb: <SheetThumb accent="#059669" bg="linear-gradient(160deg,#f0fdf4,#fff)" rows={[["姓名","部门","绩效","评级"],["张晓明","研发","92分","A"],["李思雨","产品","88分","B+"],["王建国","运营","95分","A+"]]} />,
    },
    {
      title: "项目预算与实际支出追踪",
      desc: "财务数据实时监控与预警",
      thumb: <SheetThumb accent="#f59e0b" bg="linear-gradient(160deg,#fef9f0,#fff)" rows={[["项目","预算","实际","偏差"],["AI平台","¥50万","¥48万","-4%"],["数据中台","¥80万","¥92万","+15%"],["云服务","¥30万","¥28万","-6%"]]} />,
    },
  ],
};

interface UploadedFile { file: File; name: string; size: string; type: string; }
type TemplateParseStatus = "idle" | "uploading" | "extracting" | "analyzing" | "ready" | "saving" | "saved" | "error";

/* ── Page Component ── */
// Tech badges shown per page type
const PAGE_TECH_BADGES: Record<string, string[]> = {
  docs:  ["domain_classify", "insight_fusion"],
  ppt:   ["insight_fusion", "knowledge_graph"],
  sheet: ["domain_classify", "causal"],
};

export function TemplatePage({
  config,
  onSubmit,
  busy = false,
  onOpenTechIntro,
  onOpenDatabasePage,
}: {
  config: TemplateConfig;
  onOpenTechIntro?: (techId: string) => void;
  onOpenDatabasePage?: () => void;
  onSubmit?: (payload: {
    prompt: string;
    outputFormat: "word" | "pptx" | "xlsx";
    files?: File[];
    templateFile?: File | null;
    templateFileId?: number | null;
    template?: string | null;
    scenario?: string | null;
	    pageRange?: string | null;
	    wordCount?: string | null;
	    modelId?: string | null;
	    effort?: EffortLevel;
	    skills?: string[];
	    executionMode?: "direct" | "plan";
	    kb_ids?: number[];
	    include_system_kb?: boolean;
	  }) => void;
  busy?: boolean;
}) {
  const [val, setVal] = useState("");
  const [model, setModel] = useState("dataagent-2");
  const [effort, setEffort] = useState<EffortLevel>("low");
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [showAllTemplates, setShowAllTemplates] = useState(false);
  const [pageRange, setPageRange] = useState<string | null>(null);
  const [showPageSelector, setShowPageSelector] = useState(false);
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [dbSelection, setDbSelection] = useState<DBSelection>({ kb_ids: [], include_system: true });
  const [executionMode, setExecutionMode] = useState<"direct" | "plan">("plan");
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [templateFileId, setTemplateFileId] = useState<number | null>(null);
  const [myTemplates, setMyTemplates] = useState<UploadedFileRecord[]>([]);
  const [templateParseOpen, setTemplateParseOpen] = useState(false);
  const [templateParseStatus, setTemplateParseStatus] = useState<TemplateParseStatus>("idle");
  const [templateSkillName, setTemplateSkillName] = useState("");
  const [templateSkillContent, setTemplateSkillContent] = useState("");
  const [templateSkillSavedName, setTemplateSkillSavedName] = useState<string | null>(null);
  const [templateAnalysis, setTemplateAnalysis] = useState<Record<string, any> | null>(null);
  const [templateParseError, setTemplateParseError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const templateInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    setFiles((prev) => [...prev, ...picked.map((f) => ({ file: f, name: f.name, size: formatSize(f.size), type: f.type }))]);
    e.target.value = "";
  };

  const handleTemplateFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0] ?? null;
    setTemplateFile(picked);
    setTemplateFileId(null);
    setSelectedTemplate(picked ? `我的：${shortTemplateName(picked.name)}` : null);
    e.target.value = "";
    if (!picked || config.pageKey !== "docs") return;
    setTemplateParseOpen(true);
    setTemplateParseError("");
    setTemplateSkillSavedName(null);
    setTemplateSkillName("");
    setTemplateSkillContent("");
    setTemplateAnalysis(null);
    setTemplateParseStatus("uploading");
    const timers = [
      window.setTimeout(() => setTemplateParseStatus("extracting"), 450),
      window.setTimeout(() => setTemplateParseStatus("analyzing"), 1100),
    ];
    try {
      const result = await api.analyzePromptSkill(picked);
      setTemplateSkillName(result.name);
      setTemplateSkillContent(result.content);
      setTemplateAnalysis(result.analysis || null);
      setTemplateParseStatus("ready");
    } catch (err) {
      setTemplateParseError(err instanceof Error ? err.message : "模板解析失败");
      setTemplateParseStatus("error");
    } finally {
      timers.forEach(window.clearTimeout);
    }
  };

  const handleSaveTemplateSkill = async () => {
    if (!templateSkillName || !templateSkillContent.trim()) return;
    setTemplateParseStatus("saving");
    setTemplateParseError("");
    try {
      const saved = await api.savePromptSkill(templateSkillName, templateSkillContent);
      if (templateFile && !templateFileId) {
        const uploaded = await api.uploadFile(templateFile, undefined, true);
        setTemplateFileId(uploaded.id);
        setMyTemplates((prev) => [
          {
            id: uploaded.id,
            original_name: uploaded.original_name || templateFile.name,
            file_size: uploaded.file_size,
            is_template: true,
          },
          ...prev.filter((item) => item.id !== uploaded.id),
        ]);
      }
      setTemplateSkillSavedName(saved.name);
      setSelectedTemplate(`我的：${shortTemplateName(templateFile?.name || saved.name)}`);
      setTemplateParseStatus("saved");
    } catch (err) {
      setTemplateParseError(err instanceof Error ? err.message : "保存模板失败");
      setTemplateParseStatus("error");
    }
  };

  const handleSubmit = () => {
    if (!val.trim() || busy) return;
    const outputFormat = config.pageKey === "ppt" ? "pptx" : config.pageKey === "sheet" ? "xlsx" : "word";
    onSubmit?.({
      prompt: val.trim(),
      outputFormat,
      files: files.map((f) => f.file),
      templateFile,
      templateFileId,
      template: selectedTemplate,
      scenario: selectedScenario,
      pageRange,
      wordCount: null,
      modelId: model,
	      effort,
	      skills: templateSkillSavedName ? [templateSkillSavedName] : [],
	      executionMode: config.pageKey === "docs" ? executionMode : "direct",
	      kb_ids: dbSelection.kb_ids,
      include_system_kb: dbSelection.include_system,
	    });
    setVal("");
    setFiles([]);
    setTemplateFile(null);
    setTemplateFileId(null);
  };

  useEffect(() => {
    if (config.pageKey !== "docs") return;
    let alive = true;
    api.listFiles({ templatesOnly: true })
      .then((res) => {
        if (alive) setMyTemplates(res.files || []);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [config.pageKey]);

  return (
    <div className="min-h-full flex flex-col items-center px-6 py-8 pb-20 relative">
	      {templateParseOpen && (
	        <TemplateSkillModal
          status={templateParseStatus}
          fileName={templateFile?.name || ""}
          skillName={templateSkillName}
          content={templateSkillContent}
          analysis={templateAnalysis}
          error={templateParseError}
          savedName={templateSkillSavedName}
          onNameChange={setTemplateSkillName}
          onContentChange={setTemplateSkillContent}
          onSave={handleSaveTemplateSkill}
          onClose={() => setTemplateParseOpen(false)}
	        />
	      )}
	      {/* Subtle background */}
      <div
        className="absolute inset-x-0 top-0 h-[45vh] pointer-events-none"
        style={{
          background: `radial-gradient(ellipse 45% 35% at 50% 0%, ${config.accentColor}04 0%, transparent 70%)`,
        }}
      />

	      <div className={`w-full ${config.pageKey === "docs" ? "max-w-[820px]" : "max-w-[680px]"} flex flex-col items-center relative mt-28 flex-1`}>
        <style>{`
          @keyframes gradient-flow-${config.pageKey} {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
          }
          .animated-gradient-${config.pageKey} {
            background: ${config.titleGradient || config.accentGradient};
            background-size: 200% 100%;
            animation: gradient-flow-${config.pageKey} 3s ease infinite;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }
          @keyframes agent-page-rise-${config.pageKey} {
            from { opacity: 0; transform: translateY(18px) scale(.985); }
            to { opacity: 1; transform: translateY(0) scale(1); }
          }
          @keyframes agent-soft-float-${config.pageKey} {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
          }
          @keyframes agent-card-in-${config.pageKey} {
            from { opacity: 0; transform: translateY(14px); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes agent-sheen-${config.pageKey} {
            from { transform: translateX(-120%) skewX(-18deg); opacity: 0; }
            35% { opacity: .55; }
            to { transform: translateX(320%) skewX(-18deg); opacity: 0; }
          }
          .agent-hero-in { animation: agent-page-rise-${config.pageKey} .48s cubic-bezier(.22,1,.36,1) both; }
          .agent-input-in { animation: agent-page-rise-${config.pageKey} .52s .08s cubic-bezier(.22,1,.36,1) both; }
          .agent-gallery-in { animation: agent-page-rise-${config.pageKey} .5s .16s cubic-bezier(.22,1,.36,1) both; }
          .agent-template-card { animation: agent-card-in-${config.pageKey} .44s cubic-bezier(.22,1,.36,1) both; }
          .agent-template-card:hover .agent-thumb-motion { transform: scale(1.018); }
          .agent-thumb-motion { transition: transform .35s cubic-bezier(.22,1,.36,1); }
          .agent-template-card:hover .agent-card-sheen,
          .agent-upload-card:hover .agent-card-sheen { background: linear-gradient(90deg, transparent, rgba(255,255,255,.68), transparent); animation: agent-sheen-${config.pageKey} 1.25s ease-out; }
          .agent-send-ready { animation: agent-soft-float-${config.pageKey} 2s ease-in-out infinite; }
          ${config.pageKey === "docs" ? `
          @keyframes word-page-rise {
            from { opacity: 0; transform: translateY(18px) scale(.985); }
            to { opacity: 1; transform: translateY(0) scale(1); }
          }
          @keyframes word-soft-float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
          }
          @keyframes word-line-write {
            from { transform: scaleX(.72); opacity: .45; }
            to { transform: scaleX(1); opacity: 1; }
          }
          @keyframes word-sheen {
            from { transform: translateX(-120%) skewX(-18deg); opacity: 0; }
            35% { opacity: .55; }
            to { transform: translateX(320%) skewX(-18deg); opacity: 0; }
          }
          @keyframes word-card-in {
            from { opacity: 0; transform: translateY(14px); }
            to { opacity: 1; transform: translateY(0); }
          }
          .word-hero-in { animation: word-page-rise .48s cubic-bezier(.22,1,.36,1) both; }
          .word-input-in { animation: word-page-rise .52s .08s cubic-bezier(.22,1,.36,1) both; }
          .word-gallery-in { animation: word-page-rise .5s .16s cubic-bezier(.22,1,.36,1) both; }
          .word-template-card { animation: word-card-in .44s cubic-bezier(.22,1,.36,1) both; }
          .word-template-chip { animation: word-card-in .34s cubic-bezier(.22,1,.36,1) both; }
          .word-template-chip:hover { transform: translateY(-1px); box-shadow: var(--shadow-sm); }
          .word-template-card:hover .doc-thumb { animation: word-soft-float 2.4s ease-in-out infinite; }
          .word-template-card:hover .doc-line { transform-origin: left center; animation: word-line-write .5s ease-out both; }
          .word-template-card:hover .doc-line:nth-of-type(2) { animation-delay: .04s; }
          .word-template-card:hover .doc-line:nth-of-type(3) { animation-delay: .08s; }
          .word-template-card:hover .doc-line:nth-of-type(4) { animation-delay: .12s; }
          .word-template-card:hover .doc-thumb-sheen,
          .word-upload-card:hover .doc-upload-sheen { background: linear-gradient(90deg, transparent, rgba(255,255,255,.72), transparent); animation: word-sheen 1.35s ease-out; }
          .word-send-ready { animation: word-soft-float 2s ease-in-out infinite; }
          @media (prefers-reduced-motion: reduce) {
            .agent-hero-in, .agent-input-in, .agent-gallery-in, .agent-template-card, .agent-send-ready,
            .agent-template-card:hover .agent-card-sheen, .agent-upload-card:hover .agent-card-sheen {
              animation: none !important;
            }
            .agent-template-card:hover .agent-thumb-motion { transform: none !important; }
            .word-hero-in, .word-input-in, .word-gallery-in, .word-template-card, .word-template-chip, .word-send-ready,
            .word-template-card:hover .doc-thumb, .word-template-card:hover .doc-line,
            .word-template-card:hover .doc-thumb-sheen, .word-upload-card:hover .doc-upload-sheen {
              animation: none !important;
            }
          }
          ` : ""}
        `}</style>
        {/* Title */}
        <div className={`text-center mb-4 agent-hero-in ${config.pageKey === "docs" ? "word-hero-in" : ""}`}>
          <h1 style={{ fontSize: "28px", lineHeight: 1.4, fontWeight: 500, letterSpacing: "-0.01em", color: "var(--ink-900)" }}>
            欢迎来到 <span className={`animated-gradient-${config.pageKey}`} style={{ fontWeight: 600 }}>{config.heroTitle.replace('欢迎来到 ', '')}</span>
          </h1>
          {/* Contextual tech badges */}
          {onOpenTechIntro && (PAGE_TECH_BADGES[config.pageKey] || []).length > 0 && (
            <div className="flex items-center justify-center gap-2 mt-3 flex-wrap">
              {(PAGE_TECH_BADGES[config.pageKey] || []).map(tid => (
                <TechIntroBadge key={tid} techId={tid} onOpen={id => onOpenTechIntro(id ?? tid)} />
              ))}
            </div>
          )}
        </div>

        {/* Input */}
        <div className={`w-full relative z-40 agent-input-in ${config.pageKey === "docs" ? "word-input-in" : ""}`}>
	          <div
	            className={`transition-all ${config.pageKey === "docs" ? "rounded-[22px] px-4 pt-4 pb-3" : "rounded-[20px] p-3"}`}
	            style={{
	              background: "var(--bg-elevated)",
	              border: "1px solid var(--border)",
	              boxShadow: config.pageKey === "docs" ? "0 10px 34px rgba(15, 23, 42, 0.07), 0 1px 2px rgba(15, 23, 42, 0.05)" : "var(--shadow-sm)",
	            }}
            onFocus={(e) => {
              const rgb = (() => {
                const hex = config.accentColor.replace('#', '');
                const r = parseInt(hex.substring(0, 2), 16);
                const g = parseInt(hex.substring(2, 4), 16);
                const b = parseInt(hex.substring(4, 6), 16);
                return `${r}, ${g}, ${b}`;
              })();
              e.currentTarget.style.borderColor = `rgba(${rgb}, 0.22)`;
              e.currentTarget.style.boxShadow = `0 12px 32px -8px rgba(${rgb}, 0.22)`;
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "var(--shadow-sm)";
            }}
          >
            {/* Uploaded files */}
            {files.length > 0 && (
              <div className="flex flex-wrap gap-2 px-2 pt-1.5 pb-2">
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                    <FileIcon type={f.type} />
                    <div style={{ maxWidth: 140 }}>
                      <div className="truncate text-[12.5px]" style={{ color: "var(--ink-900)", fontWeight: 500 }}>{f.name}</div>
                      <div style={{ fontSize: "11px", color: "var(--ink-400)" }}>{f.size}</div>
                    </div>
                    <button onClick={() => setFiles((p) => p.filter((_, idx) => idx !== i))} className="h-4 w-4 flex items-center justify-center flex-shrink-0" style={{ color: "var(--ink-400)" }}>
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

	            <Textarea
	              value={val}
              onChange={(e) => setVal(e.target.value)}
              onKeyDown={(e) => {
                if (config.pageKey === "docs" && e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder={config.placeholder}
	              className={`${config.pageKey === "docs" ? "min-h-[92px] text-[15px] px-2 py-1.5" : "min-h-[80px] text-[14.5px] px-2.5 py-2"} resize-none border-0 focus-visible:ring-0 focus:ring-0 focus-visible:outline-none focus:outline-none shadow-none bg-transparent placeholder:text-[var(--ink-400)]`}
	              style={{ lineHeight: 1.5, outline: "none", boxShadow: "none" }}
	            />
		            <div className="flex items-center gap-1.5 pt-2 min-w-0 flex-nowrap" style={{ borderTop: config.pageKey === "docs" ? "1px solid rgba(15, 23, 42, 0.06)" : "none" }}>
	              <input ref={fileInputRef} type="file" multiple className="hidden" accept="*/*" onChange={handleFileChange} />
	              <button
	                onClick={() => fileInputRef.current?.click()}
	                className="h-9 w-9 inline-flex items-center justify-center rounded-full transition hover:bg-[var(--hover)] flex-shrink-0"
	                style={{ color: "var(--ink-500)" }}
	                title="添加附件"
	              >
	                <Paperclip className="h-4 w-4" />
	              </button>

	              {/* Agent Tag */}
	              {config.pageKey !== "docs" && (() => {
	                const Icon = config.tagIcon;
	                return (
	                  <div
	                    className="inline-flex items-center gap-1.5 h-7 pl-2 pr-2.5 rounded-full flex-shrink-0"
	                    style={{ background: config.accentColor + "18", border: `1px solid ${config.accentColor}30` }}
	                  >
	                    <Icon style={{ color: config.accentColor, width: 13, height: 13 }} />
	                    <span style={{ fontSize: "12.5px", fontWeight: 600, color: config.accentColor }}>{config.tag}</span>
	                  </div>
	                );
	              })()}

              {/* Selected Template/Scenario Tag or Default */}
	              <div className={`relative min-w-0 ${config.pageKey === "docs" ? "max-w-[130px] flex-shrink-0" : "max-w-[280px] flex-shrink"}`}>
                {(config.pageKey === "sheet" ? selectedScenario : selectedTemplate) ? (
                  <div
                    className="inline-flex items-center gap-1.5 min-h-7 pl-2 pr-1.5 py-0.5 rounded-full min-w-0 max-w-full"
                    style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
                    title={config.pageKey === "sheet" ? selectedScenario || "" : selectedTemplate || ""}
                  >
	                    <span className="truncate min-w-0 whitespace-nowrap" style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)" }}>
                      {config.pageKey === "sheet"
                        ? selectedScenario
                        : selectedTemplate}
                    </span>
                    <button
                      onClick={() => {
                        if (config.pageKey === "sheet") {
                          setSelectedScenario(null);
                        } else {
                          setSelectedTemplate(null);
                          setTemplateFile(null);
                          setTemplateFileId(null);
                        }
                      }}
                      className="h-4 w-4 rounded-full flex items-center justify-center transition hover:bg-black/10 flex-shrink-0"
                      style={{ color: "var(--ink-500)" }}
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowTemplateSelector(!showTemplateSelector)}
	                    className="inline-flex items-center gap-1 h-7 px-2.5 rounded-full transition hover:bg-[var(--hover)] whitespace-nowrap flex-shrink-0"
                    style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
                  >
                    <span style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)" }}>
                      {config.pageKey === "sheet" ? "类型" : config.pageKey === "docs" ? "文档模板" : "默认模板"}
                    </span>
                    <ChevronDown className="h-3 w-3" style={{ color: "var(--ink-500)" }} />
                  </button>
                )}

                {/* Template/Scenario Selector Dropdown */}
                {showTemplateSelector && !(config.pageKey === "sheet" ? selectedScenario : selectedTemplate) && (
                  <>
                    <div
                      className="fixed inset-0 z-20"
                      onClick={() => setShowTemplateSelector(false)}
                    />
                    <div
                      className="absolute top-full mt-1.5 left-0 rounded-lg overflow-hidden min-w-[180px] max-h-[360px] overflow-y-auto z-30 custom-scrollbar"
                      style={{
                        background: "#fff",
                        opacity: 1,
                        backdropFilter: "none",
                        WebkitBackdropFilter: "none",
                        border: "1px solid var(--border)",
                        boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                        backgroundClip: "padding-box",
                      }}
                    >
                      <style>{`
                        .custom-scrollbar::-webkit-scrollbar {
                          width: 6px;
                        }
                        .custom-scrollbar::-webkit-scrollbar-track {
                          background: transparent;
                        }
                        .custom-scrollbar::-webkit-scrollbar-thumb {
                          background: var(--ink-200);
                          border-radius: 3px;
                        }
                        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                          background: var(--ink-300);
                        }
                      `}</style>
                      <div className="py-1">
                        {config.pageKey === "sheet" && config.scenarios ? (
                          // Sheet scenarios
                          config.scenarios.map((s) => {
                            const Icon = s.icon;
                            return (
                              <button
                                key={s.label}
                                onClick={() => {
                                  setSelectedScenario(s.label);
                                  setShowTemplateSelector(false);
                                }}
                                className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                                style={{ fontSize: "13px", color: "var(--ink-700)" }}
                              >
                                <Icon className="h-3.5 w-3.5" style={{ color: "var(--ink-500)" }} />
                                {s.label}
                              </button>
                            );
                          })
                        ) : (
                          // PPT/Docs templates
                          <>
                            <button
                              onClick={() => {
                                templateInputRef.current?.click();
                                setShowTemplateSelector(false);
                              }}
                              className="w-full px-3 py-2 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                              style={{ fontSize: "13px", color: "var(--ink-700)" }}
                            >
                              <Upload className="h-3.5 w-3.5" style={{ color: "var(--ink-500)" }} />
                              上传自定义模板
                            </button>
                            <div className="h-px mx-2 my-1" style={{ background: "var(--border)" }} />
                            {(config.pageKey === "docs" ? (config.groups || []) : config.templates.map((t) => t.title)).map((title) => (
                              <button
                                key={title}
                                onClick={() => {
                                  setSelectedTemplate(title);
                                  setTemplateFile(null);
                                  setTemplateFileId(null);
                                  setShowTemplateSelector(false);
                                }}
                                className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)]"
                                style={{ fontSize: "13px", color: "var(--ink-700)" }}
                              >
                                {title}
                              </button>
                            ))}
                            {config.pageKey === "docs" && myTemplates.length > 0 && (
                              <>
                                <div className="h-px mx-2 my-1.5" style={{ background: "var(--border)" }} />
                                <div className="px-3 pt-1 pb-1 text-[11px]" style={{ color: "var(--ink-400)", fontWeight: 650 }}>我的</div>
                                {myTemplates.map((template) => {
                                  const label = shortTemplateName(template.original_name || template.filename || "模板");
                                  return (
                                    <button
                                      key={template.id}
                                      onClick={() => {
                                        setSelectedTemplate(`我的：${label}`);
                                        setTemplateFile(null);
                                        setTemplateFileId(template.id);
                                        setShowTemplateSelector(false);
                                      }}
                                      className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)]"
                                      style={{ fontSize: "13px", color: "var(--ink-700)" }}
                                    >
                                      {label}
                                    </button>
                                  );
                                })}
                              </>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  </>
	                )}
	              </div>

	              {config.pageKey === "docs" && (
	                <>
	                  <DatabaseSelector selection={dbSelection} onChange={setDbSelection} />

	                  <div className="inline-flex h-8 p-0.5 rounded-full flex-shrink-0" style={{ background: "rgba(15, 23, 42, 0.04)", border: "1px solid rgba(15, 23, 42, 0.08)" }}>
		                    {[
		                      { key: "plan", label: "先生成计划", icon: Sparkles },
		                      { key: "direct", label: "直接执行", icon: ArrowUp },
		                    ].map((item) => {
		                      const active = executionMode === item.key;
		                      const ModeIcon = item.icon;
		                      return (
		                        <button
		                          key={item.key}
		                          onClick={() => setExecutionMode(item.key as "direct" | "plan")}
			                          className="h-7 px-2.5 rounded-full transition-all whitespace-nowrap inline-flex items-center gap-1"
		                          style={{
		                            background: active ? "#fff" : "transparent",
		                            color: active ? config.accentColor : "var(--ink-500)",
		                            boxShadow: active ? "0 1px 5px rgba(15, 23, 42, 0.10)" : "none",
		                            fontSize: "12px",
		                            fontWeight: active ? 650 : 500,
		                          }}
		                        >
		                          <ModeIcon className="h-3 w-3" />
		                          {item.label}
		                        </button>
	                      );
	                    })}
	                  </div>

		                </>
		              )}
	
	              <input
	                ref={templateInputRef}
	                type="file"
                className="hidden"
                accept={config.pageKey === "ppt" ? ".pptx,.ppt" : config.pageKey === "docs" ? ".docx,.doc,.pdf" : "*"}
                onChange={handleTemplateFileChange}
              />

              {/* Page Range Selector (PPT) */}
              {config.pageKey === "ppt" && (
                <div className="relative">
                  <button
                    onClick={() => setShowPageSelector(!showPageSelector)}
                    className="h-7 px-2.5 inline-flex items-center gap-1 rounded-full transition hover:bg-[var(--hover)] flex-shrink-0"
                    style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--ink-700)", border: "1px solid var(--border)", background: "var(--bg-subtle)" }}
                  >
                    {pageRange || "自动页数"}
                    <ChevronDown className="h-3 w-3" />
                  </button>

                  {showPageSelector && (
                    <>
                      <div
                        className="fixed inset-0 z-20"
                        onClick={() => setShowPageSelector(false)}
                      />
                      <div
                        className="absolute top-full mt-1.5 left-0 rounded-lg overflow-hidden min-w-[120px] z-30"
                        style={{
                          background: "var(--bg-elevated)",
                          border: "1px solid var(--border)",
                          boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                        }}
                      >
                        <div className="py-1">
                          {["5-10 页", "10-15 页", "15-20 页", "20-30 页", "30-50 页"].map((range) => (
                            <button
                              key={range}
                              onClick={() => {
                                setPageRange(range);
                                setShowPageSelector(false);
                              }}
                              className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)]"
                              style={{ fontSize: "13px", color: "var(--ink-700)" }}
                            >
                              {range}
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}

	              <div className="flex-1 min-w-2" />
		              <div className="flex-shrink-0">
	                <ModelSelector selectedModel={model} onSelect={setModel} selectedEffort={effort} onSelectEffort={setEffort} align="right" />
	              </div>
	              <div className="w-px h-3.5 mx-1 flex-shrink-0" style={{ background: "var(--border)" }} />
	              <button
	                onClick={handleSubmit}
	                disabled={!val.trim() || busy}
	                className={`h-9 w-9 inline-flex items-center justify-center rounded-full transition-all active:scale-95 disabled:cursor-not-allowed flex-shrink-0 ${val.trim() && !busy ? "agent-send-ready" : ""} ${config.pageKey === "docs" && val.trim() && !busy ? "word-send-ready" : ""}`}
                style={{
                  background: val.trim() && !busy ? "var(--ink-900)" : "var(--bg-subtle)",
                  color: val.trim() && !busy ? "#fff" : "var(--ink-400)",
                  boxShadow: val.trim() && !busy ? "var(--shadow-sm)" : "none",
                }}
                title="发送"
              >
                <ArrowUp className="h-4 w-4" />
              </button>
            </div>
          </div>
          <p className="text-center text-[11px] mt-2.5" style={{ color: "var(--ink-400)" }}>
            DataAgent 可能会出错，请仔细核对
          </p>
        </div>

        {/* Sheet Scenario Chips */}
        {config.pageKey === "sheet" && config.scenarios && (
          <div className="w-full mt-8 agent-gallery-in">
            <style>{`
              @keyframes chip-pop-up {
                from {
                  opacity: 0;
                  transform: translateY(12px);
                }
                to {
                  opacity: 1;
                  transform: translateY(0);
                }
              }
              .chip-animated {
                animation: chip-pop-up 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
              }
            `}</style>
            <div className="flex flex-wrap gap-2 justify-center">
              {config.scenarios.map((scenario, index) => {
                const Icon = scenario.icon;
                const isSelected = selectedScenario === scenario.label;
                return (
                  <button
                    key={scenario.label}
                    onClick={() => setSelectedScenario(isSelected ? null : scenario.label)}
                    className="chip-animated inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all"
                    style={{
                      background: isSelected ? scenario.bg : "transparent",
                      border: isSelected ? `1px solid ${scenario.color}40` : "1px solid var(--border)",
                      color: isSelected ? scenario.color : "var(--ink-500)",
                      fontSize: "12.5px",
                      fontWeight: isSelected ? 600 : 500,
                      animationDelay: `${index * 0.08}s`,
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = "var(--bg-subtle)";
                        e.currentTarget.style.borderColor = "var(--border-strong)";
                        e.currentTarget.style.color = "var(--ink-900)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.borderColor = "var(--border)";
                        e.currentTarget.style.color = "var(--ink-500)";
                      }
                    }}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {scenario.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Document Template Types */}
        {config.pageKey === "docs" && config.groups && (
          <div className="w-full mt-7 word-gallery-in">
            <div className="flex items-center justify-between mb-3">
              <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
                文档模板
              </span>
              <button
                onClick={() => templateInputRef.current?.click()}
                className="h-7 px-2.5 inline-flex items-center gap-1.5 rounded-lg transition-all hover:bg-[var(--hover)]"
                style={{ fontSize: "12px", color: "var(--ink-600)", border: "1px solid var(--border)", background: "var(--bg-elevated)" }}
              >
                <Upload className="h-3 w-3" />
                上传自定义模板
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {config.groups.map((item, index) => {
                const selected = selectedTemplate === item;
                return (
                  <button
                    key={item}
                    onClick={() => {
                      setSelectedTemplate(selected ? null : item);
                      setTemplateFile(null);
                      setTemplateFileId(null);
                    }}
                    className="word-template-chip h-8 px-3 rounded-lg transition-all"
                    style={{
                      background: selected ? `${config.accentColor}14` : "var(--bg-elevated)",
                      border: selected ? `1px solid ${config.accentColor}42` : "1px solid var(--border)",
                      color: selected ? config.accentColor : "var(--ink-650)",
                      fontSize: "12.5px",
                      fontWeight: selected ? 650 : 500,
                      animationDelay: `${index * 28}ms`,
                    }}
                  >
                    {item}
                  </button>
                );
              })}
            </div>
            {myTemplates.length > 0 && (
              <div className="mt-5 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
                <div className="mb-2" style={{ color: "var(--ink-400)", fontSize: "12px", fontWeight: 650 }}>我的</div>
                <div className="flex flex-wrap gap-2">
                  {myTemplates.map((template, index) => {
                    const label = shortTemplateName(template.original_name || template.filename || "模板");
                    const selected = selectedTemplate === `我的：${label}` && templateFileId === template.id;
                    return (
                      <button
                        key={template.id}
                        onClick={() => {
                          setSelectedTemplate(selected ? null : `我的：${label}`);
                          setTemplateFileId(selected ? null : template.id);
                          setTemplateFile(null);
                        }}
                        className="word-template-chip h-8 px-3 rounded-lg transition-all"
                        style={{
                          background: selected ? `${config.accentColor}14` : "var(--bg-elevated)",
                          border: selected ? `1px solid ${config.accentColor}42` : "1px solid var(--border)",
                          color: selected ? config.accentColor : "var(--ink-650)",
                          fontSize: "12.5px",
                          fontWeight: selected ? 650 : 500,
                          animationDelay: `${(config.groups.length + index) * 28}ms`,
                        }}
                        title={template.original_name || template.filename || "我的模板"}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Template Gallery - PPT and Docs */}
        {(config.pageKey === "ppt" || config.pageKey === "docs") && (
          <div className={`w-full mb-14 agent-gallery-in ${config.pageKey === "docs" ? "mt-14 word-gallery-in" : "mt-auto"}`}>
            <div className="flex items-center justify-between mb-4">
              <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
                {config.galleryTitle}
              </span>
              <span style={{ fontSize: "12px", color: "var(--ink-400)" }}>
                {config.pageKey === "docs" ? config.templates.length : config.templates.length + 1} 个{config.pageKey === "docs" ? "示例" : "模板"}
              </span>
            </div>

            <div className={`grid gap-3 ${config.pageKey === "docs" ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-3"}`}>
              {/* Upload Template Card */}
              {config.pageKey !== "docs" && (
                <button
                  onClick={() => templateInputRef.current?.click()}
                  className="group text-left relative overflow-hidden rounded-xl transition-all duration-200 hover:-translate-y-0.5 agent-upload-card agent-template-card"
                  style={{
                    aspectRatio: "16/10",
                    border: selectedTemplate?.startsWith("自定义模板：") ? `2px solid ${config.accentColor}` : "2px dashed var(--border)",
                    boxShadow: "var(--shadow-sm)",
                    background: "var(--bg-elevated)",
                    animationDelay: "0ms",
                  }}
                  onMouseEnter={(e) => {
                    if (!selectedTemplate?.startsWith("自定义模板：")) {
                      e.currentTarget.style.boxShadow = "0 8px 24px -6px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.04)";
                      e.currentTarget.style.borderColor = "var(--border-strong)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!selectedTemplate?.startsWith("自定义模板：")) {
                      e.currentTarget.style.boxShadow = "var(--shadow-sm)";
                      e.currentTarget.style.borderColor = "var(--border)";
                    }
                  }}
                >
                  <div className="agent-card-sheen absolute inset-y-0 -left-1/2 w-1/2 pointer-events-none" />
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                    <Upload className="h-8 w-8" style={{ color: "var(--ink-400)" }} />
                    <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-700)" }}>上传模板</div>
                    <div style={{ fontSize: "10px", color: "var(--ink-400)" }}>自定义 PPT 模板</div>
                    <div style={{ fontSize: "9px", color: "var(--ink-300)", marginTop: -4 }}>支持 .pptx, .ppt</div>
                  </div>

                  {selectedTemplate?.startsWith("自定义模板：") && (
                    <div
                      className="absolute top-2 right-2 h-6 w-6 rounded-full flex items-center justify-center z-10"
                      style={{ background: config.accentColor }}
                    >
                      <Check className="h-4 w-4" style={{ color: "#fff", strokeWidth: 3 }} />
                    </div>
                  )}
                </button>
              )}

              {/* Template Cards */}
              {(showAllTemplates ? config.templates : config.templates.slice(0, config.pageKey === "docs" ? 2 : 5)).map((t, index) => (
                <button
                  key={t.title}
                  onClick={() => {
                    if (config.pageKey !== "docs") setSelectedTemplate(t.title);
                  }}
                  className={`group text-left relative overflow-hidden rounded-xl transition-all duration-200 hover:-translate-y-0.5 agent-template-card ${config.pageKey === "docs" ? "word-template-card" : ""}`}
                  style={{
                    aspectRatio: config.pageKey === "docs" ? "3/4" : "16/10",
                    border: selectedTemplate === t.title ? `2px solid ${config.accentColor}` : "1px solid var(--border)",
                    boxShadow: "var(--shadow-sm)",
                    animationDelay: config.pageKey === "docs" ? `${(index + 1) * 70}ms` : `${(index + 1) * 60}ms`,
                  }}
                  onMouseEnter={(e) => {
                    if (selectedTemplate !== t.title) {
                      e.currentTarget.style.boxShadow = "0 8px 24px -6px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.04)";
                      e.currentTarget.style.borderColor = "var(--border-strong)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedTemplate !== t.title) {
                      e.currentTarget.style.boxShadow = "var(--shadow-sm)";
                      e.currentTarget.style.borderColor = "var(--border)";
                    }
                  }}
                >
                  {/* Thumbnail */}
                  <div className="absolute inset-0 agent-thumb-motion">
                    {config.pageKey === "ppt" && <div className="agent-card-sheen absolute inset-y-0 -left-1/2 w-1/2 pointer-events-none z-10" />}
                    {t.thumb}
                  </div>

                  {/* Badge */}
                  {t.badge && (
                    <div
                      className="absolute top-2 left-2 px-2 py-0.5 rounded-md text-[10px] font-semibold z-10"
                      style={{ background: "rgba(245,158,11,0.95)", color: "#fff" }}
                    >
                      {t.badge}
                    </div>
                  )}

                  {/* Selected indicator */}
                  {selectedTemplate === t.title && (
                    <div
                      className="absolute top-2 right-2 h-6 w-6 rounded-full flex items-center justify-center z-10"
                      style={{ background: config.accentColor }}
                    >
                      <Check className="h-4 w-4" style={{ color: "#fff", strokeWidth: 3 }} />
                    </div>
                  )}

                  {/* Hover overlay with title */}
                  <div
                    className="absolute inset-x-0 bottom-0 p-2.5 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                    style={{
                      background: "linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.4) 70%, transparent 100%)",
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "12px", color: "#fff", lineHeight: 1.3 }}>{t.title}</div>
                    {t.desc && <div className="mt-0.5" style={{ fontSize: "10.5px", color: "rgba(255,255,255,0.8)", lineHeight: 1.3 }}>{t.desc}</div>}
                  </div>
                </button>
              ))}
            </div>

            {/* Show More/Less Button */}
            {((config.pageKey === "ppt" && config.templates.length > 5) ||
              (config.pageKey === "docs" && config.templates.length > 2)) && (
              <div className="flex justify-center mt-4">
                <button
                  onClick={() => setShowAllTemplates(!showAllTemplates)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg transition-all hover:bg-[var(--hover)]"
                  style={{ fontSize: "13px", fontWeight: 500, color: "var(--ink-700)" }}
                >
                  {showAllTemplates ? "收起" : `查看更多 (${config.templates.length - (config.pageKey === "docs" ? 2 : 5)})`}
                  <ChevronDown
                    className="h-3.5 w-3.5 transition-transform"
                    style={{ transform: showAllTemplates ? "rotate(180deg)" : "rotate(0deg)" }}
                  />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Template Gallery - Sheet */}
        {config.pageKey === "sheet" && config.templates.length > 0 && (
          <div className="w-full mt-auto mb-14 agent-gallery-in">
            <div className="flex items-center justify-between mb-4">
              <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
                {config.galleryTitle}
              </span>
              <span style={{ fontSize: "12px", color: "var(--ink-400)" }}>
                {config.templates.length} 个示例
              </span>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {config.templates.map((t, index) => (
                <button
                  key={t.title}
                  onClick={() => setSelectedTemplate(t.title)}
                  className="group text-left relative overflow-hidden rounded-xl transition-all duration-200 hover:-translate-y-0.5 agent-template-card"
                  style={{
                    aspectRatio: "5/3",
                    border: selectedTemplate === t.title ? `2px solid ${config.accentColor}` : "1px solid var(--border)",
                    boxShadow: "var(--shadow-sm)",
                    animationDelay: `${index * 70}ms`,
                  }}
                  onMouseEnter={(e) => {
                    if (selectedTemplate !== t.title) {
                      e.currentTarget.style.boxShadow = "0 8px 24px -6px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.04)";
                      e.currentTarget.style.borderColor = "var(--border-strong)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedTemplate !== t.title) {
                      e.currentTarget.style.boxShadow = "var(--shadow-sm)";
                      e.currentTarget.style.borderColor = "var(--border)";
                    }
                  }}
                >
                  {/* Thumbnail */}
                  <div className="absolute inset-0 agent-thumb-motion">
                    <div className="agent-card-sheen absolute inset-y-0 -left-1/2 w-1/2 pointer-events-none z-10" />
                    {t.thumb}
                  </div>

                  {/* Badge */}
                  {t.badge && (
                    <div
                      className="absolute top-2 left-2 px-2 py-0.5 rounded-md text-[10px] font-semibold z-10"
                      style={{ background: "rgba(245,158,11,0.95)", color: "#fff" }}
                    >
                      {t.badge}
                    </div>
                  )}

                  {/* Selected indicator */}
                  {selectedTemplate === t.title && (
                    <div
                      className="absolute top-2 right-2 h-6 w-6 rounded-full flex items-center justify-center z-10"
                      style={{ background: config.accentColor }}
                    >
                      <Check className="h-4 w-4" style={{ color: "#fff", strokeWidth: 3 }} />
                    </div>
                  )}

                  {/* Hover overlay with title */}
                  <div
                    className="absolute inset-x-0 bottom-0 p-2.5 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                    style={{
                      background: "linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.4) 70%, transparent 100%)",
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "12px", color: "#fff", lineHeight: 1.3 }}>{t.title}</div>
                    {t.desc && <div className="mt-0.5" style={{ fontSize: "10.5px", color: "rgba(255,255,255,0.8)", lineHeight: 1.3 }}>{t.desc}</div>}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="w-full text-center mt-auto pt-6 pb-6" style={{ color: "var(--ink-400)", fontSize: "11px" }}>
          2026 大数据应用部 | Brdc.AI人工智能小组
        </div>
      </div>
    </div>
  );
}

function FileIcon({ type }: { type: string }) {
  if (type.startsWith("image/")) return <FileImage className="h-4 w-4 flex-shrink-0" style={{ color: "#2563eb" }} />;
  return <File className="h-4 w-4 flex-shrink-0" style={{ color: "var(--ink-400)" }} />;
}


// ── Style meta map ──────────────────────────────────────────────────────────
const DOC_STYLE_META: Record<string, { label: string; color: string; bg: string; border: string }> = {
  "academic-paper":     { label: "学术论文",      color: "#7c3aed", bg: "rgba(124,58,237,0.09)",  border: "rgba(124,58,237,0.22)" },
  "research-report":    { label: "研究分析报告",   color: "#2563eb", bg: "rgba(37,99,235,0.09)",   border: "rgba(37,99,235,0.22)"  },
  "official-document":  { label: "政务 / 公文",   color: "#b91c1c", bg: "rgba(185,28,28,0.08)",   border: "rgba(185,28,28,0.2)"   },
  "contract-document":  { label: "合同 / 协议",   color: "#b45309", bg: "rgba(180,83,9,0.09)",    border: "rgba(180,83,9,0.22)"   },
  "prd-document":       { label: "产品需求文档",   color: "#0891b2", bg: "rgba(8,145,178,0.09)",   border: "rgba(8,145,178,0.22)"  },
  "training-manual":    { label: "培训 / 操作手册", color: "#059669", bg: "rgba(5,150,105,0.09)",  border: "rgba(5,150,105,0.22)"  },
  "performance-review": { label: "绩效 / 述职报告", color: "#d97706", bg: "rgba(217,119,6,0.09)",  border: "rgba(217,119,6,0.22)"  },
  "custom-document":    { label: "自定义文档",     color: "#6b7280", bg: "rgba(107,114,128,0.09)", border: "rgba(107,114,128,0.2)" },
};

// Tiny section label
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--ink-400)", marginBottom: 7 }}>
      {children}
    </div>
  );
}

function TemplateSkillModal({
  status,
  fileName,
  skillName,
  content,
  analysis,
  error,
  savedName,
  onNameChange,
  onContentChange,
  onSave,
  onClose,
}: {
  status: TemplateParseStatus;
  fileName: string;
  skillName: string;
  content: string;
  analysis: Record<string, any> | null;
  error: string;
  savedName: string | null;
  onNameChange: (value: string) => void;
  onContentChange: (value: string) => void;
  onSave: () => void;
  onClose: () => void;
}) {
  const [rightTab, setRightTab] = useState<"analysis" | "editor">("analysis");

  const steps = [
    { key: "uploading",  label: "读取文件" },
    { key: "extracting", label: "抽取结构" },
    { key: "analyzing",  label: "深度解析" },
    { key: "ready",      label: savedName ? "已保存" : "等待确认" },
  ];
  const activeIndex = Math.max(0, steps.findIndex(
    (s) => s.key === (status === "saving" || status === "saved" ? "ready" : status)
  ));
  const isWorking = ["uploading", "extracting", "analyzing", "saving"].includes(status);

  const styleMeta = DOC_STYLE_META[analysis?.detected_style ?? ""] ?? DOC_STYLE_META["custom-document"];
  const audience   = analysis?.audience_intent     as Record<string, any> | undefined;
  const narrative  = analysis?.narrative_framework as Record<string, any> | undefined;
  const argPattern = analysis?.argumentation_pattern as Record<string, any> | undefined;
  const register   = analysis?.writing_register    as Record<string, any> | undefined;
  const skeleton   = (analysis?.macro_structure?.section_skeleton ?? []) as string[];

  // Switch to editor tab automatically once content arrives
  useEffect(() => {
    if (content && rightTab === "analysis" && !analysis) setRightTab("editor");
  }, [content]);

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center px-4"
      style={{ background: "rgba(17,24,39,0.38)", backdropFilter: "blur(7px)", WebkitBackdropFilter: "blur(7px)" }}>
      <div className="w-full max-w-6xl max-h-[92vh] rounded-2xl overflow-hidden flex flex-col"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "0 28px 90px rgba(0,0,0,0.26)" }}>

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl flex items-center justify-center"
              style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
              <FileSearch className="h-4 w-4" />
            </div>
            <div>
              <div style={{ color: "var(--ink-900)", fontWeight: 700, fontSize: 15 }}>解析自定义文档模板</div>
              <div style={{ color: "var(--ink-400)", fontSize: 11.5, marginTop: 1 }}>{fileName || "待选择模板文件"}</div>
            </div>
          </div>
          <button onClick={onClose}
            className="h-8 w-8 rounded-lg flex items-center justify-center transition hover:bg-[var(--hover)]"
            style={{ color: "var(--ink-500)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="grid grid-cols-[256px_1fr] min-h-0 flex-1 overflow-hidden">

          {/* Left sidebar: steps + dimension cards */}
          <div className="p-4 border-r overflow-y-auto"
            style={{ borderColor: "var(--border)", background: "var(--bg-subtle)" }}>

            {/* Progress steps */}
            <div className="space-y-2 mb-5">
              {steps.map((step, idx) => {
                const done   = status === "saved" || idx < activeIndex || (status === "ready" && idx <= activeIndex);
                const active = idx === activeIndex && status !== "saved";
                return (
                  <div key={step.key} className="flex items-center gap-2.5">
                    <div className="h-6 w-6 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{
                        background: done ? "#10b981" : active ? "var(--brand)" : "var(--bg-elevated)",
                        color: done || active ? "#fff" : "var(--ink-400)",
                        border: "1.5px solid " + (done ? "#10b981" : active ? "var(--brand)" : "var(--border)"),
                        fontSize: 10, fontWeight: 700,
                      }}>
                      {done ? <Check className="h-3 w-3" /> : idx + 1}
                    </div>
                    <div style={{
                      fontSize: 12.5,
                      fontWeight: active ? 700 : 500,
                      color: active ? "var(--ink-900)" : done ? "var(--ink-600)" : "var(--ink-400)",
                    }}>
                      {step.label}
                      {active && isWorking && (
                        <span style={{ marginLeft: 6, display: "inline-block", width: 12, animation: "spin 1s linear infinite" }}>⋯</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ height: 1, background: "var(--border)", marginBottom: 16 }} />

            {/* ── Document Genre Badge ── */}
            {analysis ? (
              <>
                <div className="mb-4">
                  <SectionLabel>文档类型</SectionLabel>
                  <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full"
                    style={{ background: styleMeta.bg, border: `1px solid ${styleMeta.border}`, color: styleMeta.color, fontSize: 12.5, fontWeight: 700 }}>
                    <FileText className="h-3 w-3" />
                    {styleMeta.label}
                  </div>
                  {(analysis.heading_count || analysis.table_like_rows) ? (
                    <div className="mt-2 flex gap-2 flex-wrap">
                      {analysis.heading_count > 0 && (
                        <span className="px-2 py-0.5 rounded-full" style={{ fontSize: 10.5, background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--ink-500)" }}>
                          {analysis.heading_count} 个标题
                        </span>
                      )}
                      {analysis.table_like_rows > 0 && (
                        <span className="px-2 py-0.5 rounded-full" style={{ fontSize: 10.5, background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--ink-500)" }}>
                          {analysis.table_like_rows} 行表格
                        </span>
                      )}
                      {analysis.citation_markers > 0 && (
                        <span className="px-2 py-0.5 rounded-full" style={{ fontSize: 10.5, background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--ink-500)" }}>
                          {analysis.citation_markers} 处引用
                        </span>
                      )}
                    </div>
                  ) : null}
                </div>

                {/* ── Target Audience ── */}
                {audience && (
                  <div className="mb-4 p-3 rounded-xl"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                    <SectionLabel>🎯 目标受众</SectionLabel>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 4 }}>
                      {audience.target_reader}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--ink-500)", lineHeight: 1.55, marginBottom: 7 }}>
                      {audience.intent}
                    </div>
                    {Array.isArray(audience.core_concerns) && audience.core_concerns.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {(audience.core_concerns as string[]).map((c) => (
                          <span key={c} className="px-2 py-0.5 rounded-full"
                            style={{ fontSize: 10, background: "var(--brand-soft)", color: "var(--brand)", fontWeight: 600 }}>
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* ── Argumentation Pattern ── */}
                {argPattern && (
                  <div className="mb-4 p-3 rounded-xl"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                    <SectionLabel>🧩 论证模式</SectionLabel>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)", marginBottom: 4 }}>
                      {argPattern.pattern}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--ink-500)", lineHeight: 1.55 }}>
                      {argPattern.description}
                    </div>
                  </div>
                )}

                {/* ── Writing Register ── */}
                {register && (
                  <div className="mb-4">
                    <SectionLabel>✍️ 写作语体</SectionLabel>
                    <div className="space-y-1">
                      {[register.formality, register.tone, register.perspective, register.sentence_density]
                        .filter(Boolean)
                        .map((v, i) => (
                          <div key={i} className="flex items-start gap-1.5">
                            <div className="h-1.5 w-1.5 rounded-full flex-shrink-0 mt-1.5"
                              style={{ background: "var(--brand)" }} />
                            <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.5 }}>{v}</div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* ── Section Skeleton ── */}
                {skeleton.length > 0 && (
                  <div className="mb-4">
                    <SectionLabel>📋 章节架构</SectionLabel>
                    <div className="space-y-1.5">
                      {skeleton.slice(0, 8).map((s, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <div className="h-4 w-4 rounded flex-shrink-0 flex items-center justify-center mt-0.5"
                            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", fontSize: 9, color: "var(--ink-400)", fontWeight: 700 }}>
                            {i + 1}
                          </div>
                          <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.45 }}>{s}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              /* Loading skeleton */
              <div className="space-y-3">
                {[80, 60, 90, 70].map((w, i) => (
                  <div key={i} className="h-3 rounded" style={{ width: `${w}%`, background: "var(--border)", opacity: 0.6 }} />
                ))}
              </div>
            )}

            {savedName && (
              <div className="mt-3 rounded-xl p-3"
                style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.24)", color: "#047857", fontSize: 11.5 }}>
                ✓ 已保存为：{savedName}
              </div>
            )}
            {error && (
              <div className="mt-3 rounded-xl p-3"
                style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.24)", color: "#dc2626", fontSize: 11.5 }}>
                {error}
              </div>
            )}
          </div>

          {/* Right panel */}
          <div className="flex flex-col min-h-0 overflow-hidden">
            {isWorking && !content ? (
              /* Loading state */
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                <div className="h-12 w-12 rounded-2xl flex items-center justify-center mb-5"
                  style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                  <Wand2 className="h-6 w-6 animate-pulse" />
                </div>
                <div style={{ color: "var(--ink-900)", fontWeight: 700, fontSize: 15 }}>正在深度解析文档结构</div>
                <div style={{ color: "var(--ink-400)", fontSize: 13, marginTop: 8, maxWidth: 380, lineHeight: 1.6 }}>
                  识别目标受众、叙事脉络、论证模式、写作语体和可复用章节架构…
                </div>
                <div className="mt-6 flex items-center gap-2" style={{ color: "var(--ink-300)", fontSize: 12 }}>
                  <div className="flex gap-1">
                    {[0, 150, 300].map((d) => (
                      <div key={d} className="h-1.5 w-1.5 rounded-full"
                        style={{ background: "var(--brand)", opacity: 0.5, animation: `pulse 1.2s ease-in-out ${d}ms infinite` }} />
                    ))}
                  </div>
                  分析中
                </div>
              </div>
            ) : (
              <>
                {/* Tab bar (only shown when content is ready) */}
                {content && (
                  <div className="flex items-center border-b px-5 pt-4 pb-0 gap-1"
                    style={{ borderColor: "var(--border)" }}>
                    {(["analysis", "editor"] as const).map((tab) => (
                      <button key={tab}
                        onClick={() => setRightTab(tab)}
                        className="px-4 py-2 rounded-t-lg text-sm font-semibold transition"
                        style={{
                          fontSize: 13,
                          fontWeight: rightTab === tab ? 700 : 500,
                          color: rightTab === tab ? "var(--brand)" : "var(--ink-500)",
                          borderBottom: rightTab === tab ? "2px solid var(--brand)" : "2px solid transparent",
                          background: "transparent",
                        }}>
                        {tab === "analysis" ? "📐 结构解析" : "✏️ Skill 编辑"}
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex-1 overflow-y-auto p-5">
                  {/* ── Analysis tab ── */}
                  {(rightTab === "analysis" || !content) && analysis && (
                    <div className="space-y-5">
                      {/* Narrative flow */}
                      {narrative?.arc && Array.isArray(narrative.arc) && (
                        <div>
                          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--ink-900)", marginBottom: 4 }}>
                            📖 叙事脉络
                          </div>
                          <div style={{ fontSize: 12, color: "var(--ink-500)", marginBottom: 12, lineHeight: 1.5 }}>
                            {narrative.name}
                          </div>
                          {/* Flow steps */}
                          <div className="flex flex-col gap-0">
                            {(narrative.arc as string[]).map((step, i, arr) => (
                              <div key={i} className="flex items-start gap-3">
                                <div className="flex flex-col items-center">
                                  <div className="h-7 w-7 rounded-full flex items-center justify-center flex-shrink-0 font-bold"
                                    style={{
                                      background: `hsl(${220 + i * 20}, 70%, ${55 + i * 3}%)`,
                                      color: "#fff", fontSize: 11,
                                    }}>
                                    {i + 1}
                                  </div>
                                  {i < arr.length - 1 && (
                                    <div style={{ width: 2, flexGrow: 1, minHeight: 16, background: "var(--border)", margin: "2px 0" }} />
                                  )}
                                </div>
                                <div className="pb-3" style={{ fontSize: 13, color: "var(--ink-700)", lineHeight: 1.55, paddingTop: 4 }}>
                                  {step}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Argumentation logic thread */}
                      {argPattern?.logic_thread && Array.isArray(argPattern.logic_thread) && (
                        <div className="p-4 rounded-xl"
                          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--ink-900)", marginBottom: 8 }}>
                            🧩 {argPattern.pattern} — 逻辑线索
                          </div>
                          <div className="flex flex-wrap gap-2 items-center">
                            {(argPattern.logic_thread as string[]).map((node, i, arr) => (
                              <div key={i} className="flex items-center gap-2">
                                <div className="px-3 py-1.5 rounded-lg"
                                  style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-800)", background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                                  {node}
                                </div>
                                {i < arr.length - 1 && (
                                  <span style={{ color: "var(--ink-300)", fontSize: 14 }}>→</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Two-col: audience + register */}
                      <div className="grid grid-cols-2 gap-4">
                        {audience && (
                          <div className="p-4 rounded-xl"
                            style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                            <div style={{ fontWeight: 700, fontSize: 13, color: "var(--ink-900)", marginBottom: 6 }}>🎯 读者画像</div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: styleMeta.color, marginBottom: 4 }}>{audience.target_reader}</div>
                            <div style={{ fontSize: 11.5, color: "var(--ink-500)", lineHeight: 1.55, marginBottom: 8 }}>{audience.intent}</div>
                            {Array.isArray(audience.core_concerns) && (
                              <div className="flex flex-wrap gap-1">
                                {(audience.core_concerns as string[]).map((c) => (
                                  <span key={c} className="px-2 py-0.5 rounded-full"
                                    style={{ fontSize: 10.5, background: "var(--brand-soft)", color: "var(--brand)", fontWeight: 600 }}>
                                    {c}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                        {register && (
                          <div className="p-4 rounded-xl"
                            style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                            <div style={{ fontWeight: 700, fontSize: 13, color: "var(--ink-900)", marginBottom: 8 }}>✍️ 写作语体</div>
                            <div className="space-y-2.5">
                              {[
                                { label: "语体风格", value: register.formality },
                                { label: "语气基调", value: register.tone },
                                { label: "叙述视角", value: register.perspective },
                                { label: "句式密度", value: register.sentence_density },
                              ].map(({ label, value }) => value ? (
                                <div key={label}>
                                  <div style={{ fontSize: 10, color: "var(--ink-400)", fontWeight: 700, marginBottom: 1 }}>{label}</div>
                                  <div style={{ fontSize: 12, color: "var(--ink-700)" }}>{value}</div>
                                </div>
                              ) : null)}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Section skeleton full view */}
                      {skeleton.length > 0 && (
                        <div className="p-4 rounded-xl"
                          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                          <div style={{ fontWeight: 700, fontSize: 13, color: "var(--ink-900)", marginBottom: 10 }}>📋 抽象章节架构</div>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                            {skeleton.map((s, i) => (
                              <div key={i} className="flex items-center gap-2">
                                <div className="h-5 w-5 rounded flex-shrink-0 flex items-center justify-center"
                                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", fontSize: 9, color: "var(--ink-500)", fontWeight: 700 }}>
                                  {i + 1}
                                </div>
                                <div style={{ fontSize: 12, color: "var(--ink-700)" }}>{s}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Editor tab ── */}
                  {(rightTab === "editor" || !analysis) && (
                    <div className="space-y-4">
                      <div>
                        <label style={{ color: "var(--ink-500)", fontSize: 12, fontWeight: 700 }}>模板 Skill 名称</label>
                        <input
                          value={skillName}
                          onChange={(e) => onNameChange(e.target.value)}
                          className="mt-1.5 w-full h-10 px-3 rounded-lg outline-none"
                          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)", fontSize: 13 }}
                        />
                      </div>
                      <div>
                        <label style={{ color: "var(--ink-500)", fontSize: 12, fontWeight: 700 }}>解析结果（可手动修改后保存）</label>
                        <textarea
                          value={content}
                          onChange={(e) => onContentChange(e.target.value)}
                          className="mt-1.5 w-full min-h-[400px] p-3 rounded-lg outline-none resize-y"
                          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)", fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", fontSize: 12, lineHeight: 1.6 }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-between px-6 py-4 border-t" style={{ borderColor: "var(--border)" }}>
          <div style={{ color: "var(--ink-400)", fontSize: 12 }}>
            保存后，本次 Agent 文档生成会自动启用这个用户模板 Skill。
          </div>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="h-9 px-4 rounded-lg transition hover:bg-[var(--hover)]"
              style={{ color: "var(--ink-600)", border: "1px solid var(--border)", fontSize: 13 }}>
              关闭
            </button>
            <button
              onClick={() => { setRightTab("editor"); onSave(); }}
              disabled={!content.trim() || !skillName.trim() || isWorking}
              className="h-9 px-4 rounded-lg disabled:opacity-50 flex items-center gap-1.5 font-semibold"
              style={{ background: "var(--ink-900)", color: "#fff", fontSize: 13 }}>
              <Check className="h-3.5 w-3.5" />
              {status === "saving" ? "保存中…" : savedName ? "重新保存" : "保存模板 Skill"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function shortTemplateName(name: string): string {
  const base = (name || "模板")
    .replace(/\.[^.]+$/, "")
    .replace(/^自定义模板[:：]/, "")
    .replace(/[^\p{L}\p{N}\u4e00-\u9fa5]+/gu, "");
  return Array.from(base || "模板").slice(0, 4).join("");
}
