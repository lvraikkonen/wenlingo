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

export type TopicAnalysisCard = {
  id: string;
  kind: "topic_question" | "must_include" | "shine_point";
  title: string;
  body: string;
  required_points: string[];
};

export type TopicType =
  | "generic_narrative"
  | "person_portrait"
  | "imaginative_story"
  | "expository_introduction"
  | "place_scenery"
  | "animal_object_observation"
  | "practical_writing"
  | "story_adaptation";

export type FutureTopicType =
  | "story_summary"
  | "reading_response_recommendation"
  | "central_idea_reflection"
  | "picture_prompt_story";

export type TopicVariant = string;

export type ScaffoldSelectionSource = "ai_suggested" | "manual" | "fallback";

export type MaterialSlotSpec = {
  id: string;
  label: string;
  content_kind: string;
};

export type OutlineSectionSpec = {
  id: string;
  heading: string;
  label: string;
  content_kind: string;
};

export type WritingCastleScaffoldState = {
  schema_version: "v0.6b.1";
  topic_type: TopicType;
  topic_variant: TopicVariant;
  scaffold_template_version: string;
  resolved_at: string;
  selection_source: ScaffoldSelectionSource;
  display_name_child: string;
  display_name_parent: string;
  material_slots: MaterialSlotSpec[];
  outline_sections: OutlineSectionSpec[];
  source_policy: Record<string, unknown>;
  unsupported_future_type?: FutureTopicType | null;
  unsupported_override?: boolean;
};

export type TopicTypeChoice = {
  topic_type: TopicType;
  display_name_child: string;
  display_name_parent: string;
};

export type ScaffoldSelectionRequest = {
  topic_type: TopicType;
  topic_variant?: TopicVariant;
  accepted_suggestion_id?: string;
  override_reason?: "manual_choice" | "suggestion_accepted" | "fallback_selected";
  unsupported_future_type?: FutureTopicType;
};

export type ScaffoldRef = {
  topic_type: TopicType;
  topic_variant: TopicVariant;
  scaffold_template_version: string;
};

export type AiTopicIdea = {
  id: string;
  title: string;
  topic_type: TopicType;
  topic_variant: TopicVariant;
  why_it_fits_child_interest: string;
  practice_focus: string;
  child_safe_prompt: string;
};

export type AiTopicIdeasResponse = {
  idea_batch_id: string;
  expires_at: string;
  ideas: AiTopicIdea[];
};

export type MaterialAnswer = {
  id: string;
  question_id: string;
  text: string;
  skipped: boolean;
};

export type LegacyMaterialCardCategory = "event" | "detail" | "feeling_takeaway";

export type MaterialCardSlot = {
  id: string;
  category: LegacyMaterialCardCategory | (string & {});
  text: string;
  source_answer_ids: string[];
  order: number;
  deleted: boolean;
  child_edited: boolean;
  placeholder: boolean;
};

export type LegacyOutlineSlot = "cause" | "process" | "result" | "reflection";

export type WritingOutlineSection = {
  id: string;
  slot: LegacyOutlineSlot | (string & {});
  heading: string;
  note: string;
  source_card_ids: string[];
  child_edited: boolean;
  placeholder: boolean;
};

export type WritingCastleTopicAnalysis = {
  cards: TopicAnalysisCard[];
  suggested_focus: string;
  status: string;
};

export type WritingCastleEssay = {
  id: string;
  student_id: string;
  title: string;
  status:
    | "prewriting_started"
    | "topic_ready"
    | "materials_ready"
    | "outline_ready"
    | "revision_requested"
    | "settled";
  material_card: {
    schema_version: "v0.6a.1" | "v0.6b.1";
    scaffold_ref?: ScaffoldRef | null;
    questions: Array<{ id: string; text: string; hint: string; order: number }>;
    answers: MaterialAnswer[];
    cards: MaterialCardSlot[];
    step_state: {
      questions_status: string;
      cards_status: string;
    };
  };
  outline: {
    schema_version: "v0.6a.1" | "v0.6b.1";
    scaffold?: WritingCastleScaffoldState | null;
    topic_origin?: "teacher_provided" | "ai_topic_idea" | "direct_draft" | "";
    selected_topic_idea?: Partial<AiTopicIdea> | null;
    topic_requirement?: Record<string, unknown> | null;
    topic_analysis: WritingCastleTopicAnalysis;
    child_topic_focus: {
      text: string;
      adopted_from_ai: boolean;
      skipped: boolean;
      updated_at: string;
    };
    sections: WritingOutlineSection[];
    step_state: { outline_status: string };
  };
};

export type WritingCastleEssayResponse = {
  essay: WritingCastleEssay;
};

export type CreateClassroomEssayResponse = WritingCastleEssayResponse & {
  supported_topic_types: TopicTypeChoice[];
  unsupported_future_type?: FutureTopicType | null;
};

export type ActiveWritingCastleEssayResponse = {
  essay: WritingCastleEssay | null;
  supported_topic_types?: TopicTypeChoice[];
  unsupported_future_type?: FutureTopicType | null;
};

export type WritingCastleTopicAnalysisResponse = WritingCastleEssayResponse & {
  topic_analysis: WritingCastleTopicAnalysis;
};

export type EssayArchiveItem = {
  essay_id: string;
  title: string;
  status:
    | "needs_revision"
    | "revised_once"
    | "multi_round_revision"
    | "hidden_by_child"
    | "needs_retry";
  hidden: boolean;
  hidden_by: "" | "child" | "parent";
  hidden_at?: string | null;
  latest_round_index: number;
  latest_version_id: string;
  last_version_submitted_at: string;
  revision_round_count: number;
  needs_revision: boolean;
  can_continue_revision: boolean;
  can_retry_revision_attempt: boolean;
  summary_label: string;
  topic_origin?: "teacher_provided" | "ai_topic_idea" | "direct_draft" | "";
  topic_type?: TopicType | "" | null;
  topic_variant?: TopicVariant | "" | null;
  scaffold_template_version?: string | null;
  selected_topic_idea?: Partial<AiTopicIdea> | null;
  generated_topic_metadata?: Record<string, unknown> | null;
};

export type EssayArchiveVersion = {
  version_id: string;
  version_label: string;
  round_index: number;
  content: string;
  ai_feedback: Record<string, unknown> | null;
  duration_seconds: number | null;
  completed_tasks: string[];
  skipped_tasks: string[];
  llm_call_log_id: string | null;
  created_at: string;
};

export type EssayArchiveRevisionAttempt = {
  attempt_id: string;
  status: string;
  base_version_id: string;
  target_round_index: number;
  submitted_content: string;
  error_code: string | null;
  can_retry: boolean;
  created_at: string;
  updated_at: string;
};

export type EssayArchiveContinueRevision = {
  latest_version_id: string;
  latest_content: string;
  previous_ai_guidance: string;
  next_round_index: number;
};

export type EssayArchiveParentSummary = {
  status: EssayArchiveItem["status"];
  summary_label: string;
  latest_round_index: number;
  revision_round_count: number;
  recent_improvement: string | null;
  next_suggestion: string | null;
};

export type EssayArchiveDetailResponse = EssayArchiveItem & {
  visibility: {
    hidden: boolean;
    hidden_by: EssayArchiveItem["hidden_by"];
    hidden_at?: string | null;
    visibility_changed_at?: string | null;
  };
  versions: EssayArchiveVersion[];
  revision_attempt: EssayArchiveRevisionAttempt | null;
  continue_revision: EssayArchiveContinueRevision | null;
  parent_summary: EssayArchiveParentSummary | null;
};

export type RevisionAttemptPendingResponse = {
  status: "pending_comparison";
  attempt_id: string;
  message: string;
};

export type WritingCastleSummaryMaterialSourceCategory =
  | "real_experience"
  | "imagined_setting"
  | "topic_requirement"
  | "observation"
  | "reading_material"
  | "child_confirmed";

export type WritingCastleSummarySelectionSource = ScaffoldSelectionSource | "";

export type WritingCastleProcessSummary = {
  topic: string;
  topic_origin?: "teacher_provided" | "ai_topic_idea" | "direct_draft" | "";
  topic_origin_label?: string | null;
  selected_topic_idea?: {
    id: string;
    title: string;
    topic_type: TopicType;
    topic_variant: TopicVariant;
    child_safe_prompt?: string;
  } | null;
  selected_topic_type?: string | null;
  selected_topic_type_parent?: string | null;
  selection_source?: WritingCastleSummarySelectionSource | null;
  material_source_categories?: WritingCastleSummaryMaterialSourceCategory[] | null;
  unsupported_future_type_overridden?: boolean | null;
  copy_ready_ai_body_generated?: boolean | null;
  topic_analysis_used: boolean;
  topic_focus_confirmed: boolean;
  topic_focus_edited: boolean;
  material_questions_answered: number;
  material_cards_retained: number;
  outline_confirmed: boolean;
  outline_edited: boolean;
  first_draft_completed: boolean;
  revision_completed: boolean;
  settlement_completed: boolean;
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
  writing_castle_summary?: WritingCastleProcessSummary | null;
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
  provider: string;
  model: string;
  final_status: string;
  call_count: number;
  success_count: number;
  fallback_success_count: number;
  deterministic_fallback_count: number;
  failure_count: number;
  daily_limit_hit_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  pricing_status: string;
  avg_latency_ms: number;
  streaming_enabled_count: number;
  stream_completed_count: number;
  client_disconnect_count: number;
  provider_failed_before_visible_content_count: number;
  provider_failed_after_visible_content_count: number;
  usage_available_count: number;
  usage_missing_count: number;
  calls_with_usage_applicable: number;
  usage_available_rate: number;
  first_provider_delta_p50_ms: number;
  first_visible_content_p50_ms: number;
  provider_stream_duration_p50_ms: number;
  live_llm_success_count: number;
  timeout_count: number;
  schema_validation_success_count: number;
  source_reference_success_count: number;
};

export type AdminAlphaAIUsageResponse = {
  pricing_configured: boolean;
  usage: AdminAlphaAIUsageRow[];
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

export type AdminAlphaAccountSession = {
  session_id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  revoked_at: string | null;
};

export type AdminAlphaAccountSessionsResponse = {
  account: {
    account_id: string;
    email_masked: string;
    status: string;
  };
  sessions: AdminAlphaAccountSession[];
};

export type AdminAlphaSessionRevokeResponse = {
  session: {
    session_id: string;
    revoked: boolean;
  };
};

export type AdminAlphaSessionsRevokeAllResponse = {
  account: {
    account_id: string;
    revoked_session_count: number;
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
