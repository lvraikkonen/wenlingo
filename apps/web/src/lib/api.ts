import type {
  AlphaChildCreateResponse,
  AlphaChildSummary,
  AlphaChildrenResponse,
  AlphaEventCreate,
  AlphaInviteValidationResponse,
  AlphaParentResponse,
  AdminAlphaFamilyDetail,
  AdminAlphaOverviewRow,
  DashboardResponse,
  DemoLoginResponse,
  FeedbackReactionTargetType,
  FeedbackReactionValue,
  ParentSummaryUsefulness,
  SavedFeedbackReaction,
} from "./types";

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

export type Settlement = {
  xp_delta: number;
  level_after: number;
  badge_code?: string | null;
  evidence?: {
    completed_task_count?: number;
    completed_tasks?: string[];
    [key: string]: unknown;
  };
};

export type AbilitySketch = {
  reading_power: number;
  specific_writing_power: number;
  revision_power: number;
};

export type AssessmentResponse = {
  assessment: {
    id: string;
    summary: string;
    sentence_training_id: string;
    essay_id: string;
  };
  ability_sketch: AbilitySketch;
  settlement: Settlement;
  game_event?: Settlement;
};

export type SentenceTrainingResponse = {
  training: {
    id: string;
  };
  feedback: {
    encouragement: string;
    specific_improvement: string;
    next_step: string;
    problem_monsters: string[];
  };
  settlement: Settlement;
};

export type SentenceFocus =
  | "加细节"
  | "加动作或神态"
  | "加心理感受"
  | "加比喻或拟人";

export type RevisionTask = {
  instruction: string;
  target: string;
};

export type EssayResponse = {
  essay: {
    id: string;
  };
  first_draft: {
    id: string;
    essay_id: string;
    version_label: "first_draft";
  };
  feedback: {
    strengths: string[];
    improvements: string[];
    problem_monsters: string[];
    sentence_notes: string[];
    revision_tasks: RevisionTask[];
  };
};

export type EssayRevisionResponse = {
  revision: {
    id: string;
    completed_tasks: string[];
    skipped_tasks: string[];
    duration_seconds: number | null;
  };
  comparison: {
    encouragement: string;
    improved_dimensions: string[];
    evidence: string[];
    next_step: string;
  };
  settlement: Settlement;
};

export type ReadingSessionResponse = {
  transfer_tip: string;
};

export type ReadingAnswers = {
  main_idea: string;
  detail: string;
  transfer: string;
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
    focus: SentenceFocus;
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
  payload: {
    content: string;
    completed_tasks: string[];
    skipped_tasks: string[];
    duration_seconds: number | null;
  },
): Promise<EssayRevisionResponse> {
  return requestJson<EssayRevisionResponse>(`/api/essays/${essayId}/revision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function createReadingSession(
  studentId: string,
  answers: ReadingAnswers = {
    main_idea: "春天来了，小河和鸟儿都很热闹。",
    detail: "小河发出哗啦啦的声音。",
    transfer: "写景可以写声音。",
  },
): Promise<ReadingSessionResponse> {
  return requestJson<ReadingSessionResponse>(
    `/api/students/${studentId}/readings`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        article_id: "spring-sounds",
        answers,
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

export function createAlphaParent(payload: {
  display_name: string;
  invite_code: string;
  alpha_session_id: string;
}): Promise<AlphaParentResponse> {
  return requestJson<AlphaParentResponse>("/api/alpha/parents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function validateAlphaInvite(payload: {
  code: string;
  alpha_session_id: string;
}): Promise<AlphaInviteValidationResponse> {
  return requestJson<AlphaInviteValidationResponse>(
    "/api/alpha/invites/validate",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function recordAlphaEvent(payload: AlphaEventCreate): Promise<void> {
  return requestJson<void>("/api/alpha/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => undefined);
}

export function getAlphaChildren(parentId: string): Promise<AlphaChildrenResponse> {
  return requestJson<AlphaChildrenResponse>(
    `/api/alpha/parents/${parentId}/children`,
  );
}

export function createAlphaChild(
  parentId: string,
  payload: { nickname: string; grade: number },
): Promise<AlphaChildCreateResponse> {
  return requestJson<AlphaChildCreateResponse>(
    `/api/alpha/parents/${parentId}/children`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function getAlphaChildSummary(
  parentId: string,
  studentId: string,
): Promise<AlphaChildSummary> {
  return requestJson<AlphaChildSummary>(
    `/api/alpha/parents/${parentId}/children/${studentId}/summary`,
  );
}

export function saveFeedbackReaction(
  studentId: string,
  payload: {
    target_type: FeedbackReactionTargetType;
    target_id: string;
    reaction: FeedbackReactionValue;
    alpha_session_id: string;
  },
): Promise<{ reaction: SavedFeedbackReaction }> {
  return requestJson<{ reaction: SavedFeedbackReaction }>(
    `/api/students/${studentId}/feedback-reactions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function saveParentSummaryFeedback(
  parentId: string,
  studentId: string,
  payload: {
    usefulness: ParentSummaryUsefulness;
    alpha_session_id: string;
  },
): Promise<{ feedback: { usefulness: ParentSummaryUsefulness } }> {
  return requestJson<{ feedback: { usefulness: ParentSummaryUsefulness } }>(
    `/api/alpha/parents/${parentId}/children/${studentId}/summary-feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function getAdminAlphaOverview(
  token: string,
): Promise<{ families: AdminAlphaOverviewRow[] }> {
  return requestJson<{ families: AdminAlphaOverviewRow[] }>(
    "/api/admin/alpha/overview",
    {
      headers: { "X-Alpha-Admin-Token": token },
    },
  );
}

export function getAdminAlphaFamily(
  token: string,
  parentId: string,
): Promise<AdminAlphaFamilyDetail> {
  return requestJson<AdminAlphaFamilyDetail>(
    `/api/admin/alpha/families/${parentId}`,
    {
      headers: { "X-Alpha-Admin-Token": token },
    },
  );
}
