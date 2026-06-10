import { ArrowUp, ChevronDown, ChevronRight, FileText, Presentation, Table2, Paperclip, Sparkles, Star, Upload, Check, X, FileImage, File, Wand2, Calculator, FileSearch, Sparkle, TrendingUp, Target, FolderOpen, Plus, Search, Pencil, Trash2, BookOpen, FlaskConical, Briefcase, Users, User, Scale, Building2, Package, Bug, Server, PenTool } from "lucide-react";
import { TechIntroBadge } from "./TechIntroModal";
import { Textarea } from "./ui/textarea";
import { useState, useRef, useEffect, useMemo } from "react";
import { ModelSelector, EffortLevel } from "./ModelSelector";
import { DBSelection } from "./DatabaseSelector";
import { api, UploadedFileRecord, Project, PromptSkillSummary } from "../lib/api";
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
    <div className="doc-header flex items-center gap-1.5 mb-1">
      <div className="doc-dot h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
      <div className="doc-header-line h-1.5 rounded w-10" style={{ background: accent, opacity: 0.7 }} />
    </div>
    <div className="doc-line h-2 rounded w-3/4" style={{ background: "rgba(0,0,0,0.14)" }} />
    <div className="doc-line h-2 rounded w-full" style={{ background: "rgba(0,0,0,0.08)" }} />
    <div className="doc-line h-2 rounded w-5/6" style={{ background: "rgba(0,0,0,0.08)" }} />
    <div className="doc-line h-2 rounded w-4/5" style={{ background: "rgba(0,0,0,0.08)" }} />
    <div className="doc-tag mt-1 h-10 rounded-lg flex items-center justify-center" style={{ background: `${accent}18`, border: `1px solid ${accent}30` }}>
      <div className="doc-tag-text text-[8px] font-semibold" style={{ color: accent }}>{tag}</div>
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
  heroSub: "选择文档模板，描述需求，生成可直接交付的 Word 文档",
  placeholder: "描述你想写的文档内容，例如：写一份2026年AI行业市场分析报告",
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

// ── Docs Guided Wizard constants ─────────────────────────────────────────────
const WIZARD_TYPE_TO_TEMPLATE: Record<string, string> = {
  "学术论文": "学术论文", "工作汇报": "述职报告", "商业方案": "商业计划",
  "技术文档": "产品文档", "分析报告": "运维报告", "个人简历": "个人简历",
  "公文通知": "法定公文", "会议纪要": "会议总结",
};

const HOT_SCENE_TEMPLATE_LABELS: Record<string, string> = {
  "分析报告": "运维报告",
  "工作汇报": "述职报告",
  "商业方案": "商业计划",
  "技术文档": "产品文档",
  "学术论文": "学术论文",
  "个人简历": "个人简历",
  "公文通知": "法定公文",
  "会议纪要": "会议总结",
};

const WIZARD_TYPE_QUESTIONS: Record<string, Array<{ key: string; q: string; placeholder: string }>> = {
  "学术论文": [
    { key: "topic",    q: "研究的核心问题或假设是什么？",     placeholder: "例如：探究 AI 辅助诊断对医疗效率的量化影响" },
    { key: "method",   q: "主要研究方法和数据来源？",         placeholder: "例如：问卷调研 + 统计分析，数据来自 PubMed" },
    { key: "audience", q: "目标期刊或会议是哪个领域？",       placeholder: "例如：CCF-A 类 NLP 顶会" },
  ],
  "工作汇报": [
    { key: "period",   q: "汇报周期和主要工作内容？",         placeholder: "例如：Q2，主导了三个核心项目的交付" },
    { key: "kpi",      q: "关键成果和量化指标？",             placeholder: "例如：用户增长 30%，成本降低 15%" },
    { key: "plan",     q: "下阶段重点计划是什么？",           placeholder: "例如：推进产品国际化，拓展海外市场" },
  ],
  "商业方案": [
    { key: "problem",  q: "解决什么市场痛点或问题？",         placeholder: "例如：中小企业缺乏低成本的智能客服方案" },
    { key: "model",    q: "商业模式和盈利方式？",             placeholder: "例如：SaaS 订阅 + 按量计费" },
    { key: "target",   q: "目标客群和市场规模？",             placeholder: "例如：100-500 人规模的科技企业，TAM 约 300 亿" },
  ],
  "技术文档": [
    { key: "scope",    q: "文档描述的系统或模块范围？",       placeholder: "例如：用户认证与权限管理模块 REST API" },
    { key: "reader",   q: "目标读者的技术水平？",             placeholder: "例如：有 2 年以上后端开发经验的工程师" },
    { key: "format",   q: "需要包含哪些关键章节？",           placeholder: "例如：接口说明、参数列表、错误码、调用示例" },
  ],
  "分析报告": [
    { key: "question", q: "核心分析问题或研究命题？",         placeholder: "例如：2026 年国内 AI 大模型市场竞争格局演变" },
    { key: "data",     q: "主要数据来源和分析维度？",         placeholder: "例如：公开财报、IDC 报告、用户调研" },
    { key: "output",   q: "报告的核心结论或建议？",           placeholder: "例如：提出三条差异化竞争策略" },
  ],
  "个人简历": [
    { key: "role",     q: "目标岗位和行业方向？",             placeholder: "例如：AI 产品经理 / 互联网大厂" },
    { key: "exp",      q: "最核心的工作经历和亮点项目？",     placeholder: "例如：主导某 App 从 0 到 1，DAU 达 50 万" },
    { key: "skill",    q: "关键技能和工具掌握情况？",         placeholder: "例如：Python、SQL、Axure、用户增长方法论" },
  ],
  "公文通知": [
    { key: "subject",  q: "通知的主题事项？",                 placeholder: "例如：2026 年度绩效考核工作安排" },
    { key: "scope",    q: "涉及范围和执行时间？",             placeholder: "例如：全体员工，2026 年 12 月 1-15 日" },
    { key: "action",   q: "需要各部门配合的具体事项？",       placeholder: "例如：提交自评表、配合 360 访谈" },
  ],
  "会议纪要": [
    { key: "topic",    q: "会议主题和主要议题？",             placeholder: "例如：Q4 产品路线图评审暨资源分配会" },
    { key: "decision", q: "主要决议和结论？",                 placeholder: "例如：确定 H5 端优先级最高，预算追加 50 万" },
    { key: "action",   q: "后续行动项和责任人？",             placeholder: "例如：产品部 11 月底提交需求文档" },
  ],
};

const WIZARD_GENERIC_QUESTIONS = [
  { key: "purpose",    q: "这份文档的主要用途是什么？",       placeholder: "例如：对外发布 / 内部存档 / 汇报领导" },
  { key: "key_point",  q: "最重要的核心内容或论点是什么？",   placeholder: "例如：…" },
  { key: "reader",     q: "目标读者是谁？有什么阅读背景？",   placeholder: "例如：技术背景的研发人员 / 非专业的管理层" },
];

const WIZARD_PHASES = [
  { key: "type",      label: "文档类型" },
  { key: "config",    label: "资源配置" },
  { key: "describe",  label: "需求描述" },
  { key: "questions", label: "细化确认" },
  { key: "summary",   label: "任务清单" },
] as const;

type WizardPhase = typeof WIZARD_PHASES[number]["key"];

export function TemplatePage({
  config,
  onSubmit,
  busy = false,
  onOpenTechIntro,
  onOpenDatabasePage,
  currentProjectId,
  onSelectProject,
  isLoggedIn = true,
  onNeedLogin,
}: {
  config: TemplateConfig;
  onOpenTechIntro?: (techId: string) => void;
  onOpenDatabasePage?: () => void;
  currentProjectId?: number | null;
  onSelectProject?: (projectId: number | null) => void;
  isLoggedIn?: boolean;
  onNeedLogin?: () => void;
  onSubmit?: (payload: {
    prompt: string;
    outputFormat: "word" | "pptx" | "xlsx";
    files?: File[];
    templateFile?: File | null;
    templateFileId?: number | null;
    template?: string | null;
    scenario?: string | null;
    reportType?: string | null;
    pageRange?: string | null;
    wordCount?: string | null;
    modelId?: string | null;
    effort?: EffortLevel;
    skills?: string[];
    executionMode?: "direct" | "plan";
    kb_ids?: number[];
    include_system_kb?: boolean;
    project_id?: number | null;
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
  const [myTemplateSkills, setMyTemplateSkills] = useState<PromptSkillSummary[]>([]);
  const [templateParseOpen, setTemplateParseOpen] = useState(false);
  const [templateParseStatus, setTemplateParseStatus] = useState<TemplateParseStatus>("idle");
  const [templateSkillName, setTemplateSkillName] = useState("");
  const [templateSkillContent, setTemplateSkillContent] = useState("");
  const [templateSkillSavedName, setTemplateSkillSavedName] = useState<string | null>(null);
  const [templateAnalysis, setTemplateAnalysis] = useState<Record<string, any> | null>(null);
  const [templateParseError, setTemplateParseError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const templateInputRef = useRef<HTMLInputElement>(null);
  const templateSelectorRef = useRef<HTMLDivElement>(null);

  const triggerTemplateUpload = () => {
    if (!isLoggedIn) {
      onNeedLogin?.();
      return;
    }
    templateInputRef.current?.click();
  };

  // ── Project selector state ──
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [createProjectError, setCreateProjectError] = useState("");
  const projectDropdownRef = useRef<HTMLDivElement>(null);

  // ── Docs wizard state ──
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardPhase, setWizardPhase] = useState<WizardPhase>("type");
  const [wizardDocType, setWizardDocType] = useState("");
  const [wizardUseKB, setWizardUseKB] = useState(true);
  const [wizardNeedUpload, setWizardNeedUpload] = useState(false);
  const [wizardDescription, setWizardDescription] = useState("");
  const [wizardAnswers, setWizardAnswers] = useState<Record<string, string>>({});

  // ── Wizard computed values (component-level) ──
  const wizardPhaseIdx = WIZARD_PHASES.findIndex(p => p.key === wizardPhase);
  const wizardQuestions = WIZARD_TYPE_QUESTIONS[wizardDocType] ?? WIZARD_GENERIC_QUESTIONS;
  const wizardAllAnswered = wizardQuestions.every(q => (wizardAnswers[q.key] ?? "").trim().length > 0);

  const resetWizard = () => {
    setWizardPhase("type"); setWizardDocType(""); setWizardUseKB(true);
    setWizardNeedUpload(false); setWizardDescription(""); setWizardAnswers({});
  };

  const handleWizardSubmit = () => {
    const qaLines = wizardQuestions.map(q => `• ${q.q} → ${wizardAnswers[q.key] ?? "（未填写）"}`).join("\n");
    const composed = [
      `请生成一份【${wizardDocType}】`,
      `\n核心需求：${wizardDescription.trim()}`,
      `\n补充信息：\n${qaLines}`,
      `\n配置：${wizardUseKB ? "引入系统数据库" : "不使用数据库"}${files.length > 0 ? `，参考文档：${files.map(f => f.name).join("、")}` : ""}`,
    ].join("");
    setVal(composed);
    setDbSelection(prev => ({ ...prev, include_system: wizardUseKB }));
    onSubmit?.({ prompt: composed, outputFormat: "word", files: files.map(f => f.file), templateFile, templateFileId, template: selectedTemplate, scenario: null, reportType: WIZARD_TYPE_TO_TEMPLATE[wizardDocType] || wizardDocType || null, pageRange: null, wordCount: null, modelId: model, effort, skills: templateSkillSavedName ? [templateSkillSavedName] : [], executionMode, kb_ids: dbSelection.kb_ids, include_system_kb: wizardUseKB });
    setVal(""); setWizardOpen(false); resetWizard();
  };

  const wizardGoBack = () => { const prev = WIZARD_PHASES[wizardPhaseIdx - 1]; if (prev) setWizardPhase(prev.key); };
  const wizardGoNext = () => {
    if (wizardPhase === "summary") { handleWizardSubmit(); return; }
    const next = WIZARD_PHASES[wizardPhaseIdx + 1];
    if (next) { if (wizardPhase === "describe") setVal(wizardDescription.trim()); setWizardPhase(next.key); }
  };

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

  const refreshMyTemplateSkills = async () => {
    if (config.pageKey !== "docs") return;
    try {
      const res = await api.listPromptSkills();
      setMyTemplateSkills((res.skills || []).filter((skill) => skill.custom || skill.source === "user"));
    } catch {
      setMyTemplateSkills([]);
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
      await refreshMyTemplateSkills();
      setSelectedTemplate(`我的：${shortTemplateName(templateFile?.name || saved.name)}`);
      setTemplateParseStatus("saved");
    } catch (err) {
      setTemplateParseError(err instanceof Error ? err.message : "保存模板失败");
      setTemplateParseStatus("error");
    }
  };

  const handleEditTemplateSkill = async (name: string) => {
    setTemplateParseOpen(true);
    setTemplateParseStatus("ready");
    setTemplateParseError("");
    try {
      const skill = await api.getPromptSkill(name);
      setTemplateSkillName(skill.name);
      setTemplateSkillContent(skill.content || "");
      setTemplateSkillSavedName(skill.name);
      setTemplateAnalysis(null);
      setSelectedTemplate(`我的：${shortTemplateName(skill.title || skill.name)}`);
      setTemplateFile(null);
      setTemplateFileId(null);
      setShowTemplateSelector(false);
    } catch (err) {
      setTemplateParseError(err instanceof Error ? err.message : "读取模板 Skill 失败");
      setTemplateParseStatus("error");
    }
  };

  const handleDeleteTemplateSkill = async (name: string) => {
    try {
      await api.deletePromptSkill(name);
      setMyTemplateSkills((prev) => prev.filter((skill) => skill.name !== name));
      if (templateSkillSavedName === name) {
        setTemplateSkillSavedName(null);
      }
      if (selectedTemplate?.includes(shortTemplateName(name))) {
        setSelectedTemplate(null);
      }
    } catch (err) {
      setTemplateParseError(err instanceof Error ? err.message : "删除模板 Skill 失败");
    }
  };

  const handleDeleteUploadedTemplate = async (fileId: number) => {
    try {
      await api.deleteFile(fileId);
      setMyTemplates((prev) => prev.filter((item) => item.id !== fileId));
      if (templateFileId === fileId) {
        setTemplateFileId(null);
        setSelectedTemplate(null);
      }
    } catch (err) {
      setTemplateParseError(err instanceof Error ? err.message : "删除上传模板失败");
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
      reportType: selectedScenario || selectedTemplate || null,
      pageRange,
      wordCount: null,
      modelId: model,
	      effort,
	      skills: templateSkillSavedName ? [templateSkillSavedName] : [],
	      executionMode: config.pageKey === "docs" ? executionMode : "direct",
	      kb_ids: dbSelection.kb_ids,
      include_system_kb: dbSelection.include_system,
      project_id: currentProjectId,
	    });
    setVal("");
    setFiles([]);
    setTemplateFile(null);
    setTemplateFileId(null);
  };

  useEffect(() => {
    if (config.pageKey !== "docs") return;
    let alive = true;
    Promise.all([
      api.listFiles({ templatesOnly: true }).catch(() => ({ files: [] })),
      api.listPromptSkills().catch(() => ({ skills: [] })),
    ])
      .then((res) => {
        if (!alive) return;
        setMyTemplates(res[0].files || []);
        setMyTemplateSkills((res[1].skills || []).filter((skill) => skill.custom || skill.source === "user"));
      });
    return () => { alive = false; };
  }, [config.pageKey]);

  // Load projects for selector
  useEffect(() => {
    if (!isLoggedIn) return;
    api.listProjects().then(res => setProjects(res.items || [])).catch(() => setProjects([]));
  }, [isLoggedIn]);

  // Click outside to close project dropdown
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

  // Click outside to close template selector
  useEffect(() => {
    if (!showTemplateSelector) return;
    const handler = (e: MouseEvent) => {
      if (templateSelectorRef.current && !templateSelectorRef.current.contains(e.target as Node)) {
        setShowTemplateSelector(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showTemplateSelector]);

  return (<>
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

	      <div className={`w-full ${config.pageKey === "docs" ? "max-w-[820px] mt-36" : "max-w-[680px] mt-28"} flex flex-col items-center relative flex-1`}>
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
          @keyframes word-tag-glow {
            0%, 100% { box-shadow: 0 0 0 0 currentColor; transform: scale(1); }
            50% { box-shadow: 0 0 12px 2px currentColor; transform: scale(1.03); }
          }
          @keyframes word-dot-pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.35); opacity: .75; }
          }
          @keyframes word-header-slide {
            from { transform: translateX(-4px); opacity: .7; }
            to { transform: translateX(0); opacity: 1; }
          }
          @keyframes word-card-lift {
            from { transform: translateY(0) scale(1); }
            to { transform: translateY(-4px) scale(1.012); }
          }
          .word-hero-in { animation: word-page-rise .48s cubic-bezier(.22,1,.36,1) both; }
          .word-input-in { animation: word-page-rise .52s .08s cubic-bezier(.22,1,.36,1) both; }
          .word-gallery-in { animation: word-page-rise .5s .16s cubic-bezier(.22,1,.36,1) both; }
          .word-template-card { animation: word-card-in .44s cubic-bezier(.22,1,.36,1) both; transition: transform .25s cubic-bezier(.22,1,.36,1), box-shadow .25s ease; }
          .word-template-chip { animation: word-card-in .34s cubic-bezier(.22,1,.36,1) both; }
          .word-template-chip:hover { transform: translateY(-1px); box-shadow: var(--shadow-sm); }
          .word-template-card:hover { transform: translateY(-4px) scale(1.012); box-shadow: 0 12px 28px -8px rgba(0,0,0,0.14), 0 4px 10px rgba(0,0,0,0.06) !important; }
          .word-template-card:hover .doc-thumb { animation: word-soft-float 2.4s ease-in-out infinite; }
          .word-template-card:hover .doc-line { transform-origin: left center; animation: word-line-write .5s ease-out both; }
          .word-template-card:hover .doc-line:nth-of-type(2) { animation-delay: .04s; }
          .word-template-card:hover .doc-line:nth-of-type(3) { animation-delay: .08s; }
          .word-template-card:hover .doc-line:nth-of-type(4) { animation-delay: .12s; }
          .word-template-card:hover .doc-thumb-sheen,
          .word-upload-card:hover .doc-upload-sheen { background: linear-gradient(90deg, transparent, rgba(255,255,255,.72), transparent); animation: word-sheen 1.35s ease-out; }
          .word-template-card:hover .doc-tag { animation: word-tag-glow 1.4s ease-in-out infinite; color: inherit; }
          .word-template-card:hover .doc-tag-text { transform: scale(1.08); transition: transform .25s cubic-bezier(.22,1,.36,1); }
          .word-template-card:hover .doc-dot { animation: word-dot-pulse 1s ease-in-out infinite; }
          .word-template-card:hover .doc-header { animation: word-header-slide .4s ease-out both; }
          .word-template-card:hover .doc-header-line { animation: word-line-write .45s ease-out both; }
          .word-send-ready { animation: word-soft-float 2s ease-in-out infinite; }
          .docs-official-item { transition: transform .18s ease, background .18s ease; }
          .docs-official-item:hover { transform: translateX(3px); background: var(--hover); }
          @media (prefers-reduced-motion: reduce) {
            .agent-hero-in, .agent-input-in, .agent-gallery-in, .agent-template-card, .agent-send-ready,
            .agent-template-card:hover .agent-card-sheen, .agent-upload-card:hover .agent-card-sheen {
              animation: none !important;
            }
            .agent-template-card:hover .agent-thumb-motion { transform: none !important; }
            .word-hero-in, .word-input-in, .word-gallery-in, .word-template-card, .word-template-chip, .word-send-ready,
            .word-template-card:hover .doc-thumb, .word-template-card:hover .doc-line,
            .word-template-card:hover .doc-thumb-sheen, .word-upload-card:hover .doc-upload-sheen,
            .word-template-card:hover .doc-tag, .word-template-card:hover .doc-dot, .word-template-card:hover .doc-header, .word-template-card:hover .doc-header-line {
              animation: none !important;
            }
            .word-template-card:hover { transform: none !important; }
          }
          ` : ""}
        `}</style>
        {/* Title */}
        <div className={`text-center mb-4 agent-hero-in ${config.pageKey === "docs" ? "word-hero-in" : ""}`}>
          <h1 style={{ fontSize: "28px", lineHeight: 1.4, fontWeight: 500, letterSpacing: "-0.01em", color: "var(--ink-900)" }}>
            欢迎来到 <span className={`animated-gradient-${config.pageKey}`} style={{ fontWeight: 600 }}>{config.heroTitle.replace('欢迎来到 ', '')}</span>
          </h1>
          {config.heroSub && (
            <p style={{ marginTop: 8, fontSize: "14px", color: "var(--ink-400)", lineHeight: 1.6, maxWidth: 520, margin: "8px auto 0" }}>
              {config.heroSub}
            </p>
          )}
          {/* Contextual tech badges — only shown on non-docs pages */}
          {config.pageKey !== "docs" && onOpenTechIntro && (PAGE_TECH_BADGES[config.pageKey] || []).length > 0 && (
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
                    <FileIcon type={f.type} name={f.name} />
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
	              <div className={`relative min-w-0 ${config.pageKey === "docs" ? "max-w-[130px] flex-shrink-0" : "max-w-[280px] flex-shrink"}`} ref={templateSelectorRef}>
                {(config.pageKey === "sheet" ? selectedScenario : selectedTemplate) ? (
                  <div
                    className="inline-flex items-center gap-1.5 min-h-7 pl-2 pr-1.5 py-0.5 rounded-full min-w-0 max-w-full"
                    style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}
                    title={config.pageKey === "sheet" ? selectedScenario || "" : selectedTemplate || ""}
                  >
                    {(() => {
                      const name = config.pageKey === "sheet" ? selectedScenario : selectedTemplate;
                      if (!name) return null;
                      if (config.pageKey === "sheet") {
                        const scenario = config.scenarios?.find((s) => s.label === name);
                        if (scenario) {
                          const ScenarioIcon = scenario.icon;
                          return <ScenarioIcon className="h-3 w-3 flex-shrink-0" style={{ color: scenario.color }} />;
                        }
                      }
                      if (name.startsWith("我的：")) return <Sparkles size={12} style={{ color: "var(--ink-500)", flexShrink: 0 }} />;
                      if (name.startsWith("自定义模板：")) return <Upload size={12} style={{ color: "var(--ink-500)", flexShrink: 0 }} />;
                      const meta = getGroupMeta(name);
                      return <meta.Icon size={12} style={{ color: meta.color, flexShrink: 0 }} />;
                    })()}
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
                      className={`absolute top-full mt-1.5 left-0 rounded-lg overflow-hidden z-30 custom-scrollbar ${config.pageKey === "docs" ? "w-[560px] max-w-[calc(100vw-48px)]" : "min-w-[200px] max-h-[360px] overflow-y-auto"}`}
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
                      <div className={config.pageKey === "docs" ? "p-2" : "py-1"}>
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
                        ) : config.pageKey === "docs" ? (
                          <div className="grid grid-cols-[1fr_1.18fr] gap-2">
                            <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)", background: "var(--bg-subtle)" }}>
                              <div className="px-3 py-2 text-[11px] flex items-center gap-1.5" style={{ color: "var(--ink-400)", fontWeight: 700, borderBottom: "1px solid var(--border)" }}>
                                <FileText size={12} /> 官方模板
                              </div>
                              <div className="p-1.5 max-h-[312px] overflow-y-auto custom-scrollbar">
                                {(config.groups || []).map((title) => {
                                  const selected = selectedTemplate === title;
                                  const { Icon, color, en } = getGroupMeta(title);
                                  return (
                                    <button
                                      key={title}
                                      onClick={() => {
                                        setSelectedTemplate(title);
                                        setTemplateFile(null);
                                        setTemplateFileId(null);
                                        setTemplateSkillSavedName(null);
                                        setShowTemplateSelector(false);
                                      }}
                                      className="w-full px-2.5 py-2 text-left rounded-lg flex items-center justify-between gap-2 docs-official-item"
                                      style={{ fontSize: "13px", color: selected ? config.accentColor : "var(--ink-700)", background: selected ? `${config.accentColor}10` : "transparent" }}
                                    >
                                      <span className="inline-flex items-center gap-1.5 min-w-0 flex-1">
                                        <Icon size={13} style={{ color, flexShrink: 0 }} />
                                        <span className="truncate">{title}</span>
                                        <span className="text-[10px] flex-shrink-0" style={{ color: "var(--ink-400)" }}>{en}</span>
                                      </span>
                                      {selected && <Check size={13} />}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                            <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)", background: "#fff" }}>
                              <div className="px-3 py-2 text-[11px] flex items-center justify-between gap-2" style={{ color: "var(--ink-400)", fontWeight: 700, borderBottom: "1px solid var(--border)" }}>
                                <span className="inline-flex items-center gap-1.5"><Sparkles size={12} /> 我的模板 Skill</span>
                                <button
                                  onClick={() => {
                                    triggerTemplateUpload();
                                    setShowTemplateSelector(false);
                                  }}
                                  className="h-6 px-2 rounded-md inline-flex items-center gap-1 transition hover:bg-[var(--hover)]"
                                  style={{ color: config.accentColor, background: `${config.accentColor}10`, fontSize: "11px" }}
                                >
                                  <Upload size={12} /> 上传解析
                                </button>
                              </div>
                              <div className="p-1.5 max-h-[312px] overflow-y-auto custom-scrollbar">
                                {myTemplateSkills.length > 0 ? (
                                  myTemplateSkills.map((skill) => {
                                    const label = shortTemplateName(skill.title || skill.name);
                                    const selected = templateSkillSavedName === skill.name || selectedTemplate === `我的：${label}`;
                                    return (
                                      <div
                                        key={skill.name}
                                        className="group rounded-lg border mb-1.5 transition"
                                        style={{ borderColor: selected ? `${config.accentColor}55` : "var(--border)", background: selected ? `${config.accentColor}08` : "var(--bg-subtle)" }}
                                      >
                                        <button
                                          onClick={() => {
                                            setSelectedTemplate(`我的：${label}`);
                                            setTemplateSkillSavedName(skill.name);
                                            setTemplateFile(null);
                                            setTemplateFileId(null);
                                            setShowTemplateSelector(false);
                                          }}
                                          className="w-full px-2.5 py-2 text-left flex items-start gap-2"
                                        >
                                          <span className="mt-0.5 h-5 w-5 rounded-md inline-flex items-center justify-center flex-shrink-0" style={{ background: selected ? config.accentColor : "rgba(15,23,42,0.07)", color: selected ? "#fff" : "var(--ink-500)" }}>
                                            {selected ? <Check size={12} /> : <FileText size={12} />}
                                          </span>
                                          <span className="min-w-0 flex-1">
                                            <span className="block truncate text-[13px] font-semibold" style={{ color: "var(--ink-800)" }}>{skill.title || skill.name}</span>
                                            <span className="block truncate text-[11px] mt-0.5" style={{ color: "var(--ink-400)" }}>{skill.description || "上传文档解析生成的 Skill"}</span>
                                          </span>
                                        </button>
                                        <div className="px-2.5 pb-2 flex items-center gap-1.5">
                                          <button
                                            onClick={() => handleEditTemplateSkill(skill.name)}
                                            className="h-6 px-2 rounded-md inline-flex items-center gap-1 transition hover:bg-white"
                                            style={{ color: "var(--ink-600)", fontSize: "11px" }}
                                          >
                                            <Pencil size={11} /> 修改
                                          </button>
                                          <button
                                            onClick={() => handleDeleteTemplateSkill(skill.name)}
                                            className="h-6 px-2 rounded-md inline-flex items-center gap-1 transition hover:bg-white"
                                            style={{ color: "#dc2626", fontSize: "11px" }}
                                          >
                                            <Trash2 size={11} /> 删除
                                          </button>
                                        </div>
                                      </div>
                                    );
                                  })
                                ) : (
                                  <button
                                    onClick={() => {
                                      triggerTemplateUpload();
                                      setShowTemplateSelector(false);
                                    }}
                                    className="w-full min-h-[92px] rounded-lg border border-dashed flex flex-col items-center justify-center gap-1.5 transition hover:bg-[var(--hover)]"
                                    style={{ borderColor: "var(--border)", color: "var(--ink-400)" }}
                                  >
                                    <Upload size={18} />
                                    <span className="text-[12px] font-medium">上传并解析为 Skill</span>
                                    <span className="text-[10.5px]">保存后会显示在这里，可修改和删除</span>
                                  </button>
                                )}
                                {myTemplates.length > 0 && (
                                  <div className="mt-2 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
                                    <div className="px-1 pb-1 text-[10.5px]" style={{ color: "var(--ink-400)", fontWeight: 700 }}>已上传文件</div>
                                    {myTemplates.slice(0, 4).map((template) => {
                                      const label = shortTemplateName(template.original_name || template.filename || "模板");
                                      return (
                                        <div key={template.id} className="h-7 px-2 rounded-md flex items-center gap-2" style={{ color: "var(--ink-500)" }}>
                                          <File size={11} />
                                          <span className="truncate flex-1 text-[11px]" title={template.original_name || template.filename || "模板"}>{label}</span>
                                          <button onClick={() => handleDeleteUploadedTemplate(template.id)} className="h-5 w-5 inline-flex items-center justify-center rounded hover:bg-[var(--hover)]" title="删除上传文件">
                                            <X size={11} />
                                          </button>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ) : (
                          // PPT templates
                          <>
                            <div className="px-3 pt-1 pb-1 text-[11px]" style={{ color: "var(--ink-400)", fontWeight: 650 }}>官方模板</div>
                            {config.templates.map((t) => (
                              <button
                                key={t.title}
                                onClick={() => {
                                  setSelectedTemplate(t.title);
                                  setTemplateFile(null);
                                  setTemplateFileId(null);
                                  setShowTemplateSelector(false);
                                }}
                                className="w-full px-3 py-1.5 text-left transition hover:bg-[var(--hover)]"
                                style={{ fontSize: "13px", color: "var(--ink-700)" }}
                              >
                                {t.title}
                              </button>
                            ))}
                            <div className="h-px mx-2 my-1" style={{ background: "var(--border)" }} />
                            <button
                              onClick={() => {
                                triggerTemplateUpload();
                                setShowTemplateSelector(false);
                              }}
                              className="w-full px-3 py-2 text-left transition hover:bg-[var(--hover)] flex items-center gap-2"
                              style={{ fontSize: "13px", color: "var(--ink-700)" }}
                            >
                              <Upload className="h-3.5 w-3.5" style={{ color: "var(--ink-500)" }} />
                              上传自定义模板
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </>
                )}
	              </div>

	              {config.pageKey === "docs" && (
	                <>
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

	                  <div className="inline-flex h-8 p-0.5 rounded-full flex-shrink-0" style={{ background: "rgba(15, 23, 42, 0.04)", border: "1px solid rgba(15, 23, 42, 0.08)" }}>
		                    {[
		                      { key: "plan", label: "先生成大纲", icon: Sparkles },
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

        {/* Docs wizard trigger + marquee — replaces old template chips for docs */}
        {config.pageKey === "docs" && (
          <div className="w-full mt-8 word-gallery-in">
            {/* divider + trigger */}
            <div className="flex items-center gap-3 mb-6">
              <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
              <button
                onClick={() => { resetWizard(); setWizardOpen(true); }}
                className="inline-flex items-center gap-1.5 h-8 px-4 rounded-full border text-[12.5px] font-medium transition-all flex-shrink-0"
                style={{ borderColor: "var(--border)", color: "var(--ink-500)", background: "transparent" }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.color = "#2563eb"; e.currentTarget.style.background = "rgba(37,99,235,0.04)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--ink-500)"; e.currentTarget.style.background = "transparent"; }}
              >
                <Sparkles className="h-3 w-3" />
                引导我创建
              </button>
              <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
            </div>

            {/* hot scenarios marquee */}
            <style>{`
              @keyframes marquee-left  { from { transform: translateX(0);    } to { transform: translateX(-50%); } }
              @keyframes marquee-right { from { transform: translateX(-50%); } to { transform: translateX(0);    } }
              .marquee-row { overflow: hidden; mask-image: linear-gradient(to right, transparent 0%, black 8%, black 92%, transparent 100%); -webkit-mask-image: linear-gradient(to right, transparent 0%, black 8%, black 92%, transparent 100%); }
              .marquee-track-left  { display: flex; gap: 10px; width: max-content; animation: marquee-left  32s linear infinite; }
              .marquee-track-right { display: flex; gap: 10px; width: max-content; animation: marquee-right 28s linear infinite; }
              .marquee-track-left:hover, .marquee-track-right:hover { animation-play-state: paused; }
            `}</style>
            <div className="flex items-center justify-between mb-4">
              <p className="text-[12px] font-semibold" style={{ color: "var(--ink-500)" }}>热门文档场景</p>
              <span className="text-[11px]" style={{ color: "var(--ink-300)" }}>点击即可预填</span>
            </div>
            {(() => {
              const rows: Array<Array<{type:string;color:string;title:string;heat:string;prompt:string}>> = [
                [
                  { type:"分析报告", color:"#2563eb", title:"2026年AI行业市场趋势分析",   heat:"4.2k", prompt:"撰写一份2026年AI行业市场趋势分析报告，面向公司管理层，涵盖技术演进、市场规模与竞争格局" },
                  { type:"工作汇报", color:"#7c3aed", title:"季度述职与工作总结汇报",     heat:"3.8k", prompt:"撰写本季度工作总结与述职报告，包含项目进展、关键成果、问题复盘和下季度计划" },
                  { type:"商业方案", color:"#0891b2", title:"新业务线商业计划书",          heat:"3.1k", prompt:"制定一份新业务商业计划书，包含市场分析、商业模式、财务预测和执行路径" },
                  { type:"技术文档", color:"#d97706", title:"系统API接口技术规范文档",     heat:"2.9k", prompt:"编写系统API接口技术文档，包含接口说明、请求参数、返回示例和错误码说明" },
                  { type:"学术论文", color:"#059669", title:"大语言模型应用研究论文",      heat:"2.6k", prompt:"撰写一篇关于大语言模型在企业知识管理中的应用研究论文，需含文献综述和实验设计" },
                ],
                [
                  { type:"个人简历", color:"#7c3aed", title:"技术岗位求职简历",            heat:"3.5k", prompt:"撰写一份面向技术岗位（后端开发/AI工程师）的专业简历，突出项目经验和技术栈" },
                  { type:"分析报告", color:"#2563eb", title:"竞品调研与对比分析报告",      heat:"2.7k", prompt:"撰写一份针对主要竞争对手的产品竞品分析报告，包含功能对比、优劣势评估和差异化建议" },
                  { type:"工作汇报", color:"#dc2626", title:"年终工作总结与展望",          heat:"4.1k", prompt:"撰写年终工作总结报告，回顾全年核心成果、复盘不足，并展望来年工作重点和目标" },
                  { type:"公文通知", color:"#b45309", title:"年度绩效考核安排通知",        heat:"2.1k", prompt:"起草一份关于年度绩效考核工作安排的通知，明确考核时间节点、流程和注意事项" },
                  { type:"会议纪要", color:"#0891b2", title:"项目启动会会议纪要",          heat:"1.8k", prompt:"整理并撰写项目启动会的会议纪要，包含讨论要点、决议事项、责任人和后续行动计划" },
                ],
              ];
              return rows.map((items, rowIdx) => {
                const doubled = [...items, ...items];
                return (
                  <div key={rowIdx} className={`marquee-row ${rowIdx === 0 ? "mb-2.5" : ""}`}>
                    <div className={rowIdx === 0 ? "marquee-track-left" : "marquee-track-right"}>
                      {doubled.map((s, i) => (
                        (() => {
                          const templateLabel = HOT_SCENE_TEMPLATE_LABELS[s.type] || WIZARD_TYPE_TO_TEMPLATE[s.type] || s.type;
                          return (
                            <button
                              key={i}
                              onClick={() => {
                                setVal(s.prompt);
                                setSelectedTemplate(templateLabel);
                                setTemplateFile(null);
                                setTemplateFileId(null);
                              }}
                              className="flex items-center gap-2.5 flex-shrink-0 px-3.5 rounded-2xl border transition-all"
                              style={{ height: 42, background: "#fff", borderColor: "#eaecf0", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
                              onMouseEnter={e => { e.currentTarget.style.borderColor = s.color + "55"; e.currentTarget.style.boxShadow = `0 2px 8px ${s.color}20`; e.currentTarget.style.background = `${s.color}05`; }}
                              onMouseLeave={e => { e.currentTarget.style.borderColor = "#eaecf0"; e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.06)"; e.currentTarget.style.background = "#fff"; }}
                            >
                              <span className="flex-shrink-0 px-1.5 py-0.5 rounded-md text-[10.5px] font-semibold" style={{ background: s.color + "12", color: s.color }}>{templateLabel}</span>
                              <span className="text-[13px] whitespace-nowrap" style={{ color: "#1e293b", fontWeight: 500 }}>{s.title}</span>
                              <span className="flex items-center gap-0.5 text-[11px] flex-shrink-0" style={{ color: "#f97316", fontWeight: 600 }}>🔥 {s.heat}</span>
                            </button>
                          );
                        })()
                      ))}
                    </div>
                  </div>
                );
              });
            })()}
          </div>
        )}

        {/* Document Template Types — non-docs pages only */}
        {config.pageKey !== "docs" && config.pageKey === "docs_DISABLED" && config.groups && (
          <div className="w-full mt-7 word-gallery-in">
            <div className="flex items-center justify-between mb-3">
              <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
                文档模板
              </span>
              <button
                onClick={() => triggerTemplateUpload()}
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

        {/* Template Gallery - PPT only */}
        {config.pageKey === "ppt" && (
          <div className="w-full mb-14 agent-gallery-in mt-auto">
            <div className="flex items-center justify-between mb-4">
              <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
                {config.galleryTitle}
              </span>
              <span style={{ fontSize: "12px", color: "var(--ink-400)" }}>
                {config.templates.length + 1} 个模板
              </span>
            </div>

            <div className="grid gap-3 grid-cols-2 sm:grid-cols-3">
              {/* Upload Template Card */}
              {config.pageKey !== "docs" && (
                <button
                  onClick={() => triggerTemplateUpload()}
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

    {/* ══ Docs Guided Creation Modal ══ */}
    {wizardOpen && config.pageKey === "docs" && (
      <div
        className="fixed inset-0 z-[300] flex items-center justify-center p-4"
        style={{ background: "rgba(10,15,30,0.55)", backdropFilter: "blur(8px)" }}
        onClick={e => { if (e.target === e.currentTarget) setWizardOpen(false); }}
      >
        <div className="bg-white w-full flex flex-col overflow-hidden" style={{ maxWidth: 520, maxHeight: "88vh", borderRadius: 24, boxShadow: "0 32px 80px rgba(0,0,0,0.22), 0 0 0 1px rgba(0,0,0,0.06)" }}>

          {/* header */}
          <div className="flex items-center justify-between px-6 pt-5 pb-4 flex-shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: "rgba(37,99,235,0.10)" }}>
                <Sparkles className="h-3.5 w-3.5" style={{ color: "#2563eb" }} />
              </div>
              <div>
                <p className="text-[14px] font-bold" style={{ color: "#0f172a", lineHeight: 1.2 }}>引导创建文档</p>
                <p className="text-[11.5px]" style={{ color: "#94a3b8", marginTop: 1 }}>{WIZARD_PHASES[wizardPhaseIdx]?.label}&ensp;·&ensp;{wizardPhaseIdx + 1} / {WIZARD_PHASES.length}</p>
              </div>
            </div>
            <div className="flex items-center gap-1 mx-auto">
              {WIZARD_PHASES.map((s, i) => (
                <div key={s.key} className="rounded-full transition-all" style={{ height: 5, width: i === wizardPhaseIdx ? 22 : 5, background: i <= wizardPhaseIdx ? "#2563eb" : "#e2e8f0", opacity: i > wizardPhaseIdx ? 0.5 : 1 }} />
              ))}
            </div>
            <button onClick={() => setWizardOpen(false)} className="h-8 w-8 rounded-full flex items-center justify-center transition flex-shrink-0" style={{ color: "#94a3b8" }} onMouseEnter={e => { e.currentTarget.style.background = "#f1f5f9"; }} onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="h-px flex-shrink-0" style={{ background: "#f1f5f9" }} />

          {/* body */}
          <div className="flex-1 overflow-y-auto px-6 py-5">

            {/* Phase 1: type */}
            {wizardPhase === "type" && (
              <div>
                <h2 className="text-[20px] font-bold mb-1.5" style={{ color: "#0f172a", letterSpacing: "-0.02em" }}>这份文档是什么类型？</h2>
                <p className="text-[13px] mb-6" style={{ color: "#94a3b8" }}>选中后将自动匹配专属模板</p>
                <div className="grid grid-cols-3 gap-2.5">
                  {([
                    { label: "学术论文", sub: "研究 / 期刊 / 毕业" }, { label: "工作汇报", sub: "述职 / 绩效 / 季报" },
                    { label: "商业方案", sub: "BP / 策划 / 提案" },   { label: "技术文档", sub: "PRD / 接口 / 手册" },
                    { label: "分析报告", sub: "市场 / 数据 / 行业" }, { label: "个人简历", sub: "求职 / 履历" },
                    { label: "公文通知", sub: "通知 / 函件 / 公告" }, { label: "会议纪要", sub: "会议 / 决议 / 记录" },
                  ] as Array<{label:string;sub:string}>).map(t => {
                    const sel = wizardDocType === t.label;
                    return (
                      <button key={t.label} onClick={() => { setWizardDocType(t.label); const tpl = WIZARD_TYPE_TO_TEMPLATE[t.label]; if (tpl) setSelectedTemplate(tpl); }}
                        className="flex flex-col items-start px-3.5 py-3 rounded-2xl border text-left transition-all"
                        style={{ background: sel ? "rgba(37,99,235,0.06)" : "#fafafa", borderColor: sel ? "#2563eb" : "#e8eaed", boxShadow: sel ? "0 0 0 2px rgba(37,99,235,0.12)" : "none" }}
                        onMouseEnter={e => { if (!sel) { e.currentTarget.style.borderColor = "#c7d2fe"; e.currentTarget.style.background = "#f8f9ff"; } }}
                        onMouseLeave={e => { if (!sel) { e.currentTarget.style.borderColor = "#e8eaed"; e.currentTarget.style.background = "#fafafa"; } }}
                      >
                        <span className="text-[13.5px] font-semibold mb-0.5" style={{ color: sel ? "#2563eb" : "#0f172a" }}>{t.label}</span>
                        <span className="text-[11px]" style={{ color: "#94a3b8" }}>{t.sub}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Phase 2: config */}
            {wizardPhase === "config" && (
              <div>
                <h2 className="text-[20px] font-bold mb-1.5" style={{ color: "#0f172a", letterSpacing: "-0.02em" }}>需要引用哪些资料？</h2>
                <p className="text-[13px] mb-6" style={{ color: "#94a3b8" }}>合理配置资料来源，可显著提升内容准确性</p>
                <p className="text-[11.5px] font-semibold uppercase tracking-widest mb-3" style={{ color: "#94a3b8" }}>数据库</p>
                <div className="flex flex-col gap-2 mb-6">
                  {[{ val: true, title: "引入系统数据库", desc: "基于平台积累的领域语料，生成内容更专业" }, { val: false, title: "不使用数据库", desc: "仅依赖模型自身知识，生成速度更快" }].map(opt => {
                    const sel = wizardUseKB === opt.val;
                    return (
                      <button key={String(opt.val)} onClick={() => { setWizardUseKB(opt.val); setDbSelection(prev => ({ ...prev, include_system: opt.val })); }}
                        className="flex items-center gap-3.5 px-4 py-3.5 rounded-2xl border text-left transition-all"
                        style={{ background: sel ? "rgba(37,99,235,0.05)" : "#fafafa", borderColor: sel ? "#2563eb" : "#e8eaed", boxShadow: sel ? "0 0 0 2px rgba(37,99,235,0.10)" : "none" }}
                      >
                        <div className="h-4 w-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all" style={{ borderColor: sel ? "#2563eb" : "#cbd5e1" }}>
                          {sel && <div className="h-2 w-2 rounded-full" style={{ background: "#2563eb" }} />}
                        </div>
                        <div>
                          <p className="text-[13.5px] font-semibold" style={{ color: sel ? "#2563eb" : "#0f172a" }}>{opt.title}</p>
                          <p className="text-[12px] mt-0.5" style={{ color: "#94a3b8" }}>{opt.desc}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
                <p className="text-[11.5px] font-semibold uppercase tracking-widest mb-3" style={{ color: "#94a3b8" }}>参考文档</p>
                <div className="flex flex-col gap-2">
                  {[{ val: false, title: "从零开始创作", desc: "AI 根据你的描述直接生成" }, { val: true, title: "上传我的参考文档", desc: "AI 基于你提供的资料撰写，更贴合实际" }].map(opt => {
                    const sel = wizardNeedUpload === opt.val;
                    return (
                      <button key={String(opt.val)} onClick={() => { setWizardNeedUpload(opt.val); if (opt.val) fileInputRef.current?.click(); }}
                        className="flex items-center gap-3.5 px-4 py-3.5 rounded-2xl border text-left transition-all"
                        style={{ background: sel ? "rgba(37,99,235,0.05)" : "#fafafa", borderColor: sel ? "#2563eb" : "#e8eaed", boxShadow: sel ? "0 0 0 2px rgba(37,99,235,0.10)" : "none" }}
                      >
                        <div className="h-4 w-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all" style={{ borderColor: sel ? "#2563eb" : "#cbd5e1" }}>
                          {sel && <div className="h-2 w-2 rounded-full" style={{ background: "#2563eb" }} />}
                        </div>
                        <div>
                          <p className="text-[13.5px] font-semibold" style={{ color: sel ? "#2563eb" : "#0f172a" }}>{opt.title}</p>
                          <p className="text-[12px] mt-0.5" style={{ color: "#94a3b8" }}>{opt.desc}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
                {files.length > 0 && (
                  <div className="mt-3">
                    <div className="grid grid-cols-2 gap-2">
                      {files.map((f, i) => (
                        <div key={i} className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg min-w-0" style={{ background: "#f8fafc", border: "1px solid #e2e8f0" }}>
                          <div className="flex-shrink-0">
                            <FileIcon type={f.type} name={f.name} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-[11.5px]" style={{ color: "#0f172a", fontWeight: 500 }} title={f.name}>{f.name}</div>
                            <div style={{ fontSize: "10px", color: "#64748b" }}>{f.size}</div>
                          </div>
                          <button
                            onClick={() => setFiles((p) => p.filter((_, idx) => idx !== i))}
                            className="h-5 w-5 inline-flex items-center justify-center flex-shrink-0 rounded transition hover:bg-black/5"
                            style={{ color: "#94a3b8" }}
                            title="移除"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium transition hover:opacity-80"
                      style={{ color: "#2563eb" }}
                    >
                      <Plus className="h-3.5 w-3.5" /> 继续添加文件
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Phase 3: describe */}
            {wizardPhase === "describe" && (
              <div>
                <h2 className="text-[20px] font-bold mb-1.5" style={{ color: "#0f172a", letterSpacing: "-0.02em" }}>描述你的「{wizardDocType}」需求</h2>
                <p className="text-[13px] mb-5" style={{ color: "#94a3b8" }}>越详细越好——包含主题、背景、目标读者、核心论点等，系统将据此提问</p>
                <textarea value={wizardDescription} onChange={e => setWizardDescription(e.target.value)} autoFocus
                  placeholder={`例如：为公司管理层撰写一份关于 2026 年 AI 行业市场趋势的${wizardDocType}，涵盖技术演进、市场规模预测、主流厂商对比以及我方战略建议，约 5000 字`}
                  rows={6} className="w-full rounded-2xl border px-4 py-3.5 text-[13.5px] resize-none focus:outline-none"
                  style={{ borderColor: "#e8eaed", background: "#fafafa", color: "#0f172a", lineHeight: 1.7, transition: "border-color .15s, box-shadow .15s" }}
                  onFocus={e => { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37,99,235,0.10)"; }}
                  onBlur={e => { e.currentTarget.style.borderColor = "#e8eaed"; e.currentTarget.style.boxShadow = "none"; }}
                />
                <p className="text-[12px] mt-2.5 text-right" style={{ color: wizardDescription.length > 20 ? "#2563eb" : "#cbd5e1" }}>{wizardDescription.length} 字</p>
              </div>
            )}

            {/* Phase 4: questions */}
            {wizardPhase === "questions" && (
              <div>
                <h2 className="text-[20px] font-bold mb-1.5" style={{ color: "#0f172a", letterSpacing: "-0.02em" }}>几个细化问题</h2>
                <p className="text-[13px] mb-6" style={{ color: "#94a3b8" }}>回答后将生成完整任务清单，随时可返回修改</p>
                <div className="space-y-5">
                  {wizardQuestions.map((q, qi) => {
                    const answered = !!(wizardAnswers[q.key] ?? "").trim();
                    return (
                      <div key={q.key}>
                        <div className="flex items-center gap-2 mb-2">
                          <div className="flex-shrink-0 h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-all" style={{ background: answered ? "#2563eb" : "transparent", color: answered ? "#fff" : "#94a3b8", border: answered ? "none" : "1.5px solid #e2e8f0" }}>
                            {answered ? "✓" : qi + 1}
                          </div>
                          <p className="text-[13.5px] font-semibold" style={{ color: "#0f172a" }}>{q.q}</p>
                        </div>
                        <textarea value={wizardAnswers[q.key] ?? ""} onChange={e => setWizardAnswers(prev => ({ ...prev, [q.key]: e.target.value }))}
                          placeholder={q.placeholder} rows={2} className="w-full rounded-2xl border px-4 py-3 text-[13px] resize-none focus:outline-none"
                          style={{ borderColor: "#e8eaed", background: "#fafafa", color: "#0f172a", lineHeight: 1.6, transition: "border-color .15s, box-shadow .15s" }}
                          onFocus={e => { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37,99,235,0.10)"; }}
                          onBlur={e => { e.currentTarget.style.borderColor = "#e8eaed"; e.currentTarget.style.boxShadow = "none"; }}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Phase 5: summary */}
            {wizardPhase === "summary" && (
              <div>
                <h2 className="text-[20px] font-bold mb-1.5" style={{ color: "#0f172a", letterSpacing: "-0.02em" }}>确认任务清单</h2>
                <p className="text-[13px] mb-5" style={{ color: "#94a3b8" }}>点击「开始执行」后将立即启动文档生成</p>
                <div className="rounded-2xl border overflow-hidden" style={{ borderColor: "#e8eaed" }}>
                  {[
                    { label: "文档类型", value: wizardDocType },
                    { label: "文档模板", value: WIZARD_TYPE_TO_TEMPLATE[wizardDocType] ?? "默认" },
                    { label: "数据库",   value: wizardUseKB ? "✓ 引入系统数据库" : "不使用数据库" },
                    { label: "参考文档", value: files.length > 0 ? files.map(f => f.name).join("、") : "无" },
                    { label: "核心需求", value: wizardDescription.trim() },
                    ...wizardQuestions.map(q => ({ label: q.q.slice(0, 8).replace(/？$/, ""), value: wizardAnswers[q.key] || "—" })),
                  ].map((item, idx) => (
                    <div key={item.label} className="flex gap-3 px-4 py-3.5" style={{ borderTop: idx === 0 ? "none" : "1px solid #f1f5f9", background: idx % 2 === 0 ? "#fff" : "#fafafa" }}>
                      <span className="flex-shrink-0 w-[72px] text-[12px] pt-0.5 font-medium" style={{ color: "#94a3b8" }}>{item.label}</span>
                      <span className="text-[13px] flex-1" style={{ color: "#0f172a", lineHeight: 1.5 }}>{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* footer nav */}
          <div className="flex-shrink-0 px-6 py-4 flex items-center justify-between" style={{ borderTop: "1px solid #f1f5f9" }}>
            {wizardPhaseIdx > 0 ? (
              <button onClick={wizardGoBack} className="h-9 px-4 rounded-xl text-[13px] font-medium transition-all" style={{ color: "#64748b" }}
                onMouseEnter={e => { e.currentTarget.style.background = "#f8fafc"; }} onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}>
                ← 上一步
              </button>
            ) : <div />}
            <button onClick={wizardGoNext}
              disabled={(wizardPhase === "type" && !wizardDocType) || (wizardPhase === "describe" && !wizardDescription.trim()) || (wizardPhase === "questions" && !wizardAllAnswered)}
              className="h-9 px-6 rounded-xl text-[13.5px] font-semibold transition-all disabled:opacity-40 flex items-center gap-2"
              style={{ background: "linear-gradient(135deg,#2563eb,#7c3aed)", color: "#fff", boxShadow: "0 4px 16px rgba(37,99,235,0.28)" }}
            >
              {wizardPhase === "summary" ? <><Sparkles className="h-3.5 w-3.5" /> 开始执行</> : "下一步 →"}
            </button>
          </div>
        </div>
      </div>
    )}

    {/* Create project modal */}
    {showCreateModal && (
      <div className="fixed inset-0 z-[200] flex items-center justify-center" style={{ background: "rgba(0,0,0,0.55)" }}>
        <div className="rounded-2xl p-6 w-[360px]" style={{ background: "var(--bg-elevated)", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
          <h3 className="text-[16px] font-semibold mb-4" style={{ color: "var(--ink-900)" }}>添加新项目</h3>
          <input
            className="w-full rounded-xl border px-3 py-2.5 text-[14px] outline-none transition-all mb-3"
            style={{ borderColor: "var(--border)", background: "var(--bg-subtle)", color: "var(--ink-900)" }}
            placeholder="输入项目名称"
            value={newProjectName}
            onChange={e => setNewProjectName(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") { /* handled below */ } }}
            autoFocus
          />
          {createProjectError && <p className="text-[12px] text-red-500 mb-3">{createProjectError}</p>}
          <div className="flex justify-end gap-2">
            <button
              className="h-9 px-4 rounded-xl text-[13px] font-medium transition hover:bg-[var(--hover)]"
              style={{ color: "var(--ink-600)" }}
              onClick={() => { setShowCreateModal(false); setNewProjectName(""); setCreateProjectError(""); }}
            >取消</button>
            <button
              className="h-9 px-4 rounded-xl text-[13px] font-semibold text-white disabled:opacity-50 transition"
              style={{ background: "var(--brand, #2563eb)" }}
              disabled={!newProjectName.trim() || creatingProject}
              onClick={async () => {
                if (!newProjectName.trim()) return;
                setCreatingProject(true); setCreateProjectError("");
                try {
                  const res = await api.createProject(newProjectName.trim());
                  setProjects(prev => [res, ...prev]);
                  onSelectProject?.(res.id);
                  setShowCreateModal(false);
                  setNewProjectName("");
                } catch (err) {
                  setCreateProjectError(err instanceof Error ? err.message : "创建失败");
                } finally {
                  setCreatingProject(false);
                }
              }}
            >{creatingProject ? "创建中…" : "创建"}</button>
          </div>
        </div>
      </div>
    )}
  </>);
}

function FileIcon({ type, name }: { type: string; name?: string }) {
  const ext = (name || "").split(".").pop()?.toLowerCase() || "";
  if (["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"].includes(ext) || type.startsWith("image/")) {
    return <FileImage className="h-4 w-4 flex-shrink-0" style={{ color: "#2563eb" }} />;
  }
  if (["pdf"].includes(ext)) return <FileText className="h-4 w-4 flex-shrink-0" style={{ color: "#dc2626" }} />;
  if (["doc", "docx"].includes(ext)) return <FileText className="h-4 w-4 flex-shrink-0" style={{ color: "#2563eb" }} />;
  if (["xls", "xlsx", "csv"].includes(ext)) return <Table2 className="h-4 w-4 flex-shrink-0" style={{ color: "#059669" }} />;
  if (["ppt", "pptx", "key"].includes(ext)) return <Presentation className="h-4 w-4 flex-shrink-0" style={{ color: "#ea580c" }} />;
  return <File className="h-4 w-4 flex-shrink-0" style={{ color: "var(--ink-400)" }} />;
}


function getGroupMeta(title: string): { Icon: React.ComponentType<any>; color: string; en: string } {
  const map: Record<string, { Icon: React.ComponentType<any>; color: string; en: string }> = {
    "学术论文": { Icon: BookOpen, color: "#4f46e5", en: "Academic" },
    "实验报告": { Icon: FlaskConical, color: "#0891b2", en: "Experiment" },
    "教学材料": { Icon: Presentation, color: "#059669", en: "Teaching" },
    "述职报告": { Icon: TrendingUp, color: "#d97706", en: "Review" },
    "商业计划": { Icon: Briefcase, color: "#2563eb", en: "Business" },
    "会议总结": { Icon: Users, color: "#64748b", en: "Meeting" },
    "个人简历": { Icon: User, color: "#db2777", en: "Resume" },
    "法定公文": { Icon: Scale, color: "#b91c1c", en: "Legal" },
    "企业制度": { Icon: Building2, color: "#f59e0b", en: "Policy" },
    "产品文档": { Icon: Package, color: "#0ea5e9", en: "Product" },
    "测试报告": { Icon: Bug, color: "#84cc16", en: "Testing" },
    "运维报告": { Icon: Server, color: "#14b8a6", en: "Ops" },
    "文学创作": { Icon: PenTool, color: "#e11d48", en: "Writing" },
  };
  return map[title] || { Icon: FileText, color: "var(--ink-400)", en: "Doc" };
}

// ── Style meta map ─────────────────────────────────────────────────────────-
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
  const [showRaw, setShowRaw] = useState(false);
  const [eta, setEta] = useState(10);

  const steps = [
    { key: "uploading", label: "读取文件", desc: "提取文本与结构信号" },
    { key: "extracting", label: "抽取结构", desc: "识别标题、表格、图示" },
    { key: "analyzing", label: "深度解析", desc: "抽象骨架、叙事与语体" },
    { key: "ready", label: "解析完成", desc: "可保存为模板 Skill" },
  ];
  const activeIndex = Math.max(
    0,
    steps.findIndex((s) => s.key === (status === "saving" || status === "saved" ? "ready" : status))
  );
  const isWorking = ["uploading", "extracting", "analyzing", "saving"].includes(status);
  const isReady = status === "ready" || status === "saved";

  useEffect(() => {
    if (!isWorking) return;
    const total = 10;
    const start = Date.now();
    const id = window.setInterval(() => {
      const elapsed = (Date.now() - start) / 1000;
      setEta(Math.max(1, Math.ceil(total - elapsed)));
    }, 1000);
    return () => window.clearInterval(id);
  }, [isWorking, status]);

  const insights = useMemo(() => {
    const msgs: string[] = [];
    if (!analysis) {
      return [
        "正在读取文件内容…",
        "正在识别标题层级与章节骨架…",
        "正在推断文档类型与叙事框架…",
        "正在分析目标受众与核心意图…",
        "正在抽象写作语体与段落密度…",
        "正在提取表格结构与图示作用…",
        "正在生成可复用的 SKILL 规范…",
      ];
    }
    const styleMeta = DOC_STYLE_META[analysis?.detected_style ?? ""] ?? DOC_STYLE_META["custom-document"];
    msgs.push(`已识别为「${styleMeta.label}」类型`);
    const hc = analysis?.heading_count ?? 0;
    if (hc) msgs.push(`提取到 ${hc} 个章节标题，构建完整骨架`);
    const tr = analysis?.table_like_rows ?? 0;
    if (tr) msgs.push(`检测到 ${tr} 处表格/列表结构`);
    const narrative = analysis?.narrative_framework?.name;
    if (narrative) msgs.push(`叙事框架：${narrative}`);
    const pattern = analysis?.argumentation_pattern?.pattern;
    if (pattern) msgs.push(`论证模式：${pattern}`);
    const reader = analysis?.audience_intent?.target_reader;
    if (reader) msgs.push(`目标读者：${reader}`);
    const intent = analysis?.audience_intent?.intent;
    if (intent) msgs.push(`使用意图：${intent}`);
    const concerns = analysis?.audience_intent?.core_concerns;
    if (Array.isArray(concerns) && concerns.length) msgs.push(`核心关注点：${concerns.join("、")}`);
    const skeleton = analysis?.macro_structure?.section_skeleton;
    if (Array.isArray(skeleton) && skeleton.length) msgs.push(`章节骨架：${skeleton.slice(0, 5).join(" → ")}${skeleton.length > 5 ? "…" : ""}`);
    const visual = analysis?.visual_force;
    if (Array.isArray(visual) && visual.length) {
      visual.slice(0, 2).forEach((v: any) => msgs.push(`${v.type}：${v.function}`));
    }
    const register = analysis?.writing_register?.register_summary;
    if (register) msgs.push(`写作语体：${register}`);
    msgs.push("已生成可复用 SKILL 规范，保存后即可用于后续生成");
    return msgs;
  }, [analysis]);

  const marqueeText = insights.join("    ·    ");
  const styleMeta = DOC_STYLE_META[analysis?.detected_style ?? ""] ?? DOC_STYLE_META["custom-document"];
  const progressPct = Math.min(((activeIndex + (isWorking ? 0.6 : 1)) / steps.length) * 100, 100);

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center px-4"
      style={{ background: "rgba(17,24,39,0.45)", backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)" }}>
      <div className="w-full max-w-[520px] max-h-[90vh] rounded-2xl overflow-hidden flex flex-col"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "0 24px 70px rgba(0,0,0,0.28)" }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg flex items-center justify-center"
              style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
              <FileSearch className="h-4 w-4" />
            </div>
            <div>
              <div style={{ color: "var(--ink-900)", fontWeight: 700, fontSize: 14 }}>解析自定义文档模板</div>
              <div style={{ color: "var(--ink-400)", fontSize: 11, marginTop: 1 }}>{fileName || "待上传文件"}</div>
            </div>
          </div>
          <button onClick={onClose}
            className="h-8 w-8 rounded-lg flex items-center justify-center transition hover:bg-[var(--hover)]"
            style={{ color: "var(--ink-500)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-5 flex flex-col gap-5 min-h-0 overflow-y-auto">
          {error ? (
            <div className="rounded-xl p-3"
              style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.24)", color: "#dc2626", fontSize: 12.5, lineHeight: 1.55 }}>
              {error}
            </div>
          ) : (
            <>
              {/* Progress */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>{steps[activeIndex].label}</span>
                  {isWorking ? (
                    <span style={{ fontSize: 12, color: "var(--ink-400)" }}>预计剩余 {eta} 秒</span>
                  ) : isReady ? (
                    <span style={{ fontSize: 12, color: "#059669", fontWeight: 700 }}>✓ 解析完成</span>
                  ) : null}
                </div>
                <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-subtle)" }}>
                  <div className="h-full transition-all duration-700"
                    style={{ width: `${progressPct}%`, background: "linear-gradient(90deg, var(--brand), #7c3aed)" }} />
                </div>
                <div className="flex justify-between mt-2">
                  {steps.map((s, i) => (
                    <div key={s.key} style={{ fontSize: 10, fontWeight: i === activeIndex ? 700 : 500, color: i <= activeIndex ? "var(--brand)" : "var(--ink-300)" }}>
                      {s.label}
                    </div>
                  ))}
                </div>
              </div>

              {/* Marquee ticker */}
              <div className="relative overflow-hidden rounded-lg h-9 flex items-center"
                style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                <div className="whitespace-nowrap animate-marquee flex items-center"
                  style={{ fontSize: 11.5, color: "var(--ink-400)", lineHeight: 1 }}>
                  <span className="inline-block pr-16">{marqueeText}</span>
                  <span className="inline-block pr-16">{marqueeText}</span>
                </div>
                <style>{`
                  @keyframes parse-marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
                  .animate-marquee { animation: parse-marquee 28s linear infinite; }
                `}</style>
              </div>

              {/* Summary cards */}
              {isReady && analysis && (
                <div className="space-y-3">
                  {/* Style badge + metrics */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold"
                      style={{ background: styleMeta.bg, border: `1px solid ${styleMeta.border}`, color: styleMeta.color }}>
                      <FileText className="h-3 w-3" /> {styleMeta.label}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded-md text-[10px]"
                        style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-500)" }}>
                        {analysis?.heading_count ?? 0} 个标题
                      </span>
                      <span className="px-2 py-0.5 rounded-md text-[10px]"
                        style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-500)" }}>
                        {analysis?.table_like_rows ?? 0} 处表格
                      </span>
                      <span className="px-2 py-0.5 rounded-md text-[10px]"
                        style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-500)" }}>
                        {(analysis?.visual_force?.length ?? 0)} 个图示
                      </span>
                    </div>
                  </div>

                  {/* Skeleton */}
                  {Array.isArray(analysis?.macro_structure?.section_skeleton) && analysis.macro_structure.section_skeleton.length > 0 && (
                    <div className="rounded-xl p-3" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 8 }}>📋 章节骨架</div>
                      <div className="space-y-1.5">
                        {analysis.macro_structure.section_skeleton.slice(0, 6).map((s: string, i: number) => (
                          <div key={i} className="flex items-center gap-2">
                            <div className="h-5 w-5 rounded flex-shrink-0 flex items-center justify-center"
                              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", fontSize: 10, color: "var(--ink-500)", fontWeight: 700 }}>
                              {i + 1}
                            </div>
                            <div className="truncate text-[12px]" style={{ color: "var(--ink-700)" }} title={s}>{s}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Audience + Argument */}
                  <div className="grid grid-cols-2 gap-2">
                    {analysis?.audience_intent && (
                      <div className="rounded-xl p-3" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                        <div style={{ fontSize: 10, color: "var(--ink-400)", fontWeight: 700, marginBottom: 3 }}>🎯 目标读者</div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-900)" }}>{analysis.audience_intent.target_reader}</div>
                        <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2, lineHeight: 1.45 }}>{analysis.audience_intent.intent}</div>
                      </div>
                    )}
                    {analysis?.argumentation_pattern && (
                      <div className="rounded-xl p-3" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                        <div style={{ fontSize: 10, color: "var(--ink-400)", fontWeight: 700, marginBottom: 3 }}>🧩 论证模式</div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-900)" }}>{analysis.argumentation_pattern.pattern}</div>
                        <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2, lineHeight: 1.45 }}>{analysis.argumentation_pattern.description}</div>
                      </div>
                    )}
                  </div>

                  {/* Visual force */}
                  {Array.isArray(analysis?.visual_force) && analysis.visual_force.length > 0 && (
                    <div className="rounded-xl p-3" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 8 }}>🖼️ 图示作用力</div>
                      <div className="space-y-2">
                        {analysis.visual_force.slice(0, 3).map((v: any, i: number) => (
                          <div key={i} className="flex items-start gap-2">
                            <div className="h-1.5 w-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: "var(--brand)" }} />
                            <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.5 }}>
                              <span style={{ fontWeight: 600 }}>{v.type}</span> — {v.function}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Skill name */}
              {isReady && (
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-500)" }}>模板 Skill 名称</label>
                  <input
                    value={skillName}
                    onChange={(e) => onNameChange(e.target.value)}
                    className="mt-1.5 w-full h-10 px-3 rounded-lg outline-none transition"
                    style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)", fontSize: 13 }}
                    placeholder="例如：2026-述职报告模板"
                  />
                </div>
              )}

              {/* Collapsible raw editor */}
              {isReady && (
                <div>
                  <button
                    onClick={() => setShowRaw((v) => !v)}
                    className="text-[12px] font-medium transition hover:opacity-80"
                    style={{ color: "var(--brand)" }}
                  >
                    {showRaw ? "收起 SKILL 原文 ▲" : "查看 / 编辑 SKILL 原文 ▼"}
                  </button>
                  {showRaw && (
                    <textarea
                      value={content}
                      onChange={(e) => onContentChange(e.target.value)}
                      className="mt-2 w-full min-h-[240px] p-3 rounded-lg outline-none resize-y"
                      style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-900)", fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", fontSize: 12, lineHeight: 1.6 }}
                    />
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t" style={{ borderColor: "var(--border)" }}>
          <div style={{ fontSize: 11, color: "var(--ink-400)", lineHeight: 1.5 }}>
            {savedName ? `✓ 已保存为：${savedName}` : "保存后，Agent 生成文档时将自动引用该模板"}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="h-9 px-4 rounded-lg transition hover:bg-[var(--hover)]"
              style={{ color: "var(--ink-600)", border: "1px solid var(--border)", fontSize: 13 }}>
              关闭
            </button>
            {isReady && (
              <button
                onClick={onSave}
                disabled={!skillName.trim() || !content.trim()}
                className="h-9 px-4 rounded-lg disabled:opacity-50 flex items-center gap-1.5 font-semibold transition hover:opacity-90"
                style={{ background: "var(--ink-900)", color: "#fff", fontSize: 13 }}>
                <Check className="h-3.5 w-3.5" />
                {savedName ? "重新保存" : "保存模板 Skill"}
              </button>
            )}
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
