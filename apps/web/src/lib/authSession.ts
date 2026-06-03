import type { AuthSession } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function authRequestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export type { AuthSession };

export function getAuthSession(): Promise<AuthSession> {
  return authRequestJson<AuthSession>("/api/auth/session");
}

export function requestMagicCode(payload: {
  email: string;
  alpha_session_id: string;
}): Promise<{ message: string }> {
  return authRequestJson<{ message: string }>("/api/auth/magic-codes/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function verifyMagicCode(payload: {
  email: string;
  code: string;
}): Promise<AuthSession> {
  return authRequestJson<AuthSession>("/api/auth/magic-codes/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function bindPhone(payload: { phone: string }): Promise<{
  phone_masked: string;
  phone_bound: boolean;
}> {
  return authRequestJson("/api/auth/account/phone", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
