import { APIRequestContext, expect } from "@playwright/test";

export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8001";

export async function seedMemory(
  request: APIRequestContext,
  content: string,
  extra: Record<string, unknown> = {},
) {
  const res = await request.post(`${API_URL}/v1/memory`, {
    data: { content, memory_type: "fact", ...extra },
  });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{ id: string; content: string }>;
}

export async function createSession(request: APIRequestContext) {
  const res = await request.post(`${API_URL}/v1/sessions`, { data: {} });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{ id: string }>;
}

export async function waitForApi(request: APIRequestContext) {
  const res = await request.get(`${API_URL}/v1/health`);
  expect(res.ok()).toBeTruthy();
}
