import client from './client';
import type { ReportTypeInfo } from '../types/report';

export async function listReportTypes(): Promise<{ items: ReportTypeInfo[] }> {
  const { data } = await client.get('/report-types');
  return data;
}

// ---------- Custom report types ----------

export interface CustomReportType {
  id: string; // "custom:<raw_id>"
  raw_id: number;
  user_id: number;
  label: string;
  label_en: string;
  description: string;
  original_description: string;
  visibility: 'private' | 'public';
  status: 'draft' | 'active';
  typical_output: string;
  typical_inputs: string[];
  section_skeleton: { id: string; title: string; kind: string }[];
  default_team: string[];
  is_custom: true;
  created_at?: string;
  updated_at?: string;
}

export async function createCustomReportType(payload: {
  label: string;
  description: string;
  visibility: 'private' | 'public';
}): Promise<CustomReportType> {
  const { data } = await client.post('/custom-report-types', payload);
  return data;
}

export async function listCustomReportTypes(): Promise<{
  items: CustomReportType[];
}> {
  const { data } = await client.get('/custom-report-types');
  return data;
}

export async function confirmCustomReportType(
  rawId: number,
  payload: Partial<{
    label: string;
    improved_description: string;
    typical_output: string;
    section_skeleton: { id: string; title: string; kind: string }[];
    default_team: string[];
    visibility: 'private' | 'public';
  }>,
): Promise<CustomReportType> {
  const { data } = await client.post(
    `/custom-report-types/${rawId}/confirm`,
    payload,
  );
  return data;
}

export async function reimproveCustomReportType(
  rawId: number,
): Promise<CustomReportType> {
  const { data } = await client.post(
    `/custom-report-types/${rawId}/re-improve`,
  );
  return data;
}

export async function deleteCustomReportType(rawId: number): Promise<void> {
  await client.delete(`/custom-report-types/${rawId}`);
}
