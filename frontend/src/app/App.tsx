import { useState, useEffect, useMemo, useRef, memo, useDeferredValue } from "react";
import { Sidebar, PageKey } from "./components/Sidebar";
import { ChatInput } from "./components/ChatInput";
import { SuggestionChips, ScenarioSuggestion } from "./components/SuggestionChips";
import { Sparkles, ThumbsUp, ThumbsDown, MessageCircle, Code2, Copy, Play, X, CheckCircle2, Circle, Loader2, FileCode2, Download, Pencil, File, ChevronRight, Terminal, FileSearch, PenLine, ClipboardCheck, RotateCcw, Database } from "lucide-react";
import { TemplatePage, docsConfig } from "./components/TemplatePage";
import KnowledgeGraphPage from "./components/KnowledgeGraphPage";
import SentimentPage from "./components/SentimentPage";
import HtmlPage from "./components/HtmlPage";
import TechIntroModal from "./components/TechIntroModal";
import { WelcomeModal, useWelcomeModal } from "./components/WelcomeModal";
import LabPage from "./components/LabPage";
import { DataSourcePage } from "./components/DataSourcePage";
import { DatabaseQueryCard } from "./components/DatabaseQueryCard";
import { PlanStepper, StepItem, ThinkingBlock, TypingText, stripPlanStepNumber as stripStep } from "./components/PlanStepper";
import { LoginModal } from "./components/LoginModal";
import { SearchHistoryPanel } from "./components/SearchHistoryPanel";
import { api, ChatMessage, DocumentPlan, ReportDetail, ReportItem, ReportPreview, UserInfo } from "./lib/api";
import katex from "katex";
import "katex/dist/katex.min.css";

export interface Conversation {
  id: string;
  title: string;
  preview: string;
  time: string;
  group: "今天" | "昨天" | "7 天内" | "30 天内" | "更早";
  tags?: string[];
  pinned?: boolean;
  running?: boolean;
}

type SubmitPayload = {
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
  effort?: string;
  mode?: "chat" | "agent";
  skills?: string[];
  executionMode?: "direct" | "plan";
  database?: string | null;
};

type DocumentPlanQuestion = {
  id: string;
  question: string;
  type: "text" | "single_choice" | "multi_choice";
  options: string[];
  defaultAnswer: string;
};

function normalizeDocumentPlanQuestions(plan?: DocumentPlan | null): DocumentPlanQuestion[] {
  if (!plan?.should_ask) return [];
  return (plan.questions || []).map((item, index) => {
    if (typeof item === "string") {
      const isYesNo = /(是否|是不是|能否|可否|要不要|需要不需要|需不需要|有没有|确认.*吗|吗[？?]?$)/.test(item);
      return {
        id: `${index}-${item}`,
        question: item,
        type: isYesNo ? "single_choice" as const : "text" as const,
        options: isYesNo ? ["是", "否", "暂不确定"] : [],
        defaultAnswer: "",
      };
    }
    const question = String(item?.question || "").trim();
    const options = Array.isArray(item?.options)
      ? item.options.map((option) => String(option || "").trim()).filter(Boolean)
      : [];
    const rawType = item?.type;
    const type: DocumentPlanQuestion["type"] =
      rawType === "multi_choice" && options.length >= 2 ? "multi_choice" :
      rawType === "single_choice" && options.length >= 2 ? "single_choice" : "text";
    return {
      id: `${index}-${question}`,
      question,
      type,
      options: type !== "text" ? options : [],
      defaultAnswer: String(item?.default_answer || "").trim(),
    };
  }).filter((item) => item.question);
}

type ChatArtifact = {
  type: "code" | "document" | "ppt" | "sheet";
  title: string;
  language?: string;
  content: string;
};

type DocumentWorkspacePending = {
  prompt: string;
  payload: SubmitPayload;
  uploadedIds: number[];
};

type DocumentWorkspaceState = {
  status: "planning" | "running" | "completed" | "error";
  prompt: string;
  title: string;
  reportId?: number;
  report?: ReportItem;
  pending?: DocumentWorkspacePending;
  answers?: string;
  plan?: DocumentPlan;
  initialMarkdown?: string;
  initialActivities?: DocumentActivity[];
  createdAt?: string;
  planError?: string;
  error?: string;
};

type DocumentActivity = {
  id: string;
  kind: "status" | "thinking" | "tool" | "section" | "summary" | "node" | "db_query";
  title: string;
  content?: string;
  meta?: string;
};

function FeatureInProgressPage({ title, etaText = "预期 2 月内上线" }: { title: string; etaText?: string }) {
  return (
    <div className="min-h-full flex items-center justify-center px-6 py-20">
      <div
        className="w-full max-w-[640px] rounded-2xl border p-8 text-center"
        style={{
          background: "var(--bg-panel, #fff)",
          borderColor: "var(--border)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div className="text-[14px] font-semibold" style={{ color: "var(--ink-500)" }}>
          功能正在开发中
        </div>
        <h2 className="mt-3 text-[24px] font-semibold tracking-[-0.02em]" style={{ color: "var(--ink-900)" }}>
          {title} 暂不可访问
        </h2>
        <p className="mt-3 text-[14px] leading-6" style={{ color: "var(--ink-600)" }}>
          该模块功能正在开发中，{etaText}。当前请先使用「文档」能力完成研究交付。
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [page, setPage] = useState<PageKey>("home");
  const [isLoggedIn, setIsLoggedIn] = useState(api.isLoggedIn);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [showSearchHistory, setShowSearchHistory] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<ScenarioSuggestion | null>(null);
  const [showHomeContent, setShowHomeContent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [documentWorkspace, setDocumentWorkspace] = useState<DocumentWorkspaceState | null>(null);
  const [techModalOpen, setTechModalOpen] = useState(false);
  const [techModalInitialId, setTechModalInitialId] = useState<string | undefined>();
  const { show: showWelcome, dismiss: dismissWelcome } = useWelcomeModal();
  const cancelledConversationsRef = useRef<Set<string>>(new Set());
  const activeConversationRef = useRef<string | null>(null);
  const busyTokenRef = useRef<string | null>(null);
  const [externalSearchEnabled, setExternalSearchEnabled] = useState<boolean | null>(null);
  useEffect(() => {
    activeConversationRef.current = activeConversationId;
  }, [activeConversationId]);

  useEffect(() => {
    api.systemCapabilities().then((caps) => {
      setExternalSearchEnabled(caps.external_search_enabled);
    }).catch(() => {
      setExternalSearchEnabled(false);
    });
  }, []);

  const handlePinConversation = (id: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, pinned: !c.pinned } : c))
    );
  };

  const handleDeleteConversation = (id: string) => {
    cancelledConversationsRef.current.add(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id || String(activeChatId) === id) {
      setActiveChatId(null);
      setActiveConversationId(null);
      activeConversationRef.current = null;
      setChatMessages([]);
      busyTokenRef.current = null;
      setBusy(false);
      setPage("home");
      setShowSearchHistory(false);
    }
    const reportId = Number(id);
    if (Number.isFinite(reportId)) {
      void api.deleteReport(reportId).catch(() => {
        // Keep the optimistic UI removal; a later refresh can reconcile.
      });
    }
  };

  const handleNewConversation = () => {
    setActiveChatId(null);
    setActiveConversationId(null);
    activeConversationRef.current = null;
    setChatMessages([]);
    busyTokenRef.current = null;
    setBusy(false);
    setSelectedScenario(null);
    setShowSearchHistory(false);
    setPage("home");
    setShowHomeContent(true);
  };

  useEffect(() => {
    if (!api.isLoggedIn) {
      setConversations([]);
      return;
    }
    void refreshUserAndReports();
  }, []);

  async function refreshUserAndReports() {
    try {
      const [me, list] = await Promise.all([api.me(), api.listReports()]);
      setUser(me);
      setIsLoggedIn(true);
      setConversations(mapReportsToConversations(list.reports));
    } catch {
      setIsLoggedIn(false);
      setUser(null);
      setConversations([]);
    }
  }

  const handleLogout = () => {
    api.clearToken();
    setUser(null);
    setIsLoggedIn(false);
    setConversations([]);
    setShowSearchHistory(false);
    setShowLogin(true);
  };
  const handleLogin = async (authId: string, password: string) => {
    await api.login(authId, password);
    setShowLogin(false);
    await refreshUserAndReports();
  };
  const handleRegister = async (payload: {
    auth_id: string;
    username: string;
    department: string;
    password: string;
  }) => {
    await api.register(payload);
    await handleLogin(payload.auth_id, payload.password);
  };
  const handleNeedLogin = () => setShowLogin(true);

  const recoverStreamedChat = async ({
    reportId,
    prompt,
    localConversationId,
    visibleConversationIds,
  }: {
    reportId: number;
    prompt: string;
    localConversationId: string;
    visibleConversationIds: string[];
  }) => {
    let recoveredReportId = Number.isFinite(reportId) ? reportId : null;
    // Progressive backoff: first 6 attempts every 900 ms, then give up.
    // Reduced from 25 to 6 — if the model hasn't committed a response in ~5 s
    // it likely failed; the old 41-second window just left the UI stuck.
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const delay = attempt < 3 ? 900 : 1500;
      if (attempt > 0) await new Promise((resolve) => window.setTimeout(resolve, delay));
      if (!recoveredReportId) {
        try {
          const list = await api.listReports();
          const title = prompt.slice(0, 100);
          const matched = list.reports.find((report) => (
            report.title === title &&
            (report.output_format === "chat" || report.report_type === "普通问答")
          ));
          if (matched?.id) recoveredReportId = matched.id;
        } catch {
          // Keep retrying; the report may not be visible in the list yet.
        }
      }
      if (!recoveredReportId) continue;
      const realId = String(recoveredReportId);
      if (cancelledConversationsRef.current.has(localConversationId) || cancelledConversationsRef.current.has(realId)) return true;
      try {
        const report = await api.getReport(Number(realId));
        // If the report failed, stop polling immediately — no assistant message will appear.
        if (report.status === "failed") return false;
        const messages = await api.listMessages(recoveredReportId);
        const visibleMessages = messages.filter((m) => m.role !== "system");
        const assistant = [...visibleMessages].reverse().find((m) => m.role === "assistant" && m.content.trim());
        if (!assistant) continue;
        const isVisible = visibleConversationIds.includes(activeConversationRef.current || "");
        if (isVisible) {
          setActiveChatId(recoveredReportId);
          setActiveConversationId(realId);
          activeConversationRef.current = realId;
          setChatMessages(visibleMessages);
        }
        setConversations((prev) => [
          {
            id: realId,
            title: prompt.slice(0, 100),
            preview: buildAnswerPreview(assistant.content),
            time: formatConversationTime(assistant.created_at),
            group: "今天",
            tags: ["问答"],
            running: false,
          },
          ...prev.filter((c) => c.id !== localConversationId && c.id !== realId),
        ]);
        return true;
      } catch {
        // The stream may have closed before the DB commit became visible; retry briefly.
      }
    }
    return false;
  };

  const startDocumentWorkspaceReport = async (
    pending: DocumentWorkspacePending,
    answers = "",
  ) => {
    const prompt = answers.trim()
      ? `${pending.prompt}\n\n用户补充确认：\n${answers.trim()}`
      : pending.prompt;
    const suffix = [
      pending.payload.modelId ? `模型：${pending.payload.modelId}` : "",
      pending.payload.template ? `文档模板：${pending.payload.template}` : "",
      pending.payload.database ? `专业数据库：${pending.payload.database}` : "",
      pending.payload.scenario ? `类型：${pending.payload.scenario}` : "",
      pending.payload.executionMode === "plan" ? "执行方式：已确认计划后执行" : "执行方式：直接执行",
    ].filter(Boolean).join("\n");
    setBusy(true);
    setDocumentWorkspace((prev) => ({
      ...(prev || {
        status: "running",
        prompt: pending.prompt,
        title: pending.prompt.slice(0, 36) || "文档任务",
      }),
      status: "running",
      prompt: pending.prompt,
      title: pending.prompt.slice(0, 36) || "文档任务",
      answers,
      pending,
      error: undefined,
    }));
    try {
      const report = await api.createReport({
        title: pending.prompt.slice(0, 100),
        brief: suffix ? `${prompt}\n\n${suffix}` : prompt,
        report_type: pending.payload.template || "文档",
        output_format: "word",
        uploaded_files: pending.uploadedIds,
        model_id: pending.payload.modelId || undefined,
        effort: pending.payload.effort || "low",
        skills: pending.payload.skills || [],
        skip_clarify: true,
      });
      const conversation = reportToConversation(report);
      setConversations((prev) => [{ ...conversation, running: true }, ...prev.filter((c) => c.id !== conversation.id)]);
      setDocumentWorkspace((prev) => prev ? {
        ...prev,
        status: "running",
        reportId: report.id,
        report,
        error: undefined,
      } : null);
    } catch (error) {
      setDocumentWorkspace((prev) => prev ? {
        ...prev,
        status: "error",
        error: error instanceof Error ? error.message : "文档任务启动失败",
      } : null);
    } finally {
      setBusy(false);
    }
  };

  const detectInternetQuery = (prompt: string): boolean => {
    const patterns = [
      /今天.*天气|天气.*今天|明天.*天气|后天.*天气|现在.*天气|最近.*天气|天气怎么样/,
      /今天.*几号|今天.*日期|今天.*星期|现在.*时间|当前.*时间|现在几点/,
      /最新.*新闻|今日.*新闻|今天.*发生了什么|最近.*新闻|实时.*新闻/,
      /股价|股票.*价格|比特币|加密货币.*价格|汇率.*今天|今天.*汇率/,
      /最新.*消息|今天.*头条|实时.*行情|最新.*行情/,
    ];
    return patterns.some((p) => p.test(prompt));
  };

  const handleCreateReport = async (payload: SubmitPayload) => {
    if (!isLoggedIn) {
      handleNeedLogin();
      return;
    }
    const prompt = payload.prompt.trim();
    if (!prompt) return;
    const busyToken = `busy-${Date.now()}`;
    busyTokenRef.current = busyToken;
    setBusy(true);
    try {
      const uploadedIds: number[] = [];
      if (payload.templateFile && !payload.templateFileId) {
        const uploaded = await api.uploadFile(payload.templateFile, undefined, true);
        uploadedIds.push(uploaded.id);
      }
      if (payload.templateFileId && !uploadedIds.includes(payload.templateFileId)) {
        uploadedIds.push(payload.templateFileId);
      }
      for (const file of payload.files || []) {
        const uploaded = await api.uploadFile(file);
        uploadedIds.push(uploaded.id);
      }
      if (payload.outputFormat === "word" && payload.mode !== "chat") {
        const pending = { prompt, payload, uploadedIds };
        const title = prompt.slice(0, 36) || "文档任务";
        setPage("docs");
        setShowSearchHistory(false);
        if (payload.executionMode === "direct") {
          setDocumentWorkspace({
            status: "running",
            prompt,
            title,
            pending,
          });
          await startDocumentWorkspaceReport(pending);
        } else {
          setDocumentWorkspace({
            status: "planning",
            prompt,
            title,
            pending,
          });
        }
        return;
      }
      if (payload.mode === "chat") {
        const assistantId = `assistant-${Date.now()}`;
        const localConversationId = `local-${Date.now()}`;
        const pendingUserMessage: ChatMessage = {
          id: `pending-${Date.now()}`,
          role: "user",
          content: prompt,
          attachedFiles: (payload.files || []).map((f) => ({
            name: f.name,
            size: formatFileSize(f.size),
          })),
        };

        // If external search is disabled and the query requires live internet data,
        // short-circuit with a helpful offline notice instead of hitting the LLM.
        if (externalSearchEnabled === false && detectInternetQuery(prompt)) {
          setChatMessages((prev) => [
            ...prev,
            pendingUserMessage,
            {
              id: `offline-notice-${Date.now()}`,
              role: "assistant" as const,
              content: "当前**联网搜索能力**尚未开启，无法获取实时信息（天气、新闻、行情等）。\n\n如需使用联网功能，请联系管理员在后台开启 **外部搜索** 配置。您也可以改为询问知识库中已有的内容，或上传相关文件后再提问。",
              created_at: new Date().toISOString(),
            },
          ]);
          setBusy(false);
          busyTokenRef.current = null;
          setShowSearchHistory(false);
          setPage("home");
          return;
        }

        const pendingAssistantMessage: ChatMessage = {
          id: assistantId,
          role: "assistant",
          content: "",
          streaming: true,
        };
        setChatMessages((prev) => [...prev, pendingUserMessage, pendingAssistantMessage]);
        setActiveConversationId(localConversationId);
        activeConversationRef.current = localConversationId;
        setShowSearchHistory(false);
        setPage("home");
        setConversations((prev) => [
          {
            id: localConversationId,
            title: prompt.slice(0, 100),
            preview: "DataAgent 正在回复...",
            time: "刚刚",
            group: "今天",
            tags: ["问答"],
            running: true,
          },
          ...prev.filter((c) => c.id !== localConversationId),
        ]);
        try {
          const result = await api.sendChat({
            prompt,
            model_id: payload.modelId || undefined,
            effort: payload.effort || "low",
            conversation_id: activeChatId || undefined,
            uploaded_files: uploadedIds,
          });
          if (cancelledConversationsRef.current.has(localConversationId)) return;
          const realId = String(result.report_id);
          setActiveChatId(result.report_id);
          setActiveConversationId(realId);
          activeConversationRef.current = realId;
          const visible = result.messages.filter((m) => m.role !== "system");
          if (visible.length > 0) {
            setChatMessages(visible);
          } else {
            setChatMessages((prev) => prev.map((m) =>
              m.id === assistantId ? { ...m, content: result.answer, streaming: false } : m
            ));
          }
          const conversation = reportToConversation({
            id: result.report_id,
            title: prompt.slice(0, 100),
            brief: result.answer,
            output_format: "chat",
            report_type: "普通问答",
            status: "completed",
            progress: 1,
            phase: "已回复",
          });
          setConversations((prev) => [
            { ...conversation, running: false },
            ...prev.filter((c) => c.id !== localConversationId && c.id !== conversation.id),
          ]);
        } catch (error) {
          if (cancelledConversationsRef.current.has(localConversationId)) return;
          const errMsg = error instanceof Error ? error.message : "回答失败，请重试";
          setChatMessages((prev) => prev.map((m) =>
            m.id === assistantId ? { ...m, content: errMsg, streaming: false } : m
          ));
          setConversations((prev) => prev.map((c) =>
            c.id === localConversationId
              ? { ...c, preview: "回复失败，请重试", running: false }
              : c
          ));
        }
        return;
      }
      const suffix = [
        payload.modelId ? `模型：${payload.modelId}` : "",
        payload.template ? `模板：${payload.template}` : "",
        payload.scenario ? `类型：${payload.scenario}` : "",
        payload.pageRange ? `页数：${payload.pageRange}` : "",
        payload.wordCount ? `字数：${payload.wordCount}` : "",
      ].filter(Boolean).join("\n");
      const report = await api.createReport({
        title: prompt.slice(0, 100),
        brief: suffix ? `${prompt}\n\n${suffix}` : prompt,
        output_format: payload.outputFormat,
        uploaded_files: uploadedIds,
        model_id: payload.modelId || undefined,
        effort: payload.effort || "low",
        skills: payload.skills || [],
      });
      const conversation = reportToConversation(report);
      setConversations((prev) => [conversation, ...prev.filter((c) => c.id !== conversation.id)]);
      setShowSearchHistory(true);
    } finally {
      if (busyTokenRef.current === busyToken) {
        busyTokenRef.current = null;
        setBusy(false);
      }
    }
  };

  const handleSelectConversation = async (id: string) => {
    const conversation = conversations.find((c) => c.id === id);
    setShowSearchHistory(false);
    const reportId = Number(id);
    if (!Number.isFinite(reportId)) return;
    setActiveChatId(reportId);
    setActiveConversationId(id);
    activeConversationRef.current = id;
    setBusy(true);
    try {
      const report = await api.getReport(reportId);
      if (isDocumentReport(report)) {
        setPage("docs");
        setChatMessages([]);
        setDocumentWorkspace(workspaceFromReport(report));
        return;
      }
      setPage("home");
      setDocumentWorkspace(null);
      const messages = await api.listMessages(reportId);
      const visibleMessages = messages.filter((m) => m.role !== "system");
      if (visibleMessages.length > 0) {
        setChatMessages(visibleMessages);
      } else if (conversation) {
        setChatMessages([{
          id: `history-${id}`,
          role: "assistant",
          content: conversation.preview || "这条历史记录暂无可展示的对话内容。",
        }]);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleRegenerateChatMessage = async (messageId: number | string, prompt: string) => {
    if (!isLoggedIn) {
      handleNeedLogin();
      return;
    }
    if (busy) return;
    const numericMessageId = Number(messageId);
    const sourceMessage = chatMessages.find((m) => String(m.id) === String(messageId));
    const reportId = Number(sourceMessage?.report_id || activeChatId);
    const cleanPrompt = prompt.trim();
    if (!Number.isFinite(reportId) || !Number.isFinite(numericMessageId) || !cleanPrompt) return;

    const idx = chatMessages.findIndex((m) => String(m.id) === String(messageId));
    if (idx < 0) return;

    const assistantId = `regen-${Date.now()}`;
    const busyToken = `regen-${Date.now()}`;
    busyTokenRef.current = busyToken;
    setBusy(true);
    setChatMessages((prev) => {
      const currentIdx = prev.findIndex((m) => String(m.id) === String(messageId));
      if (currentIdx < 0) return prev;
      return [
        ...prev.slice(0, currentIdx),
        { ...prev[currentIdx], content: cleanPrompt },
        { id: assistantId, role: "assistant" as const, content: "", streaming: true },
      ];
    });
    setConversations((prev) => prev.map((c) =>
      c.id === String(reportId) ? { ...c, preview: "DataAgent 正在重新回复...", running: true } : c
    ));

    try {
      const result = await api.regenerateChat({
        report_id: reportId,
        message_id: numericMessageId,
        prompt: cleanPrompt,
      });
      const visible = result.messages.filter((m) => m.role !== "system");
      setChatMessages(visible.length > 0 ? visible : [{ id: assistantId, role: "assistant", content: result.answer }]);
      const conversation = reportToConversation({
        id: result.report_id,
        title: cleanPrompt.slice(0, 100),
        brief: result.answer,
        output_format: "chat",
        report_type: "普通问答",
        status: "completed",
        progress: 1,
        phase: "已回复",
      });
      setConversations((prev) => [
        { ...conversation, running: false },
        ...prev.filter((c) => c.id !== conversation.id),
      ]);
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : "重新回复失败，请重试";
      setChatMessages((prev) => prev.map((m) =>
        m.id === assistantId ? { ...m, content: errMsg, streaming: false } : m
      ));
      setConversations((prev) => prev.map((c) =>
        c.id === String(reportId) ? { ...c, preview: "重新回复失败，请重试", running: false } : c
      ));
    } finally {
      if (busyTokenRef.current === busyToken) {
        busyTokenRef.current = null;
        setBusy(false);
      }
    }
  };

  const handlePageSelect = (pageKey: PageKey) => {
    if (false && !isLoggedIn) { // auth guard handled per-page
      setShowLogin(true);
      return;
    }
    // Only reset animation when switching TO home from another page
    if (pageKey === "home" && page !== "home") {
      setShowHomeContent(false);
    }
    if (pageKey !== "home") {
      setChatMessages([]);
      setActiveChatId(null);
    }
    setPage(pageKey);
    setShowSearchHistory(false);
  };

  const [greetingInfo] = useState(() => getGreetingInfo());
  const greetingName = shortGreetingName(user?.username || user?.auth_id || "");

  // Home page typing animation
  useEffect(() => {
    if (page === "home") {
      setShowHomeContent(false);
      const timer = setTimeout(() => {
        setShowHomeContent(true);
      }, 1800); // Show content after typing animation (1.8s)
      return () => clearTimeout(timer);
    }
  }, [page]);

  const renderPage = () => {
    switch (page) {
      case "ppt":
        return <FeatureInProgressPage title="PPT" />;
      case "docs":
        if (documentWorkspace) {
          return (
            <DocumentWorkspace
              key={documentWorkspace.prompt || documentWorkspace.title}
              workspace={documentWorkspace}
              busy={busy}
              onBack={() => setDocumentWorkspace(null)}
              onStart={(answers) => {
                if (documentWorkspace.pending) void startDocumentWorkspaceReport(documentWorkspace.pending, answers);
              }}
              onUpdate={(patch) => setDocumentWorkspace((prev) => prev ? { ...prev, ...patch } : prev)}
            />
          );
        }
	        return <TemplatePage config={docsConfig} onSubmit={handleCreateReport} busy={busy}
	          onOpenTechIntro={(id) => { setTechModalInitialId(id); setTechModalOpen(true); }}
	          onOpenDatabasePage={() => handlePageSelect("datasource")} />;
      case "sheet":
        return <FeatureInProgressPage title="表格" />;
	      case "knowledge_graph":
	      case "sentiment":
	        // Legacy aliases → unified Lab page
	        return <LabPage onOpenTechIntro={(id) => { setTechModalInitialId(id); setTechModalOpen(true); }} />;
	      case "datasource":
	        return <DataSourcePage />;
      case "lab":
        return <LabPage onOpenTechIntro={(id) => { setTechModalInitialId(id); setTechModalOpen(true); }} />;
	      case "html":
        return (
          <HtmlPage
            onOpenTechIntro={(id) => { setTechModalInitialId(id); setTechModalOpen(true); }}
          />
        );
      case "home":
      default:
        if (chatMessages.length > 0) {
          return (
            <ChatConversationView
              messages={chatMessages}
              busy={busy}
              isLoggedIn={isLoggedIn}
              onNeedLogin={handleNeedLogin}
              onSubmit={handleCreateReport}
              onRegenerate={handleRegenerateChatMessage}
            />
          );
        }
        return (
          <div className="min-h-full flex flex-col items-center justify-center px-5 py-16 relative">
            <div
              className="absolute inset-x-0 top-0 h-[45vh] pointer-events-none"
              style={{
                background:
                  "radial-gradient(ellipse 45% 35% at 50% 0%, rgba(91,78,232,0.04) 0%, transparent 70%)",
              }}
            />
            <div className="w-full max-w-[740px] flex flex-col items-center relative">
              <style>{`
                @keyframes gradient-flow {
                  0% { background-position: 0% 50%; }
                  50% { background-position: 100% 50%; }
                  100% { background-position: 0% 50%; }
                }
                @keyframes typing {
                  from { width: 0; }
                  to { width: 100%; }
                }
                @keyframes blink-caret {
                  from, to { border-color: transparent; }
                  50% { border-color: var(--ink-900); }
                }
                .animated-gradient {
                  background: linear-gradient(90deg, #5b4ee8, #ec4899, #8b5cf6, #5b4ee8);
                  background-size: 200% 100%;
                  animation: gradient-flow 3s ease infinite;
                  -webkit-background-clip: text;
                  -webkit-text-fill-color: transparent;
                  background-clip: text;
                }
                .typing-text {
                  overflow: hidden;
                  white-space: nowrap;
                  display: inline-block;
                  border-right: 2px solid var(--ink-900);
                  animation: typing 1.5s steps(10) forwards, blink-caret 0.75s step-end infinite;
                }
                @keyframes fade-in {
                  from { opacity: 0; transform: translateY(10px); }
                  to { opacity: 1; transform: translateY(0); }
                }
                .fade-in-content {
                  animation: fade-in 0.6s ease-out forwards;
                }
              `}</style>
              <div className="text-center mb-8">
                <h1 style={{ fontSize: "28px", lineHeight: 1.4, fontWeight: 500, letterSpacing: "-0.01em", color: "var(--ink-900)" }}>
                  {isLoggedIn ? (
                    <span className="typing-text">{greetingInfo.text} {greetingInfo.emoji}，{greetingName || "欢迎回来"}</span>
                  ) : (
                    <span className="typing-text">
                      {greetingInfo.text} {greetingInfo.emoji}，欢迎来到 <span className="animated-gradient" style={{ fontWeight: 600 }}>DataAgent</span>
                    </span>
                  )}
                </h1>
              </div>
              {showHomeContent && (
                <div className="w-full">
                  <div className="fade-in-content">
                    <ChatInput
                      isLoggedIn={isLoggedIn}
                      onNeedLogin={handleNeedLogin}
                      onSubmit={handleCreateReport}
                      busy={busy}
                      selectedScenario={selectedScenario}
                      onClearScenario={() => setSelectedScenario(null)}
                    />
                  </div>
                  <SuggestionChips onSelect={(scenario) => setSelectedScenario(scenario)} />
                </div>
              )}
            </div>

            {/* Footer */}
            <div
              className="absolute bottom-6 left-0 right-0 text-center"
              style={{
                color: "var(--ink-400)",
                fontSize: "11px",
                opacity: showHomeContent ? 1 : 0,
                transition: "opacity 0.6s ease-out",
              }}
            >
              2026 大数据应用部 | Brdc.AI人工智能小组
            </div>
          </div>
        );
    }
  };

  return (
    <div className="size-full flex" style={{ background: "var(--bg)" }}>
      <Sidebar
        active={page}
        onSelect={handlePageSelect}
        onNewConversation={handleNewConversation}
        onSelectConversation={handleSelectConversation}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((v) => !v)}
        isLoggedIn={isLoggedIn}
        onLogout={handleLogout}
        onNeedLogin={handleNeedLogin}
        user={user}
        onSearchHistory={() => {
          if (!isLoggedIn) {
            handleNeedLogin();
            return;
          }
          setShowSearchHistory(true);
        }}
        searchHistoryOpen={showSearchHistory}
        conversations={conversations}
        onPinConversation={handlePinConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* Wrapper gives SearchHistoryPanel a clean absolute-inset-0 context
          independent of main's scroll position */}
      <div className="flex-1 min-w-0 relative flex flex-col">
        <main
          className="flex-1 flex flex-col min-w-0 overflow-y-auto"
          style={{
            scrollbarGutter: "stable",
            visibility: showSearchHistory ? "hidden" : "visible",
            pointerEvents: showSearchHistory ? "none" : "auto",
          }}
        >
          {renderPage()}
        </main>
        <SearchHistoryPanel
          open={showSearchHistory}
          onClose={() => setShowSearchHistory(false)}
          onNewConversation={() => { setShowSearchHistory(false); handleNewConversation(); }}
          onSelectConversation={handleSelectConversation}
          conversations={conversations}
          onPinConversation={handlePinConversation}
          onDeleteConversation={handleDeleteConversation}
        />
      </div>

      {showLogin && (
        <LoginModal
          onClose={() => setShowLogin(false)}
          onLogin={handleLogin}
          onRegister={handleRegister}
        />
      )}
      <TechIntroModal
        open={techModalOpen}
        onClose={() => setTechModalOpen(false)}
        initialTechId={techModalInitialId}
        onNavigate={(pageKey) => {
          setPage(pageKey as PageKey);
          setTechModalOpen(false);
        }}
      />
      {showWelcome && (
        <WelcomeModal
          onClose={dismissWelcome}
          onLearnMore={() => {
            dismissWelcome();
            setTechModalOpen(true);
          }}
        />
      )}
    </div>
  );
}

function DocumentWorkspace({
  workspace,
  busy,
  onBack,
  onStart,
  onUpdate,
}: {
  workspace: DocumentWorkspaceState;
  busy: boolean;
  onBack: () => void;
  onStart: (answers: string) => void;
  onUpdate: (patch: Partial<DocumentWorkspaceState>) => void;
}) {
  const [answers, setAnswers] = useState(workspace.answers || "");
  const [qaIndex, setQaIndex] = useState(0);
  const [qaDraft, setQaDraft] = useState("");
  const [qaAnswers, setQaAnswers] = useState<string[]>([]);
  // "hidden" → questions not ready yet; "generating" → brief entrance animation;
  // "answering" → user is interacting; "done" → all questions answered.
  const [qaPhase, setQaPhase] = useState<"hidden" | "generating" | "answering" | "done">("hidden");
  // Per-question free-text for when the user picks "其他" in a single/multi-choice question.
  const [qaOtherInputs, setQaOtherInputs] = useState<Record<number, string>>({});
  // Per-question selected-option set for multi_choice questions.
  const [qaMultiSelects, setQaMultiSelects] = useState<Record<number, string[]>>({});
  const [steps, setSteps] = useState<Array<{ id: string; label: string; detail?: string; status: "pending" | "running" | "done" | "error" }>>(
    () => initialDocumentSteps(workspace.status),
  );
  const [sections, setSections] = useState<Array<{ idx: number; title: string; content: string; wordCount?: number }>>([]);
  const [finalMarkdown, setFinalMarkdown] = useState(workspace.initialMarkdown || "");
  const [statusText, setStatusText] = useState(workspace.status === "planning" ? "等待确认计划" : "准备启动文档管线");
  const [planLoading, setPlanLoading] = useState(workspace.status === "planning" && !workspace.plan && !workspace.planError);
  const [activities, setActivities] = useState<DocumentActivity[]>(() => initialDocumentActivities(workspace));
  const [rightMode, setRightMode] = useState<"document" | "activity">("document");
  const [rightModeLocked, setRightModeLocked] = useState(false);
  const [rightPanelVisible, setRightPanelVisible] = useState(true);
  const [selectedActivity, setSelectedActivity] = useState<DocumentActivity | null>(null);
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const [revealedPlanCount, setRevealedPlanCount] = useState(0);
  const [miniPlanExpanded, setMiniPlanExpanded] = useState(false);
  const [downloadingFormat, setDownloadingFormat] = useState<"docx" | "pdf" | null>(null);
  const [downloadError, setDownloadError] = useState("");
  const [artifactPreview, setArtifactPreview] = useState<ReportPreview | null>(null);
  const [artifactPreviewLoading, setArtifactPreviewLoading] = useState(false);
  const [artifactPreviewError, setArtifactPreviewError] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const reportId = workspace.reportId;
  const canDownload = Boolean(reportId) && workspace.status === "completed" && !downloadingFormat;
  const downloadBusy = Boolean(downloadingFormat) || workspace.status === "running" || workspace.status === "planning";
  const promptTime = useMemo(() => formatPromptTime(workspace.createdAt), [workspace.createdAt]);

  const plan = workspace.plan;
  const questions = useMemo(() => normalizeDocumentPlanQuestions(plan), [plan]);
  const currentQuestion = questions[qaIndex] || null;
  const qaDone = questions.length > 0 && qaIndex >= questions.length;
  const compiledAnswers = questions
    .map((question, index) => {
      const answer = (qaAnswers[index] || question.defaultAnswer || "").trim();
      return answer ? `Q: ${question.question}\nA: ${answer}` : "";
    })
    .filter(Boolean)
    .join("\n\n");
  const draftMarkdown = finalMarkdown || sections
    .sort((a, b) => a.idx - b.idx)
    .map((section) => `## ${section.title}\n\n${section.content}`)
    .join("\n\n");
  const previewMarkdown = draftMarkdown || buildLiveDocumentPreview(workspace.title, activities, statusText, workspace.status);

  // Streaming plan reveal — expose steps one-by-one at 380 ms intervals
  useEffect(() => {
    if (!plan?.steps?.length) { setRevealedPlanCount(0); return; }
    if (revealedPlanCount >= plan.steps.length) return;
    const t = setTimeout(() => setRevealedPlanCount((c) => c + 1), 380);
    return () => clearTimeout(t);
  }, [plan?.steps?.length, revealedPlanCount]);

  // QA phase gate: wait until all plan-step animations have finished,
  // THEN show "generating" entrance → "answering" after a brief delay.
  useEffect(() => {
    if (questions.length === 0 || planLoading || qaPhase !== "hidden") return;
    if (!plan || revealedPlanCount < plan.steps.length) return; // wait for reveal animation
    setQaPhase("generating");
    const t = setTimeout(() => setQaPhase((p) => p === "generating" ? "answering" : p), 1200);
    return () => clearTimeout(t);
  }, [questions.length, planLoading, revealedPlanCount, plan?.steps?.length]);

  // Mark done when user has answered all questions.
  useEffect(() => {
    if (qaDone && qaPhase === "answering") setQaPhase("done");
  }, [qaDone, qaPhase]);

  // Which plan step is currently executing (0-based)
  const currentExecutingStep = useMemo(() => {
    if (!plan?.steps?.length) return 0;
    if (workspace.status === "completed") return plan.steps.length;
    const norm = (s: string) => s.toLowerCase().replace(/^[\d\s.。]+/, "").trim().slice(0, 8);
    let step = 0;
    for (const a of activities) {
      if (a.kind === "summary") { step = plan.steps.length - 1; break; }
      if (a.kind === "section") {
        const title = norm(a.title.replace(/^生成章节：/, ""));
        const found = plan.steps.findIndex((s, i) => i >= step && norm(stripPlanStepNumber(s)).includes(title.slice(0, 4)));
        step = found >= 0 ? found : Math.min(step + 1, plan.steps.length - 2);
      }
    }
    return step;
  }, [activities, plan, workspace.status]);

  // Group activities by their corresponding plan step
  const activitiesByStep = useMemo(() => {
    const map = new Map<number, DocumentActivity[]>();
    if (!plan?.steps?.length) { map.set(0, activities); return map; }
    const norm = (s: string) => s.toLowerCase().replace(/^[\d\s.。]+/, "").trim().slice(0, 8);
    let step = 0;
    for (const a of activities) {
      if (a.kind === "summary") step = plan.steps.length - 1;
      else if (a.kind === "section") {
        const title = norm(a.title.replace(/^生成章节：/, ""));
        const found = plan.steps.findIndex((s, i) => i >= step && norm(stripPlanStepNumber(s)).includes(title.slice(0, 4)));
        if (found >= 0) step = found;
        else step = Math.min(step + 1, plan.steps.length - 2);
      }
      const arr = map.get(step) ?? [];
      arr.push(a);
      map.set(step, arr);
    }
    return map;
  }, [activities, plan]);

  const resolveMultiAnswer = (qIdx: number): string => {
    const selected = qaMultiSelects[qIdx] ?? [];
    if (selected.length === 0) return "";
    return selected.map((opt) => {
      if (opt === "其他") {
        const custom = (qaOtherInputs[qIdx] || "").trim();
        return custom ? `其他：${custom}` : "其他";
      }
      return opt;
    }).join("、");
  };

  const saveCurrentAnswer = (value = qaDraft) => {
    if (!currentQuestion) return;
    let finalValue: string;
    if (currentQuestion.type === "multi_choice") {
      finalValue = resolveMultiAnswer(qaIndex);
    } else {
      // When the user picked "其他", substitute with their custom typed text.
      finalValue = value;
      if (value === "其他") {
        const custom = (qaOtherInputs[qaIndex] || "").trim();
        finalValue = custom ? `其他：${custom}` : "其他";
      }
    }
    const next = [...qaAnswers];
    next[qaIndex] = finalValue.trim() || currentQuestion.defaultAnswer;
    setQaAnswers(next);
    setQaDraft(next[qaIndex + 1] || "");
    setQaIndex((idx) => Math.min(idx + 1, questions.length));
  };

  /** Save the last answer AND immediately launch. */
  const saveAndStart = () => {
    if (!currentQuestion) return;
    let finalValue: string;
    if (currentQuestion.type === "multi_choice") {
      finalValue = resolveMultiAnswer(qaIndex);
    } else {
      finalValue = qaDraft;
      if (finalValue === "其他") {
        const custom = (qaOtherInputs[qaIndex] || "").trim();
        finalValue = custom ? `其他：${custom}` : "其他";
      }
    }
    const next = [...qaAnswers];
    next[qaIndex] = finalValue.trim() || currentQuestion.defaultAnswer;
    setQaAnswers(next);
    const compiled = questions
      .map((q, i) => {
        const a = (next[i] || q.defaultAnswer || "").trim();
        return a ? `Q: ${q.question}\nA: ${a}` : "";
      })
      .filter(Boolean)
      .join("\n\n");
    const merged = [compiled, answers.trim()].filter(Boolean).join("\n\n补充偏好：\n");
    onStart(merged);
  };

  const startWithAnswers = () => {
    const merged = [compiledAnswers, answers.trim()].filter(Boolean).join("\n\n补充偏好：\n");
    onStart(merged);
  };

  const pushActivity = (entry: Omit<DocumentActivity, "id"> & { id?: string }) => {
    const id = entry.id || `${entry.kind}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const normalizedContent = normalizeActivityContent(entry.content || "");
    setActivities((prev) => {
      const next = prev.filter((item) => {
        if (item.id === id) return false;
        if (!normalizedContent) return true;
        return normalizeActivityContent(item.content || "") !== normalizedContent;
      });
      return [...next, { ...entry, id, content: normalizedContent || entry.content }].slice(-28);
    });
  };

  const openActivity = (activity: DocumentActivity) => {
    setSelectedActivity(activity);
    setRightMode("activity");
    setRightModeLocked(true);
  };

  const unlockRightPanel = () => {
    setRightModeLocked(false);
    setRightMode("document");
    setSelectedActivity(null);
  };

  const handleDownload = async (format: "docx" | "pdf") => {
    if (!reportId || !canDownload) return;
    setDownloadError("");
    setDownloadingFormat(format);
    try {
      await api.downloadReport(reportId, format);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "下载失败，请稍后重试");
    } finally {
      setDownloadingFormat(null);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [steps.length, sections.length, finalMarkdown, statusText]);

  useEffect(() => {
    if (workspace.initialMarkdown) {
      setFinalMarkdown(workspace.initialMarkdown);
      setRightMode("document");
    }
  }, [workspace.reportId, workspace.initialMarkdown]);

  useEffect(() => {
    if (!reportId || workspace.status !== "completed") {
      setArtifactPreview(null);
      setArtifactPreviewError("");
      setArtifactPreviewLoading(false);
      return;
    }
    let cancelled = false;
    setArtifactPreviewLoading(true);
    setArtifactPreviewError("");
    api.previewReport(reportId, "docx")
      .then((preview) => {
        if (cancelled) return;
        setArtifactPreview(preview);
      })
      .catch((error) => {
        if (cancelled) return;
        setArtifactPreview(null);
        setArtifactPreviewError(error instanceof Error ? error.message : "文档预览生成失败");
      })
      .finally(() => {
        if (!cancelled) setArtifactPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportId, workspace.status]);

  useEffect(() => {
    setQaIndex(0);
    setQaDraft("");
    setQaAnswers([]);
  }, [questions.map((question) => question.id).join("\n")]);

  useEffect(() => {
    if (workspace.status !== "planning" || workspace.plan || !workspace.pending || workspace.planError) return;
    let cancelled = false;
    setPlanLoading(true);
    setStatusText("正在让模型生成专属计划");
    const payload = workspace.pending.payload;
    api.createDocumentPlan({
      prompt: workspace.prompt,
      template: payload.template,
      scenario: payload.scenario,
      output_format: payload.outputFormat,
      uploaded_files: workspace.pending.uploadedIds,
      file_names: [
        ...(payload.templateFile ? [payload.templateFile.name] : []),
        ...(payload.files || []).map((file) => file.name),
      ],
      model_id: payload.modelId || undefined,
      effort: payload.effort || "low",
    }).then((nextPlan) => {
      if (cancelled) return;
      onUpdate({ plan: nextPlan, planError: undefined });
      setStatusText(nextPlan.should_ask ? "等待确认计划" : "模型判断无需额外追问");
    }).catch((error) => {
      if (cancelled) return;
      onUpdate({ planError: error instanceof Error ? error.message : "模型规划失败" });
      setStatusText("模型规划失败");
    }).finally(() => {
      if (!cancelled) setPlanLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [workspace.status, workspace.prompt, workspace.pending, workspace.plan, workspace.planError]);

  useEffect(() => {
    if (!reportId || workspace.status === "planning") return;
    let closed = false;
    let ws: WebSocket | null = null;
    const markStep = (id: string, status: "pending" | "running" | "done" | "error", detail?: string) => {
      setSteps((prev) => prev.map((step) => step.id === id ? { ...step, status, detail: detail || step.detail } : step));
    };
    const absorbEvent = (event: any) => {
      const type = event?.type || "";
      const payload = event?.payload || {};
      const absorbSectionDraft = (draft: any) => {
        markStep("write", "running", `已生成章节：${draft.title || ""}`);
        setRightMode("document");
        const sectionTitle = String(draft.title || `章节 ${Number(draft.section_idx ?? 0) + 1}`);
        pushActivity({
          id: `section-${draft.section_idx ?? sectionTitle}`,
          kind: "section",
          title: `生成章节：${sectionTitle}`,
          content: String(draft.content || "").slice(0, 900),
          meta: draft.word_count ? `${draft.word_count} 字` : "文档内容",
        });
        setSections((prev) => {
          const idx = Number(draft.section_idx ?? prev.length);
          const next = prev.filter((section) => section.idx !== idx);
          next.push({
            idx,
            title: sectionTitle,
            content: String(draft.content || ""),
            wordCount: Number(draft.word_count || 0),
          });
          return next.sort((a, b) => a.idx - b.idx);
        });
      };
      if (type === "research.status" || type === "research.progress" || type === "pipeline.phase") {
        const phase = String(payload.phase || payload.current_task || payload.stage || "正在执行");
        setStatusText(phase);
        const detail = payload.detail || {};
        const detailContent = buildMeaningfulProgressContent(phase, detail);
        if (detail.section_preview) {
          const parsed = parseSectionPreview(detail.section_preview, detail);
          absorbSectionDraft(parsed);
        }
        if (detail.outline_preview) {
          setRightMode("document");
        }
        if (detailContent) {
          pushActivity({
            id: `artifact-${phase}-${String(detail.section_id || detail.section_title || "")}`,
            kind: "node",
            title: progressArtifactTitle(phase, detail),
            content: detailContent,
            meta: progressArtifactMeta(phase, detail),
          });
        }
        if (/理解|understand|解析/.test(phase)) markStep("understand", "running", phase);
        if (/大纲|outline|规划|plan/.test(phase)) {
          markStep("understand", "done");
          markStep("outline", "running", phase);
        }
        if (/生成|撰写|写作|generat|draft/.test(phase)) {
          markStep("understand", "done");
          markStep("outline", "done");
          markStep("write", "running", phase);
        }
        if (/校验|审核|qa|quality/i.test(phase)) {
          markStep("write", "done");
          markStep("qa", "running", phase);
        }
      }
      if (type === "research.timeline") {
        const label = String(payload.label || "");
        if (label) setStatusText(label);
        const content = normalizeActivityContent(String(payload.detail || payload.message || ""));
        if (label && content) {
          pushActivity({
            id: `timeline-${label}`,
            kind: "node",
            title: label,
            content,
            meta: "过程产物",
          });
        }
      }
      if (type === "thinking" || type === "thinking.block") {
        const content = String(payload.content || payload.phase || "正在思考");
        setStatusText(content);
        const meaningful = normalizeActivityContent(content);
        if (meaningful) {
          pushActivity({
            id: `thinking-${payload.phase || meaningful.slice(0, 40)}`,
            kind: "thinking",
            title: String(payload.phase || "阶段思考"),
            content: meaningful,
            meta: "过程产物",
          });
        }
      }
      if (type === "skill.invoked") {
        const skillName = String(payload.skill_name || "Skill");
        pushActivity({
          id: `skill-${skillName}-${payload.section_id || payload.phase || ""}`,
          kind: "tool",
          title: `使用 ${skillName}`,
          content: String(payload.summary || "后台已加载并应用该技能约束。"),
          meta: payload.phase ? `阶段：${payload.phase}` : "后台执行",
        });
      }
      if (type === "document.section.draft") {
        absorbSectionDraft(payload);
      }
      if (type === "db.query.start") {
        const { source_key, source_name, query } = payload as { source_key: string; source_name: string; query?: string };
        pushActivity({
          id: `db-${source_key}-${Date.now()}`,
          kind: "db_query",
          title: `查找相关数据库 │ ${source_name}`,
          content: JSON.stringify({ sourceKey: source_key, sourceName: source_name, query, state: "searching" }),
          meta: "数据库查询",
        });
      }
      if (type === "db.query.result") {
        const { source_key, source_name, result_type, data, row_count } = payload as { source_key: string; source_name: string; result_type?: string; data?: any; row_count?: number };
        setActivities((prev) => {
          const updated = prev.map((a) => {
            if (a.kind === "db_query" && a.content && a.content.includes(`"sourceKey":"${source_key}"`)) {
              try {
                const parsed = JSON.parse(a.content);
                return { ...a, content: JSON.stringify({ ...parsed, state: "done", resultType: result_type, data, rowCount: row_count }) };
              } catch { return a; }
            }
            return a;
          });
          // If no existing card found, create a new done card
          const found = updated.some((a) => a.kind === "db_query" && a.content && a.content.includes(`"sourceKey":"${source_key}"`));
          if (!found) {
            return [...updated, {
              id: `db-${source_key}-${Date.now()}`,
              kind: "db_query" as const,
              title: `获取数据 │ ${source_name}`,
              content: JSON.stringify({ sourceKey: source_key, sourceName: source_name, state: "done", resultType: result_type, data, rowCount: row_count }),
              meta: "数据库查询",
            }].slice(-28);
          }
          return updated;
        });
      }
      if (type === "db.query.error") {
        const { source_key, error } = payload as { source_key: string; error?: string };
        setActivities((prev) => prev.map((a) => {
          if (a.kind === "db_query" && a.content && a.content.includes(`"sourceKey":"${source_key}"`)) {
            try {
              const parsed = JSON.parse(a.content);
              return { ...a, content: JSON.stringify({ ...parsed, state: "error", error }) };
            } catch { return a; }
          }
          return a;
        }));
      }
    };
    try {
      const url = api.reportSocket(reportId);
      if (url) {
        ws = new WebSocket(url);
        ws.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data);
            absorbEvent(event);
          } catch {
            // Ignore non-JSON keepalive frames.
          }
        };
      }
    } catch {
      ws = null;
    }

    const timer = window.setInterval(async () => {
      if (closed) return;
      try {
        const report = await api.getReport(reportId);
        onUpdate({ report });
        setStatusText(report.phase || statusText);
        if (report.status === "running" && report.phase) {
          pushActivity({
            id: `poll-${report.phase}`,
            kind: "node",
            title: report.phase,
            content: describeDocumentPhase(report.phase),
            meta: "节点输出",
          });
        }
        if (report.status === "failed") {
          markStep("qa", "error", report.error_message || "生成失败");
          onUpdate({ status: "error", error: report.error_message || "生成失败" });
        }
        if (report.status === "completed" || report.status === "delivered") {
          markStep("understand", "done");
          markStep("outline", "done");
          markStep("write", "done");
          markStep("qa", "done", "质量校验与导出完成");
          onUpdate({ status: "completed", report });
          const messages = await api.listMessages(reportId).catch(() => []);
          const markdown = selectBestDocumentDraft(messages);
          const reportMarkdown = markdown || extractMarkdownFromReport(report);
          if (reportMarkdown) setFinalMarkdown(reportMarkdown);
          setRightModeLocked(false);
          setRightMode("document");
          setSelectedActivity(null);
          pushActivity({
            id: "final-summary",
            kind: "summary",
            title: "Word 文档已生成",
            content: buildDocumentCompletionSummary(report.title || workspace.title, reportMarkdown, sections),
	            meta: "可下载文档",
          });
          window.clearInterval(timer);
          ws?.close();
        }
      } catch {
        // Poll again; websocket may already carry the visible state.
      }
    }, 1500);
    return () => {
      closed = true;
      window.clearInterval(timer);
      ws?.close();
    };
  }, [reportId, workspace.status]);

  return (
    <div className="h-full min-h-0 flex overflow-hidden" style={{ background: "var(--bg)" }}>
      <style>{`
        .doc-work-left { width: ${rightPanelVisible ? "48%" : "100%"}; min-width: ${rightPanelVisible ? "480px" : "0"}; transition: width 0.25s ease; }
        .doc-work-right { border-left: 1px solid var(--border); background: #f7f7f5; }
        .doc-step-line::before { content: ""; position: absolute; left: 13px; top: 30px; bottom: -18px; width: 1px; background: var(--border); }
        .doc-page { background: #fff; border: 1px solid rgba(0,0,0,.06); box-shadow: 0 18px 45px rgba(0,0,0,.08); }
        .doc-stream-caret { display: inline-block; color: var(--brand); animation: da-caret-blink 1s steps(2,start) infinite; }
        .doc-plan-todo { border: 1px solid rgba(0,0,0,.07); border-radius: 14px; background: rgba(255,255,255,.72); overflow: hidden; }
        .doc-plan-todo-item { display: grid; grid-template-columns: 28px minmax(0,1fr); gap: 10px; align-items: flex-start; padding: 11px 13px; }
        .doc-plan-todo-item + .doc-plan-todo-item { border-top: 1px solid rgba(0,0,0,.06); }
        .doc-plan-index { color: var(--ink-400); font-size: 13px; font-weight: 650; line-height: 1.65; font-variant-numeric: tabular-nums; text-align: right; }
        .doc-choice-option { width: 100%; border-radius: 12px; padding: 12px 13px; text-align: left; display: grid; grid-template-columns: 28px minmax(0,1fr); gap: 10px; align-items: center; transition: background .15s ease, border-color .15s ease; }
        .doc-choice-letter { width: 26px; height: 26px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--border); color: var(--ink-500); background: var(--bg-elevated); font-size: 12px; font-weight: 750; }
        .doc-choice-option-selected .doc-choice-letter { border-color: var(--ink-900); background: var(--ink-900); color: #fff; }
        .doc-qa-progress { display: grid; grid-template-columns: repeat(var(--qa-count), minmax(0, 1fr)); gap: 5px; }
        .doc-qa-dot { height: 4px; border-radius: 999px; background: var(--bg-subtle); overflow: hidden; }
        .doc-qa-dot-active { background: var(--ink-900); }
        /* ── PlanStepper-aligned flow animations ── */
        @keyframes doc-step-in {
          from { opacity: 0; transform: translateX(-6px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        .doc-plan-step { animation: doc-step-in 0.28s cubic-bezier(0.34,1.2,0.64,1) backwards; }

        /* ── Execution flow: same rail-style as PlanStepper ── */
        .doc-flow { position: relative; }
        .doc-flow-item {
          position: relative;
          display: flex;
          gap: 14px;
          align-items: flex-start;
          animation: doc-step-in 0.25s cubic-bezier(0.34,1.1,0.64,1) backwards;
        }
        .doc-flow-item + .doc-flow-item { margin-top: 18px; }

        /* Left rail: dot + vertical connector */
        .doc-flow-rail { display: flex; flex-direction: column; align-items: center; width: 28px; flex-shrink: 0; }
        .doc-flow-dot {
          width: 28px; height: 28px; border-radius: 999px;
          display: flex; align-items: center; justify-content: center;
          background: var(--bg-elevated); color: var(--ink-400);
          border: 1px solid var(--border);
          box-shadow: 0 1px 2px rgba(0,0,0,.04);
          flex-shrink: 0;
          transition: background .2s, border-color .2s, color .2s;
        }
        .doc-flow-connector {
          width: 1.5px; flex: 1; min-height: 14px; margin: 3px 0;
          background: var(--border);
          transition: background .4s ease;
        }
        .doc-flow-connector-running { background: var(--brand-border); }
        .doc-flow-dot-running { color: var(--brand); background: var(--brand-soft); border-color: var(--brand-border); }
        .doc-flow-dot-done { color: #16a34a; background: rgba(22,163,74,.07); border-color: rgba(22,163,74,.2); }
        .doc-flow-dot-amber { color: #b45309; background: rgba(180,83,9,.06); border-color: rgba(245,158,11,.22); }

        /* Content area */
        .doc-flow-content { flex: 1; min-width: 0; padding-bottom: 2px; }

        /* Activity rows */
        .doc-activity-row {
          width: 100%; text-align: left;
          display: flex; align-items: center; gap: 8px;
          color: var(--ink-600); font-size: 13.5px; line-height: 1.5;
          transition: color .15s ease;
          min-height: 28px;
        }
        .doc-activity-row:hover { color: var(--ink-900); }
        .doc-activity-title { color: var(--ink-700); font-size: 13.5px; line-height: 1.5; font-weight: 500; }
        .doc-activity-title strong { color: var(--ink-900); font-weight: 650; }
        .doc-activity-substeps { margin-top: 8px; display: grid; gap: 5px; color: var(--ink-500); font-size: 12.5px; line-height: 1.6; }
        .doc-activity-substep { display: flex; gap: 10px; align-items: flex-start; }
        .doc-activity-substep::before { content: ""; width: 4px; height: 4px; border-radius: 999px; background: var(--ink-300); margin-top: 9px; flex-shrink: 0; }
        .doc-activity-copy { color: var(--ink-800); font-size: 13.5px; line-height: 1.75; }
        .doc-activity-copy .da-markdown > *:first-child { margin-top: 0; }
        .doc-activity-copy .da-markdown > *:last-child { margin-bottom: 0; }

        /* Step-label dividers in execution flow */
        .doc-step-label {
          display: flex; align-items: center; gap: 8px;
          padding: 4px 0;
        }
        .doc-step-label-line { flex: 1; height: 1px; background: var(--border); }
        .doc-step-label-text { font-size: 12px; font-weight: 650; letter-spacing: 0.01em; white-space: nowrap; }
        .doc-user-prompt { margin-bottom: 28px; display: flex; flex-direction: column; align-items: flex-end; }
        .doc-user-attachments { display: flex; justify-content: flex-end; align-items: flex-end; gap: 12px; margin-bottom: 12px; }
        .doc-user-file-chip { min-width: 0; max-width: min(360px, calc(100% - 88px)); height: 38px; padding: 0 15px; border: 1px solid var(--border); border-radius: 999px; background: var(--bg-elevated); display: inline-flex; align-items: center; gap: 9px; box-shadow: 0 1px 2px rgba(0,0,0,.03); color: var(--ink-900); font-size: 15px; font-weight: 700; }
        .doc-user-word-icon { width: 18px; height: 18px; border-radius: 5px; background: #2563eb; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 800; flex-shrink: 0; }
        .doc-user-file-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .doc-user-thumb { width: 76px; height: 84px; border: 1px solid var(--border); border-radius: 14px; background: linear-gradient(180deg, #fff 0%, #fafafa 100%); box-shadow: 0 1px 2px rgba(0,0,0,.04); padding: 9px 8px; display: grid; gap: 4px; align-content: start; flex-shrink: 0; }
        .doc-user-thumb-line { height: 3px; border-radius: 999px; background: #171717; opacity: .88; }
        .doc-user-thumb-line:nth-child(2n) { width: 78%; opacity: .55; }
        .doc-user-thumb-line:nth-child(3n) { width: 92%; opacity: .72; }
        .doc-user-bubble { max-width: 78%; border-radius: 17px; background: var(--bg-subtle); color: var(--ink-900); padding: 11px 15px; font-size: 14.5px; line-height: 1.65; font-weight: 500; white-space: pre-wrap; }
        .doc-user-meta { height: 22px; margin-top: 8px; display: flex; align-items: center; justify-content: flex-end; gap: 8px; color: var(--ink-400); font-size: 12.5px; }
        .doc-user-copy { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; border-radius: 7px; color: var(--ink-400); transition: background .15s ease, color .15s ease; }
        .doc-user-copy:hover { background: var(--hover); color: var(--ink-700); }
        .doc-rendered-preview { display: grid; gap: 18px; }
        .doc-rendered-page { width: 100%; display: block; border: 1px solid rgba(0,0,0,.06); background: #fff; box-shadow: 0 18px 45px rgba(0,0,0,.08); }
        .doc-preview-note { margin: 0 0 16px; border: 1px solid rgba(0,0,0,.07); border-radius: 12px; background: #fafafa; color: var(--ink-500); padding: 10px 12px; font-size: 12.5px; line-height: 1.55; }
        .doc-preview-note-error { color: #b91c1c; background: #fff7f7; border-color: rgba(185,28,28,.18); }
        .doc-embedded-grid { display: grid; gap: 18px; }
        .doc-embedded-figure { margin: 0; border: 1px solid rgba(0,0,0,.06); border-radius: 10px; background: #fff; padding: 10px; box-shadow: 0 10px 28px rgba(0,0,0,.06); }
        .doc-embedded-figure img { display: block; width: 100%; height: auto; }
	        .doc-artifact-card { border: 1px solid var(--border); border-radius: 14px; background: var(--bg-elevated); padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; transition: border-color .15s ease, box-shadow .15s ease; }
	        .doc-artifact-card:hover { border-color: rgba(0,0,0,.18); box-shadow: var(--shadow-sm); }
	        .doc-download-wrap { position: relative; display: inline-flex; }
	        .doc-download-btn { height: 32px; padding: 0 12px; border-radius: 9px; display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--border); background: var(--bg-elevated); color: var(--ink-650); font-size: 12.5px; transition: background .15s ease, opacity .15s ease; }
	        .doc-download-btn:not(:disabled):hover { background: var(--hover); }
	        .doc-download-btn:disabled { cursor: not-allowed; opacity: .62; }
	        .doc-download-icon { width: 32px; padding: 0; justify-content: center; }
	        .doc-download-menu { position: absolute; right: 0; top: calc(100% + 8px); z-index: 30; width: 178px; border: 1px solid var(--border); background: var(--bg-elevated); border-radius: 14px; box-shadow: var(--shadow-lg); padding: 6px; }
	        .doc-download-option { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 10px; border-radius: 10px; padding: 9px 10px; color: var(--ink-800); font-size: 13px; text-align: left; }
	        .doc-download-option:hover { background: var(--hover); }
	        .doc-download-meta { color: var(--ink-400); font-size: 11.5px; }
	        .doc-download-error { margin-top: 8px; color: #dc2626; font-size: 12px; }
	        @media (max-width: 1180px) {
          .doc-work-left { width: 100%; min-width: 0; }
          .doc-work-right { display: none; }
        }
        @media (max-width: 640px) {
          .doc-user-file-chip { max-width: calc(100% - 76px); height: 36px; padding: 0 12px; font-size: 13.5px; }
          .doc-user-thumb { width: 64px; height: 74px; border-radius: 12px; padding: 8px 7px; }
          .doc-user-bubble { max-width: 86%; font-size: 14px; border-radius: 16px; padding: 10px 13px; }
          .doc-user-meta { font-size: 12px; margin-top: 7px; }
        }
      `}</style>
      <section className="doc-work-left h-full min-h-0 overflow-y-auto">
        <div className="max-w-[760px] mx-auto px-8 pt-7 pb-4">
          <div className="flex items-center justify-between mb-8">
            <button onClick={onBack} className="inline-flex items-center gap-2 transition hover:opacity-75" style={{ color: "var(--ink-700)", fontSize: 14, fontWeight: 650 }}>
              <FileText className="h-4 w-4" />
              DataAgent Word
            </button>
            <div className="flex items-center gap-2">
              {!rightPanelVisible && (
                <button
                  onClick={() => setRightPanelVisible(true)}
                  className="h-8 px-3 rounded-lg flex items-center gap-1.5 transition hover:bg-[var(--hover)]"
                  style={{ color: "var(--ink-600)", border: "1px solid var(--border)", fontSize: 12.5 }}
                  title="展开预览"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                  展开预览
                </button>
              )}
	            {workspace.reportId && (
	              <DocumentDownloadMenu
	                canDownload={canDownload}
	                busy={downloadBusy}
	                onDownload={handleDownload}
	                downloadingFormat={downloadingFormat}
	              />
	            )}
            </div>
          </div>

          <DocumentUserPromptCard workspace={workspace} timeLabel={promptTime} />

          {(workspace.status === "planning" || plan) && (
            <div className="space-y-3">
              {/* ── PlanStepper: shows in ALL phases once planning begins ──
                  During planning: loading → streaming → done animation
                  During execution: stays as "done" state (no re-animation) */}
              <PlanStepper
                planLoading={workspace.status === "planning" && planLoading}
                plan={plan}
                planError={workspace.status === "planning" ? workspace.planError : null}
                revealedPlanCount={workspace.status === "planning" ? revealedPlanCount : (plan?.steps.length ?? 0)}
              />

              {/* ── Interactive QA — planning phase only ── */}
              {workspace.status === "planning" && qaPhase !== "hidden" && (
                <StepItem
                  nodeState={qaPhase === "done" ? "done" : qaPhase === "generating" ? "loading" : "idle"}
                  title={
                    <span style={{ color: qaPhase === "done" ? "var(--ink-500)" : "var(--ink-900)" }}>
                      {qaPhase === "generating" ? "正在生成 QA 问题…" : qaPhase === "done" ? "QA 环节完成" : "待用户回答…"}
                    </span>
                  }
                  showConnector={false}
                >
                  <div
                    className="rounded-2xl overflow-hidden"
                    style={{
                      border: "1px solid var(--border)",
                      background: "var(--bg-elevated)",
                      animation: "doc-step-in 0.32s cubic-bezier(0.34,1.1,0.64,1) backwards",
                    }}
                  >
                    {/* ── Header row ── */}
                    <div className="flex items-center gap-2.5 px-4 pt-3 pb-2.5 border-b" style={{ borderColor: "var(--border)" }}>
                      <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-700)" }}>
                        进一步确认内容细节
                      </span>
                      {qaPhase === "answering" && questions.length > 0 && (
                        <>
                          <div className="flex-1 doc-qa-progress" style={{ gridTemplateColumns: `repeat(${questions.length}, minmax(0, 1fr))` }}>
                            {questions.map((q, index) => (
                              <span key={q.id} className={`doc-qa-dot ${index < qaIndex ? "doc-qa-dot-active" : ""}`} />
                            ))}
                          </div>
                          <span style={{ color: "var(--ink-400)", fontSize: 11.5, flexShrink: 0 }}>
                            {Math.min(qaIndex + 1, questions.length)} / {questions.length}
                          </span>
                        </>
                      )}
                    </div>

                    {/* ── Body ── */}
                    {qaPhase === "generating" && (
                      <div className="px-4 py-4" style={{ color: "var(--ink-400)", fontSize: 13 }}>
                        正在根据任务规划生成确认问题…
                      </div>
                    )}

                    {qaPhase === "answering" && currentQuestion && (
                      <div className="px-4 py-4 space-y-3">
                        {/* Question */}
                        <div className="rounded-xl p-3" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                          <div style={{ color: "var(--ink-400)", fontSize: 11, fontWeight: 700, marginBottom: 4, letterSpacing: "0.07em", textTransform: "uppercase" }}>
                            问题 {qaIndex + 1}
                          </div>
                          <div style={{ color: "var(--ink-900)", fontSize: 14.5, lineHeight: 1.7, fontWeight: 650 }}>
                            {currentQuestion.question}
                          </div>
                        </div>

                        {/* Answer area */}
                        {currentQuestion.type === "single_choice" || currentQuestion.type === "multi_choice" ? (() => {
                          const isMulti = currentQuestion.type === "multi_choice";
                          const multiSelected = qaMultiSelects[qaIndex] ?? [];
                          const toggleMulti = (option: string) => {
                            setQaMultiSelects((prev) => {
                              const cur = prev[qaIndex] ?? [];
                              const next = cur.includes(option) ? cur.filter((o) => o !== option) : [...cur, option];
                              return { ...prev, [qaIndex]: next };
                            });
                          };
                          return (
                            <div className="grid gap-2">
                              {isMulti && (
                                <div className="flex items-center gap-1.5 px-0.5 pb-0.5">
                                  <span
                                    className="inline-flex items-center rounded-full px-2 py-0.5"
                                    style={{ background: "rgba(37,99,235,0.09)", color: "#2563eb", fontSize: 11, fontWeight: 700, letterSpacing: "0.04em" }}
                                  >
                                    多选
                                  </span>
                                  <span style={{ color: "var(--ink-400)", fontSize: 11.5 }}>
                                    可选择多个选项
                                    {multiSelected.length > 0 && `，已选 ${multiSelected.length} 项`}
                                  </span>
                                </div>
                              )}
                              {currentQuestion.options.map((option, index) => {
                                const selected = isMulti ? multiSelected.includes(option) : qaDraft === option;
                                const isOther = option === "其他" || option.startsWith("其他");
                                const handleClick = () => {
                                  if (isMulti) {
                                    toggleMulti(option);
                                    if (isOther) setTimeout(() => document.getElementById(`qa-other-input-${qaIndex}`)?.focus(), 0);
                                  } else {
                                    setQaDraft(option);
                                    if (isOther) setTimeout(() => document.getElementById(`qa-other-input-${qaIndex}`)?.focus(), 0);
                                  }
                                };
                                return (
                                  <button
                                    key={option}
                                    type="button"
                                    onClick={handleClick}
                                    className={`doc-choice-option ${selected ? "doc-choice-option-selected" : ""}`}
                                    style={{
                                      border: selected ? "1px solid var(--ink-900)" : "1px solid var(--border)",
                                      background: selected ? "rgba(0,0,0,.045)" : "var(--bg)",
                                      color: "var(--ink-900)",
                                      fontSize: 13.5,
                                      lineHeight: 1.55,
                                      fontWeight: selected ? 700 : 500,
                                      width: "100%",
                                      alignItems: "center",
                                    }}
                                  >
                                    {/* Checkbox / radio indicator */}
                                    {isMulti ? (
                                      <span
                                        style={{
                                          width: 16, height: 16, borderRadius: 4, flexShrink: 0,
                                          border: selected ? "2px solid var(--ink-900)" : "2px solid var(--border)",
                                          background: selected ? "var(--ink-900)" : "transparent",
                                          display: "inline-flex", alignItems: "center", justifyContent: "center",
                                          transition: "all 0.15s",
                                        }}
                                      >
                                        {selected && <svg width="9" height="7" viewBox="0 0 9 7" fill="none"><path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                                      </span>
                                    ) : (
                                      <span className="doc-choice-letter">{optionLetter(index)}</span>
                                    )}
                                    {isOther ? (
                                      <>
                                        <span style={{ flex: 1, textAlign: "left" }}>其他（请说明）</span>
                                        <input
                                          id={`qa-other-input-${qaIndex}`}
                                          value={qaOtherInputs[qaIndex] || ""}
                                          onChange={(e) => {
                                            e.stopPropagation();
                                            setQaOtherInputs((prev) => ({ ...prev, [qaIndex]: e.target.value }));
                                            if (isMulti) { if (!multiSelected.includes(option)) toggleMulti(option); }
                                            else if (qaDraft !== option) setQaDraft(option);
                                          }}
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            if (isMulti) { if (!multiSelected.includes(option)) toggleMulti(option); }
                                            else if (qaDraft !== option) setQaDraft(option);
                                          }}
                                          placeholder="请输入…"
                                          className="rounded-lg outline-none px-2 py-1"
                                          style={{
                                            border: "1px solid " + (selected ? "var(--ink-600)" : "var(--border)"),
                                            background: "var(--bg-elevated)",
                                            color: "var(--ink-900)",
                                            fontSize: 13,
                                            width: 160,
                                            flexShrink: 0,
                                            opacity: selected ? 1 : 0.5,
                                          }}
                                        />
                                      </>
                                    ) : (
                                      <span>{option}</span>
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          );
                        })() : (
                          <textarea
                            value={qaDraft}
                            onChange={(e) => setQaDraft(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                e.preventDefault();
                                qaIndex === questions.length - 1 ? saveAndStart() : saveCurrentAnswer();
                              }
                            }}
                            placeholder="回答这个问题…"
                            className="w-full resize-none rounded-xl outline-none"
                            style={{ minHeight: 88, border: "1px solid var(--border)", background: "var(--bg)", padding: 12, color: "var(--ink-900)", fontSize: 13.5, lineHeight: 1.6 }}
                          />
                        )}

                        {/* "补充其他偏好" on the last question */}
                        {qaIndex === questions.length - 1 && (
                          <textarea
                            value={answers}
                            onChange={(e) => setAnswers(e.target.value)}
                            placeholder="补充其他偏好或说明（可选）"
                            className="w-full resize-none rounded-xl outline-none"
                            style={{ minHeight: 56, border: "1px solid var(--border)", background: "var(--bg)", padding: "10px 12px", color: "var(--ink-900)", fontSize: 13, lineHeight: 1.6 }}
                          />
                        )}

                        {/* Button bar:  [按默认判断] [直接开始]  ──  [跳过]  [下一题 →] / [确认计划并执行] */}
                        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                          <button
                            onClick={() => saveCurrentAnswer(currentQuestion.defaultAnswer || "按默认判断")}
                            className="h-7 px-3 rounded-full transition hover:bg-[var(--hover)]"
                            style={{ border: "1px solid var(--border)", color: "var(--ink-500)", fontSize: 12 }}
                          >
                            按默认判断
                          </button>
                          <button
                            onClick={() => onStart("")}
                            disabled={busy}
                            className="h-7 px-3 rounded-full transition hover:bg-[var(--hover)]"
                            style={{ border: "1px solid var(--border)", color: "var(--ink-500)", fontSize: 12 }}
                          >
                            直接开始
                          </button>
                          <div style={{ flex: 1 }} />
                          <button
                            onClick={() => saveCurrentAnswer("跳过")}
                            className="h-7 px-3 rounded-full transition hover:bg-[var(--hover)]"
                            style={{ border: "1px solid var(--border)", color: "var(--ink-500)", fontSize: 12 }}
                          >
                            跳过
                          </button>
                          {qaIndex === questions.length - 1 ? (
                            <button
                              onClick={saveAndStart}
                              disabled={busy}
                              className="h-7 px-4 rounded-full transition active:scale-[.99]"
                              style={{ background: "var(--ink-900)", color: "#fff", fontSize: 12, opacity: busy ? 0.6 : 1 }}
                            >
                              {busy ? "启动中…" : "确认计划并执行"}
                            </button>
                          ) : (
                            <button
                              onClick={() => saveCurrentAnswer()}
                              className="h-7 px-3 rounded-full transition active:scale-[.99]"
                              style={{ background: "var(--ink-900)", color: "#fff", fontSize: 12 }}
                            >
                              下一题 →
                            </button>
                          )}
                        </div>
                      </div>
                    )}

                    {/* ── Done state: Q&A summary + completion icon ── */}
                    {qaPhase === "done" && (
                      <div className="px-4 py-4">
                        <div className="space-y-1.5 mb-3">
                          {questions.map((q, index) => (
                            <div key={q.id} style={{ color: "var(--ink-600)", fontSize: 12.5, lineHeight: 1.55 }}>
                              <span style={{ color: "var(--ink-800)", fontWeight: 650 }}>Q{index + 1}：</span>{q.question}
                              {" · "}
                              <span style={{ color: "var(--ink-500)" }}>{qaAnswers[index] || q.defaultAnswer || "按默认判断"}</span>
                            </div>
                          ))}
                        </div>
                        <div className="flex items-center gap-2 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
                          <div style={{ flex: 1 }} />
                          <button
                            onClick={() => { setQaPhase("answering"); setQaIndex(0); setQaDraft(qaAnswers[0] || ""); }}
                            className="h-6 px-2.5 rounded-full transition hover:bg-[var(--hover)]"
                            style={{ border: "1px solid var(--border)", color: "var(--ink-400)", fontSize: 11.5 }}
                          >
                            修改
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </StepItem>
              )}

              {/* ── Bottom action card: only when no QA questions (or questions all done) ── */}
              {workspace.status === "planning" && plan && !planLoading && (questions.length === 0 || qaPhase === "done") && (
                <div
                  className="rounded-2xl"
                  style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", overflow: "hidden" }}
                >
                  <textarea
                    value={answers}
                    onChange={(e) => setAnswers(e.target.value)}
                    placeholder="补充其他偏好或说明（可选）"
                    className="w-full resize-none outline-none"
                    style={{
                      minHeight: 60,
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      background: "transparent",
                      padding: "12px 16px",
                      color: "var(--ink-900)",
                      fontSize: 13.5,
                      lineHeight: 1.6,
                      display: questions.length > 0 ? "none" : "block",
                    }}
                  />
                  <div className="flex items-center justify-between gap-3 px-4 py-3" style={{ background: "var(--bg-subtle)" }}>
                    <span style={{ fontSize: 12, color: "var(--ink-400)" }}>确认无误后开始执行</span>
                    <div className="flex gap-2">
                      {questions.length === 0 && (
                        <button
                          onClick={() => onStart("")}
                          disabled={busy}
                          className="h-8 px-4 rounded-lg transition hover:bg-[var(--hover)]"
                          style={{ color: "var(--ink-600)", border: "1px solid var(--border)", fontSize: 12.5, background: "var(--bg-elevated)" }}
                        >
                          直接开始
                        </button>
                      )}
                      <button
                        onClick={startWithAnswers}
                        disabled={busy}
                        className="h-8 px-4 rounded-lg transition active:scale-[.99]"
                        style={{ background: "var(--ink-900)", color: "#fff", fontSize: 12.5, opacity: busy ? 0.6 : 1 }}
                      >
                        {busy ? "启动中…" : "确认计划并执行"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* QA summary — execution phase only, shown below PlanStepper */}
              {workspace.status !== "planning" && questions.length > 0 && qaAnswers.some(Boolean) && (
                <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
                  <div className="space-y-1.5">
                    {questions.map((q, index) => (
                      <div key={q.id} style={{ color: "var(--ink-600)", fontSize: 12.5, lineHeight: 1.55 }}>
                        <span style={{ color: "var(--ink-900)", fontWeight: 650 }}>Q{index + 1}：</span>{q.question}
                        {" · "}
                        <span style={{ color: "var(--ink-500)" }}>{qaAnswers[index] || q.defaultAnswer || "按默认判断"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {workspace.status !== "planning" && answers?.trim() && (
                <div style={{ color: "var(--ink-500)", fontSize: 12.5, lineHeight: 1.55, fontStyle: "italic" }}>{answers}</div>
              )}
            </div>
          )}
        </div>

        {/* ── Activities ─────────────────────────────────────────────────── */}
        {workspace.status !== "planning" && (
          <div className="max-w-[760px] mx-auto px-8 pt-2 pb-8">
            {/* Compact sticky plan overview */}
            {plan && plan.steps.length > 0 && (
              <PlanMiniWidget
                plan={plan}
                currentStep={currentExecutingStep}
                status={workspace.status}
              />
            )}
            {activities.length === 0 && (
              <div style={{ color: "var(--ink-400)", fontSize: 13.5, lineHeight: 1.7 }}>我正在启动文档管线，执行步骤将实时展示在这里。</div>
            )}
                {/* Inline render helper — PlanStepper-aligned rail layout */}
                {(() => {
                  const renderItem = (activity: DocumentActivity, i: number, isLastActive: boolean) => {
                    const dotClass = activity.kind === "thinking"
                      ? "doc-flow-dot doc-flow-dot-amber"
                      : activity.kind === "summary"
                        ? "doc-flow-dot doc-flow-dot-done"
                        : isLastActive
                          ? "doc-flow-dot doc-flow-dot-running"
                          : "doc-flow-dot";

                    // Detect special node types for richer display
                    const titleUpper = String(activity.title || "").toUpperCase();
                    const isPythonGen = /PYTHON|代码生成|生成.*代码|CODE.*GEN/.test(titleUpper);
                    const isPythonExec = /执行.*代码|代码.*执行|PYTHON.*RUN|EXECUTE.*CODE/.test(titleUpper);
                    const isChart = /图表|CHART|PLOT|VISUAL/.test(titleUpper);

                    return (
                      <div key={activity.id} className="doc-flow-item" style={{ animationDelay: `${Math.min(i, 10) * 0.04}s` }}>
                        {/* Rail: dot only (connector handled by margin between items) */}
                        <div className="doc-flow-rail">
                          <div className={dotClass}>
                            <DocumentActivityIcon activity={activity} running={isLastActive} />
                          </div>
                        </div>

                        {/* Content */}
                        <div className="doc-flow-content">
                          {/* Thinking — reuse PlanStepper's ThinkingBlock */}
                          {activity.kind === "thinking" && (
                            <ThinkingBlock
                              content={activity.content || activity.title || ""}
                              defaultOpen={expandedThinking.has(activity.id)}
                              key={activity.id}
                            />
                          )}

                          {/* Node / tool / status */}
                          {(activity.kind === "node" || activity.kind === "status" || activity.kind === "tool") && (
                            <div>
                              <button className="doc-activity-row" onClick={() => openActivity(activity)}>
                                <span className="doc-activity-title">
                                  <strong>
                                    {isLastActive
                                      ? <TypingText text={activityActionLabel(activity)} speed={14} instant={false} key={activity.id} />
                                      : activityActionLabel(activity)
                                    }
                                  </strong>
                                  {activitySubtitle(activity) && (
                                    <span style={{ color: "var(--ink-500)", fontWeight: 400 }}> · {activitySubtitle(activity)}</span>
                                  )}
                                </span>
                                <ChevronRight className="h-3.5 w-3.5 flex-shrink-0" style={{ color: "var(--ink-300)" }} />
                              </button>
                              {/* Special sub-node chips for Python / chart */}
                              {(isPythonGen || isPythonExec || isChart) && (
                                <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                                  {isPythonGen && (
                                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 999, background: "rgba(91,78,232,.07)", border: "1px solid rgba(91,78,232,.18)", color: "var(--brand)", fontSize: 11.5, fontWeight: 600 }}>
                                      <Code2 style={{ width: 10, height: 10 }} /> 生成 Python 代码
                                    </span>
                                  )}
                                  {isPythonExec && (
                                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 999, background: "rgba(16,163,74,.07)", border: "1px solid rgba(16,163,74,.18)", color: "#16a34a", fontSize: 11.5, fontWeight: 600 }}>
                                      <Play style={{ width: 10, height: 10 }} /> 执行代码
                                    </span>
                                  )}
                                  {isChart && (
                                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 999, background: "rgba(245,158,11,.07)", border: "1px solid rgba(245,158,11,.22)", color: "#b45309", fontSize: 11.5, fontWeight: 600 }}>
                                      <BarChart2 style={{ width: 10, height: 10 }} /> 生成图表
                                    </span>
                                  )}
                                </div>
                              )}
                              <ActivitySubsteps activity={activity} />
                            </div>
                          )}

                          {/* DB Query card */}
                          {activity.kind === "db_query" && (() => {
                            try {
                              const props = JSON.parse(activity.content || "{}");
                              return <DatabaseQueryCard {...props} />;
                            } catch {
                              return null;
                            }
                          })()}

                          {/* Section (chapter written) */}
                          {activity.kind === "section" && (
                            <button
                              className="doc-artifact-card"
                              onClick={() => { if (!rightModeLocked) setRightMode("document"); }}
                              type="button"
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                <div
                                  className="h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0"
                                  style={{ background: "var(--brand-soft)", color: "var(--brand)" }}
                                >
                                  <FileText className="h-4 w-4" />
                                </div>
                                <div className="min-w-0 text-left">
                                  <div style={{ color: "var(--ink-900)", fontWeight: 650, fontSize: 13.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                    {activity.title.replace(/^生成章节：/, "")}
                                  </div>
                                  <div style={{ color: "var(--ink-400)", fontSize: 12, marginTop: 1 }}>
                                    {activity.meta || "正在生成..."}
                                  </div>
                                </div>
                              </div>
                              <ChevronRight className="h-4 w-4 flex-shrink-0" style={{ color: "var(--ink-300)" }} />
                            </button>
                          )}

                          {/* Summary (final document) */}
                          {activity.kind === "summary" && (
                            <div className="space-y-3">
                              <div className="doc-activity-copy">
                                <MarkdownContent content={activity.content || "文档已生成。"} />
                              </div>
                              <button
                                className="doc-artifact-card"
                                onClick={() => setRightMode("document")}
                                type="button"
                              >
                                <div className="flex items-center gap-3 min-w-0">
                                  <div
                                    className="h-10 w-10 rounded-xl flex items-center justify-center flex-shrink-0"
                                    style={{ background: "rgba(22,163,74,.08)", color: "#16a34a" }}
                                  >
                                    <FileText className="h-4.5 w-4.5" />
                                  </div>
                                  <div className="min-w-0 text-left">
                                    <div style={{ color: "var(--ink-900)", fontWeight: 700, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                      {workspace.title || "生成报告"}
                                    </div>
                                    <div style={{ color: "var(--ink-400)", fontSize: 12.5, marginTop: 1 }}>Document · DOCX</div>
                                  </div>
                                </div>
                                {workspace.reportId ? (
                                  <span onClick={(e) => e.stopPropagation()}>
                                    <DocumentDownloadMenu canDownload={canDownload} busy={downloadBusy} onDownload={handleDownload} downloadingFormat={downloadingFormat} compact />
                                  </span>
                                ) : (
                                  <ChevronRight className="h-4 w-4 flex-shrink-0" style={{ color: "var(--ink-300)" }} />
                                )}
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  };

                  // ── Activities with inline step markers ────────────────
                  // All activities always render; step labels are injected
                  // as lightweight dividers when execution advances to next step.
                  const stepItems: React.ReactNode[] = [];
                  let lastRenderedStep = -1;
                  let trackStep = 0;

                  activities.forEach((activity, i) => {
                    if (plan?.steps?.length) {
                      // Advance step tracker based on activity type
                      if (activity.kind === "summary") {
                        trackStep = plan.steps.length - 1;
                      } else if (activity.kind === "section") {
                        const norm = (s: string) => s.toLowerCase().replace(/^[\d\s.。]+/, "").trim().slice(0, 8);
                        const sTitle = norm(activity.title.replace(/^生成章节：/, ""));
                        const matched = plan.steps.findIndex((s, idx) => idx >= trackStep && norm(stripPlanStepNumber(s)).includes(sTitle.slice(0, 4)));
                        trackStep = matched >= 0 ? matched : Math.min(trackStep + 1, plan.steps.length - 2);
                      }
                      // Inject step label when we move to a new step
                      if (trackStep !== lastRenderedStep) {
                        lastRenderedStep = trackStep;
                        const isDone = workspace.status === "completed" || trackStep < currentExecutingStep;
                        const isRunning = workspace.status === "running" && trackStep === currentExecutingStep;
                        stepItems.push(
                          <div
                            key={`step-lbl-${trackStep}`}
                            className="doc-step-label"
                            style={{ marginTop: stepItems.length === 0 ? 0 : 28, marginBottom: 14 }}
                          >
                            <span style={{ width: 20, height: 20, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                              {isDone
                                ? <CheckCircle2 className="h-4 w-4" style={{ color: "#16a34a" }} />
                                : isRunning
                                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: "var(--brand)" }} />
                                  : <Circle className="h-3.5 w-3.5" style={{ color: "var(--ink-300)" }} />}
                            </span>
                            <span
                              className="doc-step-label-text"
                              style={{
                                color: isDone ? "var(--ink-400)" : isRunning ? "var(--brand)" : "var(--ink-700)",
                                textDecoration: isDone ? "line-through" : "none",
                              }}
                            >
                              {trackStep + 1}. {stripStep(plan.steps[trackStep])}
                            </span>
                            <div className="doc-step-label-line" />
                          </div>
                        );
                      }
                    }
                    stepItems.push(renderItem(activity, i, workspace.status === "running" && i === activities.length - 1));
                  });

                  return <div className="doc-flow">{stepItems}</div>;
                })()}

            {workspace.status === "running" && activities.length > 0 && (
              <div className="flex items-center gap-2 mt-6" style={{ color: "var(--ink-400)", fontSize: 12.5 }}>
                <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: "var(--brand)" }} />
                <span>{statusText}</span>
              </div>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </section>

      {rightPanelVisible && (
      <aside className="doc-work-right h-full min-h-0 flex-1 overflow-y-auto p-8">
        <div className="mb-4 flex items-center justify-between">
          <div style={{ color: "var(--ink-900)", fontSize: 15, fontWeight: 750 }}>
            {rightMode === "activity" ? `${selectedActivity?.title || "执行详情"} · LOG` : `${workspace.title || "文档草稿"} · DOCX`}
          </div>
          <div className="flex items-center gap-2">
            {rightModeLocked && rightMode === "activity" && (
              <button
                onClick={unlockRightPanel}
                className="h-7 w-7 rounded-lg flex items-center justify-center transition hover:bg-[var(--hover)]"
                style={{ color: "var(--ink-500)" }}
                title="返回文档"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
            {rightMode === "activity" && !rightModeLocked && (
              <button
                onClick={() => setRightMode("document")}
                className="h-7 w-7 rounded-lg flex items-center justify-center transition hover:bg-[var(--hover)]"
                style={{ color: "var(--ink-500)" }}
                title="查看文档"
              >
                <FileText className="h-3.5 w-3.5" />
              </button>
            )}
	            {workspace.reportId && (
	              <DocumentDownloadMenu
	                canDownload={canDownload}
	                busy={downloadBusy}
	                onDownload={handleDownload}
	                downloadingFormat={downloadingFormat}
	                iconOnly
	              />
	            )}
            <button
              onClick={() => setRightPanelVisible(false)}
              className="h-7 w-7 rounded-lg flex items-center justify-center transition hover:bg-[var(--hover)]"
              style={{ color: "var(--ink-400)" }}
              title="关闭预览"
            >
              <X className="h-3.5 w-3.5" />
            </button>
	          </div>
	        </div>
	        {downloadError && <div className="max-w-[760px] mx-auto doc-download-error">{downloadError}</div>}
        {rightMode === "activity" ? (
          <div className="doc-page max-w-[760px] mx-auto min-h-[760px] p-8">
            <div style={{ color: "var(--ink-400)", fontSize: 12.5, marginBottom: 10 }}>{selectedActivity?.meta || "后台执行详情"}</div>
            <div style={{ color: "var(--ink-900)", fontSize: 18, fontWeight: 750, marginBottom: 18 }}>{selectedActivity?.title || "执行详情"}</div>
            <div style={{ color: "var(--ink-800)", fontSize: 13.5, lineHeight: 1.75 }}>
              <MarkdownContent content={selectedActivity?.content || "暂无更多详情。"} />
            </div>
          </div>
        ) : (
          <DocumentPreviewPane
            preview={artifactPreview}
            loading={artifactPreviewLoading}
            error={artifactPreviewError}
            markdown={previewMarkdown}
            status={workspace.status}
          />
          )}
      </aside>
      )}
    </div>
  );
}

function DocumentPreviewPane({
  preview,
  loading,
  error,
  markdown,
  status,
}: {
  preview: ReportPreview | null;
  loading: boolean;
  error: string;
  markdown: string;
  status: DocumentWorkspaceState["status"];
}) {
  if (loading) {
    return (
      <div className="doc-page max-w-[760px] mx-auto min-h-[980px] p-10">
        <div className="h-full flex flex-col items-center justify-center text-center" style={{ minHeight: 760, color: "var(--ink-400)" }}>
          <Loader2 className="h-8 w-8 mb-3 animate-spin" />
          <div style={{ fontWeight: 700, color: "var(--ink-700)" }}>正在渲染最终文档预览</div>
          <div className="mt-2" style={{ fontSize: 12.5 }}>这里会直接展示 DOCX 内的图表和页面效果。</div>
        </div>
      </div>
    );
  }

  if (preview?.mode === "rendered_pages" && preview.pages?.length) {
    return (
      <div className="doc-rendered-preview max-w-[840px] mx-auto">
        {preview.warning && <div className="doc-preview-note">{preview.warning}</div>}
        {preview.pages.map((src, index) => (
          <img key={`${src.slice(0, 80)}-${index}`} className="doc-rendered-page" src={src} alt={`文档第 ${index + 1} 页`} />
        ))}
      </div>
    );
  }

  if (preview?.mode === "docx_embedded_images" && preview.images?.length) {
    return (
      <div className="doc-page max-w-[760px] mx-auto min-h-[980px] p-10">
        {preview.warning && <div className="doc-preview-note">{preview.warning}</div>}
        <div className="doc-embedded-grid">
          {preview.images.map((src, index) => (
            <figure key={`${src.slice(0, 80)}-${index}`} className="doc-embedded-figure">
              <img src={src} alt={`文档图表 ${index + 1}`} />
            </figure>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="doc-page max-w-[760px] mx-auto min-h-[980px] p-10">
      {error && <div className="doc-preview-note doc-preview-note-error">{error}，已显示文本草稿。</div>}
      {preview?.warning && <div className="doc-preview-note">{preview.warning}</div>}
      {markdown ? (
        <div style={{ color: "var(--ink-900)", fontSize: 14, lineHeight: 1.75 }}>
          <MarkdownContent content={preview?.markdown || markdown} />
          {status === "running" && <span className="doc-stream-caret">▍</span>}
        </div>
      ) : (
        <div className="h-full flex flex-col items-center justify-center text-center" style={{ minHeight: 760, color: "var(--ink-400)" }}>
          <FileCode2 className="h-10 w-10 mb-3" />
          <div style={{ fontWeight: 700, color: "var(--ink-700)" }}>{status === "planning" ? "确认计划后将在这里生成文档" : "正在等待第一段内容..."}</div>
          <div className="mt-2" style={{ fontSize: 12.5 }}>章节草稿会随着后台管线实时写入。</div>
        </div>
      )}
    </div>
  );
}

function DocumentUserPromptCard({
  workspace,
  timeLabel,
}: {
  workspace: DocumentWorkspaceState;
  timeLabel: string;
}) {
  const [copied, setCopied] = useState(false);
  const payload = workspace.pending?.payload;
  const attachments = [
    ...(payload?.templateFile ? [{ name: payload.templateFile.name, size: payload.templateFile.size }] : []),
    ...(payload?.files || []).map((file) => ({ name: file.name, size: file.size })),
  ];
  const primaryAttachment = attachments[0];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(workspace.prompt);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1100);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="doc-user-prompt">
      {primaryAttachment && (
        <div className="doc-user-attachments">
          <div className="doc-user-file-chip" title={primaryAttachment.name}>
            <span className="doc-user-word-icon">W</span>
            <span className="doc-user-file-name">{primaryAttachment.name}</span>
            {attachments.length > 1 && (
              <span style={{ color: "var(--ink-400)", fontSize: 13, fontWeight: 650 }}>
                +{attachments.length - 1}
              </span>
            )}
          </div>
          <div className="doc-user-thumb" aria-hidden="true">
            {Array.from({ length: 14 }).map((_, index) => (
              <span
                key={index}
                className="doc-user-thumb-line"
                style={{ width: `${index % 4 === 0 ? 62 : index % 3 === 0 ? 86 : 100}%` }}
              />
            ))}
          </div>
        </div>
      )}
      <div className="doc-user-bubble">{workspace.prompt}</div>
      <div className="doc-user-meta">
        <span>{timeLabel}</span>
        <button type="button" className="doc-user-copy" onClick={handleCopy} title={copied ? "已复制" : "复制"}>
          <Copy className="h-[15px] w-[15px]" />
        </button>
      </div>
    </div>
  );
}

function initialDocumentSteps(status: DocumentWorkspaceState["status"]) {
  return [
    { id: "understand", label: "理解需求与读取资料", status: status === "planning" ? "pending" : "running" as const },
    { id: "outline", label: "生成计划与文章结构", status: "pending" as const },
    { id: "write", label: "撰写正文并整合数据", status: "pending" as const },
    { id: "qa", label: "质量校验与导出 DOCX", status: "pending" as const },
  ] as Array<{ id: string; label: string; detail?: string; status: "pending" | "running" | "done" | "error" }>;
}

function initialDocumentActivities(workspace: DocumentWorkspaceState): DocumentActivity[] {
  if (workspace.initialActivities?.length) return workspace.initialActivities;
  if (workspace.status === "planning") return [];
  if (workspace.status === "completed") {
    return [{
      id: "history-summary",
      kind: "summary",
      title: "Word 文档已生成",
      content: buildDocumentCompletionSummary(workspace.title, workspace.initialMarkdown || "", []),
      meta: "可下载文档",
    }];
  }
  return [{
    id: "start",
    kind: "status",
    title: "开始执行文档任务",
    content: "我会先读取需求和上传资料，再生成结构、撰写正文并导出 Word 文档。",
  }];
}

function formatPromptTime(value?: string) {
  const parsed = value ? parseServerDate(value) : new Date();
  const date = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function DocumentDownloadMenu({
  canDownload,
  busy,
  onDownload,
  downloadingFormat,
  compact,
  iconOnly,
}: {
  canDownload: boolean;
  busy: boolean;
  onDownload: (format: "docx" | "pdf") => void;
  downloadingFormat: "docx" | "pdf" | null;
  compact?: boolean;
  iconOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const loadingLabel = downloadingFormat ? `正在下载 ${downloadingFormat.toUpperCase()}` : "内容正在生成中";
  const disabled = !canDownload;
  const buttonLabel = busy || disabled ? loadingLabel : "下载文档";
  const handleSelect = (format: "docx" | "pdf") => {
    setOpen(false);
    onDownload(format);
  };

  return (
    <span className="doc-download-wrap">
      <button
        type="button"
        className={`doc-download-btn ${iconOnly ? "doc-download-icon" : ""}`}
        disabled={disabled}
        title={busy || disabled ? loadingLabel : "下载文档"}
        onClick={() => {
          if (!disabled) setOpen((value) => !value);
        }}
      >
        {busy || disabled ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
        {!iconOnly && <span>{buttonLabel}</span>}
      </button>
      {open && (
        <div className="doc-download-menu">
          <button type="button" className="doc-download-option" onClick={() => handleSelect("docx")}>
            <span>DOCX</span>
            <span className="doc-download-meta">Word 文档</span>
          </button>
          <button type="button" className="doc-download-option" onClick={() => handleSelect("pdf")}>
            <span>PDF</span>
            <span className="doc-download-meta">高保真版</span>
          </button>
        </div>
      )}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────
// PlanMiniWidget — compact sticky plan overview during execution
// ─────────────────────────────────────────────────────────────────
function PlanMiniWidget({
  plan,
  currentStep,
  status,
}: {
  plan: { steps: string[] };
  currentStep: number;
  status: DocumentWorkspaceState["status"];
}) {
  const [expanded, setExpanded] = useState(false);
  const doneAll = status === "completed";
  const steps = plan.steps;

  return (
    <div style={{ position: "sticky", top: 0, zIndex: 10, background: "var(--bg)", paddingBottom: 10, marginBottom: 4 }}>
      {/* ── compact header row ── */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 text-left transition"
        style={{
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          borderRadius: expanded ? "14px 14px 0 0" : 14,
          padding: "8px 14px",
          boxShadow: "0 2px 8px rgba(0,0,0,.04)",
        }}
      >
        {doneAll
          ? <CheckCircle2 className="h-4 w-4 flex-shrink-0" style={{ color: "#16a34a" }} />
          : <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin" style={{ color: "var(--brand)" }} />
        }
        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-600)", flexShrink: 0, letterSpacing: "0.01em" }}>
          {doneAll ? "任务规划完成" : "执行中"}
        </span>
        {/* Step dot chips */}
        <div style={{ display: "flex", gap: 3, flex: 1, overflow: "hidden", alignItems: "center" }}>
          {steps.map((step, i) => {
            const done = doneAll || i < currentStep;
            const running = !doneAll && i === currentStep;
            return (
              <div
                key={i}
                title={stripStep(plan.steps[i])}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 999,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  background: done ? "rgba(22,163,74,.1)" : running ? "var(--brand-soft)" : "var(--bg-subtle)",
                  border: `1px solid ${done ? "rgba(22,163,74,.22)" : running ? "var(--brand-border)" : "var(--border)"}`,
                  color: done ? "#16a34a" : running ? "var(--brand)" : "var(--ink-300)",
                  fontSize: 9,
                  fontWeight: 700,
                  transition: "all 0.35s ease",
                }}
              >
                {done
                  ? <CheckCircle2 style={{ width: 11, height: 11 }} />
                  : running
                    ? <Loader2 style={{ width: 9, height: 9 }} className="animate-spin" />
                    : i + 1
                }
              </div>
            );
          })}
        </div>
        <ChevronRight
          className="h-3.5 w-3.5 flex-shrink-0 transition-transform"
          style={{
            color: "var(--ink-300)",
            transform: expanded ? "rotate(90deg)" : "none",
          }}
        />
      </button>

      {/* ── expanded step list ── */}
      {expanded && (
        <div
          style={{
            background: "var(--bg-elevated)",
            borderLeft: "1px solid var(--border)",
            borderRight: "1px solid var(--border)",
            borderBottom: "1px solid var(--border)",
            borderRadius: "0 0 14px 14px",
            padding: "4px 14px 12px",
          }}
        >
          {steps.map((step, i) => {
            const done = doneAll || i < currentStep;
            const running = !doneAll && i === currentStep;
            return (
              <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0" }}>
                {done
                  ? <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" style={{ color: "#16a34a" }} />
                  : running
                    ? <Loader2 className="h-3 w-3 flex-shrink-0 animate-spin" style={{ color: "var(--brand)" }} />
                    : <Circle className="h-3.5 w-3.5 flex-shrink-0" style={{ color: "var(--ink-200)" }} />
                }
                <span style={{
                  fontSize: 12.5,
                  lineHeight: 1.55,
                  flex: 1,
                  color: done ? "var(--ink-400)" : running ? "var(--ink-800)" : "var(--ink-500)",
                  textDecoration: done ? "line-through" : "none",
                }}>
                  {i + 1}. {stripStep(step)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function DocumentActivityIcon({ activity, running }: { activity: DocumentActivity; running: boolean }) {
  if (activity.kind === "summary") return <CheckCircle2 className="h-4 w-4" />;
  if (activity.kind === "section") return <FileText className="h-4 w-4" />;
  if (activity.kind === "thinking") return <Circle className="h-2 w-2 fill-current" />;
  if (activity.kind === "db_query") return <Database className="h-4 w-4" />;
  const title = String(activity.title || "").toUpperCase();
  // Python code / execution / chart
  if (/PYTHON|代码生成|CODE.*GEN|生成.*代码/.test(title)) return <Code2 className="h-4 w-4" />;
  if (/执行.*代码|代码.*执行|PYTHON.*RUN|EXECUTE.*CODE|RUN.*CODE/.test(title)) return <Play className="h-4 w-4" />;
  if (/图表|CHART|PLOT|VISUAL|图形/.test(title)) return <BarChart2 className="h-4 w-4" />;
  if (/SKILL|技能/.test(title) || activity.kind === "tool") return <Terminal className="h-4 w-4" />;
  if (/RESEARCH|检索|资料|读取/.test(title)) return <FileSearch className="h-4 w-4" />;
  if (/SPEC|生成|撰写|写作|PLAN|规划/.test(title)) return <PenLine className="h-4 w-4" />;
  if (/QA|校验|审核|EXPORT|导出|完成/.test(title)) return <ClipboardCheck className="h-4 w-4" />;
  return running ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCode2 className="h-4 w-4" />;
}

function activityActionLabel(activity: DocumentActivity) {
  if (activity.kind === "tool") return "调用工具";
  const title = String(activity.title || "").toUpperCase();
  if (/UNDERSTAND|理解|解析/.test(title)) return "读取需求";
  if (/PLAN|规划|大纲/.test(title)) return "生成结构";
  if (/RESEARCH|检索|资料|数据/.test(title)) return "检索资料";
  if (/SPEC|生成|撰写|写作/.test(title)) return "撰写内容";
  if (/RENDER|渲染|DOC/.test(title)) return "排版渲染";
  if (/QA|校验|审核|QUALITY/.test(title)) return "质量检查";
  if (/EXPORT|导出|完成/.test(title)) return "导出文件";
  return normalizeNodeTitle(activity.title);
}

function activitySubtitle(activity: DocumentActivity) {
  const normalized = normalizeNodeTitle(activity.title);
  const meta = activity.meta || "";
  if (activity.kind === "tool") return activity.title.replace(/^使用\s*/, "") || meta;
  if (meta && meta !== "节点输出") return meta;
  return normalized;
}

function ActivitySubsteps({ activity }: { activity: DocumentActivity }) {
  const steps = summarizeActivitySubsteps(activity);
  if (!steps.length) return null;
  return (
    <div className="doc-activity-substeps">
      {steps.map((step) => (
        <div className="doc-activity-substep" key={step}>{step}</div>
      ))}
    </div>
  );
}

function summarizeActivitySubsteps(activity: DocumentActivity) {
  const content = String(activity.content || "").trim();
  const title = String(activity.title || "");
  if (!content) return [];
  const headingLines = content
    .split(/\r?\n/)
    .map((line) => line.replace(/^#+\s*/, "").replace(/^[-*]\s*/, "").trim())
    .filter((line) => line && !line.startsWith("|") && line.length <= 80)
    .slice(0, 3);
  if (/PLAN|规划|大纲/i.test(title) && headingLines.length) return headingLines;
  if (/RESEARCH|检索|资料|数据/i.test(title)) {
    return [
      content.length > 120 ? "已整理可用资料片段" : "未发现足够外部资料",
      "将按证据口径写入章节",
    ];
  }
  if (/QA|校验|审核|QUALITY/i.test(title)) return ["检查结构完整性", "检查事实口径与导出状态"];
  if (/RENDER|DOC|渲染/i.test(title)) return ["生成 Word 版式", "整理标题、段落与下载文件"];
  return headingLines.length ? headingLines : [content.slice(0, 72)];
}

function normalizeActivityContent(content: string) {
  const text = String(content || "").trim();
  if (!text) return "";
  const genericPatterns = [
    /^后台正在推进该节点/,
    /^正在读取你的需求/,
    /^正在把需求拆成章节结构/,
    /^正在提取可用资料/,
    /^正在生成文档规格/,
    /^正在撰写正文/,
    /^正在把正文渲染为/,
    /^正在检查结构完整性/,
    /^正在生成最终可下载文件/,
    /^我会先读取需求和上传资料/,
  ];
  if (genericPatterns.some((pattern) => pattern.test(text))) return "";
  return text.replace(/\n{3,}/g, "\n\n");
}

function buildMeaningfulProgressContent(phase: string, detail: any) {
  const outline = typeof detail.outline_preview === "string" ? detail.outline_preview.trim() : "";
  const evidence = typeof detail.evidence_preview === "string" ? detail.evidence_preview.trim() : "";
  const section = typeof detail.section_preview === "string" ? detail.section_preview.trim() : "";
  const message = normalizeActivityContent(String(detail.natural_message || ""));
  const parts: string[] = [];
  if (outline) parts.push(formatOutlineArtifact(outline));
  if (evidence) parts.push(formatEvidenceArtifact(evidence, String(detail.section_title || "")));
  if (!outline && !evidence && !section && message) parts.push(message);
  return normalizeActivityContent(parts.filter(Boolean).join("\n\n"));
}

function progressArtifactTitle(phase: string, detail: any) {
  if (detail.section_title && /RESEARCH|检索|资料|数据/i.test(phase)) return `资料口径：${detail.section_title}`;
  if (detail.section_title && /SPEC|生成|撰写|写作/i.test(phase)) return `章节草稿：${detail.section_title}`;
  return normalizeNodeTitle(phase);
}

function progressArtifactMeta(phase: string, detail: any) {
  if (detail.completed && detail.total) return `${detail.completed} / ${detail.total}`;
  if (/PLAN|规划|大纲/i.test(phase)) return "结构产物";
  if (/RESEARCH|检索|资料|数据/i.test(phase)) return "证据产物";
  if (/SPEC|生成|撰写|写作/i.test(phase)) return "正文产物";
  return "过程产物";
}

function formatOutlineArtifact(outline: string) {
  const lines = outline.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const title = lines.find((line) => line.startsWith("#"))?.replace(/^#+\s*/, "") || "文档结构";
  const numbered = lines.filter((line) => /^\d+[.、]\s+/.test(line)).slice(0, 10);
  const bullets = lines.filter((line) => /^[-*]\s+/.test(line)).slice(0, 8);
  return [
    `### ${title}`,
    numbered.length ? numbered.join("\n") : "",
    bullets.length ? `\n关键覆盖点：\n${bullets.join("\n")}` : "",
  ].filter(Boolean).join("\n");
}

function formatEvidenceArtifact(evidence: string, sectionTitle = "") {
  const plain = evidence.replace(/\n{3,}/g, "\n\n").trim();
  if (!plain) return "";
  if (plain.length < 120) {
    return sectionTitle
      ? `### ${sectionTitle}\n\n${plain}`
      : plain;
  }
  const sourceLabels = Array.from(plain.matchAll(/【([^】]{2,40})】/g)).map((match) => match[1]);
  const sourceSummary = Array.from(new Set(sourceLabels)).slice(0, 4);
  const snippets = plain
    .split(/\n+/)
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter((line) => line && !/^【[^】]+】$/.test(line))
    .slice(0, 5);
  return [
    `### ${sectionTitle || "资料提取"}`,
    sourceSummary.length ? `来源/口径：${sourceSummary.join("、")}` : "未发现可引用的外部资料，将避免编造具体事实。",
    snippets.length ? snippets.map((item) => `- ${item.slice(0, 140)}`).join("\n") : "",
  ].filter(Boolean).join("\n\n");
}

function buildDocumentCompletionSummary(
  title: string,
  markdown: string,
  sections: Array<{ title: string; content: string; wordCount?: number }>,
) {
  const sectionTitles = sections.map((section) => section.title).filter(Boolean).slice(0, 6);
  const wordCount = sections.reduce((sum, section) => sum + (section.wordCount || section.content.length || 0), 0);
  const bullets = sectionTitles.length
    ? sectionTitles.map((item) => `- ${item}`).join("\n")
    : markdown
      .split("\n")
      .filter((line) => /^#{1,3}\s+/.test(line))
      .slice(0, 6)
      .map((line) => `- ${line.replace(/^#{1,3}\s+/, "")}`)
      .join("\n");
  return [
    `这份 **${title || "Word 文档"}** 已生成，以下是内容结构概览：`,
    bullets || "- 已完成正文撰写、结构整理和格式校验",
    wordCount ? `约 ${wordCount} 字，已生成可下载的 DOCX 文件。` : "已生成可下载的 DOCX 文件。",
  ].join("\n\n");
}

function normalizeNodeTitle(title: string) {
  const text = String(title || "执行节点").replace(/_/g, " ").trim();
  const map: Record<string, string> = {
    UNDERSTAND: "理解需求与资料",
    PLAN: "生成结构计划",
    RESEARCH: "检索与提取信息",
    SPEC_GEN: "生成文档规格",
    DOC_RENDER: "渲染 Word 文档",
    QA: "质量检查",
    EXPORT: "导出文件",
  };
  return map[text.toUpperCase()] || text;
}

function describeDocumentPhase(phase: string) {
  const text = String(phase || "");
  const upper = text.toUpperCase();
  if (/UNDERSTAND|理解|解析/.test(upper)) return "正在读取你的需求、上传文件和模板信息，确定文档目标、受众、约束和交付格式。";
  if (/PLAN|大纲|规划/.test(upper)) return "正在把需求拆成章节结构和写作任务，确定每个部分要回答的问题。";
  if (/RESEARCH|检索|资料|数据/.test(upper)) return "正在提取可用资料、数据口径和参考信息，避免正文出现空泛内容。";
  if (/SPEC|规格|结构/.test(upper)) return "正在生成文档规格，包括标题层级、段落组织、表格/要点和导出约束。";
  if (/GENERAT|撰写|写作|DRAFT/.test(upper)) return "正在撰写正文，右侧会优先展示实时草稿，收到章节内容后自动替换为完整报告。";
  if (/RENDER|渲染|DOC/.test(upper)) return "正在把正文渲染为 Word 文档版式，并整理标题、页眉页脚和段落样式。";
  if (/QA|校验|审核|QUALITY/.test(upper)) return "正在检查结构完整性、事实口径、格式一致性和可下载文件状态。";
  if (/EXPORT|导出|完成/.test(upper)) return "正在生成最终可下载文件，并整理内容结构摘要。";
  return "后台正在推进该节点，当前输出会持续更新，正文草稿会在右侧展示。";
}

function buildLiveDocumentPreview(
  title: string,
  activities: DocumentActivity[],
  statusText: string,
  status: DocumentWorkspaceState["status"],
) {
  if (status === "planning") return "";
  const useful = activities
    .filter((item) => item.kind === "thinking" || item.kind === "node" || item.kind === "section")
    .slice(-8);
  const nodeLines = useful.map((item) => `- **${normalizeNodeTitle(item.title)}**：${item.kind === "section" ? "章节内容已生成。" : (item.content || describeDocumentPhase(item.title))}`);
  return [
    `# ${title || "文档草稿"}`,
    "",
    "> 正在生成中，收到章节正文后这里会自动切换为完整报告内容。",
    "",
    "## 当前进展",
    "",
    nodeLines.length ? nodeLines.join("\n") : `- ${statusText || "正在启动文档管线"}`,
    "",
    "## 草稿输出",
    "",
    "正在等待第一段正文写入...",
  ].join("\n");
}

function parseSectionPreview(preview: string, detail: any = {}) {
  const lines = String(preview || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const titleLine = lines.find((line) => line.startsWith("#"));
  const title = titleLine ? titleLine.replace(/^#+\s*/, "") : `章节 ${detail.completed || ""}`.trim();
  const content = lines.filter((line) => line !== titleLine).join("\n");
  return {
    section_idx: Number(detail.completed || 1) - 1,
    title: title || "章节草稿",
    content: content || preview,
    word_count: (content || preview || "").length,
  };
}

function extractMarkdownFromReport(report: ReportItem & { output_index?: unknown }) {
  const output = report.output_index as any;
  if (!output || typeof output !== "object") return "";
  const candidates = [
    output.markdown,
    output.final_markdown,
    output.content_markdown,
    output.report_markdown,
    output.draft_markdown,
  ];
  return candidates.find((item) => typeof item === "string" && item.trim().length > 20) || "";
}

function isDocumentReport(report: ReportDetail | ReportItem) {
  const format = String(report.output_format || "").toLowerCase();
  const type = String(report.report_type || "");
  if (format === "chat" || type === "普通问答") return false;
  return ["word", "doc", "docx", "wps"].includes(format) || type.includes("文档") || type.includes("论文") || type.includes("报告") || type.includes("公文");
}

function workspaceFromReport(report: ReportDetail): DocumentWorkspaceState {
  const markdown = extractMarkdownFromReport(report);
  const status = documentWorkspaceStatus(report);
  return {
    status,
    prompt: documentPromptFromReport(report),
    title: report.title || "历史文档",
    reportId: report.id,
    report,
    initialMarkdown: markdown,
    initialActivities: buildRestoredDocumentActivities(report, markdown),
    createdAt: report.created_at,
    error: report.error_message || undefined,
  };
}

function documentWorkspaceStatus(report: ReportItem): DocumentWorkspaceState["status"] {
  if (report.status === "failed") return "error";
  if (report.status === "completed" || report.status === "delivered") return "completed";
  return "running";
}

function documentPromptFromReport(report: ReportDetail | ReportItem) {
  const brief = String(report.brief || "").trim();
  const cleaned = brief
    .replace(/\n\n(?:模型|文档模板|模板|类型|页数|字数|执行方式)[：:][\s\S]*$/u, "")
    .trim();
  return cleaned || report.title || "历史文档任务";
}

function buildRestoredDocumentActivities(report: ReportDetail, markdown = ""): DocumentActivity[] {
  const timeline = Array.isArray(report.timeline) ? report.timeline : [];
  const activities = timeline
    .filter((event) => event.event_type !== "artifact_quality")
    // No slice cap — show the full timeline so all phases remain visible on history review.
    .map((event) => {
      const label = String(event.label || event.event_type || "执行节点");
      const payload = event.payload && typeof event.payload === "object" ? event.payload as Record<string, unknown> : {};
      const detail = payload.detail && typeof payload.detail === "object" ? payload.detail as Record<string, unknown> : payload;
      const richContent = buildMeaningfulProgressContent(label, detail);
      const msgContent = normalizeActivityContent(String(detail.message || ""));
      // For history restore: always include each phase, falling back to the phase description
      // so the full execution timeline remains readable even when no rich artifact was stored.
      const content = richContent || msgContent || describeDocumentPhase(label);
      return {
        id: `history-${event.id}`,
        kind: event.event_type === "skill_invoked" ? "tool" as const : "node" as const,
        title: label,
        content,
        meta: event.created_at ? formatHistoryActivityTime(event.created_at) : "历史节点",
      };
    })
    .filter(Boolean) as DocumentActivity[];
  if (activities.length === 0) {
    activities.push({
      id: "history-start",
      kind: "status",
      title: report.phase || "文档任务",
      content: describeDocumentPhase(report.phase || "文档任务"),
      meta: "历史节点",
    });
  }
  if (report.status === "completed" || report.status === "delivered") {
    activities.push({
      id: "final-summary",
      kind: "summary",
      title: "Word 文档已生成",
      content: buildDocumentCompletionSummary(report.title || "历史文档", markdown, []),
      meta: "可下载文档",
    });
  }
  return activities;
}

function formatHistoryActivityTime(value?: string | null) {
  if (!value) return "历史节点";
  const d = parseServerDate(value);
  if (Number.isNaN(d.getTime())) return "历史节点";
  return d.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function selectBestDocumentDraft(messages: ChatMessage[]) {
  const candidates = messages
    .filter((m) => m.role === "assistant" && (m.content || "").trim().length > 200)
    .map((m) => m.content.trim())
    .filter((content) => !/^QA审核结果/.test(content) && !/^报告已生成完毕/.test(content));
  return candidates.sort((a, b) => b.length - a.length)[0] || "";
}

function mapReportsToConversations(reports: ReportItem[]): Conversation[] {
  const mapped = reports.map(reportToConversation);
  return mapped;
}

function getConversationGroup(dateStr?: string | null): Conversation["group"] {
  if (!dateStr) return "更早";
  const date = parseServerDate(dateStr);
  const diffMs = Date.now() - date.getTime();
  const diffDays = diffMs / (24 * 60 * 60 * 1000);
  if (diffDays < 1) return "今天";
  if (diffDays < 2) return "昨天";
  if (diffDays < 7) return "7 天内";
  if (diffDays < 30) return "30 天内";
  return "更早";
}

function reportToConversation(report: ReportItem): Conversation {
  const isChat = report.output_format === "chat" || report.report_type === "普通问答";
  const tag = report.output_format === "pptx" ? "PPT" : report.output_format === "xlsx" ? "数据分析" : isChat ? "问答" : "文档";
  const running = ["running", "processing", "pending", "planning", "researching", "writing", "reviewing", "paused", "queued"].includes(String(report.status || "").toLowerCase());
  const preview = isChat
    ? (running ? report.phase || "DataAgent 正在回复..." : buildAnswerPreview(report.brief || report.phase || ""))
    : report.phase || report.brief || "报告任务已提交，正在等待 DataAgent 处理";
  return {
    id: String(report.id),
    title: report.title || "未命名研究",
    preview,
    time: formatConversationTime(report.created_at),
    group: getConversationGroup(report.created_at),
    tags: [tag],
    running,
  };
}

function buildAnswerPreview(value?: string | null) {
  const text = toPlainPreviewText(value || "");
  if (!text) return "解答内容 暂无可展示内容";
  return `解答内容 ${truncatePreview(text, 120)}`;
}

function toPlainPreviewText(value: string) {
  return String(value || "")
    .replace(/```[\s\S]*?```/g, "代码片段")
    .replace(/!\[[^\]]*\]\([^)]+\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[#>*_`~\-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function truncatePreview(value: string, maxLength: number) {
  const chars = Array.from(value);
  return chars.length > maxLength ? `${chars.slice(0, maxLength).join("")}...` : value;
}

function ChatConversationView({
  messages,
  busy,
  isLoggedIn,
  onNeedLogin,
  onSubmit,
  onRegenerate,
}: {
  messages: ChatMessage[];
  busy: boolean;
  isLoggedIn: boolean;
  onNeedLogin: () => void;
  onSubmit: (payload: SubmitPayload) => void;
  onRegenerate: (messageId: number | string, prompt: string) => void;
}) {
  const hasPendingAssistant = messages.some((message) => message.role === "assistant" && !message.created_at);
  const showGlobalThinking = busy && !hasPendingAssistant;
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const contentSignature = messages.map((message) => `${message.id}:${message.content.length}`).join("|");
  const artifact = useMemo(() => detectChatArtifact(messages), [contentSignature]);
  const artifactKey = artifact ? `${artifact.type}:${artifact.title}:${artifact.language || ""}:${artifact.content.length}` : "";
  const [panelArtifact, setPanelArtifact] = useState<ChatArtifact | null>(null);
  const [prefillText, setPrefillText] = useState("");
  const prevArtifactKeyRef = useRef("");
  useEffect(() => {
    if (artifact && artifactKey !== prevArtifactKeyRef.current) {
      setPanelArtifact(artifact);
      prevArtifactKeyRef.current = artifactKey;
    }
  }, [artifact, artifactKey]);
  useEffect(() => {
    const node = bottomRef.current;
    if (!node) return;
    try {
      node.scrollIntoView({ behavior: "smooth", block: "end" });
    } catch {
      node.scrollIntoView(false);
    }
  }, [contentSignature, busy]);

  return (
    <div className="h-full min-h-0 flex relative overflow-hidden da-chat-workspace">
      <style>{`
        @media (max-width: 1180px) {
          .da-chat-workspace { display: flex; overflow: hidden; }
          .da-chat-left { width: 100% !important; min-width: 0 !important; }
          .da-artifact-panel { display: none !important; }
        }
        .da-bubble {
          content-visibility: auto;
          contain-intrinsic-size: auto 80px;
        }
        /* Claude-style message area */
        .da-msg-area {
          width: 100%;
          max-width: 780px;
          margin: 0 auto;
          padding: 36px 20px 16px;
        }
        .da-msg-list {
          display: flex;
          flex-direction: column;
          gap: 28px;
        }
        /* Input bar stays pinned at bottom */
        .da-input-bar {
          flex-shrink: 0;
          padding: 6px 16px 18px;
          background: var(--bg, #f7f7f5);
        }
        .da-input-inner {
          max-width: 780px;
          margin: 0 auto;
        }
      `}</style>

      <div className="da-chat-left h-full min-h-0 overflow-hidden flex flex-col relative" style={{ width: panelArtifact ? "52%" : "100%", minWidth: panelArtifact ? 520 : 0 }}>
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="da-msg-area">
            <div className="da-msg-list">
              {messages.map((message) => (
                <ChatBubble
                  key={message.id}
                  message={message}
                  showFeedback={message.role === "assistant" && Boolean(message.created_at)}
                  onSelectArtifact={(a) => setPanelArtifact(a)}
                  onEditMessage={(text) => setPrefillText(text)}
                  onRegenerate={(text) => onRegenerate(message.id, text)}
                />
              ))}
              {showGlobalThinking && (
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 h-7 w-7 rounded-full flex items-center justify-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                    <Sparkles className="h-3.5 w-3.5" />
                  </div>
                  <ThinkingPhaseDisplay />
                </div>
              )}
              <div ref={bottomRef} style={{ height: 1, scrollMarginBottom: 24 }} />
            </div>
          </div>
        </div>

        <div className="da-input-bar">
          <div className="da-input-inner">
            <ChatInput
              isLoggedIn={isLoggedIn}
              onNeedLogin={onNeedLogin}
              onSubmit={onSubmit}
              busy={busy}
              prefillText={prefillText}
              onPrefillConsumed={() => setPrefillText("")}
            />
          </div>
        </div>
      </div>

      {panelArtifact && <ArtifactPanel artifact={panelArtifact} streaming={busy} onClose={() => setPanelArtifact(null)} />}
    </div>
  );
}

const THINKING_PHASES = [
  "分析问题",
  "工具调用中",
  "检索相关知识",
  "整理回答",
  "构建输出",
];

function ThinkingPhaseDisplay({ initialPhase }: { initialPhase?: string } = {}) {
  const phases = initialPhase
    ? [initialPhase, ...THINKING_PHASES.filter((p) => p !== initialPhase)]
    : THINKING_PHASES;
  const [idx, setIdx] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const advance = () => {
      setVisible(false);
      setTimeout(() => {
        setIdx((prev) => (prev + 1) % phases.length);
        setVisible(true);
      }, 220);
    };
    const timer = setInterval(advance, 2200);
    return () => clearInterval(timer);
  }, [phases.length]);

  return (
    <>
      <style>{`
        @keyframes da-thinking-dot {
          0%, 100% { opacity: 0.25; transform: scale(0.75); }
          50% { opacity: 1; transform: scale(1.1); }
        }
        .da-thinking-wrap {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 11px 16px;
          border-radius: 16px;
          border: 1px solid var(--border);
          background: var(--bg-elevated);
          transition: opacity 0.22s ease;
          width: fit-content;
        }
        .da-thinking-dot {
          width: 5px;
          height: 5px;
          border-radius: 999px;
          background: var(--brand);
          display: inline-block;
          flex-shrink: 0;
        }
        .da-thinking-label {
          color: var(--ink-600);
          font-size: 13.5px;
          font-weight: 500;
          white-space: nowrap;
        }
      `}</style>
      <div className="da-thinking-wrap" style={{ opacity: visible ? 1 : 0 }}>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="da-thinking-dot"
              style={{ animation: `da-thinking-dot 1.1s ease-in-out ${i * 0.18}s infinite` }}
            />
          ))}
        </div>
        <span className="da-thinking-label">{phases[idx]}</span>
      </div>
    </>
  );
}

function ChatBubble({
  message,
  showFeedback = false,
  onSelectArtifact,
  onEditMessage,
  onRegenerate,
}: {
  message: ChatMessage;
  showFeedback?: boolean;
  onSelectArtifact?: (artifact: ChatArtifact) => void;
  onEditMessage?: (text: string) => void;
  onRegenerate?: (text: string) => void;
}) {
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [showFeedbackBox, setShowFeedbackBox] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editDraft, setEditDraft] = useState(message.content);
  const editRef = useRef<HTMLTextAreaElement>(null);
  const isUser = message.role === "user";

  const handleCopy = () => {
    void navigator.clipboard?.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  const startEditing = () => {
    setEditDraft(message.content);
    setEditing(true);
    setTimeout(() => {
      if (editRef.current) {
        editRef.current.focus();
        editRef.current.setSelectionRange(editRef.current.value.length, editRef.current.value.length);
        editRef.current.style.height = "auto";
        editRef.current.style.height = `${editRef.current.scrollHeight}px`;
      }
    }, 30);
  };

  const cancelEditing = () => {
    setEditing(false);
    setEditDraft(message.content);
  };

  const submitEdit = () => {
    const text = editDraft.trim();
    if (!text) return;
    setEditing(false);
    onRegenerate?.(text);
  };

  if (isUser) {
    if (editing) {
      return (
        <div className="da-bubble flex flex-col items-end">
          <style>{`
            @keyframes da-action-in {
              from { opacity: 0; transform: translateY(2px); }
              to   { opacity: 1; transform: translateY(0); }
            }
            .da-edit-box {
              width: 100%;
              max-width: 80%;
              border-radius: 18px;
              border: 1.5px solid var(--brand-border, rgba(91,78,232,0.35));
              background: var(--bg-elevated);
              padding: 12px 14px 10px;
              box-shadow: 0 0 0 3px rgba(91,78,232,0.08);
            }
            .da-edit-textarea {
              width: 100%;
              background: transparent;
              border: none;
              outline: none;
              resize: none;
              overflow: hidden;
              color: var(--ink-900);
              font-size: 15px;
              line-height: 1.65;
              min-height: 36px;
              font-family: inherit;
            }
            .da-edit-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); }
            .da-edit-btn { height: 30px; padding: 0 12px; border-radius: 9px; font-size: 12.5px; font-weight: 550; display: inline-flex; align-items: center; cursor: pointer; transition: opacity .15s; }
            .da-edit-btn:hover { opacity: .8; }
          `}</style>
          {message.attachedFiles && message.attachedFiles.length > 0 && (
            <div className="flex flex-wrap justify-end gap-1.5 mb-2">
              {message.attachedFiles.map((f, i) => (
                <div key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl"
                  style={{ background: "rgba(0,0,0,.05)", border: "1px solid rgba(0,0,0,.08)", fontSize: 12, color: "var(--ink-700)" }}>
                  <File className="h-3 w-3 flex-shrink-0" style={{ color: "var(--brand)" }} />
                  <span className="max-w-[180px] truncate font-medium">{f.name}</span>
                  <span style={{ color: "var(--ink-400)", fontSize: 11 }}>{f.size}</span>
                </div>
              ))}
            </div>
          )}
          <div className="da-edit-box">
            <textarea
              ref={editRef}
              className="da-edit-textarea"
              value={editDraft}
              onChange={(e) => {
                setEditDraft(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${e.target.scrollHeight}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitEdit(); }
                if (e.key === "Escape") cancelEditing();
              }}
            />
            <div className="da-edit-actions">
              <button className="da-edit-btn" onClick={cancelEditing}
                style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", color: "var(--ink-600)" }}>
                取消
              </button>
              <button className="da-edit-btn" onClick={submitEdit}
                style={{ background: "var(--ink-900)", color: "#fff", border: "none" }}>
                重新发送
              </button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div
        className="da-bubble flex flex-col items-end"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <style>{`
          @keyframes da-action-in {
            from { opacity: 0; transform: translateY(2px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        `}</style>

        {/* Attached file chips */}
        {message.attachedFiles && message.attachedFiles.length > 0 && (
          <div className="flex flex-wrap justify-end gap-1.5 mb-2">
            {message.attachedFiles.map((f, i) => (
              <div
                key={i}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl"
                style={{ background: "rgba(0,0,0,.05)", border: "1px solid rgba(0,0,0,.08)", fontSize: 12, color: "var(--ink-700)" }}
              >
                <File className="h-3 w-3 flex-shrink-0" style={{ color: "var(--brand)" }} />
                <span className="max-w-[180px] truncate font-medium">{f.name}</span>
                <span style={{ color: "var(--ink-400)", fontSize: 11 }}>{f.size}</span>
              </div>
            ))}
          </div>
        )}

        {/* Bubble row */}
        <div className="w-full flex justify-end items-end">
          <div className="relative flex justify-end" style={{ maxWidth: "80%" }}>
            {hovered && (
              <div
                className="absolute inline-flex items-center gap-1"
                style={{
                  right: "100%",
                  bottom: 3,
                  marginRight: 8,
                  width: "max-content",
                  color: "var(--ink-400)",
                  zIndex: 5,
                  animation: "da-action-in 0.15s ease-out",
                }}
              >
                {onRegenerate && (
                  <button
                    onClick={() => onRegenerate(message.content)}
                    className="h-6 w-6 inline-flex items-center justify-center rounded-md transition hover:bg-[var(--hover)]"
                    style={{ color: "var(--ink-400)" }}
                    title="重新发送"
                  >
                    <RotateCcw className="h-[14px] w-[14px]" />
                  </button>
                )}
                {(onRegenerate || onEditMessage) && (
                  <button
                    onClick={startEditing}
                    className="h-6 w-6 inline-flex items-center justify-center rounded-md transition hover:bg-[var(--hover)]"
                    style={{ color: "var(--ink-400)" }}
                    title="编辑后重新发送"
                  >
                    <Pencil className="h-[14px] w-[14px]" />
                  </button>
                )}
                <button
                  onClick={handleCopy}
                  className="h-6 w-6 inline-flex items-center justify-center rounded-md transition hover:bg-[var(--hover)]"
                  style={{ color: "var(--ink-400)" }}
                  title={copied ? "已复制" : "复制"}
                >
                  <Copy className="h-[14px] w-[14px]" />
                </button>
                {copied && (
                  <span
                    style={{
                      position: "absolute",
                      right: 0,
                      top: "calc(100% + 4px)",
                      padding: "3px 7px",
                      borderRadius: 7,
                      background: "var(--ink-900)",
                      color: "#fff",
                      fontSize: 11,
                      whiteSpace: "nowrap",
                      boxShadow: "0 4px 12px rgba(0,0,0,.12)",
                    }}
                  >
                    已复制
                  </span>
                )}
              </div>
            )}
            {/* Claude-style user bubble */}
            <div
              className="rounded-[18px] px-4 py-2.5"
              style={{
                background: "rgba(0,0,0,.07)",
                color: "var(--ink-900)",
                fontSize: 15,
                lineHeight: 1.65,
                width: "fit-content",
                maxWidth: "min(100%, 36em)",
                whiteSpace: "pre-wrap",
                overflowWrap: "break-word",
                wordBreak: "normal",
              }}
            >
              {message.content}
            </div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="da-bubble flex items-start gap-3">
      {/* Claude-style sparkle icon — small circle */}
      <div
        className="flex-shrink-0 h-[30px] w-[30px] rounded-full flex items-center justify-center"
        style={{ background: "var(--brand-soft, rgba(91,78,232,0.1))", color: "var(--brand, #5b4ee8)", marginTop: 1 }}
      >
        <Sparkles className="h-3.5 w-3.5" />
      </div>
      <div
        className="min-w-0 flex-1"
        style={{ color: "var(--ink-900)", fontSize: 15, lineHeight: 1.75 }}
      >
        {message.content ? (
          message.streaming ? (
            <StreamingMarkdown content={message.content} />
          ) : (
            <MarkdownContent content={message.content} onSelectArtifact={onSelectArtifact} />
          )
        ) : (
          <ThinkingPhaseDisplay />
        )}
        {showFeedback && (
          <div
            className="mt-3 flex items-center gap-1.5 flex-wrap"
            style={{ color: "var(--ink-400)", fontSize: 11, lineHeight: 1.4, fontWeight: 500 }}
          >
            <span>{formatMessageTime(message.created_at)}</span>
            <span style={{ width: 3, height: 3, borderRadius: 999, background: "var(--ink-300)", display: "inline-block" }} />
            <button
              onClick={() => setFeedback(feedback === "up" ? null : "up")}
              className="h-[20px] px-1 inline-flex items-center gap-1 rounded-md transition hover:bg-[var(--hover)]"
              style={{ color: feedback === "up" ? "var(--ink-700)" : "inherit", font: "inherit" }}
            >
              <ThumbsUp className="h-[11px] w-[11px]" />
              有用
            </button>
            <button
              onClick={() => setFeedback(feedback === "down" ? null : "down")}
              className="h-[20px] px-1 inline-flex items-center gap-1 rounded-md transition hover:bg-[var(--hover)]"
              style={{ color: feedback === "down" ? "var(--ink-700)" : "inherit", font: "inherit" }}
            >
              <ThumbsDown className="h-[11px] w-[11px]" />
              不准
            </button>
            <button
              onClick={() => {
                setFeedback("down");
                setShowFeedbackBox((v) => !v);
              }}
              className="h-[20px] px-1 inline-flex items-center gap-1 rounded-md transition hover:bg-[var(--hover)]"
              style={{ color: "inherit", font: "inherit" }}
            >
              <MessageCircle className="h-[11px] w-[11px]" />
              反馈
            </button>
          </div>
        )}
        {showFeedback && showFeedbackBox && (
          <div className="mt-2 rounded-lg p-2.5" style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)" }}>
            {feedbackSent ? (
              <div style={{ color: "var(--ink-500)", fontSize: 11.5 }}>已收到反馈，我们会用于改进回答质量。</div>
            ) : (
              <>
                <textarea
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                  placeholder="请描述哪里不准确、遗漏或格式不理想..."
                  className="w-full resize-none bg-transparent outline-none"
                  style={{ minHeight: 48, color: "var(--ink-800)", fontSize: 12, lineHeight: 1.5 }}
                />
                <div className="flex justify-end gap-2 mt-1">
                  <button
                    onClick={() => setShowFeedbackBox(false)}
                    className="h-6 px-2 rounded-md transition hover:bg-[var(--hover)]"
                    style={{ color: "var(--ink-500)", fontSize: 11.5 }}
                  >
                    取消
                  </button>
                  <button
                    onClick={() => setFeedbackSent(true)}
                    className="h-6 px-2 rounded-md"
                    style={{ background: "var(--ink-900)", color: "#fff", fontSize: 11.5 }}
                  >
                    提交反馈
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function detectChatArtifact(messages: ChatMessage[]): ChatArtifact | null {
  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant" && message.content.trim());
  if (!latestAssistant) return null;
  // Don't pop the right-side artifact panel while the answer is still
  // streaming — code fences are often half-open mid-stream and the
  // detection misfires on incomplete content. Wait for completion.
  if (latestAssistant.streaming) return null;
  const content = latestAssistant.content.trim();
  const code = extractLastCodeBlock(content);
  if (code && shouldPromoteCodeArtifact(code.language, code.code, content)) {
    return {
      type: "code",
      title: codeTitle(code.language, code.code),
      language: code.language || "text",
      content: code.code,
    };
  }

  const docArtifact = detectDocumentArtifact(content);
  return docArtifact;
}

function extractLastCodeBlock(content: string): { language: string; code: string } | null {
  const matches: Array<{ language: string; code: string }> = [];
  const fence = /```([a-zA-Z0-9_+#.-]*)\s*\n([\s\S]*?)(?:```|$)/g;
  let match: RegExpExecArray | null;
  while ((match = fence.exec(content))) {
    const code = (match[2] || "").trimEnd();
    if (code.trim()) matches.push({ language: (match[1] || "").trim().toLowerCase(), code });
  }
  if (!matches.length) return null;
  return matches.sort((a, b) => b.code.length - a.code.length)[0];
}

function shouldPromoteCodeArtifact(language: string, code: string, fullContent: string) {
  const lang = language.toLowerCase();
  if (["js", "jsx", "ts", "tsx", "python", "py", "html", "css", "sql", "json", "yaml", "yml", "bash", "sh", "go", "java", "cpp", "c", "rust"].includes(lang)) {
    return code.length >= 150;
  }
  if (/生成|新建|实现|代码|脚本|组件|页面|函数|class|interface|def |import |export |SELECT |CREATE TABLE/i.test(fullContent + "\n" + code)) {
    return code.length > 200;
  }
  return false;
}

function codeTitle(language: string, code: string) {
  const firstNamed = code.match(/(?:function|class|interface|type|def)\s+([A-Za-z0-9_]+)/);
  if (firstNamed?.[1]) return firstNamed[1];
  const lang = language ? language.toUpperCase() : "CODE";
  return `${lang} 代码`;
}

function codeCardTitle(language: string, code: string) {
  const firstNamed = code.match(/(?:function|class|interface|type|def)\s+([A-Za-z0-9_]+)/);
  const lang = language ? language.toUpperCase() : "CODE";
  if (firstNamed?.[1]) return `${firstNamed[1]} · ${lang}`;
  return `${lang} 代码`;
}

function detectDocumentArtifact(content: string): ChatArtifact | null {
  const headingCount = (content.match(/^#{1,3}\s+/gm) || []).length;
  const tableCount = (content.match(/^\|.+\|$/gm) || []).length;
  // Require content to start with a heading (documents/drafts do; Q&A answers typically don't)
  const startsWithHeading = /^\s*#{1,3}\s+/.test(content);
  const hasLongStructuredDraft = content.length > 800 && headingCount >= 3 && startsWithHeading;
  const lower = content.toLowerCase();
  const isPpt = /ppt|powerpoint|演示文稿|幻灯片|封面页|目录页|结束页|第\s*\d+\s*页/.test(lower);
  // Only trigger sheet when the user explicitly asked for spreadsheet/Excel content — a table alone is not a spreadsheet
  const isSheet = /excel|xlsx|工作簿|工作表|数据透视/.test(lower) && tableCount >= 1;
  // isDoc is intentionally NOT used as a standalone trigger — the model may
  // discuss a document topic without producing one. Only promote when the
  // response is actually structured as a document (starts with a heading).
  if (!hasLongStructuredDraft && !isPpt && !isSheet) return null;

  const type: ChatArtifact["type"] = isPpt ? "ppt" : isSheet ? "sheet" : "document";
  return {
    type,
    title: artifactTitle(type, content),
    content: stripArtifactPreamble(content),
  };
}

function artifactTitle(type: ChatArtifact["type"], content: string) {
  const heading = content.match(/^#\s+(.+)$/m)?.[1]?.trim();
  if (heading) return heading.slice(0, 60);
  if (type === "ppt") return "演示文稿草稿";
  if (type === "sheet") return "表格与数据草稿";
  return "文档草稿";
}

function stripArtifactPreamble(content: string) {
  const firstHeading = content.search(/^#{1,3}\s+/m);
  if (firstHeading > 0 && firstHeading < 240) return content.slice(firstHeading).trim();
  return content;
}

function ArtifactPanel({ artifact, streaming, onClose }: { artifact: ChatArtifact; streaming: boolean; onClose: () => void }) {
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const artifactKey = `${artifact.type}:${artifact.title}:${artifact.language || ""}`;
  const [draft, setDraft] = useState(artifact.content);
  const [dirty, setDirty] = useState(false);
  const [runningCode, setRunningCode] = useState(false);
  const [runResult, setRunResult] = useState("");

  useEffect(() => {
    const node = bodyRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [artifact.content.length]);

  useEffect(() => {
    setDraft(artifact.content);
    setDirty(false);
    setRunResult("");
  }, [artifactKey]);

  useEffect(() => {
    if (!dirty) setDraft(artifact.content);
  }, [artifact.content, dirty]);

  const Icon = artifact.type === "code" ? Code2 : artifact.type === "ppt" ? Presentation : artifact.type === "sheet" ? Table2 : FileText;
  const label = artifact.type === "code" ? (artifact.language || "code") : artifact.type === "ppt" ? "PPT 草稿" : artifact.type === "sheet" ? "Excel 草稿" : "文档草稿";
  const activeContent = dirty ? draft : artifact.content;
  const canRun = artifact.type === "code" && isRunnableCodeLanguage(artifact.language || "");
  const runArtifact = async () => {
    if (!canRun || runningCode) return;
    setRunningCode(true);
    setRunResult("正在执行...");
    try {
      const result = await executeArtifactCode(artifact.language || "text", activeContent);
      setRunResult(result);
    } catch (error) {
      setRunResult(error instanceof Error ? error.message : "执行失败，请检查代码。");
    } finally {
      setRunningCode(false);
    }
  };

  return (
    <aside
      className="da-artifact-panel h-full flex-1 min-w-0"
      style={{ borderLeft: "1px solid var(--border)", background: "var(--bg-elevated)" }}
    >
      <div className="h-full flex flex-col">
        <div className="h-12 px-4 flex items-center justify-between flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-7 w-7 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
              <Icon className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0">
              <div className="truncate" style={{ color: "var(--ink-900)", fontWeight: 700, fontSize: 13.5 }}>{artifact.title}</div>
              <div className="flex items-center gap-1.5" style={{ color: "var(--ink-400)", fontSize: 11 }}>
                {streaming && <span className="da-artifact-dot" />}
                <span>{streaming ? "正在写入" : "已生成"} · {label}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {artifact.type === "code" && (
              <button
                className="h-8 px-2.5 inline-flex items-center gap-1.5 rounded-lg transition hover:bg-[var(--hover)] disabled:opacity-50"
                style={{ color: canRun ? "var(--ink-700)" : "var(--ink-300)", fontSize: 12, fontWeight: 650 }}
                title={canRun ? "运行代码" : "当前语言暂不支持直接运行"}
                disabled={!canRun || runningCode}
                onClick={runArtifact}
              >
                <Play className="h-3.5 w-3.5" />
                <span>{runningCode ? "运行中" : "运行"}</span>
              </button>
            )}
            <button
              className="h-8 w-8 inline-flex items-center justify-center rounded-lg transition hover:bg-[var(--hover)]"
              style={{ color: "var(--ink-500)" }}
              title="复制内容"
              onClick={() => void navigator.clipboard?.writeText(activeContent)}
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
            <button
              className="h-8 w-8 inline-flex items-center justify-center rounded-lg transition hover:bg-[var(--hover)]"
              style={{ color: "var(--ink-500)" }}
              title="关闭右侧内容"
              onClick={onClose}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
        <style>{`
          @keyframes da-artifact-pulse {
            0%, 100% { opacity: .35; transform: scale(.8); }
            50% { opacity: 1; transform: scale(1.1); }
          }
          .da-artifact-dot {
            width: 6px;
            height: 6px;
            border-radius: 999px;
            background: var(--brand);
            display: inline-block;
            animation: da-artifact-pulse 1s ease-in-out infinite;
          }
          .da-code-artifact {
            font-family: var(--font-mono), ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 12.5px;
            line-height: 1.65;
            white-space: pre-wrap;
            tab-size: 2;
          }
          .da-code-editor-shell {
            min-height: 100%;
            padding: 12px;
            background: #f7f7f5;
          }
          .da-code-editor-frame {
            overflow: hidden;
            border-radius: 10px;
            border: 1px solid rgba(0,0,0,.08);
            box-shadow: 0 14px 34px rgba(0,0,0,.10);
            background: #171717;
          }
          .da-code-output-frame {
            margin-top: 12px;
            overflow: hidden;
            border-radius: 10px;
            border: 1px solid rgba(0,0,0,.08);
            box-shadow: 0 10px 26px rgba(0,0,0,.08);
            background: #171717;
          }
          .da-code-editor-bar {
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 12px;
            border-bottom: 1px solid rgba(255,255,255,.08);
            background: #202020;
            color: #a3a3a3;
            font-size: 11px;
            font-weight: 650;
          }
          .da-code-editor-wrap {
            position: relative;
            background: #171717;
            color: #d4d4d4;
          }
          .da-code-editor-highlight {
            position: absolute;
            inset: 0;
            margin: 0;
            overflow: hidden;
            pointer-events: none;
            color: #d4d4d4;
          }
          .da-code-editor-highlight code {
            white-space: pre-wrap;
            word-break: break-word;
          }
          .da-code-editor-wrap .tok-comment { color: #6a9955; }
          .da-code-editor-wrap .tok-string { color: #ce9178; }
          .da-code-editor-wrap .tok-keyword { color: #569cd6; }
          .da-code-editor-wrap .tok-number { color: #b5cea8; }
          .da-code-editor-wrap .tok-function { color: #dcdcaa; }
          .da-code-editor {
            width: 100%;
            min-height: 100%;
            display: block;
            border: 0;
            outline: none;
            resize: none;
            color: transparent;
            -webkit-text-fill-color: transparent;
            background: transparent;
            caret-color: #ffffff;
            position: relative;
            z-index: 1;
          }
          .da-code-editor::selection { background: rgba(38, 79, 120, .95); }
          .da-code-run-result {
            color: #d4d4d4;
          }
          .da-code-run-result pre {
            margin: 0;
            max-height: 260px;
            overflow: auto;
            background: #171717;
            color: #d4d4d4;
            white-space: pre-wrap;
            word-break: break-word;
            font-family: var(--font-mono), ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 12px;
            line-height: 1.55;
          }
          .da-doc-artifact {
            font-size: 14px;
            line-height: 1.75;
            color: var(--ink-900);
          }
          .da-doc-artifact .da-markdown h1 { font-size: 22px; }
          .da-doc-artifact .da-markdown h2 { font-size: 18px; }
        `}</style>
        <div ref={bodyRef} className="flex-1 overflow-auto">
          {artifact.type === "code" ? (
            <div className="da-code-editor-shell">
              <div className="da-code-editor-frame">
                <div className="da-code-editor-bar">
                  <span>{artifact.language || "code"}</span>
                  <span>{activeContent.split("\n").length} 行</span>
                </div>
                <div
                  className="da-code-editor-wrap"
                  style={{ minHeight: 420, height: Math.max(420, activeContent.split("\n").length * 21 + 48) }}
                >
                  <pre className="da-code-artifact da-code-editor-highlight p-5" aria-hidden="true">
                    <code>{highlightCode(activeContent, artifact.language || "text")}</code>
                  </pre>
                  <textarea
                    className="da-code-artifact da-code-editor p-5"
                    value={activeContent}
                    spellCheck={false}
                    onChange={(event) => {
                      setDirty(true);
                      setDraft(event.target.value);
                    }}
                  />
                </div>
              </div>
              {runResult && (
                <div className="da-code-output-frame da-code-run-result">
                  <div className="da-code-editor-bar">
                    <span>运行结果</span>
                    <span>{runningCode ? "执行中" : "完成"}</span>
                  </div>
                  <pre className="p-5">{runResult}</pre>
                </div>
              )}
            </div>
          ) : (
            <div className="da-doc-artifact p-6 max-w-[760px] mx-auto">
              <MarkdownContent content={activeContent} />
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

function normalizeCodeLanguage(language: string) {
  const lang = (language || "text").trim().toLowerCase();
  if (lang === "py") return "python";
  if (lang === "js") return "javascript";
  if (lang === "jsx") return "javascript";
  return lang;
}

function isRunnableCodeLanguage(language: string) {
  const lang = normalizeCodeLanguage(language);
  return ["python", "javascript", "json"].includes(lang);
}

async function executeArtifactCode(language: string, code: string) {
  const lang = normalizeCodeLanguage(language);
  if (lang === "python") {
    const result = await api.executeCode({ language: "python", code });
    const output: string[] = [];
    if (result.stdout?.trim()) output.push(result.stdout.trimEnd());
    if (result.stderr?.trim()) output.push(`stderr:\n${result.stderr.trimEnd()}`);
    if (result.error) output.push(result.error.trimEnd());
    const variables = result.variables || {};
    const variableText = Object.keys(variables).length ? formatExecutionValue(variables) : "";
    if (variableText) output.push(`variables:\n${variableText}`);
    if (result.figures?.length) output.push(`已生成 ${result.figures.length} 张图，图像结果已由后端捕获。`);
    if (typeof result.exec_ms === "number") output.push(`耗时 ${result.exec_ms} ms`);
    return output.filter(Boolean).join("\n\n") || (result.ok ? "执行完成，没有输出。" : "执行失败，没有返回错误详情。");
  }
  if (lang === "json") {
    return JSON.stringify(JSON.parse(code), null, 2);
  }
  if (lang === "javascript") {
    return executeJavaScriptSnippet(code);
  }
  throw new Error("当前语言暂不支持直接运行。");
}

function executeJavaScriptSnippet(code: string): Promise<string> {
  return new Promise((resolve, reject) => {
    if (typeof Worker === "undefined" || typeof Blob === "undefined" || typeof URL === "undefined") {
      reject(new Error("当前浏览器不支持本地 JavaScript 沙箱执行。"));
      return;
    }
    const workerSource = `
      self.onmessage = async function(event) {
        var logs = [];
        function format(value) {
          if (typeof value === "undefined") return "undefined";
          if (typeof value === "string") return value;
          try { return JSON.stringify(value, null, 2); } catch (error) { return String(value); }
        }
        var consoleProxy = {
          log: function() { logs.push(Array.prototype.map.call(arguments, format).join(" ")); },
          error: function() { logs.push("error: " + Array.prototype.map.call(arguments, format).join(" ")); },
          warn: function() { logs.push("warn: " + Array.prototype.map.call(arguments, format).join(" ")); }
        };
        try {
          var fn = new Function("console", "\\"use strict\\";\\n" + event.data);
          var value = fn(consoleProxy);
          if (value && typeof value.then === "function") value = await value;
          self.postMessage({ ok: true, text: logs.concat(typeof value === "undefined" ? [] : ["return: " + format(value)]).join("\\n") || "执行完成，没有输出。" });
        } catch (error) {
          self.postMessage({ ok: false, text: error && error.stack ? error.stack : String(error) });
        }
      };
    `;
    const url = URL.createObjectURL(new Blob([workerSource], { type: "text/javascript" }));
    const worker = new Worker(url);
    const timer = window.setTimeout(() => {
      worker.terminate();
      URL.revokeObjectURL(url);
      reject(new Error("执行超时，请检查是否存在死循环。"));
    }, 3000);
    worker.onmessage = (event) => {
      window.clearTimeout(timer);
      worker.terminate();
      URL.revokeObjectURL(url);
      resolve(String(event.data?.text || "执行完成，没有输出。"));
    };
    worker.onerror = (event) => {
      window.clearTimeout(timer);
      worker.terminate();
      URL.revokeObjectURL(url);
      reject(new Error(event.message || "JavaScript 执行失败。"));
    };
    worker.postMessage(code);
  });
}

function stripPlanStepNumber(value: string) {
  return String(value || "").replace(/^\s*(?:\d+|[一二三四五六七八九十]+)[\.、\)]\s*/, "").trim();
}

function optionLetter(index: number) {
  return String.fromCharCode(65 + (index % 26));
}

function formatExecutionValue(value: unknown) {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

// Hybrid renderer used during streaming. Splits the content at the last
// "definitely closed" boundary (closed code fence or \n\n outside a fence):
//   - closed blocks before that boundary -> proper markdown (parsed only
//     when the boundary advances; memoized per block)
//   - everything after -> plain text with pre-wrap (no parsing, no regex)
// This gives Claude-style "line/block lights up as it completes" feel
// while keeping the hot-path per-token cost essentially free.
//
// useDeferredValue marks the streamed string as a low-priority update so
// React can pause this re-render to keep input/scroll/sidebar responsive
// under fast token bursts.
const StreamingMarkdown = memo(function StreamingMarkdown({ content }: { content: string }) {
  const deferredContent = useDeferredValue(content);
  const splitIdx = useMemo(() => findStableSplitIndex(deferredContent), [deferredContent]);
  const stableContent = deferredContent.slice(0, splitIdx);
  const tail = deferredContent.slice(splitIdx);
  // Closed-block parse — only re-runs when stableContent value actually changes.
  const stableBlocks = useMemo(() => parseMarkdownBlocks(stableContent), [stableContent]);
  // Track tail length to split "already visible" from "freshly arrived" text.
  const prevTailRef = useRef("");
  const oldTail = tail.startsWith(prevTailRef.current) ? prevTailRef.current : "";
  const newTail = tail.slice(oldTail.length);
  // Bucket new tail into ~60-char chunks so the fade-in key only changes
  // every chunk rather than every character — keeps DOM churn minimal.
  const newTailKey = Math.floor(tail.length / 60);
  useEffect(() => { prevTailRef.current = tail; });
  return (
    <div className="da-markdown da-streaming">
      <style>{`
        .da-streaming-caret {
          display: inline-block;
          margin-left: 1px;
          color: var(--brand);
          animation: da-caret-blink 1s steps(2, start) infinite;
          vertical-align: text-bottom;
        }
        @keyframes da-caret-blink { to { visibility: hidden; } }
        .da-streaming-tail {
          white-space: pre-wrap;
          word-break: break-word;
          margin: 0;
        }
        @keyframes da-block-in {
          from { opacity: 0; transform: translateY(3px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .da-streaming > *:not(.da-streaming-caret-lone) {
          animation: da-block-in 0.28s ease-out backwards;
        }
        @keyframes da-tail-new-in {
          from { opacity: 0.3; }
          to   { opacity: 1; }
        }
        .da-tail-new {
          animation: da-tail-new-in 0.18s ease-out;
        }
      `}</style>
      {stableBlocks.map((block, index) => renderMarkdownBlock(block, `s${index}`))}
      {tail && (
        <p className="da-streaming-tail">
          {oldTail}
          <span key={newTailKey} className="da-tail-new">{newTail}</span>
          <span className="da-streaming-caret" aria-hidden>▍</span>
        </p>
      )}
      {!tail && <span className="da-streaming-caret da-streaming-caret-lone" aria-hidden>▍</span>}
    </div>
  );
});

function findStableSplitIndex(content: string): number {
  // Walk the string once, tracking code-fence state. The "stable" prefix ends
  // at the last paragraph break (\n\n) we encounter *outside* a fence, or just
  // after a fence closes. Everything past that point may still be growing.
  let inFence = false;
  let lastSafe = 0;
  let i = 0;
  const n = content.length;
  while (i < n) {
    if (content.charCodeAt(i) === 96 /* ` */ && content.startsWith("```", i)) {
      inFence = !inFence;
      const nl = content.indexOf("\n", i);
      i = nl === -1 ? n : nl + 1;
      if (!inFence) lastSafe = i;
      continue;
    }
    if (!inFence && content.charCodeAt(i) === 10 /* \n */ && content.charCodeAt(i + 1) === 10) {
      i += 2;
      lastSafe = i;
      continue;
    }
    i += 1;
  }
  return lastSafe;
}

const MarkdownContent = memo(function MarkdownContent({
  content,
  onSelectArtifact,
}: {
  content: string;
  onSelectArtifact?: (artifact: ChatArtifact) => void;
}) {
  // Split into a frozen prefix and a small growing tail. parseMarkdownBlocks
  // is O(N), so re-parsing the whole 5KB+ answer on every streamed frame
  // becomes the dominant main-thread cost. The prefix is only re-parsed when
  // a new paragraph or fenced code block closes (rare); the tail is small.
  const splitIdx = useMemo(() => findStableSplitIndex(content), [content]);
  const stableContent = content.slice(0, splitIdx);
  const tailContent = content.slice(splitIdx);
  const stableBlocks = useMemo(() => parseMarkdownBlocks(stableContent), [stableContent]);
  const tailBlocks = useMemo(() => parseMarkdownBlocks(tailContent), [tailContent]);
  return (
    <div className="da-markdown">
      <style>{`
        .da-markdown > *:first-child { margin-top: 0; }
        .da-markdown > *:last-child { margin-bottom: 0; }
        .da-markdown p { margin: 0 0 10px; }
        .da-markdown h1, .da-markdown h2, .da-markdown h3 { position: relative; margin: 16px 0 8px; color: var(--ink-900); font-weight: 780; letter-spacing: 0; }
        .da-markdown h1 { font-size: 21px; line-height: 1.35; }
        .da-markdown h2 { font-size: 17px; line-height: 1.45; padding-left: 10px; }
        .da-markdown h2::before { content: ""; position: absolute; left: 0; top: .28em; bottom: .28em; width: 3px; border-radius: 99px; background: var(--brand, #5b4ee8); }
        .da-markdown h3 { font-size: 15px; line-height: 1.5; color: var(--ink-800); }
        .da-markdown strong { color: var(--ink-900); font-weight: 760; }
        .da-markdown em { color: var(--ink-600); }
        .da-markdown .md-highlight { padding: 1px 4px 2px; border-radius: 4px; background: rgba(245,158,11,.18); box-decoration-break: clone; -webkit-box-decoration-break: clone; }
        .da-markdown .md-color-red { color: #a61b1b; font-weight: 700; }
        .da-markdown .md-color-blue { color: #1d4ed8; font-weight: 680; }
        .da-markdown .md-color-green { color: #047857; font-weight: 680; }
        .da-markdown .md-color-muted { color: var(--ink-500); }
        .da-markdown .md-soft-red { padding: 1px 5px 2px; border-radius: 5px; color: #a61b1b; background: rgba(220,38,38,.09); box-decoration-break: clone; -webkit-box-decoration-break: clone; }
        .da-markdown .md-soft-blue { padding: 1px 5px 2px; border-radius: 5px; color: #1d4ed8; background: rgba(37,99,235,.09); box-decoration-break: clone; -webkit-box-decoration-break: clone; }
        .da-markdown .md-soft-green { padding: 1px 5px 2px; border-radius: 5px; color: #047857; background: rgba(16,185,129,.10); box-decoration-break: clone; -webkit-box-decoration-break: clone; }
        .da-markdown .md-badge { display: inline-flex; align-items: center; min-height: 20px; padding: 1px 7px; border-radius: 6px; color: #a61b1b; background: rgba(220,38,38,.10); font-size: .9em; font-weight: 740; vertical-align: baseline; }
        .da-markdown ul, .da-markdown ol { margin: 6px 0 12px; padding-left: 22px; }
        .da-markdown li { margin: 3px 0; }
        .da-markdown code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.92em; background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 5px; padding: 1px 5px; }
        .da-markdown .md-hr { border: 0; border-top: 1px solid var(--border); margin: 16px 0; }
        .da-markdown .md-code-wrap { margin: 13px 0 15px; border: 1px solid rgba(255,255,255,.08); border-radius: 10px; background: #171717; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,.08), inset 0 1px 0 rgba(255,255,255,.04); }
        .da-markdown .md-code-head { height: 32px; padding: 0 8px 0 12px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,.08); background: #202020; color: #a3a3a3; font-size: 11px; font-weight: 650; }
        .da-markdown .md-code-copy { height: 20px; padding: 0 5px; display: inline-flex; align-items: center; gap: 4px; border-radius: 5px; color: #a3a3a3; font-size: 11px; font-weight: 650; transition: background .15s ease, color .15s ease; }
        .da-markdown .md-code-copy:hover { background: rgba(255,255,255,.08); color: #f5f5f5; }
        .da-markdown pre { margin: 0; padding: 14px 16px; overflow-x: auto; color: #d4d4d4; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; line-height: 1.65; tab-size: 2; }
        .da-markdown pre code { padding: 0; border: 0; background: transparent; border-radius: 0; font-size: inherit; white-space: pre; }
        .da-markdown .md-artifact-card { width: 100%; margin: 12px 0 14px; display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg-elevated); box-shadow: var(--shadow-sm); text-align: left; transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease; }
        .da-markdown .md-artifact-card:hover { border-color: var(--brand-border); box-shadow: var(--shadow-brand); transform: translateY(-1px); }
        .da-markdown .md-artifact-title { color: var(--ink-900); font-size: 13px; font-weight: 700; line-height: 1.4; }
        .da-markdown .md-artifact-meta { margin-top: 3px; color: var(--ink-400); font-size: 11px; font-weight: 500; }
        .da-markdown .md-artifact-preview { width: 54px; height: 38px; border-radius: 6px; background: #171717; border: 1px solid rgba(0,0,0,.08); color: #d4d4d4; overflow: hidden; opacity: .9; }
        .da-markdown .md-artifact-preview pre { padding: 6px; font-size: 5px; line-height: 1.25; color: #d4d4d4; }
        .da-markdown .md-math { display: inline-block; color: var(--ink-900); }
        .da-markdown .md-math-block { display: block; text-align: center; margin: 14px 0 18px; overflow-x: auto; overflow-y: hidden; }
        /* KaTeX surfaces — give display math a bit more vertical breathing
           room and ensure long formulas can scroll horizontally rather
           than blow out the bubble width. */
        .da-markdown .md-katex-display { display: inline-block; font-size: 1.05em; }
        .da-markdown .md-katex-inline { display: inline-block; }
        .da-markdown .md-math-block .katex-display { margin: 0; }
        .da-markdown .tok-comment { color: #6a9955; }
        .da-markdown .tok-string { color: #ce9178; }
        .da-markdown .tok-keyword { color: #569cd6; }
        .da-markdown .tok-number { color: #b5cea8; }
        .da-markdown .tok-function { color: #dcdcaa; }
        .da-markdown .md-table-wrap { max-width: 100%; overflow-x: auto; margin: 12px 0 14px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-elevated); }
        .da-markdown table { width: 100%; border-collapse: collapse; min-width: 420px; }
        .da-markdown th, .da-markdown td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
        .da-markdown th { background: var(--bg-subtle); font-weight: 700; color: var(--ink-800); }
        .da-markdown tr:last-child td { border-bottom: 0; }
      `}</style>
      {renderMarkdownBlocks([...stableBlocks, ...tailBlocks], onSelectArtifact)}
    </div>
  );
});

type MarkdownBlock =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "table"; rows: string[][] }
  | { type: "code"; language: string; code: string; open?: boolean }
  | { type: "math"; formula: string; block: boolean }
  | { type: "hr" };

function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const codeFence = /^```([a-zA-Z0-9_+#.-]*)\s*$/.exec(line.trim());
    if (codeFence) {
      const language = (codeFence[1] || "text").trim();
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i].trim())) {
        codeLines.push(lines[i]);
        i += 1;
      }
      const closed = i < lines.length && /^```\s*$/.test(lines[i].trim());
      if (closed) i += 1;
      blocks.push({ type: "code", language, code: codeLines.join("\n"), open: !closed });
      continue;
    }
    if (isMarkdownHr(line)) {
      blocks.push({ type: "hr" });
      i += 1;
      continue;
    }
    // Single-line display math:  \[ ... \]   or   $$ ... $$
    const displayMathSingle = /^\\\[(.+)\\\]$/.exec(line.trim()) || /^\$\$(.+)\$\$$/.exec(line.trim());
    if (displayMathSingle) {
      blocks.push({ type: "math", formula: displayMathSingle[1].trim(), block: true });
      i += 1;
      continue;
    }
    // Multi-line display math opening with \[ or $$ on its own line —
    // consume until the matching closer. LLMs frequently break long
    // formulas across lines, which the single-line regex above misses.
    const opener = /^(\\\[|\$\$)\s*$/.exec(line.trim());
    if (opener) {
      const closeMarker = opener[1] === "\\[" ? "\\]" : "$$";
      const formulaLines: string[] = [];
      i += 1;
      while (i < lines.length && lines[i].trim() !== closeMarker) {
        formulaLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) i += 1; // consume closer if present
      blocks.push({ type: "math", formula: formulaLines.join("\n").trim(), block: true });
      continue;
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2].trim() });
      i += 1;
      continue;
    }
    if (isTableStart(lines, i)) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        tableLines.push(lines[i]);
        i += 1;
      }
      const rows = tableLines
        .filter((row, idx) => idx !== 1 || !isTableSeparator(row))
        .map(splitTableRow)
        .filter((row) => row.length > 0);
      blocks.push({ type: "table", rows });
      continue;
    }
    const listMatch = /^(\s*)([-*+]|\d+\.)\s+(.+)$/.exec(line);
    if (listMatch) {
      const ordered = /\d+\./.test(listMatch[2]);
      const items: string[] = [];
      while (i < lines.length) {
        const item = /^(\s*)([-*+]|\d+\.)\s+(.+)$/.exec(lines[i]);
        if (!item || /\d+\./.test(item[2]) !== ordered) break;
        items.push(item[3].trim());
        i += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }
    const paragraph: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,3})\s+/.test(lines[i]) &&
      !/^```/.test(lines[i].trim()) &&
      !isMarkdownHr(lines[i]) &&
      !/^(\s*)([-*+]|\d+\.)\s+/.test(lines[i]) &&
      !isTableStart(lines, i) &&
      !/^(\\\[|\$\$)\s*$/.test(lines[i].trim())
    ) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    blocks.push({ type: "paragraph", text: paragraph.join("\n") });
  }
  return blocks;
}

const HeadingBlock = memo(function HeadingBlock({ level, text }: { level: number; text: string }) {
  const Tag = (`h${level}` as "h1" | "h2" | "h3");
  return <Tag>{renderInlineMarkdown(text)}</Tag>;
});

const ParagraphBlock = memo(function ParagraphBlock({ text }: { text: string }) {
  return <p>{renderInlineMarkdown(text)}</p>;
});

const MathBlock = memo(function MathBlock({ formula, block }: { formula: string; block: boolean }) {
  return (
    <div className={block ? "md-math-block" : "md-math"}>
      {renderMathFormula(formula, block)}
    </div>
  );
});

const ListBlock = memo(
  function ListBlock({ ordered, items }: { ordered: boolean; items: string[] }) {
    const Tag = ordered ? "ol" : "ul";
    return <Tag>{items.map((item, i) => <li key={i}>{renderInlineMarkdown(item)}</li>)}</Tag>;
  },
  (a, b) =>
    a.ordered === b.ordered &&
    a.items.length === b.items.length &&
    a.items.every((v, i) => v === b.items[i]),
);

const TableBlock = memo(
  function TableBlock({ rows }: { rows: string[][] }) {
    const [head = [], ...body] = rows;
    return (
      <div className="md-table-wrap">
        <table>
          <thead><tr>{head.map((cell, i) => <th key={i}>{renderInlineMarkdown(cell)}</th>)}</tr></thead>
          <tbody>
            {body.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{renderInlineMarkdown(cell)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  },
  (a, b) => {
    if (a.rows.length !== b.rows.length) return false;
    for (let i = 0; i < a.rows.length; i += 1) {
      const ra = a.rows[i];
      const rb = b.rows[i];
      if (ra.length !== rb.length) return false;
      for (let j = 0; j < ra.length; j += 1) if (ra[j] !== rb[j]) return false;
    }
    return true;
  },
);

const CodeBlock = memo(function CodeBlock({ language, code, open }: { language: string; code: string; open: boolean }) {
  // Defer syntax highlighting until the fence closes — while a code block is
  // still streaming we render as plain text to avoid O(N) re-tokenization on
  // every delta. Once `open` flips to false the memoized highlight runs once.
  const content = useMemo(() => (open ? code : highlightCode(code, language)), [code, language, open]);
  return (
    <div className="md-code-wrap">
      <div className="md-code-head">
        <span>{language || "code"}</span>
        <button
          className="md-code-copy"
          title="复制代码"
          onClick={() => void navigator.clipboard?.writeText(code)}
        >
          <Copy className="h-2.5 w-2.5" />
          <span>复制</span>
        </button>
      </div>
      <pre><code>{content}</code></pre>
    </div>
  );
});

function InlineCodeCard({ artifact, onSelect }: { artifact: ChatArtifact; onSelect?: (a: ChatArtifact) => void }) {
  return (
    <button className="md-artifact-card" title="在右侧查看代码" onClick={() => onSelect?.(artifact)}>
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <Code2 className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="md-artifact-title truncate">{artifact.title}</div>
          <div className="md-artifact-meta">{artifact.language || "code"} · 点击在右侧查看</div>
        </div>
      </div>
      <div className="md-artifact-preview flex-shrink-0" aria-hidden="true">
        <pre>{artifact.content.slice(0, 220)}</pre>
      </div>
    </button>
  );
}

function isPromoCodeBlock(block: MarkdownBlock & { type: "code" }) {
  const lang = (block.language || "").toLowerCase();
  const promoLangs = ["js", "jsx", "ts", "tsx", "python", "py", "html", "css", "sql", "json", "yaml", "yml", "bash", "sh", "go", "java", "cpp", "c", "rust"];
  return promoLangs.includes(lang) && block.code.length >= 60;
}

function renderMarkdownBlocks(blocks: MarkdownBlock[], onSelectArtifact?: (artifact: ChatArtifact) => void) {
  return blocks.map((block, index) => {
    if (block.type === "code" && isPromoCodeBlock(block)) {
      const art: ChatArtifact = {
        type: "code",
        title: codeCardTitle(block.language, block.code),
        language: block.language || "text",
        content: block.code,
      };
      return <InlineCodeCard key={index} artifact={art} onSelect={onSelectArtifact} />;
    }
    return renderMarkdownBlock(block, index);
  });
}

function renderMarkdownBlock(block: MarkdownBlock, index: number | string) {
  if (block.type === "hr") return <hr className="md-hr" key={index} />;
  if (block.type === "heading") return <HeadingBlock key={index} level={block.level} text={block.text} />;
  if (block.type === "list") return <ListBlock key={index} ordered={block.ordered} items={block.items} />;
  if (block.type === "table") return <TableBlock key={index} rows={block.rows} />;
  if (block.type === "math") return <MathBlock key={index} formula={block.formula} block={block.block} />;
  if (block.type === "code") return <CodeBlock key={index} language={block.language} code={block.code} open={!!block.open} />;
  return <ParagraphBlock key={index} text={block.text} />;
}

function isMarkdownHr(line: string) {
  return /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line);
}

function highlightCode(code: string, language: string) {
  const lines = code.split("\n");
  const nodes: React.ReactNode[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    nodes.push(...highlightCodeLine(lines[index], language, index));
    if (index < lines.length - 1) nodes.push("\n");
  }
  return nodes;
}

function highlightCodeLine(line: string, language: string, lineIndex: number) {
  const normalized = normalizeCodeLanguage(language);
  const nodes: React.ReactNode[] = [];
  const keywords = codeKeywords(normalized);
  const pattern = /(\/\/.*|#.*|\/\*.*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(\b\d+(?:\.\d+)?\b)|(\b[A-Za-z_$][\w$]*\b)(?=\s*\()|(\b[A-Za-z_$][\w$]*\b)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(line))) {
    if (match.index > lastIndex) nodes.push(line.slice(lastIndex, match.index));
    const token = match[0];
    const key = `${lineIndex}-${match.index}-${token}`;
    if (match[1]) nodes.push(<span className="tok-comment" key={key}>{token}</span>);
    else if (match[2]) nodes.push(<span className="tok-string" key={key}>{token}</span>);
    else if (match[3]) nodes.push(<span className="tok-number" key={key}>{token}</span>);
    else if (match[4] && !keywords.has(token)) nodes.push(<span className="tok-function" key={key}>{token}</span>);
    else if (keywords.has(token)) nodes.push(<span className="tok-keyword" key={key}>{token}</span>);
    else nodes.push(token);
    lastIndex = match.index + token.length;
  }
  if (lastIndex < line.length) nodes.push(line.slice(lastIndex));
  return nodes;
}

function codeKeywords(language: string) {
  const common = ["if", "else", "for", "while", "return", "break", "continue", "try", "catch", "finally", "throw", "true", "false", "null", "undefined"];
  const python = ["def", "class", "import", "from", "as", "with", "lambda", "yield", "None", "True", "False", "and", "or", "not", "in", "is", "elif", "except", "raise", "pass", "global", "nonlocal"];
  const javascript = ["const", "let", "var", "function", "class", "new", "this", "async", "await", "import", "export", "default", "extends", "super", "typeof", "instanceof", "switch", "case"];
  const sql = ["SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "GROUP", "BY", "ORDER", "HAVING", "INSERT", "UPDATE", "DELETE", "CREATE", "TABLE", "ALTER", "DROP", "AND", "OR", "NOT", "NULL"];
  if (language === "python") return new Set([...common, ...python]);
  if (["javascript", "typescript", "tsx", "jsx"].includes(language)) return new Set([...common, ...javascript]);
  if (language === "sql") return new Set([...common, ...sql, ...sql.map((item) => item.toLowerCase())]);
  return new Set([...common, ...javascript, ...python]);
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Use [\s\S] for math groups so block math like \[ ... \] that spans
  // multiple lines (common from LLMs) is still captured. Match groups:
  //   2 = \( inline \), 3 = \[ display \], 4 = $$ display $$, 5 = $ inline $
  const pattern = /(\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]|\$\$([\s\S]+?)\$\$|\$([^$\n]+)\$|`[^`]+`|==[^=\n]+==|\{(?:red|blue|green|muted|soft-red|soft-blue|soft-green|badge):[^{}\n]+\}|\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*|_[^_\n]+_)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const token = match[0];
    const key = `${match.index}-${token.length}`;
    const inlineMath = match[2] || match[5];
    const displayMath = match[3] || match[4];
    if (inlineMath !== undefined) parts.push(<span className="md-math" key={key}>{renderMathFormula(inlineMath, false)}</span>);
    else if (displayMath !== undefined) parts.push(<span className="md-math-block" key={key}>{renderMathFormula(displayMath, true)}</span>);
    else if (token.startsWith("`")) parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    else if (token.startsWith("==")) parts.push(<span className="md-highlight" key={key}>{token.slice(2, -2)}</span>);
    else if (token.startsWith("{")) {
      const rich = /^\{(red|blue|green|muted|soft-red|soft-blue|soft-green|badge):([\s\S]+)\}$/.exec(token);
      const cls = rich
        ? rich[1] === "badge"
          ? "md-badge"
          : rich[1].startsWith("soft-")
            ? `md-${rich[1]}`
            : `md-color-${rich[1]}`
        : "";
      parts.push(rich ? <span className={cls} key={key}>{rich[2]}</span> : token);
    }
    else if (token.startsWith("**") || token.startsWith("__")) parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    else parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

// Render a LaTeX formula via KaTeX. Handles nested braces, \frac, \sqrt,
// Greek letters, subscript/superscript groups, \varphi, etc. — i.e. all
// the cases the previous hand-rolled renderer would silently mangle.
// We also normalize Unicode dashes that LLMs frequently produce
// (`–` en-dash, `—` em-dash, `−` minus sign) back to plain `-` so KaTeX
// can parse them.
function renderMathFormula(formula: string, displayMode = false): React.ReactNode {
  const cleaned = formula.replace(/[–—−]/g, "-").trim();
  try {
    const html = katex.renderToString(cleaned, {
      displayMode,
      throwOnError: false,
      strict: "ignore",
      output: "html",
    });
    return <span className={displayMode ? "md-katex-display" : "md-katex-inline"} dangerouslySetInnerHTML={{ __html: html }} />;
  } catch {
    // KaTeX rejected the formula — fall back to raw text so the user
    // still sees the model's output instead of an empty hole.
    return <code>{cleaned}</code>;
  }
}

function isTableStart(lines: string[], index: number) {
  return Boolean(lines[index]?.includes("|") && lines[index + 1] && isTableSeparator(lines[index + 1]));
}

function isTableSeparator(line: string) {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()));
}

function splitTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function formatConversationTime(value?: string) {
  if (!value) return "刚刚";
  const d = parseServerDate(value);
  if (Number.isNaN(d.getTime())) return "刚刚";
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function shortGreetingName(value: string) {
  const chars = Array.from((value || "").trim());
  if (chars.length <= 2) return chars.join("");
  return chars.slice(-2).join("");
}

function getGreetingInfo() {
  const h = new Date().getHours();
  if (h < 6) return { text: "夜深了", emoji: pickGreetingEmoji(["🌙", "✨", "🌌", "😴", "🛌"]) };
  if (h < 12) return { text: "早上好", emoji: pickGreetingEmoji(["😊", "☀️", "🌤️", "🌱", "🙌"]) };
  if (h < 18) return { text: "下午好", emoji: pickGreetingEmoji(["😊", "🍵", "🌿", "☕", "📚"]) };
  return { text: "晚上好", emoji: pickGreetingEmoji(["🌙", "🌛", "⭐", "🌃", "✨"]) };
}

function pickGreetingEmoji(pool: string[]) {
  return pool[Math.floor(Math.random() * pool.length)] || "😊";
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatMessageTime(value?: string) {
  if (!value) return "刚刚完成";
  const d = parseServerDate(value);
  if (Number.isNaN(d.getTime())) return "刚刚完成";
  return `完成于 ${d.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
}

function parseServerDate(value: string) {
  const raw = String(value || "").trim();
  if (!raw) return new Date(NaN);
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);
  return new Date(hasTimezone ? raw : `${raw}Z`);
}
