export interface User {
  id: number;
  username: string;
  role: 'admin' | 'user';
}

export interface UploadedFile {
  id: number;
  filename: string;
  original_name: string;
  file_type: string;
  file_size: number;
  extracted_text?: string;
  created_at?: string;
}

export interface WorkflowStep {
  step_id: string;
  description: string;
  employee_ids: string[];
  expected_output: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export interface Employee {
  id: string;
  name: string;
  name_en: string;
  description: string;
  avatar_emoji: string;
  avatar_color: string;
  skills: string[];
  tools?: string[];
  default_model?: string;
  category: string;
  enabled: boolean;
}

export interface TaskResult {
  format: 'ppt' | 'word' | 'text' | 'json' | 'csv' | 'html';
  content: any;
  download_url?: string;
  preview_html?: string;
}

export interface Task {
  id: number;
  title: string;
  description: string;
  status: TaskStatus;
  enriched_description?: string;
  enriched_data?: EnrichedData;
  clarification_questions?: string[];
  clarification_answers?: Record<string, string>;
  knowledge_base?: KnowledgeBaseSummary;
  allow_clarification?: boolean;
  workflow_steps?: WorkflowStep[];
  selected_employees?: string[];
  result?: TaskResult;
  created_at: string;
  updated_at: string;
  user_id?: number;
  username?: string;
}

export type TaskStatus =
  | 'pending'
  | 'enriching'
  | 'waiting_approval'
  | 'executing'
  | 'evaluating'
  | 'completed'
  | 'failed'
  | 'refining';

export interface EnrichedData {
  original_request: string;
  enriched_description: string;
  key_objectives: string[];
  constraints: string[];
  suggested_output_format: string;
  estimated_complexity: 'low' | 'medium' | 'high';
  clarification_questions?: string[];
  clarification_answers?: Record<string, string>;
  knowledge_base?: KnowledgeBaseSummary;
}

export interface KnowledgeBaseSummary {
  enabled?: boolean;
  vector_store_enabled?: boolean;
  embedding_model?: string | null;
  document_count?: number;
  chunk_count?: number;
  evidence_summary?: string;
}

export interface WebSocketEvent {
  type: string;
  [key: string]: any;
}

export interface AgentConfig {
  id: number;
  employee_id: string;
  model_profile_id?: string | null;
  llm_base_url?: string | null;
  llm_model?: string | null;
  llm_api_key?: string | null;
  custom_params?: Record<string, any> | null;
  enabled: boolean;
  max_tokens?: number | null;
  temperature?: number | null;
}

export interface LlmProfile {
  id: string;
  name: string;
  base_url: string;
  model: string;
  api_key?: string;
  description?: string;
}

export interface SystemConfig {
  enable_external_search: boolean;
  enable_browser: boolean;
  default_llm_profile_id?: string;
  llm_profiles: LlmProfile[];
  default_llm_base_url: string;
  default_llm_model: string;
  default_llm_api_key?: string;
  embedding_base_url: string;
  embedding_model: string;
  embedding_api_key?: string;
  vector_store_enabled: boolean;
  kb_chunk_size: number;
  kb_top_k: number;
  sandbox_timeout: number;
  max_workers: number;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  type:
    | 'supervisor_thinking'
    | 'employee_started'
    | 'employee_progress'
    | 'employee_completed'
    | 'code_executing'
    | 'code_result'
    | 'evaluation_start'
    | 'evaluation_result'
    | 'task_completed'
    | 'task_failed'
    | 'error'
    | 'info'
    | 'workflow_created';
  message: string;
  employee_id?: string;
  employee_name?: string;
  employee_emoji?: string;
  code?: string;
  code_language?: string;
  output?: string;
  progress?: number;
  step_id?: string;
}

export interface AgentStatus {
  employee_id: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  last_message?: string;
  progress?: number;
}

export interface TaskCreateRequest {
  title: string;
  description: string;
  file_ids?: number[];
  rule_description?: string;
  output_format?: string;
  batch_mode?: boolean;
  allow_clarification?: boolean;
  template_file_id?: number;
}

export interface TaskApproveRequest {
  approved: boolean;
  modifications?: string;
}

export interface RefineRequest {
  feedback: string;
}

export interface ClarificationAnswerRequest {
  answers: Record<string, string>;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
