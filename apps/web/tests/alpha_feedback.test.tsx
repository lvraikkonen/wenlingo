import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Suspense } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import AssessmentPage from "../src/app/children/[studentId]/assessment/page";
import EssayPage from "../src/app/children/[studentId]/essay/page";
import SentencePage from "../src/app/children/[studentId]/sentence/page";
import ParentChildSummaryPage from "../src/app/parent/children/[studentId]/summary/page";
import { FeedbackReaction } from "../src/components/FeedbackReaction";
import { ParentSummaryFeedback } from "../src/components/ParentSummaryFeedback";
import { ALPHA_PARENT_STORAGE_KEY } from "../src/lib/alphaParent";
import { ALPHA_SESSION_STORAGE_KEY } from "../src/lib/alphaSession";

const apiMocks = vi.hoisted(() => ({
  createAssessment: vi.fn(),
  createSentenceTraining: vi.fn(),
  createEssay: vi.fn(),
  submitEssayRevision: vi.fn(),
  getAlphaChildren: vi.fn(),
  getAlphaChildSummary: vi.fn(),
  recordAlphaEvent: vi.fn(async () => undefined),
  saveFeedbackReaction: vi.fn(),
  saveParentSummaryFeedback: vi.fn(),
}));

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("../src/lib/api", () => ({
  createAssessment: apiMocks.createAssessment,
  createSentenceTraining: apiMocks.createSentenceTraining,
  createEssay: apiMocks.createEssay,
  submitEssayRevision: apiMocks.submitEssayRevision,
  getAlphaChildren: apiMocks.getAlphaChildren,
  getAlphaChildSummary: apiMocks.getAlphaChildSummary,
  recordAlphaEvent: apiMocks.recordAlphaEvent,
  saveFeedbackReaction: apiMocks.saveFeedbackReaction,
  saveParentSummaryFeedback: apiMocks.saveParentSummaryFeedback,
}));

const summaryChild = {
  id: "s1",
  nickname: "小星",
  name: "小星",
  grade_label: "四年级",
  persona: "real_child" as const,
  is_real_child: true,
  dashboard_url: "/children/s1",
  summary_url: "/parent/children/s1/summary",
};

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-1");
  replace.mockClear();
  apiMocks.createAssessment.mockResolvedValue({
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
  });
  apiMocks.createSentenceTraining.mockResolvedValue({
    training: { id: "training-1" },
    feedback: {
      encouragement: "你把画面写得更清楚了。",
      specific_improvement: "加入了可看见的细节",
      next_step: "再加一个动作，会更生动。",
      problem_monsters: ["空泛表达"],
    },
    settlement: {
      xp_delta: 25,
      level_after: 2,
      badge_code: "first_sentence_upgrade",
    },
  });
  apiMocks.createEssay.mockResolvedValue({
    essay: { id: "essay-1" },
    first_draft: {
      id: "draft-1",
      essay_id: "essay-1",
      version_label: "first_draft",
    },
    feedback: {
      strengths: ["能写清楚发生了什么"],
      improvements: [],
      problem_monsters: [],
      sentence_notes: [],
      revision_tasks: [{ instruction: "给第二段加一个动作描写", target: "第二段" }],
    },
  });
  apiMocks.submitEssayRevision.mockResolvedValue({
    revision: {
      id: "revision-1",
      completed_tasks: ["给第二段加一个动作描写"],
      skipped_tasks: [],
      duration_seconds: 10,
    },
    comparison: {
      encouragement: "你把最重要的画面写清楚了。",
      improved_dimensions: ["细节更多"],
      evidence: [],
      next_step: "继续保留动作细节。",
    },
    settlement: {
      xp_delta: 60,
      level_after: 2,
      badge_code: "first_revision",
      evidence: { completed_task_count: 1 },
    },
  });
  apiMocks.getAlphaChildSummary.mockResolvedValue({
    parent_id: "parent-1",
    child: summaryChild,
    assessment_completed: true,
    practice_counts: {
      assessments: 1,
      sentence_trainings: 1,
      essays: 1,
    },
    ability_changes: [{ ability: "expression", label: "表达力", delta: 9 }],
    recent_highlight: "孩子完成了第一次能力草图。",
    next_suggestion: "继续练习把句子写具体。",
    empty_state: null,
  });
  apiMocks.getAlphaChildren.mockResolvedValue({
    parent: { id: "parent-1", email: "demo@example.com", display_name: "演示家长" },
    children: [summaryChild],
  });
  apiMocks.recordAlphaEvent.mockResolvedValue(undefined);
  apiMocks.saveFeedbackReaction.mockResolvedValue({
    reaction: {
      id: "reaction-1",
      student_id: "s1",
      target_type: "assessment",
      target_id: "assessment-1",
      reaction: "positive",
    },
  });
  apiMocks.saveParentSummaryFeedback.mockResolvedValue({
    feedback: { usefulness: "helpful" },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("FeedbackReaction renders three child-friendly reaction buttons", () => {
  render(
    <FeedbackReaction
      studentId="s1"
      targetType="assessment"
      targetId="assessment-1"
    />,
  );

  expect(screen.getByText("这次 AI 教练的提示对你有帮助吗？")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "有帮助" })).toHaveTextContent("😊");
  expect(screen.getByRole("button", { name: "一般" })).toHaveTextContent("😐");
  expect(screen.getByRole("button", { name: "没帮助" })).toHaveTextContent("😞");
});

test("clicking a reaction saves the selected feedback reaction with alpha session id", async () => {
  render(
    <FeedbackReaction
      studentId="s1"
      targetType="sentence_training"
      targetId="training-1"
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));

  expect(apiMocks.saveFeedbackReaction).toHaveBeenCalledWith("s1", {
    target_type: "sentence_training",
    target_id: "training-1",
    reaction: "positive",
    alpha_session_id: "session-1",
  });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "有帮助" })).toHaveAttribute(
      "aria-pressed",
      "true",
    ),
  );
});

test("clicking a second reaction updates FeedbackReaction selected state", async () => {
  render(
    <FeedbackReaction
      studentId="s1"
      targetType="essay_draft"
      targetId="draft-1"
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));
  await userEvent.click(screen.getByRole("button", { name: "一般" }));

  expect(screen.getByRole("button", { name: "有帮助" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  expect(screen.getByRole("button", { name: "一般" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("FeedbackReaction save failure shows a retry message and keeps other controls usable", async () => {
  apiMocks.saveFeedbackReaction.mockRejectedValueOnce(new Error("network"));
  render(
    <div>
      <FeedbackReaction
        studentId="s1"
        targetType="assessment"
        targetId="assessment-1"
      />
      <button type="button">继续学习</button>
    </div>,
  );

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));

  expect(
    await screen.findByText("这次没有保存成功，稍后可以再点一次。"),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "继续学习" })).toBeEnabled();
});

test("ParentSummaryFeedback renders usefulness choices", () => {
  render(<ParentSummaryFeedback parentId="parent-1" studentId="s1" />);

  expect(screen.getByText("这份成长摘要对你有帮助吗？")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "有帮助" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "没帮助" })).toBeInTheDocument();
});

test("ParentSummaryFeedback posts parent summary usefulness with alpha session id", async () => {
  render(<ParentSummaryFeedback parentId="parent-1" studentId="s1" />);

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));

  expect(apiMocks.saveParentSummaryFeedback).toHaveBeenCalledWith(
    "parent-1",
    "s1",
    {
      usefulness: "not_helpful",
      alpha_session_id: "session-1",
    },
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "没帮助" })).toHaveAttribute(
      "aria-pressed",
      "true",
    ),
  );
});

test("assessment page renders a feedback reaction after assessment result with assessment id", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <AssessmentPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(await screen.findByRole("button", { name: "开始小试炼" }));
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "公园里的花红红的，风一吹就轻轻摇。",
  );
  await userEvent.click(screen.getByRole("button", { name: "继续写小作文" }));
  await userEvent.type(
    screen.getByLabelText("小写作"),
    "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "生成能力草图" }));
  await userEvent.click(await screen.findByRole("button", { name: "有帮助" }));

  expect(apiMocks.saveFeedbackReaction).toHaveBeenCalledWith("s1", {
    target_type: "assessment",
    target_id: "assessment-1",
    reaction: "positive",
    alpha_session_id: "session-1",
  });
});

test("sentence page renders a feedback reaction after sentence result with training id", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.type(await screen.findByLabelText("原句"), "公园很美。");
  await userEvent.type(screen.getByLabelText("升级后的句子"), "公园里花香很浓。");
  await userEvent.click(screen.getByRole("button", { name: "提交给 AI 教练" }));
  await userEvent.click(await screen.findByRole("button", { name: "一般" }));

  expect(apiMocks.saveFeedbackReaction).toHaveBeenCalledWith("s1", {
    target_type: "sentence_training",
    target_id: "training-1",
    reaction: "neutral",
    alpha_session_id: "session-1",
  });
});

test("essay page renders draft and revision feedback reactions with persisted ids", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.type(await screen.findByLabelText("作文题目"), "我学会了骑车");
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
  );
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  await userEvent.click(await screen.findByRole("button", { name: "有帮助" }));

  expect(apiMocks.saveFeedbackReaction).toHaveBeenCalledWith("s1", {
    target_type: "essay_draft",
    target_id: "draft-1",
    reaction: "positive",
    alpha_session_id: "session-1",
  });

  await userEvent.type(
    screen.getByLabelText("二稿"),
    "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "提交二稿" }));
  const comparison = await screen.findByLabelText("二稿对比");
  await userEvent.click(
    within(comparison).getByRole("button", { name: "没帮助" }),
  );

  expect(apiMocks.saveFeedbackReaction).toHaveBeenCalledWith("s1", {
    target_type: "essay_revision",
    target_id: "revision-1",
    reaction: "negative",
    alpha_session_id: "session-1",
  });
});

test("summary page renders parent feedback after summary loads", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <ParentChildSummaryPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByText("这份成长摘要对你有帮助吗？")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));

  expect(apiMocks.saveParentSummaryFeedback).toHaveBeenCalledWith(
    "parent-1",
    "s1",
    {
      usefulness: "helpful",
      alpha_session_id: "session-1",
    },
  );
});
