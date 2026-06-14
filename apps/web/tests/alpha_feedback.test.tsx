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
import { ALPHA_SESSION_STORAGE_KEY } from "../src/lib/alphaSession";
import { ApiRequestError } from "../src/lib/api";
import { useAssessmentRecommendation } from "../src/lib/useAssessmentRecommendation";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });

  return { promise, resolve, reject };
}

function AssessmentRecommendationProbe({ studentId }: { studentId: string }) {
  const {
    shouldShowAssessmentRecommendation,
    dismissAssessmentRecommendation,
  } = useAssessmentRecommendation(studentId);

  return (
    <div>
      <p>
        {shouldShowAssessmentRecommendation
          ? `recommendation shown for ${studentId}`
          : `recommendation hidden for ${studentId}`}
      </p>
      <button type="button" onClick={dismissAssessmentRecommendation}>
        dismiss recommendation
      </button>
    </div>
  );
}

const apiMocks = vi.hoisted(() => ({
  createAssessment: vi.fn(),
  createSentenceChallenge: vi.fn(),
  completeSentenceChallenge: vi.fn(),
  createSentenceTraining: vi.fn(),
  createEssay: vi.fn(),
  submitEssayRevision: vi.fn(),
  demoLogin: vi.fn(),
  getAlphaChildren: vi.fn(),
  getDashboard: vi.fn(),
  getMyAlphaChildSummary: vi.fn(),
  recordAlphaEvent: vi.fn(async () => undefined),
  saveFeedbackReaction: vi.fn(),
  saveMyParentSummaryFeedback: vi.fn(),
}));

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("../src/lib/api", () => ({
  ApiRequestError: class ApiRequestError extends Error {
    status: number;

    constructor(status: number) {
      super(`Request failed: ${status}`);
      this.name = "ApiRequestError";
      this.status = status;
    }
  },
  createAssessment: apiMocks.createAssessment,
  createSentenceChallenge: apiMocks.createSentenceChallenge,
  completeSentenceChallenge: apiMocks.completeSentenceChallenge,
  createSentenceTraining: apiMocks.createSentenceTraining,
  createEssay: apiMocks.createEssay,
  submitEssayRevision: apiMocks.submitEssayRevision,
  demoLogin: apiMocks.demoLogin,
  getAlphaChildren: apiMocks.getAlphaChildren,
  getDashboard: apiMocks.getDashboard,
  getMyAlphaChildSummary: apiMocks.getMyAlphaChildSummary,
  isUnauthorizedError: (error: unknown) =>
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    error.status === 401,
  recordAlphaEvent: apiMocks.recordAlphaEvent,
  saveFeedbackReaction: apiMocks.saveFeedbackReaction,
  saveMyParentSummaryFeedback: apiMocks.saveMyParentSummaryFeedback,
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

const challengeResponse = {
  challenge: {
    id: "training-1",
    source_sentence: "小猫跑了。",
    challenge_prompt: "请把句子写具体，加上动作和样子。",
    hint: "可以写小猫怎么跑、跑到哪里、看起来怎么样。",
    focus: "动作描写",
    target_skill: "action_expression",
    difficulty_label: "四年级基础",
    grade_label: "四年级",
  },
};

const existingFreeInputResponse = {
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
};

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
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
  apiMocks.createSentenceChallenge.mockResolvedValue(challengeResponse);
  apiMocks.completeSentenceChallenge.mockResolvedValue({
    training: { id: "training-1" },
    feedback: {
      encouragement: "你写得很有画面感！",
      highlight: "你加上了飞快地冲过去，动作更清楚了。",
      suggestion: "还可以加一点表情或心情。",
      example_upgrade: "小狗瞪大眼睛，飞快地冲过草地。",
    },
    settlement: { xp_delta: 25, level_after: 2 },
    next_task: { kind: "sentence", title: "再练一句", focus: "动作描写", minutes: "5" },
  });
  apiMocks.createSentenceTraining.mockResolvedValue(existingFreeInputResponse);
  apiMocks.getDashboard.mockResolvedValue({
    student: {
      id: "s1",
      name: "小星",
      grade_label: "四年级",
      persona: "real_child",
      level: 1,
      xp: 0,
    },
    ability_note: "等待入门小试点",
    assessment_completed: false,
    assessment_recommended: true,
    child_abilities: {
      reading_power: 40,
      specific_writing_power: 40,
      revision_power: 40,
    },
    today_tasks: {
      main: {
        kind: "assessment",
        title: "入门小试炼",
        focus: "第一张能力草图",
        minutes: "3-5",
      },
      quick: {
        kind: "sentence",
        title: "句子工坊",
        focus: "加细节",
        minutes: "5-8",
      },
    },
    map: ["句子工坊", "作文城堡", "阅读峡谷"],
    coach_message: "今天先完成推荐任务，再看看哪里变强了。",
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
  apiMocks.demoLogin.mockResolvedValue({
    parent: {
      id: "parent-1",
      email: "demo@example.com",
      display_name: "演示家长",
    },
    students: [summaryChild],
  });
  apiMocks.getMyAlphaChildSummary.mockResolvedValue({
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
  apiMocks.saveMyParentSummaryFeedback.mockResolvedValue({
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

test("FeedbackReaction initializes selected state from persisted reaction", () => {
  render(
    <FeedbackReaction
      studentId="s1"
      targetType="assessment"
      targetId="assessment-1"
      initialReaction="neutral"
    />,
  );

  expect(screen.getByRole("button", { name: "一般" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("button", { name: "有帮助" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("FeedbackReaction disables buttons while saving and ignores rapid clicks", async () => {
  const save = deferred<Awaited<ReturnType<typeof apiMocks.saveFeedbackReaction>>>();
  apiMocks.saveFeedbackReaction.mockReturnValueOnce(save.promise);
  render(
    <FeedbackReaction
      studentId="s1"
      targetType="assessment"
      targetId="assessment-1"
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));

  expect(screen.getByRole("button", { name: "有帮助" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "一般" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "一般" }));
  expect(apiMocks.saveFeedbackReaction).toHaveBeenCalledTimes(1);

  save.resolve({
    reaction: {
      id: "reaction-1",
      student_id: "s1",
      target_type: "assessment",
      target_id: "assessment-1",
      reaction: "positive",
    },
  });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "有帮助" })).toBeEnabled(),
  );
});

test("FeedbackReaction save failure reverts to last confirmed reaction", async () => {
  apiMocks.saveFeedbackReaction
    .mockResolvedValueOnce({
      reaction: {
        id: "reaction-1",
        student_id: "s1",
        target_type: "assessment",
        target_id: "assessment-1",
        reaction: "neutral",
      },
    })
    .mockRejectedValueOnce(new Error("network"));
  render(
    <FeedbackReaction
      studentId="s1"
      targetType="assessment"
      targetId="assessment-1"
      initialReaction="positive"
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "一般" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "一般" })).toHaveAttribute(
      "aria-pressed",
      "true",
    ),
  );

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));

  expect(
    await screen.findByText("这次没有保存成功，稍后可以再点一次。"),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "一般" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("button", { name: "没帮助" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("FeedbackReaction resets on target change and ignores stale save completions", async () => {
  const firstSave = deferred<Awaited<ReturnType<typeof apiMocks.saveFeedbackReaction>>>();
  apiMocks.saveFeedbackReaction.mockReturnValueOnce(firstSave.promise);
  const { rerender } = render(
    <FeedbackReaction
      studentId="s1"
      targetType="assessment"
      targetId="assessment-1"
      initialReaction={null}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));
  expect(screen.getByRole("button", { name: "有帮助" })).toBeDisabled();

  rerender(
    <FeedbackReaction
      studentId="s1"
      targetType="assessment"
      targetId="assessment-2"
      initialReaction="negative"
    />,
  );

  expect(screen.getByRole("button", { name: "没帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("button", { name: "有帮助" })).toBeEnabled();

  firstSave.resolve({
    reaction: {
      id: "reaction-1",
      student_id: "s1",
      target_type: "assessment",
      target_id: "assessment-1",
      reaction: "positive",
    },
  });
  apiMocks.saveFeedbackReaction.mockRejectedValueOnce(new Error("network"));

  await userEvent.click(screen.getByRole("button", { name: "一般" }));

  expect(
    await screen.findByText("这次没有保存成功，稍后可以再点一次。"),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "没帮助" })).toHaveAttribute(
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
  expect(screen.getByRole("alert")).toHaveTextContent(
    "这次没有保存成功，稍后可以再点一次。",
  );
  expect(screen.getByRole("button", { name: "继续学习" })).toBeEnabled();
});

test("ParentSummaryFeedback renders usefulness choices", () => {
  render(<ParentSummaryFeedback parentId="parent-1" studentId="s1" />);

  expect(screen.getByText("这份成长摘要对你有帮助吗？")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "有帮助" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "没帮助" })).toBeInTheDocument();
});

test("ParentSummaryFeedback initializes selected state from persisted usefulness", () => {
  render(
    <ParentSummaryFeedback
      parentId="parent-1"
      studentId="s1"
      initialUsefulness="not_helpful"
    />,
  );

  expect(screen.getByRole("button", { name: "没帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("button", { name: "有帮助" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("ParentSummaryFeedback disables buttons while saving and ignores rapid clicks", async () => {
  const save = deferred<Awaited<ReturnType<typeof apiMocks.saveMyParentSummaryFeedback>>>();
  apiMocks.saveMyParentSummaryFeedback.mockReturnValueOnce(save.promise);
  render(<ParentSummaryFeedback parentId="parent-1" studentId="s1" />);

  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));

  expect(screen.getByRole("button", { name: "有帮助" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "没帮助" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));
  expect(apiMocks.saveMyParentSummaryFeedback).toHaveBeenCalledTimes(1);

  save.resolve({ feedback: { usefulness: "helpful" } });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "有帮助" })).toBeEnabled(),
  );
});

test("ParentSummaryFeedback save failure reverts to last confirmed usefulness", async () => {
  apiMocks.saveMyParentSummaryFeedback
    .mockResolvedValueOnce({ feedback: { usefulness: "not_helpful" } })
    .mockRejectedValueOnce(new Error("network"));
  render(
    <ParentSummaryFeedback
      parentId="parent-1"
      studentId="s1"
      initialUsefulness="helpful"
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "没帮助" })).toHaveAttribute(
      "aria-pressed",
      "true",
    ),
  );

  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));

  expect(await screen.findByText("反馈没有保存成功，请稍后再试。")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "反馈没有保存成功，请稍后再试。",
  );
  expect(screen.getByRole("button", { name: "没帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("button", { name: "有帮助" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("ParentSummaryFeedback resets on parent change and ignores stale save completions", async () => {
  const firstSave = deferred<Awaited<ReturnType<typeof apiMocks.saveMyParentSummaryFeedback>>>();
  apiMocks.saveMyParentSummaryFeedback.mockReturnValueOnce(firstSave.promise);
  const { rerender } = render(
    <ParentSummaryFeedback
      parentId="parent-1"
      studentId="s1"
      initialUsefulness="helpful"
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));
  expect(screen.getByRole("button", { name: "有帮助" })).toBeDisabled();

  rerender(
    <ParentSummaryFeedback
      parentId="parent-2"
      studentId="s1"
      initialUsefulness="helpful"
    />,
  );

  expect(screen.getByRole("button", { name: "有帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("button", { name: "没帮助" })).toBeEnabled();

  firstSave.resolve({ feedback: { usefulness: "not_helpful" } });
  apiMocks.saveMyParentSummaryFeedback.mockRejectedValueOnce(new Error("network"));

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));

  expect(await screen.findByText("反馈没有保存成功，请稍后再试。")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "有帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("ParentSummaryFeedback posts parent summary usefulness with alpha session id", async () => {
  render(<ParentSummaryFeedback parentId="parent-1" studentId="s1" />);

  await userEvent.click(screen.getByRole("button", { name: "没帮助" }));

  expect(apiMocks.saveMyParentSummaryFeedback).toHaveBeenCalledWith(
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

test("ParentSummaryFeedback redirects to alpha start when save is unauthorized", async () => {
  apiMocks.saveMyParentSummaryFeedback.mockRejectedValueOnce({ status: 401 });
  render(<ParentSummaryFeedback parentId="parent-1" studentId="s1" />);

  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));

  await waitFor(() => expect(replace).toHaveBeenCalledWith("/alpha/start"));
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

test("assessment page passes persisted reaction from assessment response", async () => {
  apiMocks.createAssessment.mockResolvedValueOnce({
    assessment: {
      id: "assessment-1",
      summary: "完成入门小试炼，生成第一张能力草图。",
      sentence_training_id: "sentence-training-1",
      essay_id: "essay-1",
      reaction: "negative",
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

  expect(await screen.findByRole("button", { name: "没帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("assessment page ignores stale assessment completion after student route changes", async () => {
  const assessment = deferred<Awaited<ReturnType<typeof apiMocks.createAssessment>>>();
  apiMocks.createAssessment.mockReturnValueOnce(assessment.promise);
  let rerender!: ReturnType<typeof render>["rerender"];
  await act(async () => {
    ({ rerender } = render(
      <Suspense fallback={null}>
        <AssessmentPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    ));
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

  await act(async () => {
    rerender(
      <Suspense fallback={null}>
        <AssessmentPage params={Promise.resolve({ studentId: "s2" })} />
      </Suspense>,
    );
  });

  await act(async () => {
    assessment.resolve({
      assessment: {
        id: "assessment-old",
        summary: "旧孩子的能力草图。",
        sentence_training_id: "sentence-training-old",
        essay_id: "essay-old",
        reaction: "positive",
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
  });

  expect(screen.queryByText("旧孩子的能力草图。")).not.toBeInTheDocument();
  expect(screen.queryByText("第一张能力草图")).not.toBeInTheDocument();
  expect(screen.queryByText("这次 AI 教练的提示对你有帮助吗？")).not.toBeInTheDocument();
});

test("sentence page loads an ai challenge by default", async () => {
  apiMocks.createSentenceChallenge.mockResolvedValueOnce({
    challenge: {
      id: "training-1",
      source_sentence: "小猫跑了。",
      challenge_prompt: "请把句子写具体，加上动作和样子。",
      hint: "可以写小猫怎么跑、跑到哪里、看起来怎么样。",
      focus: "动作描写",
      target_skill: "action_expression",
      difficulty_label: "四年级基础",
      grade_label: "四年级",
    },
  });

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByText("小猫跑了。")).toBeInTheDocument();
  expect(screen.getByText("请把句子写具体，加上动作和样子。")).toBeInTheDocument();
  expect(
    screen.getByText("可以写小猫怎么跑、跑到哪里、看起来怎么样。"),
  ).toBeInTheDocument();
  expect(apiMocks.createSentenceTraining).not.toHaveBeenCalled();
});

test("sentence page recommends initial assessment but allows continuing practice", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByText("先点亮第一张能力草图")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "先去小试炼" })).toHaveAttribute(
    "href",
    "/children/s1/assessment",
  );

  await userEvent.click(screen.getByRole("button", { name: "今天先练句子" }));

  await waitFor(() =>
    expect(screen.queryByText("先点亮第一张能力草图")).not.toBeInTheDocument(),
  );
  expect(await screen.findByText("小猫跑了。")).toBeInTheDocument();
});

test("sentence page hides assessment recommendation after assessment completion", async () => {
  apiMocks.getDashboard.mockResolvedValueOnce({
    student: {
      id: "s1",
      name: "小星",
      grade_label: "四年级",
      persona: "real_child",
      level: 1,
      xp: 0,
    },
    ability_note: "第一张能力草图",
    assessment_completed: true,
    assessment_recommended: false,
    child_abilities: {
      reading_power: 40,
      specific_writing_power: 46,
      revision_power: 40,
    },
    today_tasks: {
      main: {
        kind: "essay",
        title: "作文城堡",
        focus: "把细节写具体",
        minutes: "10-15",
      },
      quick: {
        kind: "sentence",
        title: "句子工坊",
        focus: "加细节",
        minutes: "5-8",
      },
    },
    map: ["句子工坊", "作文城堡", "阅读峡谷"],
    coach_message: "今天先完成推荐任务，再看看哪里变强了。",
  });

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByText("小猫跑了。")).toBeInTheDocument();
  expect(screen.queryByText("先点亮第一张能力草图")).not.toBeInTheDocument();
});

test("assessment recommendation dismissal resets when student id changes", async () => {
  const { rerender } = render(<AssessmentRecommendationProbe studentId="s1" />);

  expect(
    await screen.findByText("recommendation shown for s1"),
  ).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "dismiss recommendation" }));
  await waitFor(() =>
    expect(screen.getByText("recommendation hidden for s1")).toBeInTheDocument(),
  );

  rerender(<AssessmentRecommendationProbe studentId="s2" />);
  expect(
    await screen.findByText("recommendation shown for s2"),
  ).toBeInTheDocument();

  rerender(<AssessmentRecommendationProbe studentId="s1" />);
  expect(
    await screen.findByText("recommendation shown for s1"),
  ).toBeInTheDocument();
});

test("sentence page completes generated challenge and shows short feedback", async () => {
  apiMocks.createSentenceChallenge.mockResolvedValueOnce(challengeResponse);
  apiMocks.completeSentenceChallenge.mockResolvedValueOnce({
    training: { id: "training-1" },
    feedback: {
      encouragement: "你写得很有画面感！",
      highlight: "你加上了飞快地冲过去，动作更清楚了。",
      suggestion: "还可以加一点表情或心情。",
      example_upgrade: "小狗瞪大眼睛，飞快地冲过草地。",
    },
    settlement: { xp_delta: 25, level_after: 2 },
    next_task: { kind: "sentence", title: "再练一句", focus: "动作描写", minutes: "5" },
  });

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.type(
    await screen.findByLabelText("升级后的句子"),
    "小猫瞪大眼睛，飞快地跑过草地。",
  );
  await userEvent.click(screen.getByRole("button", { name: /提交给 AI 教练/ }));

  expect(apiMocks.completeSentenceChallenge).toHaveBeenCalledWith("s1", "training-1", {
    upgraded_sentence: "小猫瞪大眼睛，飞快地跑过草地。",
  });
  expect(await screen.findByText("你写得很有画面感！")).toBeInTheDocument();
  expect(screen.getByText("小狗瞪大眼睛，飞快地冲过草地。")).toBeInTheDocument();
});

test("sentence page daily limit response shows rest message", async () => {
  apiMocks.createSentenceChallenge.mockRejectedValueOnce(new ApiRequestError(429));

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(
    await screen.findByText("今天的句子挑战已经完成很多啦，休息一下，明天继续闯关！"),
  ).toBeInTheDocument();
});

test("sentence page keeps bring your own sentence mode", async () => {
  apiMocks.createSentenceChallenge.mockResolvedValueOnce(challengeResponse);
  apiMocks.createSentenceTraining.mockResolvedValueOnce(existingFreeInputResponse);

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(await screen.findByRole("button", { name: "自己带句子来练" }));
  await userEvent.type(screen.getByLabelText("原句"), "公园很美。");
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "清晨的公园里，荷叶上的水珠一闪一闪。",
  );
  await userEvent.click(screen.getByRole("button", { name: /提交给 AI 教练/ }));

  expect(apiMocks.createSentenceTraining).toHaveBeenCalled();
});

test("sentence page renders a feedback reaction after sentence result with training id", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(await screen.findByRole("button", { name: "自己带句子来练" }));
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

test("sentence page passes persisted reaction from sentence response", async () => {
  apiMocks.createSentenceTraining.mockResolvedValueOnce({
    training: { id: "training-1", reaction: "neutral" },
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
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(await screen.findByRole("button", { name: "自己带句子来练" }));
  await userEvent.type(await screen.findByLabelText("原句"), "公园很美。");
  await userEvent.type(screen.getByLabelText("升级后的句子"), "公园里花香很浓。");
  await userEvent.click(screen.getByRole("button", { name: "提交给 AI 教练" }));

  expect(await screen.findByRole("button", { name: "一般" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("sentence page ignores stale sentence completion after student route changes", async () => {
  const training = deferred<Awaited<ReturnType<typeof apiMocks.createSentenceTraining>>>();
  apiMocks.createSentenceTraining.mockReturnValueOnce(training.promise);
  let rerender!: ReturnType<typeof render>["rerender"];
  await act(async () => {
    ({ rerender } = render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    ));
  });

  await userEvent.click(await screen.findByRole("button", { name: "自己带句子来练" }));
  await userEvent.type(await screen.findByLabelText("原句"), "公园很美。");
  await userEvent.type(screen.getByLabelText("升级后的句子"), "公园里花香很浓。");
  await userEvent.click(screen.getByRole("button", { name: "提交给 AI 教练" }));

  await act(async () => {
    rerender(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s2" })} />
      </Suspense>,
    );
  });

  await act(async () => {
    training.resolve({
      training: { id: "training-old", reaction: "positive" },
      feedback: {
        encouragement: "旧孩子的句子反馈。",
        specific_improvement: "旧反馈不应该出现",
        next_step: "继续练习。",
        problem_monsters: ["空泛表达"],
      },
      settlement: {
        xp_delta: 25,
        level_after: 2,
        badge_code: "first_sentence_upgrade",
      },
    });
  });

  expect(screen.queryByText("旧孩子的句子反馈。")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("AI 教练反馈")).not.toBeInTheDocument();
  expect(screen.queryByText("这次 AI 教练的提示对你有帮助吗？")).not.toBeInTheDocument();
});

test("essay page recommends initial assessment but allows continuing writing", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByText("先点亮第一张能力草图")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "先去小试炼" })).toHaveAttribute(
    "href",
    "/children/s1/assessment",
  );

  await userEvent.click(screen.getByRole("button", { name: "今天先写作文" }));

  await waitFor(() =>
    expect(screen.queryByText("先点亮第一张能力草图")).not.toBeInTheDocument(),
  );
  expect(screen.getByLabelText("作文题目")).toBeInTheDocument();
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

test("essay page passes persisted reactions from draft and revision responses", async () => {
  apiMocks.createEssay.mockResolvedValueOnce({
    essay: { id: "essay-1" },
    first_draft: {
      id: "draft-1",
      essay_id: "essay-1",
      version_label: "first_draft",
      reaction: "positive",
    },
    feedback: {
      strengths: ["能写清楚发生了什么"],
      improvements: [],
      problem_monsters: [],
      sentence_notes: [],
      revision_tasks: [{ instruction: "给第二段加一个动作描写", target: "第二段" }],
    },
  });
  apiMocks.submitEssayRevision.mockResolvedValueOnce({
    revision: {
      id: "revision-1",
      completed_tasks: ["给第二段加一个动作描写"],
      skipped_tasks: [],
      duration_seconds: 10,
      reaction: "negative",
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

  const draftFeedback = await screen.findByLabelText("AI 教练反馈评价");
  expect(
    within(draftFeedback).getByRole("button", { name: "有帮助" }),
  ).toHaveAttribute("aria-pressed", "true");

  await userEvent.type(
    screen.getByLabelText("二稿"),
    "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "提交二稿" }));

  const comparison = await screen.findByLabelText("二稿对比");
  expect(
    within(comparison).getByRole("button", { name: "没帮助" }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("essay page ignores stale draft feedback after student route changes", async () => {
  const essay = deferred<Awaited<ReturnType<typeof apiMocks.createEssay>>>();
  apiMocks.createEssay.mockReturnValueOnce(essay.promise);
  let rerender!: ReturnType<typeof render>["rerender"];
  await act(async () => {
    ({ rerender } = render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    ));
  });

  await userEvent.type(await screen.findByLabelText("作文题目"), "我学会了骑车");
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
  );
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));

  await act(async () => {
    rerender(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s2" })} />
      </Suspense>,
    );
  });

  await act(async () => {
    essay.resolve({
      essay: { id: "essay-old" },
      first_draft: {
        id: "draft-old",
        essay_id: "essay-old",
        version_label: "first_draft",
        reaction: "positive",
      },
      feedback: {
        strengths: ["旧孩子的作文点评。"],
        improvements: [],
        problem_monsters: [],
        sentence_notes: [],
        revision_tasks: [{ instruction: "旧任务", target: "第二段" }],
      },
    });
  });

  expect(screen.queryByText("作文点评")).not.toBeInTheDocument();
  expect(screen.queryByText("旧孩子的作文点评。")).not.toBeInTheDocument();
  expect(screen.queryByText("这次 AI 教练的提示对你有帮助吗？")).not.toBeInTheDocument();
});

test("essay page ignores stale revision comparison after student route changes", async () => {
  const revision = deferred<Awaited<ReturnType<typeof apiMocks.submitEssayRevision>>>();
  apiMocks.submitEssayRevision.mockReturnValueOnce(revision.promise);
  let rerender!: ReturnType<typeof render>["rerender"];
  await act(async () => {
    ({ rerender } = render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    ));
  });

  await userEvent.type(await screen.findByLabelText("作文题目"), "我学会了骑车");
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
  );
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  await screen.findByText("作文点评");

  await userEvent.type(
    screen.getByLabelText("二稿"),
    "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "提交二稿" }));

  await act(async () => {
    rerender(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s2" })} />
      </Suspense>,
    );
  });

  await act(async () => {
    revision.resolve({
      revision: {
        id: "revision-old",
        completed_tasks: ["给第二段加一个动作描写"],
        skipped_tasks: [],
        duration_seconds: 10,
        reaction: "negative",
      },
      comparison: {
        encouragement: "旧孩子的二稿对比。",
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
  });

  expect(screen.queryByLabelText("二稿对比")).not.toBeInTheDocument();
  expect(screen.queryByText("旧孩子的二稿对比。")).not.toBeInTheDocument();
  expect(screen.queryByText("这次 AI 教练的提示对你有帮助吗？")).not.toBeInTheDocument();
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

  expect(apiMocks.saveMyParentSummaryFeedback).toHaveBeenCalledWith(
    "s1",
    {
      usefulness: "helpful",
      alpha_session_id: "session-1",
    },
  );
});

test("summary page passes persisted usefulness from summary response", async () => {
  apiMocks.getMyAlphaChildSummary.mockResolvedValue({
    parent_id: "parent-1",
    child: summaryChild,
    usefulness: "not_helpful",
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
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <ParentChildSummaryPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByRole("button", { name: "没帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("summary page clears previous child feedback while a new child summary loads", async () => {
  const secondSummary = deferred<Awaited<ReturnType<typeof apiMocks.getMyAlphaChildSummary>>>();
  apiMocks.getMyAlphaChildSummary
    .mockResolvedValueOnce({
      parent_id: "parent-1",
      child: summaryChild,
      usefulness: "helpful",
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
    })
    .mockReturnValueOnce(secondSummary.promise);
  let rerender!: ReturnType<typeof render>["rerender"];
  await act(async () => {
    ({ rerender } = render(
      <Suspense fallback={null}>
        <ParentChildSummaryPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    ));
  });

  expect(await screen.findByRole("button", { name: "有帮助" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await act(async () => {
    rerender(
      <Suspense fallback={null}>
        <ParentChildSummaryPage params={Promise.resolve({ studentId: "s2" })} />
      </Suspense>,
    );
  });

  await waitFor(() =>
    expect(apiMocks.getMyAlphaChildSummary).toHaveBeenLastCalledWith("s2"),
  );
  expect(screen.getByRole("status")).toHaveTextContent("正在加载成长摘要...");
  expect(screen.queryByText("这份成长摘要对你有帮助吗？")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "有帮助" })).not.toBeInTheDocument();

  secondSummary.resolve({
    parent_id: "parent-1",
    child: {
      ...summaryChild,
      id: "s2",
      nickname: "小月",
      name: "小月",
    },
    usefulness: "not_helpful",
    assessment_completed: true,
    practice_counts: {
      assessments: 1,
      sentence_trainings: 1,
      essays: 1,
    },
    ability_changes: [{ ability: "expression", label: "表达力", delta: 3 }],
    recent_highlight: "新孩子的成长摘要。",
    next_suggestion: "继续练习。",
    empty_state: null,
  });

  expect(await screen.findByText("小月的成长摘要")).toBeInTheDocument();
});
