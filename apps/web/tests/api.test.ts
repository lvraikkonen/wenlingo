import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  completeSentenceChallenge,
  createAssessment,
  createClassroomWritingCastleEssay,
  createSentenceChallenge,
  createSentenceTraining,
  fetchChildEssayArchive,
  fetchEssayArchiveDetail,
  fetchParentEssayArchive,
  fetchParentEssayArchiveDetail,
  generateMaterialCards,
  generateMaterialQuestions,
  generateOutline,
  generateTopicAnalysis,
  getAdminAlphaOverview,
  getAdminAlphaAIUsage,
  getActiveClassroomWritingCastleEssay,
  getDashboard,
  hideChildEssay,
  restoreParentEssay,
  retryEssayRevisionAttempt,
  saveMaterialAnswers,
  saveMaterialCards,
  saveOutline,
  saveTopicFocus,
  selectWritingCastleScaffold,
  submitEssayRevision,
  submitPrewritingFirstDraft,
} from "../src/lib/api";
import type {
  DashboardResponse,
  EssayArchiveDetailResponse,
  RevisionAttemptPendingResponse,
} from "../src/lib/types";

const fetchMock = vi.fn();

function assertTopicAnalysisTypes(
  response: Awaited<ReturnType<typeof generateTopicAnalysis>>,
) {
  const topLevelSuggestedFocus: string =
    response.topic_analysis.suggested_focus;
  const nestedSuggestedFocus: string =
    response.essay.outline.topic_analysis.suggested_focus;

  return { nestedSuggestedFocus, topLevelSuggestedFocus };
}

void assertTopicAnalysisTypes;

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  };
}

const student = {
  id: "s1",
  name: "小宇",
  grade_label: "三年级",
  persona: "real_child",
  level: 3,
  xp: 120,
} satisfies DashboardResponse["student"];

const dashboardResponse = {
  student,
  ability_note: "阅读理解稳定，表达可以继续具体化。",
  assessment_completed: true,
  assessment_recommended: false,
  child_abilities: {
    reading_power: 50,
    specific_writing_power: 54,
    revision_power: 20,
  },
  today_tasks: {
    main: {
      kind: "essay",
      title: "把经历写具体",
      focus: "动作和感受",
      minutes: "20",
    },
    quick: {
      kind: "reading",
      title: "读短文找线索",
      focus: "概括重点",
      minutes: "8",
    },
  },
  map: ["阅读", "表达", "修改"],
  coach_message: "今天先完成主线任务，再做快速练习。",
} satisfies DashboardResponse;

const archiveDetailTypeAssertion = {
  essay_id: "essay-1",
  title: "我学会了骑车",
  status: "revised_once",
  hidden: false,
  hidden_by: "",
  latest_round_index: 1,
  latest_version_id: "version-2",
  last_version_submitted_at: "2026-07-01T00:00:00Z",
  revision_round_count: 1,
  needs_revision: false,
  can_continue_revision: true,
  can_retry_revision_attempt: false,
  summary_label: "已修改 1 次",
  topic_type: "",
  topic_variant: "",
  selected_topic_idea: {
    id: "idea-1",
    title: "足球场边的小发现",
  },
  generated_topic_metadata: {
    idea_id: "idea-1",
  },
  visibility: {
    hidden: false,
    hidden_by: "",
    hidden_at: null,
    visibility_changed_at: null,
  },
  versions: [],
  revision_attempt: null,
  continue_revision: {
    latest_version_id: "version-2",
    latest_content: "我把骑车过程写具体了。",
    previous_ai_guidance: "下一轮可以继续补充心理感受。",
    next_round_index: 2,
  },
  parent_summary: null,
} satisfies EssayArchiveDetailResponse;

void archiveDetailTypeAssertion;

const pendingRevisionTypeAssertion: RevisionAttemptPendingResponse = {
  status: "pending_comparison",
  attempt_id: "attempt-1",
  message: "这次修改正在保存，请不要重复提交。",
};

const submitEssayRevisionTypeAssertion:
  Awaited<ReturnType<typeof submitEssayRevision>> = pendingRevisionTypeAssertion;

void submitEssayRevisionTypeAssertion;

describe("api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  test("api client no longer exposes demo login", async () => {
    const api = await import("../src/lib/api");
    const removedExport = `demo${"Login"}`;

    expect(removedExport in api).toBe(false);
  });

  test("getDashboard defaults to same-origin API path", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => dashboardResponse,
    }) as unknown as typeof fetch;

    await getDashboard("s1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/students/s1/dashboard",
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("getDashboard respects NEXT_PUBLIC_API_BASE_URL override", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test/");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => dashboardResponse,
    }) as unknown as typeof fetch;
    const { getDashboard: getDashboardWithOverride } = await import(
      "../src/lib/api"
    );

    await getDashboardWithOverride("s1");

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.test/api/students/s1/dashboard",
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("getDashboard treats /api override as same-origin API path", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "/api");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => dashboardResponse,
    }) as unknown as typeof fetch;
    const { getDashboard: getDashboardWithApiBase } = await import(
      "../src/lib/api"
    );

    await getDashboardWithApiBase("s1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/students/s1/dashboard",
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("createAssessment posts entry trial payload", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        assessment: {
          id: "assessment-1",
          summary: "完成入门小试炼，生成第一张能力草图。",
          sentence_training_id: "sentence-training-1",
          essay_id: "essay-1",
        },
        ability_sketch: {
          reading_power: 40,
          specific_writing_power: 46,
          revision_power: 40,
        },
        settlement: {
          xp_delta: 20,
          level_after: 1,
          badge_code: null,
        },
      }),
    }) as unknown as typeof fetch;
    const payload = {
      sentence_before: "公园很美。",
      sentence_after: "公园里的花红红的，风一吹就轻轻摇。",
      short_writing: "我学会了骑车。",
    };

    await createAssessment("s1", payload);

    expect(fetch).toHaveBeenCalledWith(
      "/api/students/s1/assessment",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("createSentenceTraining posts sentence training payload", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        feedback: {
          encouragement: "你把画面写得更清楚了。",
          specific_improvement: "加入了可看见的细节",
        },
        settlement: { xp_delta: 25, level_after: 2 },
      }),
    }) as unknown as typeof fetch;
    const payload = {
      source_sentence: "公园很美。",
      upgraded_sentence: "清晨的公园里，荷叶上的水珠一闪一闪。",
      focus: "加细节",
    } satisfies Parameters<typeof createSentenceTraining>[1];

    await createSentenceTraining("s1", payload);

    expect(fetch).toHaveBeenCalledWith(
      "/api/students/s1/sentences",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("createSentenceChallenge posts to challenge endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ challenge: { id: "training-1" } }),
    );

    await createSentenceChallenge("student-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/students/student-1/sentence-challenges",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      }),
    );
  });

  test("completeSentenceChallenge posts upgraded sentence", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ training: { id: "training-1" } }),
    );

    await completeSentenceChallenge("student-1", "training-1", {
      upgraded_sentence: "小猫飞快地跑过草地。",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/students/student-1/sentences/training-1/complete",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upgraded_sentence: "小猫飞快地跑过草地。" }),
        credentials: "include",
      }),
    );
  });

  test("getAdminAlphaAIUsage uses admin token header", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ pricing_configured: false, usage: [] }),
    );

    const result = await getAdminAlphaAIUsage("secret");

    expect(result).toEqual({ pricing_configured: false, usage: [] });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/alpha/ai-usage",
      expect.objectContaining({
        credentials: "include",
        cache: "no-store",
        headers: { "X-Alpha-Admin-Token": "secret" },
      }),
    );
  });

  test("getAdminAlphaOverview can include revoked families", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ families: [] }));

    await getAdminAlphaOverview("secret", true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/alpha/overview?include_revoked=true",
      expect.objectContaining({
        headers: { "X-Alpha-Admin-Token": "secret" },
      }),
    );
  });

  test("getAdminAlphaOverview omits revoked families by default", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ families: [] }));

    await getAdminAlphaOverview("secret");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/alpha/overview",
      expect.objectContaining({
        headers: { "X-Alpha-Admin-Token": "secret" },
      }),
    );
  });

  test("selectWritingCastleScaffold patches scaffold selection", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ essay: { id: "essay-1" }, scaffold: {} }),
    );
    const payload = {
      topic_type: "person_portrait",
      override_reason: "manual_choice",
    } satisfies Parameters<typeof selectWritingCastleScaffold>[1];

    await selectWritingCastleScaffold("essay-1", payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/essays/essay-1/scaffold-selection",
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include",
        cache: "no-store",
      }),
    );
  });

  test("throws when the API response is not ok", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;

    await expect(getDashboard("s1")).rejects.toThrow("Request failed: 500");
  });

  test("writing castle api functions call prewriting endpoints", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ essay: { id: "essay-1" } }));

    const topicPayload = {
      topic_text: "我学会了骑车",
    };
    const focusPayload = {
      text: "写学会骑车",
      adopted_from_ai: false,
      skipped: false,
    };
    const answersPayload = {
      answers: [
        {
          id: "answer-1",
          question_id: "question-1",
          text: "我先练习保持平衡。",
          skipped: false,
        },
      ],
    };
    const cardsPayload = {
      cards: [
        {
          id: "card-1",
          category: "event",
          text: "第一次骑车摇摇晃晃",
          source_answer_ids: ["answer-1"],
          order: 1,
          deleted: false,
          child_edited: true,
          placeholder: false,
        },
      ],
    } satisfies Parameters<typeof saveMaterialCards>[1];
    const outlinePayload = {
      sections: [
        {
          id: "section-1",
          slot: "process",
          heading: "练习过程",
          note: "写从害怕到会骑的过程",
          source_card_ids: ["card-1"],
          child_edited: true,
          placeholder: false,
        },
      ],
      skipped: true,
    } satisfies Parameters<typeof saveOutline>[1];
    const firstDraftPayload = {
      draft: "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
    };

    await getActiveClassroomWritingCastleEssay("student-1");
    await createClassroomWritingCastleEssay("student-1", topicPayload);
    await generateTopicAnalysis("essay-1");
    await saveTopicFocus("essay-1", focusPayload);
    await generateMaterialQuestions("essay-1");
    await saveMaterialAnswers("essay-1", answersPayload);
    await generateMaterialCards("essay-1");
    await saveMaterialCards("essay-1", cardsPayload);
    await generateOutline("essay-1");
    await saveOutline("essay-1", outlinePayload);
    await submitPrewritingFirstDraft("essay-1", firstDraftPayload);

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/api/students/student-1/writing-castle/classroom/active",
      "/api/students/student-1/writing-castle/classroom",
      "/api/essays/essay-1/topic-analysis",
      "/api/essays/essay-1/topic-focus",
      "/api/essays/essay-1/material-questions",
      "/api/essays/essay-1/material-answers",
      "/api/essays/essay-1/material-cards",
      "/api/essays/essay-1/material-cards",
      "/api/essays/essay-1/outline",
      "/api/essays/essay-1/outline",
      "/api/essays/essay-1/first-draft",
    ]);

    expect(fetchMock.mock.calls.map((call) => call[1])).toEqual([
      expect.objectContaining({
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(topicPayload),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(focusPayload),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(answersPayload),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cardsPayload),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(outlinePayload),
        credentials: "include",
        cache: "no-store",
      }),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(firstDraftPayload),
        credentials: "include",
        cache: "no-store",
      }),
    ]);
  });

  test("essay archive helpers call child and parent archive endpoints", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [] }));

    await fetchChildEssayArchive("student-1");
    await fetchParentEssayArchive("student-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/students/student-1/essay-archive?limit=3",
      expect.objectContaining({
        credentials: "include",
        cache: "no-store",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/parents/students/student-1/essay-archive?include_hidden=true&limit=20",
      expect.objectContaining({
        credentials: "include",
        cache: "no-store",
      }),
    );
  });

  test("essay archive detail helpers call child and parent detail endpoints", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ item: { essay_id: "essay-1" } }));

    await fetchEssayArchiveDetail("essay-1");
    await fetchParentEssayArchiveDetail("essay-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/essays/essay-1/archive-detail",
      expect.objectContaining({
        credentials: "include",
        cache: "no-store",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/parents/essays/essay-1/archive-detail",
      expect.objectContaining({
        credentials: "include",
        cache: "no-store",
      }),
    );
  });

  test("essay visibility helpers patch child hide and parent restore endpoints", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ essay_id: "essay-1" }));

    await hideChildEssay("essay-1");
    await restoreParentEssay("essay-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/essays/essay-1/visibility",
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hidden: true }),
        credentials: "include",
        cache: "no-store",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/parents/essays/essay-1/visibility",
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hidden: false }),
        credentials: "include",
        cache: "no-store",
      }),
    );
  });

  test("retryEssayRevisionAttempt posts to retry comparison endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        status: "pending_comparison",
        attempt_id: "attempt-1",
        message: "Retry queued.",
      }),
    );

    await retryEssayRevisionAttempt("essay-1", "attempt-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/essays/essay-1/revision-attempts/attempt-1/retry-comparison",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
        cache: "no-store",
      }),
    );
  });

  test("submitEssayRevision posts base version and idempotency key", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        revision: { id: "revision-1" },
        comparison: { encouragement: "修改得更清楚了。" },
        settlement: { xp_delta: 20, level_after: 2 },
      }),
    );
    const payload = {
      base_version_id: "version-1",
      content: "我把骑车过程写得更具体了。",
      idempotency_key: "revision-key-1",
      completed_tasks: ["加上动作"],
      skipped_tasks: [],
      duration_seconds: 180,
    } satisfies Parameters<typeof submitEssayRevision>[1];

    await submitEssayRevision("essay-1", payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/essays/essay-1/revision",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include",
        cache: "no-store",
      }),
    );
  });

  test("submitEssayRevision returns successful pending comparison response", async () => {
    const pendingResponse = {
      status: "pending_comparison",
      attempt_id: "attempt-1",
      message: "这次修改正在保存，请不要重复提交。",
    } satisfies RevisionAttemptPendingResponse;
    fetchMock.mockResolvedValueOnce(jsonResponse(pendingResponse));

    const result = await submitEssayRevision("essay-1", {
      base_version_id: "version-1",
      content: "我把骑车过程写得更具体了。",
      idempotency_key: "revision-key-1",
      completed_tasks: ["加上动作"],
      skipped_tasks: [],
      duration_seconds: 180,
    });

    expect(result).toEqual(pendingResponse);
  });
});
