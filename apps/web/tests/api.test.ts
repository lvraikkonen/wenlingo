import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  completeSentenceChallenge,
  createAssessment,
  createClassroomWritingCastleEssay,
  createSentenceChallenge,
  createSentenceTraining,
  generateMaterialCards,
  generateMaterialQuestions,
  generateOutline,
  generateTopicAnalysis,
  getAdminAlphaOverview,
  getAdminAlphaAIUsage,
  getActiveClassroomWritingCastleEssay,
  getDashboard,
  saveMaterialAnswers,
  saveMaterialCards,
  saveOutline,
  saveTopicFocus,
  submitPrewritingFirstDraft,
} from "../src/lib/api";
import type { DashboardResponse } from "../src/lib/types";

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
});
