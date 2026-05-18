import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Suspense } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import EssayPage from "../src/app/children/[studentId]/essay/page";
import ReadingPage from "../src/app/children/[studentId]/reading/page";
import ReportPage from "../src/app/parent/[studentId]/report/page";

const apiMocks = vi.hoisted(() => ({
  createEssay: vi.fn(),
  submitEssayRevision: vi.fn(),
  createReadingSession: vi.fn(),
  createReport: vi.fn(),
}));

const essayFeedbackResponse = {
  essay: { id: "e1" },
  feedback: {
    strengths: ["能写清楚发生了什么", "有一处心情表达"],
    revision_tasks: [
      { instruction: "给第二段加一个动作描写", target: "第二段" },
    ],
  },
};

vi.mock("../src/lib/api", () => ({
  createEssay: apiMocks.createEssay,
  submitEssayRevision: apiMocks.submitEssayRevision,
  createReadingSession: apiMocks.createReadingSession,
  createReport: apiMocks.createReport,
}));

beforeEach(() => {
  apiMocks.createEssay.mockResolvedValue(essayFeedbackResponse);
  apiMocks.submitEssayRevision.mockResolvedValue({
    comparison: {
      encouragement: "你把最重要的画面写清楚了。",
      improved_dimensions: ["细节更多", "动作更具体"],
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
});

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
  });

  await userEvent.type(
    screen.getByLabelText("二稿"),
    "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "提交二稿" }));
  expect(
    await screen.findByText("你把最重要的画面写清楚了。"),
  ).toBeInTheDocument();
  expect(await screen.findByText("细节更多")).toBeInTheDocument();
  expect(screen.getByText("完成 1 个修改任务")).toBeInTheDocument();
  expect(apiMocks.submitEssayRevision).toHaveBeenCalledWith(
    "e1",
    expect.objectContaining({
      content: "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
      completed_tasks: ["给第二段加一个动作描写"],
      skipped_tasks: [],
      duration_seconds: expect.any(Number),
    }),
  );
  expect(screen.getByRole("button", { name: "提交二稿" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "提交二稿" }));
  expect(apiMocks.submitEssayRevision).toHaveBeenCalledTimes(1);

  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  await waitFor(() => {
    expect(apiMocks.createEssay).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("二稿")).toHaveValue("");
  });
});

test("reading page shows transfer tip", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <ReadingPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  const mainIdeaControl = await screen.findByLabelText("主要内容");
  await userEvent.clear(mainIdeaControl);
  await userEvent.type(mainIdeaControl, "小河和小鸟都在唱春天。");
  await userEvent.clear(screen.getByLabelText("文中细节"));
  await userEvent.type(screen.getByLabelText("文中细节"), "小鸟在枝头叫。");
  await userEvent.clear(screen.getByLabelText("迁移练习"));
  await userEvent.type(screen.getByLabelText("迁移练习"), "写校园也可以写声音。");
  await userEvent.click(screen.getByRole("button", { name: "提交阅读答案" }));

  expect(await screen.findByText("写景时可以加入声音。")).toBeInTheDocument();
  expect(apiMocks.createReadingSession).toHaveBeenCalledWith("s1", {
    main_idea: "小河和小鸟都在唱春天。",
    detail: "小鸟在枝头叫。",
    transfer: "写校园也可以写声音。",
  });
});

test("report page renders parent-safe stage report", async () => {
  render(await ReportPage({ params: Promise.resolve({ studentId: "s1" }) }));

  expect(
    await screen.findByText("本阶段完成了 1 次句子训练和 1 次阅读练习。"),
  ).toBeInTheDocument();
  expect(screen.getByText("继续做 1 次句子加细节")).toBeInTheDocument();
  expect(apiMocks.createReport).toHaveBeenCalledWith("s1");
});
