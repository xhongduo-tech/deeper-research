import client from './client';
import type { WorkforceResponse, WorkforceMember } from '../types/report';

export async function getWorkforce(): Promise<WorkforceResponse> {
  const { data } = await client.get('/workforce');
  return data;
}

export async function getWorkforceMember(id: string): Promise<WorkforceMember> {
  const { data } = await client.get(`/workforce/${id}`);
  return data;
}
