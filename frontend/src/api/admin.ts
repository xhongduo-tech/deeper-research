import client from './client';
import type { AgentConfig, SystemConfig, PaginatedResponse } from '../types';
import type { Report } from '../types/report';

export async function getAgentConfigs(): Promise<AgentConfig[]> {
  const response = await client.get<AgentConfig[]>('/admin/agent-configs');
  return response.data;
}

export async function updateAgentConfig(
  configId: number,
  data: Partial<AgentConfig>
): Promise<AgentConfig> {
  const response = await client.put<AgentConfig>(
    `/admin/agent-configs/${configId}`,
    data
  );
  return response.data;
}

export async function createAgentConfig(
  data: Omit<AgentConfig, 'id'>
): Promise<AgentConfig> {
  const response = await client.post<AgentConfig>('/admin/agent-configs', data);
  return response.data;
}

export async function applyDefaultConfig(
  defaultConfig: { model_profile_id?: string }
): Promise<void> {
  await client.post('/admin/agent-configs/apply-default', defaultConfig);
}

export async function getSystemConfig(): Promise<SystemConfig> {
  const response = await client.get<SystemConfig>('/admin/system-config');
  return response.data;
}

export async function updateSystemConfig(data: Partial<SystemConfig>): Promise<SystemConfig> {
  const response = await client.put<SystemConfig>('/admin/system-config', data);
  return response.data;
}

export async function getAllReports(
  page = 1,
  pageSize = 20
): Promise<PaginatedResponse<Report>> {
  const response = await client.get<PaginatedResponse<Report>>('/admin/reports', {
    params: { page, page_size: pageSize },
  });
  return response.data;
}

export async function adminDeleteReport(reportId: number): Promise<void> {
  await client.delete(`/admin/reports/${reportId}`);
}

// Legacy aliases to ease Phase 6 migration
export const getAllTasks = getAllReports;
export const adminDeleteTask = adminDeleteReport;

export async function testLlmConnection(data: {
  base_url: string;
  model: string;
  api_key: string;
  endpoint_type?: 'chat' | 'embedding';
}): Promise<{ success: boolean; message: string; latency_ms?: number }> {
  const response = await client.post('/admin/test-llm', data);
  return response.data;
}

export async function getSystemStats(): Promise<{
  total_reports: number;
  running_reports: number;
  completed_reports: number;
  failed_reports: number;
  total_users: number;
}> {
  const response = await client.get('/admin/stats');
  return response.data;
}
