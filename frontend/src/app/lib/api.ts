export type UserInfo = {
  id?: number;
  username?: string;
  auth_id?: string;
  department?: string;
  role?: string;
};

export type ReportItem = {
  id: number;
  title: string;
  brief?: string;
  report_type?: string;
  output_format?: string;
  status: string;
  progress?: number;
  phase?: string;
  created_at?: string;
  completed_at?: string | null;
};

export type ReportDetail = ReportItem & {
  section_outline?: unknown;
  output_index?: unknown;
  final_file_name?: string | null;
  final_file_path?: string | null;
  error_message?: string | null;
  updated_at?: string;
  started_at?: string | null;
  timeline?: Array<{
    id: number;
    event_type?: string;
    label?: string;
    payload?: unknown;
    created_at?: string | null;
  }>;
  clarifications?: Array<{
    id: number;
    question: string;
    default_answer?: string;
    status?: string;
    priority?: string;
  }>;
};

export type ReportPreview = {
  mode: "rendered_pages" | "docx_embedded_images" | "markdown_fallback" | string;
  source_format?: string;
  page_count?: number;
  pages?: string[];
  images?: string[];
  markdown?: string;
  warning?: string;
};

export type ChatMessage = {
  id: number | string;
  report_id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at?: string;
  /** True while this assistant message is being streamed; renderers should
   *  skip markdown parsing and just show plain text until streaming ends. */
  streaming?: boolean;
  /** Files the user attached when sending this message (display only, not persisted). */
  attachedFiles?: { name: string; size: string }[];
};

export type CodeExecuteResult = {
  ok: boolean;
  stdout?: string;
  stderr?: string;
  error?: string | null;
  variables?: Record<string, unknown>;
  figures?: Array<{ format?: string; base64?: string; size_kb?: number }>;
  exec_ms?: number;
};

export type DocumentPlan = {
  summary?: string;
  steps: string[];
  questions: Array<string | {
    question: string;
    type?: "text" | "single_choice" | string;
    options?: string[];
    default_answer?: string;
  }>;
  should_ask?: boolean;
  reasoning?: string;
};

export type UploadedFileRecord = {
  id: number;
  filename?: string;
  original_name?: string;
  file_type?: string;
  file_size?: number;
  report_id?: number | null;
  is_template?: boolean;
  created_at?: string | null;
};

export type KnowledgeBase = {
  id: number;
  name: string;
  description?: string;
  scope?: string;
  kb_type?: string;
  doc_count?: number;
  chunk_count?: number;
  total_size?: number;
  created_at?: string;
  updated_at?: string;
};

export type OfficialDataSource = {
  key: string;
  name: string;
  description: string;
  category: string;
  domain_tags: string[];
  is_active: boolean;
  icon_color: string;
  icon_bg: string;
  sample_queries?: string[];
  coverage?: string;
  doc_count?: number;
};

export type ModelDisplayConfig = {
  active_model: string;
  base_url_host?: string;
  models: Array<{
    id: string;
    model: string;
    name: string;
    tier: string;
    description?: string;
    active?: boolean;
  }>;
};

export type DashboardMetrics = {
  metrics?: {
    monthly_calls?: number;
    token_consumption?: number | null;
    token_consumption_available?: boolean;
    generated_reports?: number;
    kb_documents?: number;
    active_api_keys?: number;
  };
  user_metrics?: {
    running_tasks?: number;
    failed_tasks?: number;
    success_rate?: number;
    avg_completion_minutes?: number;
    monthly_tasks?: number;
  };
  business_scenarios?: Array<{ label: string; count: number; percent: number }>;
  output_formats?: Array<{ label: string; count: number; percent: number }>;
  knowledge_base?: {
    total?: number;
    documents?: number;
    chunks?: number;
    total_size?: number;
    total_size_gb?: number;
    categories?: Array<{ label: string; count: number; documents: number; chunks: number; total_size: number }>;
  };
};

const API_BASE = resolveApiBase();
const safeStorage = {
  get(key: string) {
    try {
      return localStorage.getItem(key);
    } catch {
      return "";
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Ignore storage failures in locked-down intranet browsers.
    }
  },
  remove(key: string) {
    try {
      localStorage.removeItem(key);
    } catch {
      // Ignore storage failures in locked-down intranet browsers.
    }
  },
};

function resolveApiBase() {
  if (typeof window !== "undefined" && (window as any).DA_API_BASE) {
    return String((window as any).DA_API_BASE).replace(/\/$/, "");
  }
  if (typeof window === "undefined") return "";
  const { protocol, port, origin } = window.location;
  if (protocol === "file:" || ["4173", "5173"].includes(port)) return "http://127.0.0.1:8000";
  return origin;
}

class DataAgentApi {
  token = safeStorage.get("da_token") || "";

  setToken(token: string) {
    this.token = token;
    safeStorage.set("da_token", token);
  }

  clearToken() {
    this.token = "";
    safeStorage.remove("da_token");
  }

  get isLoggedIn() {
    return Boolean(this.token);
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const isForm = options.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(options.headers as Record<string, string> | undefined),
    };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401) {
      // Auth/login endpoints: show the actual backend error (wrong credentials, etc.)
      // Other protected endpoints: token expired / session ended
      const body = await res.json().catch(() => ({}));
      const isAuthEndpoint = path.startsWith("/api/auth/");
      if (!isAuthEndpoint) this.clearToken();
      throw new Error(
        body.detail || body.message ||
        (isAuthEndpoint ? "用户名或密码错误" : "登录已过期，请重新登录")
      );
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.message || `请求失败 (${res.status})`);
    }
    const text = await res.text();
    return (text ? JSON.parse(text) : null) as T;
  }

  async login(auth_id: string, password: string) {
    const data = await this.request<{ access_token: string; username?: string; role?: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ auth_id, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(payload: {
    auth_id: string;
    username: string;
    department: string;
    scene?: string;
    description?: string;
    password: string;
  }) {
    return this.request<{ message: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        scene: "frontend",
        description: "DataAgent Web",
        ...payload,
      }),
    });
  }

  async recover(payload: { auth_id: string; username: string; department: string; scene?: string }) {
    return this.request<{ message: string; new_password?: string }>("/api/auth/recover", {
      method: "POST",
      body: JSON.stringify({ scene: "frontend", ...payload }),
    });
  }

  async me() {
    return this.request<UserInfo>("/api/auth/me");
  }

  async modelConfig() {
    return this.request<ModelDisplayConfig>("/api/system/models");
  }

  async systemCapabilities() {
    return this.request<{ external_search_enabled: boolean; browser_enabled: boolean }>("/api/system/capabilities");
  }

  async dashboardMetrics() {
    return this.request<DashboardMetrics>("/api/dashboard/metrics");
  }

  // Generic helpers for feature-specific APIs
  async get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: "POST", body: JSON.stringify(body) });
  }

  async listReports(status?: string) {
    const qs = status ? `?status_filter=${encodeURIComponent(status)}` : "";
    return this.request<{ reports: ReportItem[]; total: number }>(`/api/reports${qs}`);
  }

  async getReport(reportId: number) {
    return this.request<ReportDetail>(`/api/reports/${reportId}`);
  }

  async previewReport(reportId: number, fmt: "docx" | "pdf" = "docx") {
    return this.request<ReportPreview>(`/api/reports/${reportId}/preview?fmt=${fmt}`);
  }

  async createReport(payload: {
    title: string;
    brief: string;
    report_type?: string;
    output_format: "word" | "pptx" | "xlsx";
    uploaded_files?: number[];
    kb_ids?: number[];
    model_id?: string;
    effort?: string;
    skills?: string[];
    skip_clarify?: boolean;
    strict_facts?: boolean;
  }) {
    return this.request<ReportItem>("/api/reports", {
      method: "POST",
      body: JSON.stringify({
        report_type: "经营分析",
        skip_clarify: false,
        strict_facts: true,
        uploaded_files: [],
        kb_ids: [],
        ...payload,
      }),
    });
  }

  async createDocumentPlan(payload: {
    prompt: string;
    template?: string | null;
    scenario?: string | null;
    output_format?: "word" | "pptx" | "xlsx";
    uploaded_files?: number[];
    file_names?: string[];
    model_id?: string | null;
    effort?: string;
  }) {
    return this.request<DocumentPlan>("/api/reports/document-plan", {
      method: "POST",
      body: JSON.stringify({
        output_format: "word",
        uploaded_files: [],
        file_names: [],
        ...payload,
      }),
    });
  }

  async sendChat(payload: {
    prompt: string;
    model_id?: string;
    effort?: string;
    conversation_id?: number;
    uploaded_files?: number[];
  }) {
    return this.request<{ report_id: number; answer: string; messages: ChatMessage[] }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        uploaded_files: [],
        ...payload,
      }),
    });
  }

  async regenerateChat(payload: {
    report_id: number;
    message_id: number;
    prompt: string;
    model_id?: string;
    effort?: string;
  }) {
    return this.request<{ report_id: number; answer: string; messages: ChatMessage[] }>("/api/chat/regenerate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async streamChat(
    payload: {
      prompt: string;
      model_id?: string;
      effort?: string;
      conversation_id?: number;
      uploaded_files?: number[];
    },
    handlers: {
      onStart?: (reportId: number) => void;
      onDelta?: (delta: string) => void;
      /** Called when the server signals completion. messages are fetched separately. */
      onDone?: (data: { report_id: number; answer: string }) => void;
      onError?: (message: string) => void;
    } = {},
  ) {
    const res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      },
      body: JSON.stringify({ uploaded_files: [], ...payload }),
    });
    if (res.status === 401) {
      this.clearToken();
      throw new Error("登录已过期，请重新登录");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.message || `请求失败 (${res.status})`);
    }
    if (!res.body) {
      const data = await this.sendChat(payload);
      handlers.onStart?.(data.report_id);
      handlers.onDone?.({ report_id: data.report_id, answer: data.answer });
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let sawDone = false;
    const handleLine = (rawLine: string) => {
      const line = rawLine.trim();
      if (!line || line === "heartbeat") return;
      let event: any;
      try {
        event = JSON.parse(line);
      } catch {
        // Silently skip unparseable lines (e.g. partial flush artifacts)
        return;
      }
      if (event.type === "heartbeat") return;
      if (event.type === "start") handlers.onStart?.(event.report_id);
      if (event.type === "delta") handlers.onDelta?.(event.delta || "");
      if (event.type === "done") {
        sawDone = true;
        handlers.onDone?.({ report_id: event.report_id, answer: event.answer || "" });
      }
      if (event.type === "error") {
        handlers.onError?.(event.detail || "模型调用失败");
        throw new Error(event.detail || "模型调用失败");
      }
    };
    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch {
        // Connection dropped — let the caller's catch block handle recovery
        throw new Error("连接中断，请稍后重试");
      }
      const { done, value } = chunk;
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        handleLine(line);
      }
    }
    // Flush any remaining buffered bytes
    buffer += decoder.decode();
    if (buffer.trim()) handleLine(buffer);
    // If the stream ended without a done event, the backend likely completed
    // but the connection was dropped after the DB commit. The caller's catch
    // block will poll the API to recover the completed response.
    if (!sawDone) throw new Error("__stream_incomplete__");
  }

  async listMessages(reportId: number) {
    return this.request<ChatMessage[]>(`/api/reports/${reportId}/messages`);
  }

  async executeCode(payload: { language: string; code: string }) {
    return this.request<CodeExecuteResult>("/api/chat/execute", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async deleteReport(reportId: number) {
    return this.request<{ message: string }>(`/api/reports/${reportId}`, {
      method: "DELETE",
    });
  }

  async uploadFile(file: File, reportId?: number, isTemplate = false) {
    const form = new FormData();
    form.append("file", file);
    if (reportId) form.append("report_id", String(reportId));
    if (isTemplate) form.append("is_template", "true");
    return this.request<{ id: number; original_name?: string; file_size?: number }>("/api/files/upload", {
      method: "POST",
      body: form,
    });
  }

  async listFiles(options: { templatesOnly?: boolean } = {}) {
    const qs = options.templatesOnly ? "?templates_only=true" : "";
    return this.request<{ files: UploadedFileRecord[] }>(`/api/files${qs}`);
  }

  async analyzePromptSkill(file: File) {
    const form = new FormData();
    form.append("file", file);
    return this.request<{
      name: string;
      content: string;
      analysis?: {
        line_count?: number;
        heading_count?: number;
        table_like_rows?: number;
        citation_markers?: number;
        detected_style?: string;
        outline_samples?: string[];
      };
    }>("/api/prompt-skills/analyze", {
      method: "POST",
      body: form,
    });
  }

  async savePromptSkill(name: string, content: string) {
    return this.request<{ message: string; name: string; path?: string; source?: string }>(`/api/prompt-skills/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    });
  }

  async listKBs() {
    return this.request<{ items: KnowledgeBase[]; total: number }>("/api/kb");
  }

  async listOfficialSources(): Promise<{ sources: OfficialDataSource[] }> {
    return this.request<{ sources: OfficialDataSource[] }>("/api/v1/official-sources");
  }

  async createKB(name: string, description = "") {
    return this.request<KnowledgeBase>("/api/kb", {
      method: "POST",
      body: JSON.stringify({ name, description, scope: "personal", kb_type: "general" }),
    });
  }

  async uploadKBDocument(kbId: number, file: File) {
    const form = new FormData();
    form.append("file", file);
    return this.request(`/api/kb/${kbId}/documents`, {
      method: "POST",
      body: form,
    });
  }

  downloadReportUrl(reportId: number, outputFormat = "word") {
    const fmt = outputFormat === "pptx" ? "pptx" : outputFormat === "xlsx" ? "xlsx" : outputFormat === "pdf" ? "pdf" : "docx";
    return `${API_BASE}/api/reports/${reportId}/download?fmt=${fmt}`;
  }

  async downloadReport(reportId: number, outputFormat: "docx" | "pdf" | "word" = "docx") {
    const fmt = outputFormat === "pdf" ? "pdf" : "docx";
    const res = await fetch(this.downloadReportUrl(reportId, fmt), {
      method: "GET",
      headers: {
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      },
    });
    if (res.status === 401) {
      this.clearToken();
      throw new Error("登录已过期，请重新登录");
    }
    if (!res.ok) {
      const body = await res.json().catch(async () => {
        const text = await res.text().catch(() => "");
        return { detail: text };
      });
      throw new Error(body.detail || body.message || `下载失败 (${res.status})`);
    }

    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const filename = parseDownloadFilename(disposition) || `DataAgent文档.${fmt}`;
    triggerBrowserDownload(blob, filename);
    return { filename, size: blob.size, format: fmt };
  }

  reportSocket(reportId: number) {
    if (typeof window === "undefined") return "";
    const base = API_BASE || window.location.origin;
    const url = new URL(base, window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `/ws/reports/${reportId}`;
    url.search = "";
    if (this.token) url.searchParams.set("token", this.token);
    return url.toString();
  }
}

function parseDownloadFilename(disposition: string) {
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim().replace(/^"|"$/g, ""));
    } catch {
      return utf8Match[1].trim().replace(/^"|"$/g, "");
    }
  }
  const plainMatch = disposition.match(/filename=([^;]+)/i);
  return plainMatch?.[1]?.trim().replace(/^"|"$/g, "") || "";
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = new DataAgentApi();
