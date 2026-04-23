export function getApiErrorMessage(err: unknown, fallback = '请求失败'): string {
  const anyErr = err as any;
  const detail = anyErr?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === 'string') {
      return first;
    }
    if (first && typeof first === 'object') {
      const loc = Array.isArray(first.loc) ? first.loc.join('.') : '';
      const msg = typeof first.msg === 'string' ? first.msg : '';
      if (loc && msg) return `${loc}: ${msg}`;
      if (msg) return msg;
    }
  }

  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }

  if (typeof anyErr?.message === 'string' && anyErr.message.trim()) {
    return anyErr.message;
  }

  return fallback;
}
