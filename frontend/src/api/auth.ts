import client from './client';
import type { LoginRequest, LoginResponse, User } from '../types';

export async function login(data: LoginRequest): Promise<LoginResponse> {
  // OAuth2 password flow uses form data
  const formData = new URLSearchParams();
  formData.append('username', data.username);
  formData.append('password', data.password);
  const response = await client.post<LoginResponse>('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
}

export async function register(data: { username: string; password: string }): Promise<User> {
  const response = await client.post<User>('/auth/register', data);
  return response.data;
}

export async function getCurrentUser(): Promise<User> {
  const response = await client.get<User>('/auth/me');
  return response.data;
}

export async function logout(): Promise<void> {
  try {
    await client.post('/auth/logout');
  } catch {
    // Ignore errors on logout
  }
}
