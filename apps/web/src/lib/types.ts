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

export type AlphaParent = {
  id: string;
  email: string;
  display_name: string;
};

export type AlphaParentResponse = {
  parent: AlphaParent;
  children_url: string;
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
  assessment_completed: boolean;
  practice_counts: {
    assessments: number;
    sentence_trainings: number;
    essays: number;
  };
  ability_changes: AlphaAbilityChange[];
  recent_highlight: string | null;
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
