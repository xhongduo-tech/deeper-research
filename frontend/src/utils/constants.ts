export const API_BASE_URL = (import.meta.env.VITE_API_URL as string) || '/api/v1';

export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

export const TOKEN_KEY = 'deep_research_token';
export const USER_KEY = 'deep_research_user';

export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  enriching: '分析中',
  waiting_approval: '等待确认',
  executing: '执行中',
  evaluating: '评估中',
  completed: '已完成',
  failed: '执行失败',
  refining: '优化中',
};

export const TASK_STATUS_COLORS: Record<string, string> = {
  pending: '#6d5a4e',
  enriching: '#f5a623',
  waiting_approval: '#8a6f5a',
  executing: '#7d8b63',
  evaluating: '#9b59b6',
  completed: '#7d8b63',
  failed: '#b85c4a',
  refining: '#f5a623',
};

export const FILE_TYPE_ICONS: Record<string, string> = {
  pdf: '📄',
  doc: '📝',
  docx: '📝',
  xls: '📊',
  xlsx: '📊',
  ppt: '📊',
  pptx: '📊',
  txt: '📃',
  csv: '📊',
  json: '⚙️',
  md: '📋',
  png: '🖼️',
  jpg: '🖼️',
  jpeg: '🖼️',
  gif: '🖼️',
  zip: '🗜️',
  default: '📎',
};

export const FILE_SIZE_LIMIT = 50 * 1024 * 1024; // 50MB

export const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-powerpoint': ['.ppt'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'text/plain': ['.txt'],
  'text/csv': ['.csv'],
  'application/json': ['.json'],
  'text/markdown': ['.md'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
};

export const EMPLOYEE_CATEGORIES: Record<string, string> = {
  research: '研究分析',
  writing: '内容创作',
  data: '数据处理',
  code: '代码开发',
  design: '设计规划',
  strategy: '战略咨询',
  legal: '法律合规',
  finance: '财务分析',
  marketing: '市场营销',
  hr: '人力资源',
  operations: '运营管理',
  tech: '技术架构',
};

export const LOG_TYPE_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  supervisor_thinking: { label: '主管思考', color: '#f5a623', bg: 'rgba(245, 166, 35, 0.1)' },
  employee_started: { label: '开始执行', color: '#7d8b63', bg: 'rgba(125, 139, 99, 0.1)' },
  employee_progress: { label: '执行中', color: '#8a6f5a', bg: 'transparent' },
  employee_completed: { label: '完成', color: '#7d8b63', bg: 'rgba(125, 139, 99, 0.05)' },
  code_executing: { label: '执行代码', color: '#6d5a4e', bg: 'rgba(92, 65, 43, 0.3)' },
  code_result: { label: '代码输出', color: '#7d8b63', bg: 'rgba(125, 139, 99, 0.05)' },
  evaluation_start: { label: '质量评估', color: '#9b59b6', bg: 'rgba(155, 89, 182, 0.1)' },
  evaluation_result: { label: '评估结果', color: '#9b59b6', bg: 'rgba(155, 89, 182, 0.1)' },
  task_completed: { label: '任务完成', color: '#7d8b63', bg: 'rgba(125, 139, 99, 0.15)' },
  task_failed: { label: '任务失败', color: '#b85c4a', bg: 'rgba(184, 92, 74, 0.1)' },
  error: { label: '错误', color: '#b85c4a', bg: 'rgba(184, 92, 74, 0.1)' },
  info: { label: '信息', color: '#6d5a4e', bg: 'transparent' },
  workflow_created: { label: '工作流', color: '#8a6f5a', bg: 'rgba(138, 111, 90, 0.1)' },
};

export const MAX_LOG_ENTRIES = 500;
export const WS_RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

// ---------------------------------------------------------------------------
// v2 — Report system
// ---------------------------------------------------------------------------

export const REPORT_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  intake: '需求确认',
  scoping: '阵容定案',
  producing: '生产中',
  reviewing: '质检中',
  delivered: '已交付',
  failed: '失败',
  cancelled: '已取消',
};

export const REPORT_STATUS_TONE: Record<
  string,
  'neutral' | 'brand' | 'warning' | 'success' | 'danger' | 'info'
> = {
  draft: 'neutral',
  intake: 'info',
  scoping: 'info',
  producing: 'brand',
  reviewing: 'warning',
  delivered: 'success',
  failed: 'danger',
  cancelled: 'neutral',
};

export const REPORT_STATUS_ACTIVE = new Set([
  'intake',
  'scoping',
  'producing',
  'reviewing',
]);

export const REPORT_TYPE_ACCENTS: Record<string, string> = {
  ops_review: '#8c4f3a',
  internal_research: '#3d6e8f',
  risk_assessment: '#a85a33',
  regulatory_filing: '#6a5d8c',
  training_material: '#5f7a3e',
};

