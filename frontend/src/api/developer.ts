import client from './client';
import type { ApiKeyRecord } from '../types/report';

export async function listMyApiKeys(): Promise<{ items: ApiKeyRecord[] }> {
  const { data } = await client.get('/developer/api-keys');
  return data;
}

export async function createApiKey(payload: {
  name: string;
  daily_request_limit?: number | null;
  monthly_token_limit?: number | null;
}): Promise<ApiKeyRecord> {
  const { data } = await client.post('/developer/api-keys', payload);
  return data;
}

export async function setApiKeyStatus(
  keyId: number,
  status: 'active' | 'suspended' | 'revoked'
): Promise<ApiKeyRecord> {
  const { data } = await client.put(`/developer/api-keys/${keyId}/status`, {
    status,
  });
  return data;
}

export async function setApiKeyQuota(
  keyId: number,
  payload: {
    daily_request_limit?: number | null;
    monthly_token_limit?: number | null;
  }
): Promise<ApiKeyRecord> {
  const { data } = await client.put(`/developer/api-keys/${keyId}/quota`, payload);
  return data;
}

export async function deleteApiKey(keyId: number): Promise<void> {
  await client.delete(`/developer/api-keys/${keyId}`);
}

export async function revealApiKey(
  keyId: number,
): Promise<{ id: number; raw_key: string }> {
  const { data } = await client.get(`/developer/api-keys/${keyId}/reveal`);
  return data;
}
