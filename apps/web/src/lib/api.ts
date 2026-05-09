import type { DashboardResponse, DemoLoginResponse } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    cache: "no-store",
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

export type AssessmentResponse = {
  assessment: {
    summary: string;
  };
};

export type SentenceTrainingResponse = {
  feedback: {
    encouragement: string;
    specific_improvement: string;
  };
  settlement: {
    xp_delta: number;
    level_after: number;
    badge_code?: string;
  };
};

export function createAssessment(
  studentId: string,
  payload: {
    sentence_before: string;
    sentence_after: string;
    short_writing: string;
  },
): Promise<AssessmentResponse> {
  return requestJson<AssessmentResponse>(
    `/api/students/${studentId}/assessment`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function createSentenceTraining(
  studentId: string,
  payload: {
    source_sentence: string;
    upgraded_sentence: string;
    focus: string;
  },
): Promise<SentenceTrainingResponse> {
  return requestJson<SentenceTrainingResponse>(
    `/api/students/${studentId}/sentences`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}
