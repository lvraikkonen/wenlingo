import type {
  ActiveWritingCastleEssayResponse,
  AlphaChildCreateResponse,
  AlphaChildSummary,
  AlphaChildrenResponse,
  AlphaEventCreate,
  AlphaInviteValidationResponse,
  AlphaParentResponse,
  AdminAlphaAIUsageResponse,
  AdminAlphaAccountActionResponse,
  AdminAlphaAccountRow,
  AdminAlphaAccountSessionsResponse,
  AdminAlphaFamilyDetail,
  AdminAlphaInviteActionResponse,
  AdminAlphaInviteCreateResponse,
  AdminAlphaOverviewRow,
  AdminAlphaSessionRevokeResponse,
  AdminAlphaSessionsRevokeAllResponse,
  AdminAlphaTestAccountDeleteResponse,
  CreateClassroomEssayResponse,
  DashboardResponse,
  FeedbackReactionTargetType,
  FeedbackReactionValue,
  MaterialAnswer,
  MaterialCardSlot,
  ParentSummaryUsefulness,
  SavedFeedbackReaction,
  ScaffoldSelectionRequest,
  SentenceChallengeCompletionResponse,
  SentenceChallengeResponse,
  WritingCastleEssayResponse,
  WritingCastleScaffoldState,
  WritingCastleTopicAnalysisResponse,
  WritingOutlineSection,
} from "./types";

const rawApiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
const API_BASE_URL = rawApiBaseUrl === "/api" ? "" : rawApiBaseUrl;

export class ApiRequestError extends Error {
  status: number;

  constructor(status: number) {
    super(`Request failed: ${status}`);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 401;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiRequestError(response.status);
  }

  return response.json() as Promise<T>;
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
    reaction?: FeedbackReactionValue | null;
  };
  ability_sketch: AbilitySketch;
  settlement: Settlement;
  game_event?: Settlement;
};

export type SentenceTrainingResponse = {
  training: {
    id: string;
    reaction?: FeedbackReactionValue | null;
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
    reaction?: FeedbackReactionValue | null;
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
    reaction?: FeedbackReactionValue | null;
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

export function createSentenceChallenge(
  studentId: string,
): Promise<SentenceChallengeResponse> {
  return requestJson<SentenceChallengeResponse>(
    `/api/students/${studentId}/sentence-challenges`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

export function completeSentenceChallenge(
  studentId: string,
  trainingId: string,
  payload: { upgraded_sentence: string },
): Promise<SentenceChallengeCompletionResponse> {
  return requestJson<SentenceChallengeCompletionResponse>(
    `/api/students/${studentId}/sentences/${trainingId}/complete`,
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

export function createClassroomWritingCastleEssay(
  studentId: string,
  payload: { topic_text: string },
): Promise<CreateClassroomEssayResponse> {
  return requestJson<CreateClassroomEssayResponse>(
    `/api/students/${studentId}/writing-castle/classroom`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function selectWritingCastleScaffold(
  essayId: string,
  payload: ScaffoldSelectionRequest,
): Promise<WritingCastleEssayResponse & { scaffold: WritingCastleScaffoldState }> {
  return requestJson<WritingCastleEssayResponse & { scaffold: WritingCastleScaffoldState }>(
    `/api/essays/${essayId}/scaffold-selection`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function getActiveClassroomWritingCastleEssay(
  studentId: string,
): Promise<ActiveWritingCastleEssayResponse> {
  return requestJson<ActiveWritingCastleEssayResponse>(
    `/api/students/${studentId}/writing-castle/classroom/active`,
  );
}

export function generateTopicAnalysis(
  essayId: string,
): Promise<WritingCastleTopicAnalysisResponse> {
  return requestJson<WritingCastleTopicAnalysisResponse>(
    `/api/essays/${essayId}/topic-analysis`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

export function saveTopicFocus(
  essayId: string,
  payload: { text: string; adopted_from_ai: boolean; skipped: boolean },
): Promise<WritingCastleEssayResponse> {
  return requestJson<WritingCastleEssayResponse>(
    `/api/essays/${essayId}/topic-focus`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function generateMaterialQuestions(
  essayId: string,
): Promise<WritingCastleEssayResponse> {
  return requestJson<WritingCastleEssayResponse>(
    `/api/essays/${essayId}/material-questions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

export function saveMaterialAnswers(
  essayId: string,
  payload: { answers: MaterialAnswer[] },
): Promise<WritingCastleEssayResponse> {
  return requestJson<WritingCastleEssayResponse>(
    `/api/essays/${essayId}/material-answers`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function generateMaterialCards(
  essayId: string,
): Promise<WritingCastleEssayResponse> {
  return requestJson<WritingCastleEssayResponse>(
    `/api/essays/${essayId}/material-cards`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

export function saveMaterialCards(
  essayId: string,
  payload: { cards: MaterialCardSlot[] },
): Promise<WritingCastleEssayResponse> {
  return requestJson<WritingCastleEssayResponse>(
    `/api/essays/${essayId}/material-cards`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function generateOutline(
  essayId: string,
): Promise<WritingCastleEssayResponse> {
  return requestJson<WritingCastleEssayResponse>(
    `/api/essays/${essayId}/outline`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

export function saveOutline(
  essayId: string,
  payload: { sections: WritingOutlineSection[]; skipped: boolean },
): Promise<WritingCastleEssayResponse> {
  return requestJson<WritingCastleEssayResponse>(
    `/api/essays/${essayId}/outline`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function submitPrewritingFirstDraft(
  essayId: string,
  payload: { draft: string },
): Promise<EssayResponse> {
  return requestJson<EssayResponse>(`/api/essays/${essayId}/first-draft`, {
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

export function getMyAlphaChildren(): Promise<AlphaChildrenResponse> {
  return requestJson<AlphaChildrenResponse>("/api/alpha/parents/me/children");
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

export function createMyAlphaChild(payload: {
  nickname: string;
  grade: number;
}): Promise<AlphaChildCreateResponse> {
  return requestJson<AlphaChildCreateResponse>(
    "/api/alpha/parents/me/children",
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

export function getMyAlphaChildSummary(
  studentId: string,
): Promise<AlphaChildSummary> {
  return requestJson<AlphaChildSummary>(
    `/api/alpha/parents/me/children/${studentId}/summary`,
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

export function saveMyParentSummaryFeedback(
  studentId: string,
  payload: {
    usefulness: ParentSummaryUsefulness;
    alpha_session_id: string;
  },
): Promise<{ feedback: { usefulness: ParentSummaryUsefulness } }> {
  return requestJson<{ feedback: { usefulness: ParentSummaryUsefulness } }>(
    `/api/alpha/parents/me/children/${studentId}/summary-feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function getAdminAlphaOverview(
  token: string,
  includeRevoked = false,
): Promise<{ families: AdminAlphaOverviewRow[] }> {
  const suffix = includeRevoked ? "?include_revoked=true" : "";
  return requestJson<{ families: AdminAlphaOverviewRow[] }>(
    `/api/admin/alpha/overview${suffix}`,
    {
      headers: { "X-Alpha-Admin-Token": token },
    },
  );
}

export function getAdminAlphaAIUsage(
  token: string,
): Promise<AdminAlphaAIUsageResponse> {
  return requestJson<AdminAlphaAIUsageResponse>(
    "/api/admin/alpha/ai-usage",
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

export function getAdminAlphaAccounts(
  token: string,
): Promise<{ accounts: AdminAlphaAccountRow[] }> {
  return requestJson<{ accounts: AdminAlphaAccountRow[] }>(
    "/api/admin/alpha/accounts",
    {
      headers: { "X-Alpha-Admin-Token": token },
    },
  );
}

export function createAdminAlphaInvites(
  token: string,
  payload: {
    count: number;
    label_prefix: string;
    issued_to_note: string;
  },
): Promise<AdminAlphaInviteCreateResponse> {
  return requestJson<AdminAlphaInviteCreateResponse>(
    "/api/admin/alpha/invites",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Alpha-Admin-Token": token,
      },
      body: JSON.stringify(payload),
    },
  );
}

export function revokeAdminAlphaInvite(
  token: string,
  inviteId: string,
): Promise<AdminAlphaInviteActionResponse> {
  return requestJson<AdminAlphaInviteActionResponse>(
    `/api/admin/alpha/invites/${inviteId}/revoke`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Alpha-Admin-Token": token,
      },
      body: JSON.stringify({}),
    },
  );
}

export function disableAdminAlphaAccount(
  token: string,
  accountId: string,
): Promise<AdminAlphaAccountActionResponse> {
  return requestJson<AdminAlphaAccountActionResponse>(
    `/api/admin/alpha/accounts/${accountId}/disable`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Alpha-Admin-Token": token,
      },
      body: JSON.stringify({}),
    },
  );
}

export function enableAdminAlphaAccount(
  token: string,
  accountId: string,
): Promise<AdminAlphaAccountActionResponse> {
  return requestJson<AdminAlphaAccountActionResponse>(
    `/api/admin/alpha/accounts/${accountId}/enable`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Alpha-Admin-Token": token,
      },
      body: JSON.stringify({}),
    },
  );
}

export function getAdminAlphaAccountSessions(
  token: string,
  accountId: string,
): Promise<AdminAlphaAccountSessionsResponse> {
  return requestJson<AdminAlphaAccountSessionsResponse>(
    `/api/admin/alpha/accounts/${accountId}/sessions`,
    {
      headers: { "X-Alpha-Admin-Token": token },
    },
  );
}

export function revokeAdminAlphaAccountSession(
  token: string,
  accountId: string,
  sessionId: string,
): Promise<AdminAlphaSessionRevokeResponse> {
  return requestJson<AdminAlphaSessionRevokeResponse>(
    `/api/admin/alpha/accounts/${accountId}/sessions/${sessionId}/revoke`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Alpha-Admin-Token": token,
      },
      body: "{}",
    },
  );
}

export function revokeAllAdminAlphaAccountSessions(
  token: string,
  accountId: string,
): Promise<AdminAlphaSessionsRevokeAllResponse> {
  return requestJson<AdminAlphaSessionsRevokeAllResponse>(
    `/api/admin/alpha/accounts/${accountId}/sessions/revoke-all`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Alpha-Admin-Token": token,
      },
      body: "{}",
    },
  );
}

export function deleteAdminAlphaTestAccounts(
  token: string,
  payload: { account_ids: string[]; confirm: string },
): Promise<AdminAlphaTestAccountDeleteResponse> {
  return requestJson<AdminAlphaTestAccountDeleteResponse>(
    "/api/admin/alpha/accounts/delete-test",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Alpha-Admin-Token": token,
      },
      body: JSON.stringify(payload),
    },
  );
}
