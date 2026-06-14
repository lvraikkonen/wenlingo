export type Student = {
  id: string;
  name: string;
  grade_label: string;
  persona:
    | "real_child"
    | "vague_expression"
    | "weak_structure"
    | "weak_reading_summary";
  level: number;
  xp: number;
};

export type DemoLoginResponse = {
  parent: { id: string; email: string; display_name: string };
  students: Student[];
};

export type RecommendedTask = {
  kind: "assessment" | "sentence" | "essay" | "reading";
  title: string;
  focus: string;
  minutes: string;
};

export type DashboardResponse = {
  student: Student;
  ability_note: string;
  assessment_completed: boolean;
  assessment_recommended: boolean;
  child_abilities: {
    reading_power: number;
    specific_writing_power: number;
    revision_power: number;
  };
  today_tasks: {
    main: RecommendedTask;
    quick: RecommendedTask;
  };
  map: string[];
  coach_message: string;
};

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

export type SentenceChallenge = {
  id: string;
  source_sentence: string;
  challenge_prompt: string;
  hint: string;
  focus: "扩句" | "动作描写" | "心理感受";
  target_skill: "expand_sentence" | "action_expression" | "feeling";
  difficulty_label:
    | "三年级基础"
    | "三年级进阶"
    | "四年级基础"
    | "四年级进阶"
    | "五年级基础"
    | "五年级进阶"
    | "六年级基础"
    | "六年级进阶";
  grade_label: "三年级" | "四年级" | "五年级" | "六年级";
};

export type SentenceChallengeResponse = {
  challenge: SentenceChallenge;
};

export type SentenceChallengeCompletionResponse = {
  training: {
    id: string;
    reaction?: FeedbackReactionValue | null;
  };
  feedback: {
    encouragement: string;
    highlight: string;
    suggestion: string;
    example_upgrade: string;
  };
  settlement: Settlement;
  next_task: RecommendedTask;
};

export type AlphaParent = {
  id: string;
  email: string;
  display_name: string;
};

export type AlphaParentResponse = {
  parent: AlphaParent;
  children_url: string;
};

export type AuthSession =
  | { authenticated: false }
  | {
      authenticated: true;
      account: {
        email_masked: string;
        phone_bound: boolean;
        last_login_at?: string | null;
      };
      parent?: {
        id: string;
        display_name: string;
      } | null;
      parent_id?: string | null;
    };

export type AlphaInviteValidationResponse = {
  valid: boolean;
  invite_id: string;
  label: string;
};

export type AlphaEventPayload = Record<string, string | number | boolean | null>;

export type AlphaEventCreate = {
  event_type: string;
  parent_id?: string | null;
  student_id?: string | null;
  invite_code_id?: string | null;
  alpha_session_id?: string;
  payload?: AlphaEventPayload;
};

export type AlphaChild = {
  id: string;
  nickname: string;
  name: string;
  grade_label: string;
  persona: "real_child";
  is_real_child: boolean;
  dashboard_url: string;
  summary_url: string;
  assessment_completed?: boolean;
};

export type AlphaChildrenResponse = {
  parent: AlphaParent;
  account?: {
    email_masked: string;
    phone_bound: boolean;
    phone_masked?: string | null;
  };
  children: AlphaChild[];
};

export type AlphaChildCreateResponse = {
  child: AlphaChild;
  dashboard_url: string;
  summary_url: string;
};

export type AlphaAbilityChange = {
  ability: string;
  label: string;
  delta: number;
};

export type AlphaChildSummary = {
  parent_id: string;
  child: AlphaChild;
  usefulness?: ParentSummaryUsefulness | null;
  assessment_completed: boolean;
  practice_counts: {
    assessments: number;
    sentence_trainings: number;
    essays: number;
  };
  ability_changes: AlphaAbilityChange[];
  recent_highlight: string | null;
  sentence_training_summary: string | null;
  next_suggestion: string;
  empty_state: string | null;
};

export type FeedbackReactionValue = "positive" | "neutral" | "negative";

export type FeedbackReactionTargetType =
  | "assessment"
  | "sentence_training"
  | "essay_draft"
  | "essay_revision";

export type SavedFeedbackReaction = {
  id: string;
  student_id: string;
  target_type: FeedbackReactionTargetType;
  target_id: string;
  reaction: FeedbackReactionValue;
};

export type ParentSummaryUsefulness = "helpful" | "not_helpful";

export type AdminAlphaOverviewRow = {
  invite_id: string;
  invite_label: string;
  invite_status: string;
  parent_id: string | null;
  parent_display_name: string | null;
  child_count: number;
  funnel_stage: string;
  assessment_completed_count: number;
  summary_viewed: boolean;
  reaction_counts: Record<string, number>;
  latest_parent_feedback: string | null;
  last_event_at: string | null;
  account_linked: boolean;
  account_email_masked: string | null;
  phone_bound: boolean;
  last_login_at: string | null;
};

export type AdminAlphaAIUsageRow = {
  date: string;
  task_type: string;
  model: string;
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  failure_count: number;
  daily_limit_hit_count: number;
};

export type AdminAlphaAccountRow = {
  account_id: string;
  email_masked: string;
  status: "active" | "disabled" | string;
  parent_id: string | null;
  parent_display_name: string | null;
  children_count: number;
  last_login_at: string | null;
  active_session_count: number;
  created_at: string | null;
};

export type AdminAlphaInviteCreateResponse = {
  invites: Array<{
    invite_id: string;
    label: string;
    status: string;
    raw_code: string;
  }>;
};

export type AdminAlphaInviteActionResponse = {
  invite: {
    invite_id: string;
    label: string;
    status: string;
  };
};

export type AdminAlphaAccountActionResponse = {
  account: {
    account_id: string;
    status: string;
    revoked_session_count?: number;
  };
};

export type AdminAlphaTestAccountDeleteResponse = {
  deleted_count: number;
  accounts: Array<{
    account_id: string;
    email_masked: string;
    parent_ids: string[];
    child_count: number;
    deleted_session_count: number;
    deleted_invite_count: number;
  }>;
};

export type AdminAlphaEvent = {
  id: string;
  event_type: string;
  created_at: string;
  payload: Record<string, unknown>;
};

export type AdminAlphaFamilyDetail = {
  parent: {
    id: string;
    display_name: string;
  };
  children: Array<{
    id: string;
    grade_label: string;
  }>;
  events: AdminAlphaEvent[];
  reaction_counts: Record<string, number>;
  parent_feedback: Array<{
    student_id: string;
    usefulness: string;
  }>;
};
