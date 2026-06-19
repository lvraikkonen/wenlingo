import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Suspense } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import AssessmentPage from "../src/app/children/[studentId]/assessment/page";
import SentencePage from "../src/app/children/[studentId]/sentence/page";

const apiMocks = vi.hoisted(() => ({
  createAssessment: vi.fn(),
  createSentenceChallenge: vi.fn(),
  completeSentenceChallenge: vi.fn(),
  createSentenceTraining: vi.fn(),
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
}));

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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });

  return { promise, resolve, reject };
}

beforeEach(() => {
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
    next_task: {
      kind: "sentence",
      title: "再练一句",
      focus: "动作描写",
      minutes: "5",
    },
  });
  apiMocks.createSentenceTraining.mockResolvedValue({
    training: { id: "sentence-training-1" },
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
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function expectReturnToChildrenLink() {
  expect(
    screen
      .getAllByRole("link", { name: "返回孩子列表" })
      .some((link) => link.getAttribute("href") === "/parent/children"),
  ).toBe(true);
}

test("assessment page renders four steps and submits all fields once", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <AssessmentPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(
    await screen.findByRole("heading", { name: "认识你的写作超能力" }),
  ).toBeInTheDocument();
  expect(screen.getByText("约 3-5 分钟")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到 Dashboard" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
  expectReturnToChildrenLink();

  await userEvent.click(screen.getByRole("button", { name: "开始小试炼" }));

  expect(screen.getByText("公园很美。")).toBeInTheDocument();
  expect(screen.queryByLabelText("升级前的句子")).not.toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "公园里的花红红的，风一吹就轻轻摇。",
  );
  await userEvent.click(screen.getByRole("button", { name: "继续写小作文" }));

  expect(screen.getByText("写一写你最近一次开心的经历")).toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("小写作"),
    "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "生成能力草图" }));

  expect(apiMocks.createAssessment).toHaveBeenCalledTimes(1);
  expect(apiMocks.createAssessment).toHaveBeenCalledWith("s1", {
    sentence_before: "公园很美。",
    sentence_after: "公园里的花红红的，风一吹就轻轻摇。",
    short_writing:
      "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
  });
  expect(
    await screen.findByRole("heading", { name: "第一张能力草图" }),
  ).toBeInTheDocument();
  expect(screen.getByText("写具体力")).toBeInTheDocument();
  expect(screen.getByText("46 / 100")).toBeInTheDocument();
  expect(screen.getByText("等待阅读试炼")).toBeInTheDocument();
  expect(screen.getByText("等待二稿试炼")).toBeInTheDocument();
  expect(screen.getByLabelText("第一张能力草图雷达图")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到 Dashboard" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
});

test("sentence page shows ai feedback and settlement", async () => {
  const sentenceResponse = {
    training: { id: "sentence-training-1" },
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
  let resolveSentenceTraining!: (value: typeof sentenceResponse) => void;
  const pendingSentenceTraining = new Promise<typeof sentenceResponse>(
    (resolve) => {
      resolveSentenceTraining = resolve;
    },
  );
  let resolveChallenge!: (value: typeof challengeResponse) => void;
  const pendingChallenge = new Promise<typeof challengeResponse>((resolve) => {
    resolveChallenge = resolve;
  });
  apiMocks.createSentenceChallenge.mockReturnValueOnce(pendingChallenge);
  apiMocks.createSentenceTraining.mockReturnValueOnce(pendingSentenceTraining);

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByText("正在出题...")).toBeInTheDocument();
  await act(async () => {
    resolveChallenge(challengeResponse);
    await pendingChallenge;
  });
  expect(
    await screen.findByRole("button", { name: "提交给 AI 教练" }),
  ).toBeEnabled();
  await userEvent.click(
    await screen.findByRole("button", { name: "自己带句子来练" }),
  );
  await userEvent.type(await screen.findByLabelText("原句"), "公园很美。");
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "提交给 AI 教练" }),
  );

  expect(screen.getByText("把一句话升级成小画面")).toBeInTheDocument();
  expect(await screen.findByText("AI 教练正在读你的句子...")).toBeInTheDocument();
  expect(screen.getByText("AI 教练正在看你的句子")).toBeInTheDocument();
  await act(async () => {
    resolveSentenceTraining(sentenceResponse);
    await pendingSentenceTraining;
  });
  expect(
    await screen.findByRole("heading", { name: "AI 教练反馈" }),
  ).toBeInTheDocument();
  expect(
    await screen.findByText("你把画面写得更清楚了。"),
  ).toBeInTheDocument();
  expect(screen.getByText("再加一个动作，会更生动。")).toBeInTheDocument();
  expect(screen.getByText("空泛表达")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到 Dashboard" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
  expect(screen.getByRole("link", { name: "给家长看报告" })).toHaveAttribute(
    "href",
    "/parent/s1/report",
  );
  expectReturnToChildrenLink();
  expect(await screen.findByText("加入了可看见的细节")).toBeInTheDocument();
  expect(screen.getByText("+25 XP")).toBeInTheDocument();
  expect(apiMocks.createSentenceTraining).toHaveBeenCalledWith("s1", {
    source_sentence: "公园很美。",
    upgraded_sentence: "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
    focus: "加细节",
  });
});

test("sentence page clears old feedback when retrying after success", async () => {
  const sentenceResponse = {
    training: { id: "sentence-training-1" },
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
  let rejectSecondSentenceTraining!: (reason?: unknown) => void;

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "自己带句子来练" }),
  );
  await userEvent.type(await screen.findByLabelText("原句"), "公园很美。");
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "提交给 AI 教练" }),
  );

  expect(await screen.findByText("加入了可看见的细节")).toBeInTheDocument();
  expect(screen.getByText("+25 XP")).toBeInTheDocument();

  const secondSentenceTraining = new Promise<typeof sentenceResponse>(
    (_, reject) => {
      rejectSecondSentenceTraining = reject;
    },
  );
  apiMocks.createSentenceTraining.mockReturnValueOnce(secondSentenceTraining);

  await userEvent.click(
    screen.getByRole("button", { name: "提交给 AI 教练" }),
  );

  expect(screen.getByText("AI 教练正在看你的句子")).toBeInTheDocument();
  expect(screen.queryByText("加入了可看见的细节")).not.toBeInTheDocument();
  expect(screen.queryByText("+25 XP")).not.toBeInTheDocument();

  await act(async () => {
    rejectSecondSentenceTraining(new Error("network"));
    await secondSentenceTraining.catch(() => undefined);
  });

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "这次句子练习没有提交成功。先别急，检查一下网络后再试一次。",
  );
  expect(screen.queryByText("加入了可看见的细节")).not.toBeInTheDocument();
  expect(screen.queryByText("+25 XP")).not.toBeInTheDocument();
});

test("assessment page disables submit while loading and permits retry after failure", async () => {
  let rejectAssessment!: (reason?: unknown) => void;
  apiMocks.createAssessment.mockReturnValueOnce(
    new Promise((_, reject) => {
      rejectAssessment = reject;
    }),
  );

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
    "公园里的花在风里轻轻摇。",
  );
  await userEvent.click(screen.getByRole("button", { name: "继续写小作文" }));
  await userEvent.type(
    screen.getByLabelText("小写作"),
    "我学会了骑车。刚开始我有点害怕，后来慢慢能骑过小路，我很开心。",
  );
  const submit = screen.getByRole("button", { name: "生成能力草图" });

  await userEvent.click(submit);

  expect(submit).toBeDisabled();
  expect(submit.querySelector(".animate-spin")).toBeInTheDocument();
  const status = screen.getByRole("status");
  expect(status).toHaveTextContent("AI 教练正在整理第一张能力草图");
  expect(status).toHaveClass(
    "rounded-lg",
    "bg-[var(--wen-bg)]",
    "text-[var(--wen-orange)]",
  );

  rejectAssessment(new Error("network"));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "这次小试炼没有提交成功。不是你的问题，检查一下网络后再试一次。",
  );
  await waitFor(() => expect(submit).not.toBeDisabled());
});

test("sentence page disables submit while pending and reports failures", async () => {
  let rejectSentenceTraining!: (reason?: unknown) => void;
  apiMocks.createSentenceTraining.mockReturnValueOnce(
    new Promise((_, reject) => {
      rejectSentenceTraining = reject;
    }),
  );

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <SentencePage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "自己带句子来练" }),
  );
  await userEvent.type(await screen.findByLabelText("原句"), "公园很美。");
  await userEvent.type(screen.getByLabelText("升级后的句子"), "公园里花香很浓。");
  const submit = screen.getByRole("button", { name: "提交给 AI 教练" });

  await userEvent.click(submit);

  expect(submit).toBeDisabled();

  rejectSentenceTraining(new Error("network"));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "这次句子练习没有提交成功。先别急，检查一下网络后再试一次。",
  );
  await waitFor(() => expect(submit).not.toBeDisabled());
});

test.each(["resolve", "reject"] as const)(
  "sentence page ignores stale challenge %s while free-input validation is pending",
  async (settlement) => {
    const challengeLoad = deferred<typeof challengeResponse>();
    const sentenceTraining = deferred<
      Awaited<ReturnType<typeof apiMocks.createSentenceTraining>>
    >();
    apiMocks.createSentenceChallenge.mockReturnValueOnce(challengeLoad.promise);
    apiMocks.createSentenceTraining.mockReturnValueOnce(sentenceTraining.promise);

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <SentencePage params={Promise.resolve({ studentId: "s1" })} />
        </Suspense>,
      );
    });

    await userEvent.click(
      await screen.findByRole("button", { name: "自己带句子来练" }),
    );
    await userEvent.type(await screen.findByLabelText("原句"), "公园很美。");
    await userEvent.type(screen.getByLabelText("升级后的句子"), "公园里花香很浓。");
    const submit = screen.getByRole("button", { name: "提交给 AI 教练" });

    await userEvent.click(submit);

    expect(await screen.findByText("AI 教练正在读你的句子...")).toBeInTheDocument();
    expect(submit).toBeDisabled();

    await act(async () => {
      if (settlement === "resolve") {
        challengeLoad.resolve(challengeResponse);
        await challengeLoad.promise;
      } else {
        challengeLoad.reject(new Error("stale challenge failed"));
        await challengeLoad.promise.catch(() => undefined);
      }
    });

    expect(screen.getByText("AI 教练正在读你的句子...")).toBeInTheDocument();
    expect(submit).toBeDisabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    sentenceTraining.resolve({
      training: { id: "sentence-training-1" },
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

    expect(
      await screen.findByText("你把画面写得更清楚了。"),
    ).toBeInTheDocument();
  },
);

test("sentence page disables mode switch while challenge validation is pending", async () => {
  const challengeCompletion = deferred<
    Awaited<ReturnType<typeof apiMocks.completeSentenceChallenge>>
  >();
  apiMocks.completeSentenceChallenge.mockReturnValueOnce(challengeCompletion.promise);

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
  await userEvent.click(screen.getByRole("button", { name: "提交给 AI 教练" }));

  expect(await screen.findByText("AI 教练正在读你的句子...")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "提交给 AI 教练" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "自己带句子来练" })).toBeDisabled();

  challengeCompletion.resolve({
    training: { id: "training-1" },
    feedback: {
      encouragement: "你写得很有画面感！",
      highlight: "你加上了飞快地冲过去，动作更清楚了。",
      suggestion: "还可以加一点表情或心情。",
      example_upgrade: "小狗瞪大眼睛，飞快地冲过草地。",
    },
    settlement: { xp_delta: 25, level_after: 2 },
    next_task: {
      kind: "sentence",
      title: "再练一句",
      focus: "动作描写",
      minutes: "5",
    },
  });

  expect(await screen.findByText("你写得很有画面感！")).toBeInTheDocument();
});

test("assessment sketch uses no charting package", async () => {
  const { readFileSync } = await import("node:fs");
  const { resolve } = await import("node:path");
  const packageJson = JSON.parse(
    readFileSync(resolve(process.cwd(), "package.json"), "utf8"),
  );
  const installedDependencies = {
    ...packageJson.dependencies,
    ...packageJson.devDependencies,
  };

  expect(installedDependencies).not.toHaveProperty("recharts");
  expect(installedDependencies).not.toHaveProperty("chart.js");
  expect(installedDependencies).not.toHaveProperty("@nivo/radar");
});
