import type { DashboardResponse, DemoLoginResponse } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function demoLogin(): Promise<DemoLoginResponse> {
  return requestJson<DemoLoginResponse>("/api/auth/demo-login", {
    method: "POST",
  });
}

export function getDashboard(studentId: string): Promise<DashboardResponse> {
  return requestJson<DashboardResponse>(
    `/api/students/${studentId}/dashboard`,
  );
}
