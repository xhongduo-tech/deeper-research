import client from './client';
import type { UploadedFile } from '../types';

function normalizeUploadedFile(data: any): UploadedFile {
  return {
    id: Number(data?.id ?? data?.file_id),
    filename: String(data?.filename ?? ''),
    original_name: String(data?.original_name ?? ''),
    file_type: String(data?.file_type ?? ''),
    file_size: Number(data?.file_size ?? 0),
    extracted_text: data?.extracted_text ?? undefined,
    created_at: data?.created_at ?? undefined,
  };
}

export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<UploadedFile> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await client.post<UploadedFile>('/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total));
      }
    },
  });
  return normalizeUploadedFile(response.data);
}

export async function getFiles(): Promise<UploadedFile[]> {
  const response = await client.get<UploadedFile[]>('/files/');
  return (response.data || []).map(normalizeUploadedFile);
}

export async function deleteFile(fileId: number): Promise<void> {
  await client.delete(`/files/${fileId}`);
}

export async function getFileDownloadUrl(fileId: number): Promise<string> {
  return `${client.defaults.baseURL}/files/${fileId}/download`;
}

export interface TemplateFile {
  id: number;
  original_name: string;
  file_type: string;
  file_size: number;
  user_id: number;
  created_at?: string;
}

export async function listTemplates(): Promise<TemplateFile[]> {
  const res = await client.get<TemplateFile[]>('/files/templates');
  return res.data || [];
}

export async function uploadTemplate(file: File): Promise<TemplateFile> {
  const fd = new FormData();
  fd.append('file', file);
  const res = await client.post<any>('/files/template', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return {
    id: Number(res.data.file_id ?? res.data.id),
    original_name: res.data.original_name ?? file.name,
    file_type: res.data.file_type ?? 'docx',
    file_size: res.data.file_size ?? 0,
    user_id: -1,
  };
}

export async function deleteTemplate(fileId: number): Promise<void> {
  await client.delete(`/files/${fileId}`);
}
