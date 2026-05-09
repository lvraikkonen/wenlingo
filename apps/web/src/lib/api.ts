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

export type Settlement = {
  xp_delta: number;
  level_after: number;
  badge_code?: string;
};

export type SentenceTrainingResponse = {
  feedback: {
    encouragement: string;
    specific_improvement: string;
  };
  settlement: Settlement;
};

export type EssayResponse = {
  essay: {
    id: string;
  };
  feedback: {
    strengths: string[];
    revision_tasks: {
      instruction: string;
      target: string;
    }[];
  };
};

export type EssayRevisionResponse = {
  comparison: {
    encouragement: string;
    improved_dimensions: string[];
  };
  settlement: Settlement;
};

export type ReadingSessionResponse = {
  transfer_tip: string;
};

export type ReportResponse = {
  content: {
    practice_summary: string;
    ability_changes: string[];
    best_revision: string;
    weak_points: string[];
    next_suggestions: string[];
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

export function createEssay(
  studentId: string,
  payload: { title: string; draft: string; entry: "existing_draft" | "topic" },
): Promise<EssayResponse> {
  return requestJson<EssayResponse>(`/api/students/${studentId}/essays`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function submitEssayRevision(
  essayId: string,
  payload: { content: string },
): Promise<EssayRevisionResponse> {
  return requestJson<EssayRevisionResponse>(`/api/essays/${essayId}/revision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function createReadingSession(
  studentId: string,
): Promise<ReadingSessionResponse> {
  return requestJson<ReadingSessionResponse>(
    `/api/students/${studentId}/readings`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        article_id: "spring-sounds",
        answers: {
          main_idea: "春天来了，小河和鸟儿都很热闹。",
          detail: "小河发出哗啦啦的声音。",
          transfer: "写景可以写声音。",
        },
      }),
    },
  );
}

export function createReport(studentId: string): Promise<ReportResponse> {
  return requestJson<ReportResponse>(`/api/students/${studentId}/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report_type: "stage" }),
  });
}
