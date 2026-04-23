// v2 types for the Supervisor-led report system.
// These coexist with legacy task-centric types during the migration.

export type ReportType =
  | 'ops_review'
  | 'internal_research'
  | 'risk_assessment'
  | 'regulatory_filing'
  | 'training_material'
  // User-defined types take the form `custom:<id>`.
  | (string & { readonly __brand?: 'custom' });

export type ReportStatus =
  | 'draft'
  | 'intake'
  | 'scoping'
  | 'producing'
  | 'reviewing'
  | 'delivered'
  | 'failed'
  | 'cancelled';

export type ReportPhase = ReportStatus | string;

export type MessageRole =
  | 'supervisor_say'
  | 'supervisor_ask'
  | 'team_change'
  | 'employee_note'
  | 'user_reply'
  | 'user_interject'
  | 'phase_transition';

export interface ReportMessage {
  id: number;
  report_id: number;
  role: MessageRole;
  author_id?: string | null;
  author_name?: string | null;
  content: string;
  meta?: Record<string, any> | null;
  created_at: string;
}

export interface Clarification {
  id: number;
  report_id: number;
  question: string;
  default_answer?: string | null;
  answer?: string | null;
  status: 'pending' | 'answered' | 'defaulted' | 'skipped';
  priority?: 'high' | 'medium' | 'low';
  created_at: string;
  answered_at?: string | null;
}

export interface TimelineEvent {
  id: number;
  report_id: number;
  event_type: string;
  label: string;
  payload?: Record<string, any> | null;
  created_at: string;
}

export interface SectionOutlineItem {
  id: string;
  title: string;
  kind: string;
}

export interface OutputSection {
  text: string;
  employee_id?: string;
  employee_name?: string;
  note?: string;
  error?: string | null;
}

export interface Report {
  id: number;
  user_id: number;
  title: string;
  brief: string;
  report_type: ReportType;
  depth: string;
  status: ReportStatus;
  phase: ReportPhase;
  progress: number;
  scoping_plan?: any;
  team_roster?: string[] | null;
  section_outline?: SectionOutlineItem[] | null;
  output_index?: Record<string, OutputSection> | null;
  final_file_path?: string | null;
  final_file_name?: string | null;
  error_message?: string | null;
  trace_log?: Record<string, any> | null;
  data_context?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ReportDetail extends Report {
  messages: ReportMessage[];
  clarifications: Clarification[];
  timeline: TimelineEvent[];
}

export interface ReportTypeInfo {
  id: ReportType;
  label: string;
  label_en: string;
  description: string;
  typical_inputs: string[];
  typical_output: string;
  default_team: string[];
  section_skeleton: SectionOutlineItem[];
  is_custom?: boolean;
  visibility?: 'private' | 'public';
  owner_is_me?: boolean;
}

// ----------------------------- Workforce -----------------------------

export interface WorkforceMember {
  id: string;
  name: string;
  first_name_en: string;
  role_title_en: string;
  tagline_en: string;
  portrait_seed: string;
  category: string;
  description: string;
  skills: string[];
  tools: string[];
  applicable_report_types: string[];
  inputs: string[];
  outputs: string[];
  default_model?: string | null;
  resolved_model_id?: string | null;
  resolved_model_name?: string | null;
  enabled: boolean;
  is_supervisor?: boolean;
}

export interface WorkforceResponse {
  supervisor: WorkforceMember;
  employees: WorkforceMember[];
}

// ----------------------------- API Keys ------------------------------

export interface ApiKeyRecord {
  id: number;
  user_id: number;
  name: string;
  prefix: string;
  masked_key: string;
  status: 'active' | 'suspended' | 'revoked';
  daily_request_limit?: number | null;
  monthly_token_limit?: number | null;
  total_requests: number;
  last_used_at?: string | null;
  created_at: string;
  expires_at?: string | null;
  raw_key?: string; // Only present on creation
}
