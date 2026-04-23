import client from './client';
import type {
  Report,
  ReportDetail,
  ReportType,
  Clarification,
} from '../types/report';

export interface ReportCreatePayload {
  title?: string;
  brief: string;
  report_type: ReportType | string;
  depth?: string;
  file_ids?: number[];
  /** Template file id (is_template=true) to use for the output Word doc. */
  template_file_id?: number;
  /** Skip Chief's clarification Q&A — auto-adopt defaults. */
  skip_clarifications?: boolean;
  /** Immediately enter the producing phase after creation. */
  auto_start?: boolean;
}

export async function listReports(options?: {
  status_filter?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: Report[] }> {
  const { data } = await client.get('/reports', { params: options });
  return data;
}

export async function createReport(payload: ReportCreatePayload): Promise<Report> {
  const { data } = await client.post('/reports', payload);
  return data;
}

export async function getReport(id: number): Promise<ReportDetail> {
  const { data } = await client.get(`/reports/${id}`);
  return data;
}

export async function deleteReport(id: number): Promise<void> {
  await client.delete(`/reports/${id}`);
}

export async function replyToReport(id: number, content: string): Promise<void> {
  await client.post(`/reports/${id}/reply`, { content });
}

export async function interjectReport(id: number, content: string): Promise<void> {
  await client.post(`/reports/${id}/interject`, { content });
}

export async function startReport(id: number): Promise<void> {
  await client.post(`/reports/${id}/start`);
}

export async function cancelReport(id: number): Promise<void> {
  await client.post(`/reports/${id}/cancel`);
}

export async function downloadReport(
  id: number,
  filename?: string
): Promise<void> {
  const response = await client.get(`/reports/${id}/download`, {
    responseType: 'blob',
  });
  const blob = new Blob([response.data], {
    type:
      response.headers['content-type'] ||
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || `report-${id}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function answerClarification(
  reportId: number,
  clarificationId: number,
  opts: { answer?: string; use_default?: boolean }
): Promise<Clarification> {
  const { data } = await client.post(
    `/reports/${reportId}/clarifications/${clarificationId}/answer`,
    opts
  );
  return data;
}

/**
 * Build the SSE URL for a report event stream.
 *
 * EventSource does not support custom headers in browsers, so the backend also
 * accepts `?token=<jwt>` as a fallback when the session cookie isn't present.
 * For now we use the /events endpoint directly — it reads Authorization header
 * via the fetch-based stream reader wrapper below.
 */
export function buildEventStreamUrl(id: number): string {
  const base = client.defaults.baseURL ?? '';
  return `${base}/reports/${id}/events`;
}
