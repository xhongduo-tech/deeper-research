import { FILE_TYPE_ICONS } from './constants';

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return String(dateStr);
  }
}

/** Compact relative label used only in message/feed timestamps. */
export function formatRelative(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    const diff = Date.now() - date.getTime();
    const m = Math.floor(diff / 60000);
    const h = Math.floor(m / 60);
    const d = Math.floor(h / 24);
    if (diff < 60000) return '刚刚';
    if (m < 60) return `${m}分钟前`;
    if (h < 24) return `${h}小时前`;
    if (d < 7) return `${d}天前`;
    return formatDate(dateStr);
  } catch {
    return String(dateStr);
  }
}

export function formatDateTime(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export function formatTime(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export function getFileExtension(filename: string): string {
  return filename.split('.').pop()?.toLowerCase() || '';
}

export function getFileIcon(filename: string): string {
  const ext = getFileExtension(filename);
  return FILE_TYPE_ICONS[ext] || FILE_TYPE_ICONS.default;
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

export function formatProgress(progress: number): string {
  return `${Math.round(Math.max(0, Math.min(100, progress)))}%`;
}

export function generateId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function parseWebSocketUrl(apiUrl: string): string {
  return apiUrl.replace(/^https?/, (match) => (match === 'https' ? 'wss' : 'ws'));
}

export function formatCodeLanguage(lang?: string): string {
  const map: Record<string, string> = {
    py: 'Python',
    python: 'Python',
    js: 'JavaScript',
    javascript: 'JavaScript',
    ts: 'TypeScript',
    typescript: 'TypeScript',
    sh: 'Shell',
    bash: 'Shell',
    sql: 'SQL',
    json: 'JSON',
    yaml: 'YAML',
    html: 'HTML',
    css: 'CSS',
  };
  return map[lang?.toLowerCase() || ''] || lang || 'Code';
}

export function maskApiKey(key: string): string {
  if (!key || key.length < 8) return '****';
  return key.slice(0, 4) + '****' + key.slice(-4);
}

export function buildWsUrl(_apiBaseUrl: string, taskId: number): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/ws/${taskId}`;
}
