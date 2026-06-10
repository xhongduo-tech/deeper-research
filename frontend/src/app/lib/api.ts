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
  project_id?: number | null;
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

export type RagSource = {
  source: string;
  snippet: string;
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
  /** RAG sources that grounded this answer (populated on assistant messages). */
  sources?: RagSource[];
  /** Ontology domain detected for this query (e.g. "business_research"). */
  intent_domain?: string | null;
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

export type PromptSkillSummary = {
  name: string;
  title?: string;
  description?: string;
  owner?: string;
  purpose?: string;
  source?: "official" | "user" | string;
  custom?: boolean;
  detected_style?: string;
};

export type KnowledgeBase = {
  id: number;
  name: string;
  description?: string;
  scope?: string;
  scope_label?: string;
  kb_type?: string;
  type_label?: string;
  doc_count?: number;
  chunk_count?: number;
  total_size?: number;
  size_display?: string;
  embed_model?: string;
  owner_id?: number;
  created_at?: string;
  updated_at?: string;
};

export type KBDocument = {
  id: number;
  kb_id: number;
  title: string;
  file_type?: string;
  file_size?: number;
  content_preview?: string;
  chunk_count?: number;
  status?: string;
  error_msg?: string;
  created_at?: string;
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
  // offline / ingestion metadata
  source_type?: string;
  offline_available?: boolean;
  offline_doc_count?: number;
  requires_api_key?: boolean;
  last_synced_at?: string | null;
};

export type Project = {
  id: number;
  name: string;
  description?: string;
  status?: string;
  owner_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
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
const REQUEST_TIMEOUT_MS = 15000;
export const safeStorage = {
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

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: controller.signal });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new Error("后端服务无响应，请确认 127.0.0.1:8000 已启动且数据库连接正常");
      }
      throw err;
    } finally {
      window.clearTimeout(timeout);
    }
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

  async recover(payload: { auth_id: string; username: string; department: string; scene?: string; new_password?: string }) {
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

  async kbCoverage() {
    return this.request<{
      summary: {
        total_planned_kbs: number;
        total_actual_kbs: number;
        total_kb_coverage_pct: number;
        total_planned_docs: number;
        total_actual_files: number;
        total_doc_coverage_pct: number;
        total_planned_size_gb: number;
        total_actual_size_gb: number;
        total_size_coverage_pct: number;
      };
      domains: Array<{
        name: string;
        en_name: string;
        color: string;
        planned_kbs: number;
        actual_kbs: number;
        actual_files: number;
        actual_size_mb: number;
        coverage_score: number;
        kb_coverage_pct: number;
        doc_coverage_pct: number;
        size_coverage_pct: number;
        subdomains: Array<{
          name: string;
          planned_kbs: number;
          actual_kbs: number;
          actual_files: number;
          actual_size_mb: number;
          coverage_pct: number;
          sources: string[];
          key_apis: string[];
        }>;
      }>;
      missing_sources: Array<{
        category: string;
        missing: Array<{
          source: string;
          issue: string;
          alternative: string;
          effort: string;
        }>;
      }>;
    }>("/api/dashboard/kb-coverage");
  }

  async kbNetworkGraph() {
    return this.request<{
      nodes: Array<{
        id: string;
        label: string;
        type: string;
        coverage_score: number;
        size: number;
        color: string;
        status: string;
        planned_kbs?: number;
        actual_kbs?: number;
        actual_files?: number;
        actual_size_mb?: number;
        parent?: string;
      }>;
      edges: Array<{ source: string; target: string; strength: number }>;
      summary: unknown;
      domains: unknown[];
      missing_sources: unknown[];
    }>("/api/dashboard/kb-coverage/network");
  }

  // Generic helpers for feature-specific APIs
  async get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: "POST", body: JSON.stringify(body) });
  }

  async listReports(status?: string, projectId?: number | null) {
    const params = new URLSearchParams();
    if (status) params.set("status_filter", status);
    if (projectId != null) params.set("project_id", String(projectId));
    const qs = params.toString() ? `?${params.toString()}` : "";
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
    project_id?: number | null;
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
    kb_ids?: number[];
    include_system_kb?: boolean;
    project_id?: number | null;
  }) {
    return this.request<{ report_id: number; answer: string; messages: ChatMessage[]; sources?: RagSource[]; intent_domain?: string | null }>("/api/chat", {
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
    return this.request<{ report_id: number; answer: string; messages: ChatMessage[]; sources?: RagSource[]; intent_domain?: string | null }>("/api/chat/regenerate", {
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
      kb_ids?: number[];
      include_system_kb?: boolean;
    },
    handlers: {
      onStart?: (reportId: number) => void;
      onDelta?: (delta: string) => void;
      /** Called when the server signals completion. messages are fetched separately. */
      onDone?: (data: { report_id: number; answer: string; sources?: RagSource[]; intent_domain?: string | null }) => void;
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
        handlers.onDone?.({
          report_id: event.report_id,
          answer: event.answer || "",
          sources: event.sources,
          intent_domain: event.intent_domain,
        });
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

  async deleteFile(fileId: number) {
    return this.request<{ message: string; id: number }>(`/api/files/${fileId}`, {
      method: "DELETE",
    });
  }

  async listPromptSkills() {
    return this.request<{ skills: PromptSkillSummary[] }>("/api/prompt-skills");
  }

  async getPromptSkill(name: string) {
    return this.request<PromptSkillSummary & { content: string; path?: string }>(`/api/prompt-skills/${encodeURIComponent(name)}`);
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

  async deletePromptSkill(name: string) {
    return this.request<{ message: string; name: string }>(`/api/prompt-skills/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
  }

  async listKBs(scope?: string) {
    const qs = scope ? `?scope=${encodeURIComponent(scope)}` : "";
    return this.request<{ items: KnowledgeBase[]; total: number }>(`/api/kb${qs}`);
  }

  async listOfficialSources(): Promise<{ sources: OfficialDataSource[]; categories: string[]; by_category: Record<string, OfficialDataSource[]> }> {
    return this.request<{ sources: OfficialDataSource[]; categories: string[]; by_category: Record<string, OfficialDataSource[]> }>("/api/v1/official-sources");
  }

  async getOfficialSource(key: string) {
    return this.request<OfficialDataSource>(`/api/v1/official-sources/${encodeURIComponent(key)}`);
  }

  async getOfficialSourceSample(key: string) {
    return this.request<{
      source_key: string;
      samples: Array<{ kb_id: number; kb_name: string; content: string }>;
      total_kb_matched: number;
    }>(`/api/v1/official-sources/${encodeURIComponent(key)}/sample`);
  }

  async getDataGraph() {
    return this.request<{
      nodes: Array<{
        id: string;
        label: string;
        type: string;
        coverage_score: number;
        size: number;
        color: string;
        status: string;
        planned_kbs?: number;
        actual_kbs?: number;
        actual_files?: number;
        actual_size_mb?: number;
        parent?: string;
        kb_ids?: string[];
      }>;
      edges: Array<{ source: string; target: string; strength: number }>;
      summary: unknown;
      domains: unknown[];
      missing_sources: unknown[];
    }>("/api/dashboard/kb-coverage/network");
  }

  /** List knowledge bases with optional scope filter. scope="corp" → system KBs. */
  async listKBsByScope(scope: "corp" | "personal" | "dept" | "team" | "all" = "corp") {
    return this.request<{ items: KnowledgeBase[]; total: number }>(`/api/kb?scope=${scope}`);
  }

  /** Get ontology graph with real KB connections (nodes + edges from OntologyNode + corp KBs). */
  async getOntologyDataGraph() {
    return this.request<{
      nodes: Array<{
        id: string; label: string; type: "ontology_domain" | "knowledge_base";
        domain?: string; importance?: number;
        kb_type?: string; doc_count?: number; chunk_count?: number;
      }>;
      edges: Array<{ source: string; target: string; relation: string; strength: number }>;
      kb_count: number;
      ontology_count: number;
    }>("/api/ontology/graph/data-kb");
  }

  /** Public: list all corp-scope (system) KBs with real doc counts. No auth required. */
  async listSystemKBs(kbType?: string) {
    const qs = kbType ? `?kb_type=${encodeURIComponent(kbType)}` : "";
    return this.request<{
      items: Array<KnowledgeBase & { type_label: string }>;
      total: number;
      total_docs: number;
      total_size: number;
      size_display: string;
    }>(`/api/kb/system${qs}`);
  }

  async searchKBsMulti(query: string, kbIds: number[], includeSystem = false) {
    return this.request<{
      query: string;
      results: Array<{ content: string; score: number; source: string; kb_id: number; doc_id: number }>;
      total: number;
      kb_ids_searched: number[];
    }>("/api/kb/search/multi", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 8, score_threshold: 0.15, kb_ids: kbIds, include_system: includeSystem }),
    });
  }

  async createKB(name: string, opts: { description?: string; scope?: string; kb_type?: string } = {}) {
    return this.request<KnowledgeBase>("/api/kb", {
      method: "POST",
      body: JSON.stringify({
        name,
        description: opts.description ?? "",
        scope: opts.scope ?? "personal",
        kb_type: opts.kb_type ?? "general",
      }),
    });
  }

  async deleteKB(kbId: number) {
    return this.request<{ message: string }>(`/api/kb/${kbId}`, { method: "DELETE" });
  }

  async listKBDocuments(kbId: number) {
    return this.request<{ items: KBDocument[]; total: number }>(`/api/kb/${kbId}/documents`);
  }

  async uploadKBDocument(kbId: number, file: File) {
    const form = new FormData();
    form.append("file", file);
    return this.request<KBDocument>(`/api/kb/${kbId}/documents`, {
      method: "POST",
      body: form,
    });
  }

  async deleteKBDocument(kbId: number, docId: number) {
    return this.request<{ message: string }>(`/api/kb/${kbId}/documents/${docId}`, { method: "DELETE" });
  }

  async queryKBStructured(kbId: number, query: string, nl = true) {
    return this.request<{
      success: boolean;
      sql?: string;
      rows?: Record<string, unknown>[];
      row_count?: number;
      error?: string;
    }>(`/api/kb/${kbId}/query`, {
      method: "POST",
      body: JSON.stringify({ query, nl }),
    });
  }

  // ── Projects ───────────────────────────────────────────────────────────────

  async listProjects() {
    return this.request<{ items: Project[]; total: number }>("/api/projects");
  }

  async createProject(name: string, description = "") {
    return this.request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  }

  async getProject(projectId: number) {
    return this.request<Project & { knowledge_bases: KnowledgeBase[] }>(`/api/projects/${projectId}`);
  }

  async updateProject(projectId: number, data: { name?: string; description?: string; status?: string }) {
    return this.request<Project>(`/api/projects/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deleteProject(projectId: number) {
    return this.request<{ ok: boolean }>(`/api/projects/${projectId}`, { method: "DELETE" });
  }

  async listProjectKBs(projectId: number) {
    return this.request<{ items: KnowledgeBase[]; total: number }>(`/api/projects/${projectId}/kbs`);
  }

  async createProjectKB(projectId: number, name: string, description = "") {
    return this.request<KnowledgeBase & { project_id?: number }>(`/api/projects/${projectId}/kbs`, {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  }

  // ── Ontology ───────────────────────────────────────────────────────────────

  async getOntologyGraph(kbId?: number, reportId?: number) {
    const params = new URLSearchParams();
    if (kbId != null) params.set("kb_id", String(kbId));
    if (reportId != null) params.set("report_id", String(reportId));
    const qs = params.toString();
    return this.request<{
      nodes: Array<{
        id: number;
        name: string;
        node_type: string;
        domain: string;
        description?: string;
        importance?: number;
        aliases?: string[];
      }>;
      edges: Array<{
        id: number;
        source: number;
        target: number;
        relation_type: string;
        relation_label?: string;
        weight?: number;
        confidence?: number;
      }>;
    }>(`/api/ontology/graph${qs ? "?" + qs : ""}`);
  }

  async extractOntologyFromKB(kbId: number, domain = "general") {
    return this.request<{
      kb_id: number;
      chunks_processed: number;
      kg: { nodes: unknown[]; edges: unknown[] };
      node_count: number;
      edge_count: number;
    }>(`/api/ontology/extract-kb/${kbId}?domain=${encodeURIComponent(domain)}`, { method: "POST" });
  }

  async extractOntologyFromText(text: string, domain = "general", context = "") {
    return this.request<{
      kg: { nodes: unknown[]; edges: unknown[] };
      saved: boolean;
      node_count: number;
      edge_count: number;
      persisted_nodes: number;
      persisted_edges: number;
    }>("/api/ontology/extract", {
      method: "POST",
      body: JSON.stringify({ text, domain, context, save: false }),
    });
  }

  // ── Admin: offline bulk import (2TB lane) ──────────────────────────────────

  async bulkImportScan(sourceDir?: string) {
    const qs = sourceDir ? `?source_dir=${encodeURIComponent(sourceDir)}` : "";
    return this.request<{
      source_dir: string; exists: boolean; hint?: string;
      kb_dirs: Array<{ dir: string; name: string; kb_type: string; has_metadata: boolean; file_count: number; size_mb: number }>;
      total_kb?: number; total_files?: number; total_size_mb?: number;
    }>(`/api/admin/bulk-import/scan${qs}`);
  }

  async bulkImportRun(sourceDir?: string) {
    return this.request<{ status: string; source_dir: string }>("/api/admin/bulk-import/run", {
      method: "POST",
      body: JSON.stringify({ source_dir: sourceDir ?? null }),
    });
  }

  async bulkImportStatus() {
    return this.request<{
      running: boolean; source_dir: string; started_at: string | null; finished_at: string | null;
      last_summary: { kb_count: number; files_processed: number; chunks_ingested: number; elapsed_seconds: number } | null;
      error: string | null;
      checkpoint: { files_processed: number; chunks_ingested: number; last_updated: string };
    }>("/api/admin/bulk-import/status");
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

  // ── LLM-OS: Ingress Gateway ──────────────────────────────────────────────────

  /** 上传任意文件（含 .zip/.tar.gz），解析为标准化资产摘要 */
  async ingestUpload(file: File, reportId?: number, isTemplate = false) {
    const form = new FormData();
    form.append("file", file);
    if (reportId) form.append("report_id", String(reportId));
    if (isTemplate) form.append("is_template", "true");
    return this.request<{
      file_id: number;
      filename: string;
      vfs_summary: { total_files: number; by_type: Record<string, number>; total_size_kb: number };
      directory_tree: string;
      assets: Array<{ path: string; type: string; language: string; size_bytes: number; summary: string }>;
      total_assets: number;
    }>("/api/ingress/upload", { method: "POST", body: form });
  }

  /** 获取 VFS 目录树 */
  async getVfsTree(fileId: string) {
    return this.request<{ file_id: string; tree: string; summary: Record<string, unknown> }>(
      `/api/ingress/vfs/${fileId}/tree`
    );
  }

  /** 获取 VFS 中某文件的解析内容 */
  async getVfsFile(fileId: string, path: string) {
    const qs = `?path=${encodeURIComponent(path)}`;
    return this.request<{ path: string; type: string; language: string; context_text: string; summary: string }>(
      `/api/ingress/vfs/${fileId}/file${qs}`
    );
  }

  // ── LLM-OS: Compute ───────────────────────────────────────────────────────────

  /** 将已上传的结构化文件注册为 DuckDB 内存表 */
  async duckdbRegister(sessionId: string, fileId: number, tableName?: string) {
    return this.request<{ session_id: string; table_name: string; schema: string; sample: Record<string, unknown>[] }>(
      "/api/compute/duckdb/register",
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, file_id: fileId, table_name: tableName }),
      }
    );
  }

  /** 执行 SQL 查询或自然语言查询 */
  async duckdbQuery(sessionId: string, query: string, nl = false) {
    return this.request<{
      success: boolean; sql: string; error?: string;
      columns: string[]; rows: Record<string, unknown>[];
      row_count: number; exec_ms: number; markdown: string;
    }>("/api/compute/duckdb/query", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, query, nl }),
    });
  }

  /** 多语言代码执行 */
  async sandboxRun(code: string, language = "python", timeout?: number) {
    return this.request<{
      success: boolean; language: string;
      stdout: string; stderr: string; error?: string;
      exec_ms: number; figures: Array<{ format: string; base64: string }>;
    }>("/api/compute/sandbox/run", {
      method: "POST",
      body: JSON.stringify({ code, language, timeout }),
    });
  }

  /** 自然语言 → ECharts iframe widget */
  async generateWidget(question: string, records: Record<string, unknown>[], title = "") {
    return this.request<{ html: string }>("/api/compute/widget/generate", {
      method: "POST",
      body: JSON.stringify({ question, records, title }),
    });
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
