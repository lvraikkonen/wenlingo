import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { beforeEach, expect, test, vi } from "vitest";
import ParentChildSummaryPage from "../src/app/parent/children/[studentId]/summary/page";
import { getMyAlphaChildSummary, recordAlphaEvent } from "../src/lib/api";
import { ALPHA_SESSION_STORAGE_KEY } from "../src/lib/alphaSession";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("../src/lib/api", () => ({
  getMyAlphaChildSummary: vi.fn(),
  isUnauthorizedError: (error: unknown) =>
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    error.status === 401,
  recordAlphaEvent: vi.fn(async () => undefined),
}));

const child = {
  id: "student-1",
  nickname: "小星",
  name: "小星",
  grade_label: "四年级",
  persona: "real_child" as const,
  is_real_child: true,
  dashboard_url: "/children/student-1",
  summary_url: "/parent/children/student-1/summary",
};

async function renderSummaryPage(studentId = "student-1") {
  await act(async () => {
    render(
      <Suspense fallback={<p>测试加载中</p>}>
        <ParentChildSummaryPage params={Promise.resolve({ studentId })} />
      </Suspense>,
    );
  });
}

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  replace.mockClear();
  vi.mocked(getMyAlphaChildSummary).mockReset();
  vi.mocked(recordAlphaEvent).mockClear();
});

test("summary page redirects to alpha start when session is unauthorized", async () => {
  vi.mocked(getMyAlphaChildSummary).mockRejectedValueOnce({ status: 401 });

  await renderSummaryPage();

  await waitFor(() => expect(replace).toHaveBeenCalledWith("/alpha/start"));
  expect(getMyAlphaChildSummary).toHaveBeenCalledWith("student-1");
});

test("summary page renders empty state for a child without training records", async () => {
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
  vi.mocked(getMyAlphaChildSummary).mockResolvedValue({
    parent_id: "parent-1",
    child,
    assessment_completed: false,
    practice_counts: {
      assessments: 0,
      sentence_trainings: 0,
      essays: 0,
    },
    ability_changes: [],
    recent_highlight: null,
    sentence_training_summary: null,
    next_suggestion: "先完成入门小试炼，生成第一张能力草图。",
    empty_state: "还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。",
  });

  await renderSummaryPage();

  expect(await screen.findByRole("heading", { name: "小星的成长摘要" })).toBeInTheDocument();
  expect(getMyAlphaChildSummary).toHaveBeenCalledWith("student-1");
  expect(recordAlphaEvent).toHaveBeenCalledWith({
    event_type: "summary_viewed",
    parent_id: "parent-1",
    student_id: "student-1",
    alpha_session_id: "session-1",
    payload: { path: "/parent/children/student-1/summary", status: "viewed" },
  });
  expect(screen.getByText("还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。")).toBeInTheDocument();
  expect(screen.getByText("先完成入门小试炼，生成第一张能力草图。")).toBeInTheDocument();
});

test("summary page renders populated practice counts, ability changes, and actions", async () => {
  vi.mocked(getMyAlphaChildSummary).mockResolvedValue({
    parent_id: "parent-1",
    child,
    assessment_completed: true,
    practice_counts: {
      assessments: 1,
      sentence_trainings: 1,
      essays: 1,
    },
    ability_changes: [
      { ability: "expression", label: "表达力", delta: 9 },
      { ability: "observation", label: "观察力", delta: 4 },
    ],
    recent_highlight: "孩子完成了第一次能力草图。",
    sentence_training_summary: null,
    next_suggestion: "继续练习把句子写具体。",
    empty_state: null,
  });

  await renderSummaryPage();

  expect(await screen.findByRole("heading", { name: "小星的成长摘要" })).toBeInTheDocument();
  expect(screen.getByText("入门小试炼 1 次")).toBeInTheDocument();
  expect(screen.getByText("句子训练 1 次")).toBeInTheDocument();
  expect(screen.getByText("小写作 1 次")).toBeInTheDocument();
  expect(screen.getByText("表达力 +9")).toBeInTheDocument();
  expect(screen.getByText("观察力 +4")).toBeInTheDocument();
  expect(screen.getByText("孩子完成了第一次能力草图。")).toBeInTheDocument();
  expect(screen.getByText("继续练习把句子写具体。")).toBeInTheDocument();
  expect(screen.getByText(/本周.*完成了.*次练习/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到孩子空间" })).toHaveAttribute(
    "href",
    "/children/student-1",
  );
  expect(screen.getByRole("link", { name: "返回孩子列表" })).toHaveAttribute(
    "href",
    "/parent/children",
  );
});

test("summary page renders writing castle process summary", async () => {
  vi.mocked(getMyAlphaChildSummary).mockResolvedValueOnce({
    parent_id: "parent-1",
    child,
    assessment_completed: true,
    practice_counts: { assessments: 1, sentence_trainings: 0, essays: 1 },
    ability_changes: [{ ability: "structure", label: "结构力", delta: 4 }],
    recent_highlight: "孩子完成了一次作文构思。",
    sentence_training_summary: null,
    next_suggestion: "下一次继续练习把经过写具体。",
    empty_state: null,
    writing_castle_summary: {
      topic: "我学会了骑车",
      selected_topic_type: "记事作文",
      selected_topic_type_parent: "叙事作文",
      selection_source: "fallback",
      material_source_categories: ["observation", "child_confirmed"],
      unsupported_future_type_overridden: true,
      copy_ready_ai_body_generated: false,
      topic_analysis_used: true,
      topic_focus_confirmed: true,
      topic_focus_edited: true,
      material_questions_answered: 2,
      material_cards_retained: 3,
      outline_confirmed: true,
      outline_edited: true,
      first_draft_completed: true,
      revision_completed: false,
      settlement_completed: false,
    },
  });

  await renderSummaryPage();

  expect(await screen.findByText("作文构思过程")).toBeInTheDocument();
  expect(screen.getByText("题目：我学会了骑车")).toBeInTheDocument();
  expect(screen.getByText("作文类型：记事作文（叙事作文）")).toBeInTheDocument();
  expect(screen.getByText("选择方式：孩子选择相近类型")).toBeInTheDocument();
  expect(screen.getByText("素材来源：观察记录、孩子确认")).toBeInTheDocument();
  expect(screen.getByText("题型覆盖：孩子选择了相近的已支持类型")).toBeInTheDocument();
  expect(screen.getByText("AI 正文：没有生成可直接照抄的作文正文")).toBeInTheDocument();
  expect(screen.getByText("审题：已使用")).toBeInTheDocument();
  expect(screen.getByText("选材：回答 2 个问题")).toBeInTheDocument();
  expect(screen.getByText("素材卡：保留 3 张")).toBeInTheDocument();
  expect(screen.getByText("提纲：已确认并修改")).toBeInTheDocument();
  expect(screen.getByText("初稿：已完成")).toBeInTheDocument();
});

test("summary page renders ai topic origin and no body generation", async () => {
  vi.mocked(getMyAlphaChildSummary).mockResolvedValueOnce({
    parent_id: "parent-1",
    child,
    assessment_completed: true,
    practice_counts: { assessments: 0, sentence_trainings: 0, essays: 1 },
    ability_changes: [],
    recent_highlight: "孩子完成了一次作文构思。",
    sentence_training_summary: null,
    next_suggestion: "下一次继续练习把素材写具体。",
    empty_state: null,
    writing_castle_summary: {
      topic: "足球场边的小发现",
      topic_origin: "ai_topic_idea",
      topic_origin_label: "AI 出题灵感，孩子选择",
      selected_topic_type: "写景作文",
      selected_topic_type_parent: "写景类：地点 / 景物 / 体验",
      selection_source: "ai_suggested",
      material_source_categories: [],
      unsupported_future_type_overridden: false,
      copy_ready_ai_body_generated: false,
      topic_analysis_used: false,
      topic_focus_confirmed: false,
      topic_focus_edited: false,
      material_questions_answered: 0,
      material_cards_retained: 0,
      outline_confirmed: false,
      outline_edited: false,
      first_draft_completed: false,
      revision_completed: false,
      settlement_completed: false,
      selected_topic_idea: {
        id: "idea-1",
        title: "足球场边的小发现",
        topic_type: "place_scenery",
        topic_variant: "default",
        child_safe_prompt: "选择你熟悉的一处球场边景物来写。",
      },
    },
  });

  await renderSummaryPage();

  expect(await screen.findByText("作文构思过程")).toBeInTheDocument();
  expect(screen.getByText("题目来源：AI 出题灵感，孩子选择")).toBeInTheDocument();
  expect(
    screen.getByText("AI 正文：没有生成可直接照抄的作文正文"),
  ).toBeInTheDocument();
});

test("summary page omits empty writing castle selection source", async () => {
  vi.mocked(getMyAlphaChildSummary).mockResolvedValueOnce({
    parent_id: "parent-1",
    child,
    assessment_completed: true,
    practice_counts: { assessments: 1, sentence_trainings: 0, essays: 1 },
    ability_changes: [{ ability: "structure", label: "结构力", delta: 4 }],
    recent_highlight: "孩子完成了一次作文构思。",
    sentence_training_summary: null,
    next_suggestion: "下一次继续练习把经过写具体。",
    empty_state: null,
    writing_castle_summary: {
      topic: "我学会了骑车",
      selected_topic_type: "记事作文",
      selection_source: "",
      topic_analysis_used: true,
      topic_focus_confirmed: true,
      topic_focus_edited: true,
      material_questions_answered: 2,
      material_cards_retained: 3,
      outline_confirmed: true,
      outline_edited: false,
      first_draft_completed: true,
      revision_completed: false,
      settlement_completed: false,
    },
  });

  await renderSummaryPage();

  expect(await screen.findByText("作文构思过程")).toBeInTheDocument();
  expect(screen.getByText("作文类型：记事作文")).toBeInTheDocument();
  expect(screen.queryByText(/^选择方式：/)).not.toBeInTheDocument();
});

test("summary page renders lightweight sentence training summary", async () => {
  vi.mocked(getMyAlphaChildSummary).mockResolvedValueOnce({
    parent_id: "parent-1",
    child: {
      id: "s1",
      nickname: "小星",
      name: "小星",
      grade_label: "四年级",
      persona: "real_child",
      is_real_child: true,
      dashboard_url: "/children/s1",
      summary_url: "/parent/children/s1/summary",
      assessment_completed: true,
    },
    usefulness: null,
    assessment_completed: true,
    practice_counts: { assessments: 1, sentence_trainings: 3, essays: 0 },
    ability_changes: [{ ability: "expression", label: "表达力", delta: 3 }],
    recent_highlight: "孩子完成了第一次能力草图。",
    next_suggestion: "保持每周一次短练习。",
    empty_state: null,
    sentence_training_summary: "本周完成 3 次句子挑战，主要练习了“动作描写”和“扩句”。",
  });

  await renderSummaryPage("s1");

  expect(await screen.findByText("句子训练 3 次")).toBeInTheDocument();
  expect(
    screen.getByText("本周完成 3 次句子挑战，主要练习了“动作描写”和“扩句”。"),
  ).toBeInTheDocument();
});

test("summary page omits sentence practice copy when there is no sentence practice", async () => {
  vi.mocked(getMyAlphaChildSummary).mockResolvedValueOnce({
    parent_id: "parent-1",
    child,
    assessment_completed: true,
    practice_counts: {
      assessments: 1,
      sentence_trainings: 0,
      essays: 1,
    },
    ability_changes: [{ ability: "expression", label: "表达力", delta: 5 }],
    recent_highlight: "孩子完成了一次小写作。",
    sentence_training_summary: null,
    next_suggestion: "下一步可以尝试一次句子练习。",
    empty_state: null,
  });

  await renderSummaryPage();

  expect(await screen.findByText("句子训练 0 次")).toBeInTheDocument();
  expect(screen.queryByText(/本周.*完成了.*次练习/)).not.toBeInTheDocument();
});

test("summary page renders an error state when summary loading fails", async () => {
  vi.mocked(getMyAlphaChildSummary).mockRejectedValue(new Error("boom"));

  await renderSummaryPage();

  expect(await screen.findByRole("alert")).toHaveTextContent("成长摘要加载失败，请稍后再试。");
});
