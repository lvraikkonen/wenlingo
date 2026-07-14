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
import EssayPage from "../src/app/children/[studentId]/essay/page";
import ReadingPage from "../src/app/children/[studentId]/reading/page";
import { ReportPageContent } from "../src/app/parent/[studentId]/report/page";

const apiMocks = vi.hoisted(() => ({
  createEssay: vi.fn(),
  fetchEssayFeedbackResult: vi.fn(),
  fetchChildEssayArchive: vi.fn(),
  fetchEssayArchiveDetail: vi.fn(),
  hideChildEssay: vi.fn(),
  streamEssayFeedback: vi.fn(),
  submitEssayRevision: vi.fn(),
  createReadingSession: vi.fn(),
  createReport: vi.fn(),
}));

const essayFeedbackResponse = {
  essay: { id: "e1" },
  first_draft: { id: "draft-1" },
  feedback: {
    strengths: ["能写清楚发生了什么", "有一处心情表达"],
    revision_tasks: [
      { instruction: "给第二段加一个动作描写", target: "第二段" },
    ],
  },
};

vi.mock("../src/lib/api", () => ({
  createEssay: apiMocks.createEssay,
  fetchEssayFeedbackResult: apiMocks.fetchEssayFeedbackResult,
  fetchChildEssayArchive: apiMocks.fetchChildEssayArchive,
  fetchEssayArchiveDetail: apiMocks.fetchEssayArchiveDetail,
  hideChildEssay: apiMocks.hideChildEssay,
  streamEssayFeedback: apiMocks.streamEssayFeedback,
  submitEssayRevision: apiMocks.submitEssayRevision,
  createReadingSession: apiMocks.createReadingSession,
  createReport: apiMocks.createReport,
}));

beforeEach(() => {
  delete process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED;
  apiMocks.createEssay.mockResolvedValue(essayFeedbackResponse);
  apiMocks.fetchEssayFeedbackResult.mockResolvedValue(essayFeedbackResponse);
  apiMocks.submitEssayRevision.mockResolvedValue({
    revision: {
      id: "revision-1",
      completed_tasks: ["给第二段加一个动作描写"],
      skipped_tasks: [],
      duration_seconds: 120,
      reaction: null,
    },
    comparison: {
      encouragement: "你把最重要的画面写清楚了。",
      improved_dimensions: ["细节更多", "动作更具体"],
      evidence: [],
      next_step: "继续把心理感受写出来。",
    },
    settlement: {
      xp_delta: 60,
      level_after: 2,
      badge_code: "first_revision",
      evidence: { completed_task_count: 1 },
    },
  });
  apiMocks.createReadingSession.mockResolvedValue({
    transfer_tip: "写景时可以加入声音。",
  });
  apiMocks.createReport.mockResolvedValue({
    content: {
      practice_summary: "本阶段完成了 1 次句子训练和 1 次阅读练习。",
      ability_changes: ["写具体力有新的证据"],
      best_revision: "我紧紧抓着车把，手心都出汗了。",
      weak_points: ["作文结构还需要更清楚"],
      next_suggestions: ["继续做 1 次句子加细节"],
    },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  delete process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED;
});

function expectReturnToChildrenLink() {
  expect(
    screen
      .getAllByRole("link", { name: "返回孩子列表" })
      .some((link) => link.getAttribute("href") === "/parent/children"),
  ).toBe(true);
}

test("essay page supports draft feedback and revision settlement", async () => {
  let resolveFeedback: (value: typeof essayFeedbackResponse) => void = () => {};
  const pendingFeedback = new Promise<typeof essayFeedbackResponse>((resolve) => {
    resolveFeedback = resolve;
  });
  apiMocks.createEssay.mockReturnValueOnce(pendingFeedback);

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "直接写初稿" }),
  );
  await userEvent.type(
    await screen.findByLabelText("作文题目"),
    "我学会了骑车",
  );
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
  );
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  expect(screen.getByText("AI 教练正在读你的初稿")).toBeInTheDocument();
  await act(async () => {
    resolveFeedback(essayFeedbackResponse);
    await pendingFeedback;
  });
  expect(await screen.findByText("修改小任务")).toBeInTheDocument();
  expect(await screen.findByText("给第二段加一个动作描写")).toBeInTheDocument();
  expect(
    screen.getByRole("checkbox", { name: "给第二段加一个动作描写" }),
  ).toBeChecked();
  await waitFor(() => {
    expect(screen.queryByText("AI 教练正在读你的初稿")).not.toBeInTheDocument();
  });
  expect(apiMocks.createEssay).toHaveBeenCalledWith("s1", {
    title: "我学会了骑车",
    draft: "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
    entry: "existing_draft",
    client_submission_id: expect.any(String),
  });

  await userEvent.type(
    screen.getByLabelText("下一稿"),
    "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));
  expect(
    await screen.findByText("你把最重要的画面写清楚了。"),
  ).toBeInTheDocument();
  expect(await screen.findByText("细节更多")).toBeInTheDocument();
  expect(screen.getByText("完成 1 个修改任务")).toBeInTheDocument();
  expect(apiMocks.submitEssayRevision).toHaveBeenCalledWith(
    "e1",
    expect.objectContaining({
      base_version_id: "draft-1",
      content: "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
      idempotency_key: expect.any(String),
      completed_tasks: ["给第二段加一个动作描写"],
      skipped_tasks: [],
      duration_seconds: expect.any(Number),
    }),
  );
  expect(screen.getByRole("button", { name: "提交下一稿" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));
  expect(apiMocks.submitEssayRevision).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("link", { name: "回到 Dashboard" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
  expectReturnToChildrenLink();

  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  await waitFor(() => {
    expect(apiMocks.createEssay).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("下一稿")).toHaveValue("");
  });
});

test("essay page streams direct draft previews before canonical feedback replaces them", async () => {
  process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED = "true";
  const canonicalFeedback = {
    essay: { id: "e-stream" },
    first_draft: {
      id: "draft-stream",
      essay_id: "e-stream",
      version_label: "first_draft" as const,
      reaction: null,
    },
    feedback: {
      strengths: ["最终稿优点来自保存结果"],
      improvements: ["最终稿建议来自保存结果"],
      problem_monsters: [],
      sentence_notes: ["最终句子提示"],
      revision_tasks: [
        { instruction: "最终修改任务", target: "第二段" },
      ],
    },
  };
  let resolveCanonical: (value: typeof canonicalFeedback) => void = () => {};
  const canonicalFetch = new Promise<typeof canonicalFeedback>((resolve) => {
    resolveCanonical = resolve;
  });
  apiMocks.fetchEssayFeedbackResult.mockReturnValueOnce(canonicalFetch);
  apiMocks.streamEssayFeedback.mockImplementationOnce(
    async (
      _studentId: string,
      _payload: unknown,
      onFrame: (frame: { event: string; data: Record<string, unknown> }) => void,
    ) => {
      onFrame({ event: "start", data: { seq: 1 } });
      onFrame({
        event: "feedback_section_preview",
        data: {
          seq: 2,
          section: "strengths",
          items: ["能写清楚发生了什么"],
        },
      });
      onFrame({
        event: "feedback_section_preview",
        data: {
          seq: 3,
          section: "revision_tasks",
          items: ["给第二段加一个动作描写"],
        },
      });
      onFrame({
        event: "done",
        data: { seq: 4, result: { fetch_url: "/opaque/essay-feedback/e-stream" } },
      });
    },
  );

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "直接写初稿" }),
  );
  await userEvent.type(
    await screen.findByLabelText("作文题目"),
    "我学会了骑车",
  );
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
  );
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));

  expect(await screen.findByText("能写清楚发生了什么")).toBeInTheDocument();
  expect(await screen.findByText("给第二段加一个动作描写")).toBeInTheDocument();
  expect(screen.queryByText("最终稿优点来自保存结果")).not.toBeInTheDocument();

  await act(async () => {
    resolveCanonical(canonicalFeedback);
    await canonicalFetch;
  });

  expect(await screen.findByText("最终稿优点来自保存结果")).toBeInTheDocument();
  expect(await screen.findByText("最终稿建议来自保存结果")).toBeInTheDocument();
  expect(await screen.findByText("最终句子提示")).toBeInTheDocument();
  expect(screen.getByText("最终修改任务")).toBeInTheDocument();
  const feedbackSection = screen.getByLabelText("作文点评");
  const orderedHeadings = [
    "写得好的地方",
    "可以改进的地方",
    "句子小提示",
    "修改小任务",
  ].map((heading) => within(feedbackSection).getByText(heading));
  expect(
    orderedHeadings.every((heading, index) => {
      const nextHeading = orderedHeadings[index + 1];
      return (
        !nextHeading ||
        Boolean(
          heading.compareDocumentPosition(nextHeading) &
            Node.DOCUMENT_POSITION_FOLLOWING,
        )
      );
    }),
  ).toBe(true);
  await waitFor(() => {
    expect(screen.queryByText("能写清楚发生了什么")).not.toBeInTheDocument();
    expect(screen.queryByText("给第二段加一个动作描写")).not.toBeInTheDocument();
  });
  expect(apiMocks.streamEssayFeedback).toHaveBeenCalledWith(
    "s1",
    expect.objectContaining({
      title: "我学会了骑车",
      draft: "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
      entry: "existing_draft",
      client_submission_id: expect.any(String),
    }),
    expect.any(Function),
    expect.any(Object),
  );
  expect(apiMocks.fetchEssayFeedbackResult).toHaveBeenCalledWith(
    "/opaque/essay-feedback/e-stream",
  );
  expect(apiMocks.createEssay).not.toHaveBeenCalled();
});

test("essay page streaming error before preview falls back with a fresh submission id", async () => {
  process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED = "true";
  apiMocks.streamEssayFeedback.mockRejectedValueOnce(
    new Error("stream failed before preview"),
  );

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "直接写初稿" }),
  );
  await userEvent.type(
    await screen.findByLabelText("作文题目"),
    "我学会了骑车",
  );
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
  );
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));

  expect(await screen.findByText("给第二段加一个动作描写")).toBeInTheDocument();
  expect(apiMocks.streamEssayFeedback).toHaveBeenCalledWith(
    "s1",
    expect.objectContaining({
      client_submission_id: expect.any(String),
    }),
    expect.any(Function),
    expect.any(Object),
  );
  expect(apiMocks.createEssay).toHaveBeenCalledWith("s1", {
    title: "我学会了骑车",
    draft: "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
    entry: "existing_draft",
    client_submission_id: expect.any(String),
  });
  const streamPayload = apiMocks.streamEssayFeedback.mock.calls[0]?.[1] as {
    client_submission_id: string;
  };
  const fallbackPayload = apiMocks.createEssay.mock.calls[0]?.[1] as {
    client_submission_id: string;
  };
  expect(fallbackPayload.client_submission_id).not.toBe(
    streamPayload.client_submission_id,
  );
  expect(apiMocks.fetchEssayFeedbackResult).not.toHaveBeenCalled();
});

test("essay page ignores stale streaming previews after reset", async () => {
  process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED = "true";
  let emitFrame: ((frame: { event: string; data: Record<string, unknown> }) => void) | null =
    null;
  let resolveStream: () => void = () => undefined;
  const streamRequest = new Promise<void>((resolve) => {
    resolveStream = resolve;
  });
  apiMocks.streamEssayFeedback.mockImplementationOnce(
    async (
      _studentId: string,
      _payload: unknown,
      onFrame: (frame: { event: string; data: Record<string, unknown> }) => void,
    ) => {
      emitFrame = onFrame;
      onFrame({ event: "start", data: { seq: 1 } });
      onFrame({
        event: "feedback_section_preview",
        data: {
          seq: 2,
          section: "strengths",
          items: ["当前预览点评"],
        },
      });
      await streamRequest;
    },
  );

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "直接写初稿" }),
  );
  await userEvent.type(screen.getByLabelText("作文题目"), "我学会了骑车");
  await userEvent.type(screen.getByLabelText("初稿"), "我学会了骑车。");
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));

  expect(await screen.findByText("当前预览点评")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "写新的作文" })[0]);
  expect(screen.queryByText("当前预览点评")).not.toBeInTheDocument();

  await act(async () => {
    emitFrame?.({
      event: "feedback_section_preview",
      data: {
        seq: 3,
        section: "strengths",
        items: ["过期点评不应该出现"],
      },
    });
  });

  expect(screen.queryByText("过期点评不应该出现")).not.toBeInTheDocument();
  await act(async () => {
    resolveStream();
    await streamRequest;
  });
});

test("essay page ignores stale streaming previews after switching modes", async () => {
  process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED = "true";
  let emitFrame: ((frame: { event: string; data: Record<string, unknown> }) => void) | null =
    null;
  let resolveStream: () => void = () => undefined;
  const streamRequest = new Promise<void>((resolve) => {
    resolveStream = resolve;
  });
  apiMocks.streamEssayFeedback.mockImplementationOnce(
    async (
      _studentId: string,
      _payload: unknown,
      onFrame: (frame: { event: string; data: Record<string, unknown> }) => void,
    ) => {
      emitFrame = onFrame;
      onFrame({ event: "start", data: { seq: 1 } });
      onFrame({
        event: "feedback_section_preview",
        data: {
          seq: 2,
          section: "strengths",
          items: ["切换前的预览点评"],
        },
      });
      await streamRequest;
    },
  );

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "直接写初稿" }),
  );
  await userEvent.type(screen.getByLabelText("作文题目"), "我学会了骑车");
  await userEvent.type(screen.getByLabelText("初稿"), "我学会了骑车。");
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  expect(await screen.findByText("切换前的预览点评")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "课内同步作文" }));
  expect(screen.queryByText("切换前的预览点评")).not.toBeInTheDocument();

  await act(async () => {
    emitFrame?.({
      event: "feedback_section_preview",
      data: {
        seq: 3,
        section: "strengths",
        items: ["切换模式后的过期点评"],
      },
    });
  });

  expect(screen.queryByText("切换模式后的过期点评")).not.toBeInTheDocument();
  await act(async () => {
    resolveStream();
    await streamRequest;
  });
});

test("reading page shows friendly construction state", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <ReadingPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(
    await screen.findByRole("heading", { name: "阅读峡谷施工中" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "这里还在建设。小文星球会先把今天推荐的作文和句子任务陪你做好。",
    ),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到小文星球" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
  expect(screen.getByRole("link", { name: "去完成今日推荐" })).toHaveAttribute(
    "href",
    "/children/s1/sentence",
  );
  expect(screen.getByRole("link", { name: "回到 Dashboard" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
  expectReturnToChildrenLink();
  expect(apiMocks.createReadingSession).not.toHaveBeenCalled();
});

test("report page renders parent-safe stage report", async () => {
  render(<ReportPageContent studentId="s1" />);

  expect(
    await screen.findByText("本阶段完成了 1 次句子训练和 1 次阅读练习。"),
  ).toBeInTheDocument();
  expect(screen.getByText("继续做 1 次句子加细节")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "回到当前孩子 Dashboard" }),
  ).toHaveAttribute("href", "/children/s1");
  expectReturnToChildrenLink();
  expect(apiMocks.createReport).toHaveBeenCalledWith("s1");
});
