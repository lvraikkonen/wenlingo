import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Suspense } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import EssayPage from "../src/app/children/[studentId]/essay/page";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });

  return { promise, resolve, reject };
}

const apiMocks = vi.hoisted(() => ({
  createEssay: vi.fn(),
  fetchChildEssayArchive: vi.fn(),
  fetchEssayArchiveDetail: vi.fn(),
  hideChildEssay: vi.fn(),
  submitEssayRevision: vi.fn(),
}));

vi.mock("../src/lib/api", () => ({
  createEssay: apiMocks.createEssay,
  fetchChildEssayArchive: apiMocks.fetchChildEssayArchive,
  fetchEssayArchiveDetail: apiMocks.fetchEssayArchiveDetail,
  hideChildEssay: apiMocks.hideChildEssay,
  submitEssayRevision: apiMocks.submitEssayRevision,
}));

const archiveItems = [
  archiveItem("essay-1", "第一次骑车", 1),
  archiveItem("essay-2", "雨天的操场", 2),
  archiveItem("essay-3", "我的好朋友", 3),
  archiveItem("essay-4", "多出来的一篇", 4),
];

beforeEach(() => {
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "revision-key-1") });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  apiMocks.createEssay.mockResolvedValue({
    essay: { id: "essay-new" },
    first_draft: {
      id: "draft-new",
      essay_id: "essay-new",
      version_label: "first_draft",
      reaction: null,
    },
    feedback: {
      strengths: ["能写清楚发生了什么"],
      improvements: [],
      problem_monsters: [],
      sentence_notes: [],
      revision_tasks: [{ instruction: "给第二段加一个动作描写", target: "第二段" }],
    },
  });
  apiMocks.fetchChildEssayArchive.mockResolvedValue({ items: archiveItems });
  apiMocks.fetchEssayArchiveDetail.mockResolvedValue(archiveDetail("essay-2"));
  apiMocks.submitEssayRevision.mockResolvedValue({
    revision: {
      id: "revision-1",
      completed_tasks: [],
      skipped_tasks: [],
      duration_seconds: 8,
      reaction: null,
    },
    comparison: {
      encouragement: "这一稿更清楚了。",
      improved_dimensions: ["画面更具体"],
      evidence: [],
      next_step: "继续保留动作细节。",
    },
    settlement: {
      xp_delta: 60,
      level_after: 2,
      badge_code: "first_revision",
      evidence: { completed_task_count: 0 },
    },
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function renderEssayPage() {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "student-1" })} />
      </Suspense>,
    );
  });
}

async function startFirstDraftFeedback() {
  await renderEssayPage();
  await userEvent.click(await screen.findByRole("button", { name: "直接写初稿" }));
  await userEvent.type(screen.getByLabelText("作文题目"), "我学会了骑车");
  await userEvent.type(screen.getByLabelText("初稿"), "我学会了骑车。后来我会了。");
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  await screen.findByText("修改小任务");
}

test("essay archive drawer is hidden by default and opens from the right", async () => {
  await renderEssayPage();

  const drawer = screen.getByRole("complementary", { hidden: true });
  expect(drawer).toHaveClass("translate-x-full");
  expect(drawer).toHaveAttribute("aria-hidden", "true");

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));

  expect(drawer).toHaveClass("translate-x-0");
  expect(drawer).toHaveAttribute("aria-hidden", "false");
  expect(apiMocks.fetchChildEssayArchive).toHaveBeenCalledWith("student-1", 3);
});

test("closed essay archive drawer does not expose focusable drawer controls", async () => {
  await renderEssayPage();

  expect(
    screen.queryByRole("button", { name: "关闭作文档案", hidden: true }),
  ).not.toBeInTheDocument();
});

test("essay archive drawer renders at most three items", async () => {
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));

  expect(await screen.findByRole("button", { name: /第一次骑车/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /雨天的操场/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /我的好朋友/ })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /多出来的一篇/ })).not.toBeInTheDocument();
});

test("essay archive drawer disables items that cannot continue revision", async () => {
  apiMocks.fetchChildEssayArchive.mockResolvedValueOnce({
    items: [
      archiveItem("essay-locked", "暂时不能续写", 1, {
        canContinueRevision: false,
      }),
      archiveItem("essay-2", "雨天的操场", 2),
    ],
  });
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  const lockedItem = await screen.findByRole("button", { name: /暂时不能续写/ });

  expect(lockedItem).toBeDisabled();
  expect(screen.getByText("这篇暂时不能继续修改")).toBeInTheDocument();
  await userEvent.click(lockedItem);
  expect(apiMocks.fetchEssayArchiveDetail).not.toHaveBeenCalled();
});

test("selecting an archive item loads latest content and AI guidance into the revision editor", async () => {
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(apiMocks.fetchEssayArchiveDetail).toHaveBeenCalledWith("essay-2");
  expect(await screen.findByLabelText("下一稿")).toHaveValue("上一稿正文，已经写到第二稿。");
  expect(screen.getByText("AI 建议：把操场上的动作写得更清楚。")).toBeInTheDocument();
});

test("archive detail that cannot continue revision is not restored", async () => {
  apiMocks.fetchEssayArchiveDetail.mockResolvedValueOnce(
    archiveDetail("essay-2", { canContinueRevision: false }),
  );
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "这篇作文现在还不能继续修改。",
  );
  expect(screen.getByRole("complementary", { hidden: true })).toHaveAttribute(
    "aria-hidden",
    "true",
  );
  expect(screen.queryByText("AI 建议：把操场上的动作写得更清楚。")).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue("上一稿正文，已经写到第二稿。")).not.toBeInTheDocument();
});

test("switching archive item with unsaved input asks for confirmation", async () => {
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "我自己新写了一段，还没有提交。");
  apiMocks.fetchEssayArchiveDetail.mockResolvedValueOnce(archiveDetail("essay-3"));

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await screen.findByRole("button", { name: /我的好朋友/ });
  await userEvent.click(screen.getByRole("button", { name: /我的好朋友/ }));

  expect(window.confirm).toHaveBeenCalled();
  expect(apiMocks.fetchEssayArchiveDetail).toHaveBeenLastCalledWith("essay-3");
});

test("clearing restored revision text still asks before archive restore", async () => {
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  apiMocks.fetchEssayArchiveDetail.mockClear();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /我的好朋友/ }));

  expect(window.confirm).toHaveBeenCalled();
  expect(apiMocks.fetchEssayArchiveDetail).not.toHaveBeenCalled();
  expect(screen.getByLabelText("下一稿")).toHaveValue("");
});

test("selecting archive with unsaved direct title or draft asks before restore", async () => {
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  await renderEssayPage();

  await userEvent.click(await screen.findByRole("button", { name: "直接写初稿" }));
  await userEvent.type(screen.getByLabelText("作文题目"), "还没提交的新题目");
  await userEvent.type(screen.getByLabelText("初稿"), "这是一段还没提交的初稿。");
  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(window.confirm).toHaveBeenCalled();
  expect(apiMocks.fetchEssayArchiveDetail).not.toHaveBeenCalled();
  expect(screen.getByLabelText("作文题目")).toHaveValue("还没提交的新题目");
  expect(screen.getByLabelText("初稿")).toHaveValue("这是一段还没提交的初稿。");
});

test("selecting archive after feedback asks before overwriting edited title or draft", async () => {
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  await startFirstDraftFeedback();

  await userEvent.clear(screen.getByLabelText("作文题目"));
  await userEvent.type(screen.getByLabelText("作文题目"), "点评后又改的新题目");
  await userEvent.clear(screen.getByLabelText("初稿"));
  await userEvent.type(screen.getByLabelText("初稿"), "点评后又改的一段初稿。");
  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(window.confirm).toHaveBeenCalled();
  expect(apiMocks.fetchEssayArchiveDetail).not.toHaveBeenCalled();
  expect(screen.getByLabelText("作文题目")).toHaveValue("点评后又改的新题目");
  expect(screen.getByLabelText("初稿")).toHaveValue("点评后又改的一段初稿。");
});

test("clearing direct title and draft after feedback still asks before archive restore", async () => {
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  await startFirstDraftFeedback();

  await userEvent.clear(screen.getByLabelText("作文题目"));
  await userEvent.clear(screen.getByLabelText("初稿"));
  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(window.confirm).toHaveBeenCalled();
  expect(apiMocks.fetchEssayArchiveDetail).not.toHaveBeenCalled();
  expect(screen.getByLabelText("作文题目")).toHaveValue("");
  expect(screen.getByLabelText("初稿")).toHaveValue("");
});

test("latest archive selection wins when detail responses resolve out of order", async () => {
  const firstDetail = deferred<ReturnType<typeof archiveDetail>>();
  const secondDetail = deferred<ReturnType<typeof archiveDetail>>();
  apiMocks.fetchEssayArchiveDetail
    .mockReturnValueOnce(firstDetail.promise)
    .mockReturnValueOnce(secondDetail.promise);
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /第一次骑车/ }));
  await userEvent.click(screen.getByRole("button", { name: /我的好朋友/ }));

  await act(async () => {
    secondDetail.resolve(
      archiveDetail("essay-3", {
        latestVersionId: "version-3",
        latestContent: "最新选择的第三稿内容。",
        previousAiGuidance: "AI 建议：继续把朋友的动作写清楚。",
        nextRoundIndex: 4,
        title: "我的好朋友",
      }),
    );
    await secondDetail.promise;
  });
  expect(await screen.findByLabelText("下一稿")).toHaveValue("最新选择的第三稿内容。");

  await act(async () => {
    firstDetail.resolve(
      archiveDetail("essay-1", {
        latestVersionId: "version-1",
        latestContent: "较早选择的第一篇内容。",
        previousAiGuidance: "AI 建议：这是旧响应。",
        nextRoundIndex: 2,
        title: "第一次骑车",
      }),
    );
    await firstDetail.promise;
  });

  expect(screen.getByLabelText("下一稿")).toHaveValue("最新选择的第三稿内容。");
  await userEvent.clear(screen.getByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "我继续修改最新选择的作文。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));
  expect(apiMocks.submitEssayRevision).toHaveBeenCalledWith(
    "essay-3",
    expect.objectContaining({
      base_version_id: "version-3",
      content: "我继续修改最新选择的作文。",
    }),
  );
});

test("stale first draft feedback is ignored after archive restore", async () => {
  const firstDraftFeedback = deferred<Awaited<ReturnType<typeof apiMocks.createEssay>>>();
  apiMocks.createEssay.mockReturnValueOnce(firstDraftFeedback.promise);
  await renderEssayPage();

  await userEvent.click(await screen.findByRole("button", { name: "直接写初稿" }));
  await userEvent.type(screen.getByLabelText("作文题目"), "还在提交的题目");
  await userEvent.type(screen.getByLabelText("初稿"), "这是一篇还在等点评的初稿。");
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(await screen.findByLabelText("下一稿")).toHaveValue("上一稿正文，已经写到第二稿。");
  expect(screen.getByText("AI 建议：把操场上的动作写得更清楚。")).toBeInTheDocument();

  await act(async () => {
    firstDraftFeedback.resolve({
      essay: { id: "essay-old-feedback" },
      first_draft: {
        id: "draft-old-feedback",
        essay_id: "essay-old-feedback",
        version_label: "first_draft",
        reaction: null,
      },
      feedback: {
        strengths: ["旧初稿点评不应该出现"],
        improvements: [],
        problem_monsters: [],
        sentence_notes: [],
        revision_tasks: [{ instruction: "旧任务不应该出现", target: "旧段落" }],
      },
    });
    await firstDraftFeedback.promise;
  });

  expect(screen.getByLabelText("下一稿")).toHaveValue("上一稿正文，已经写到第二稿。");
  expect(screen.getByText("AI 建议：把操场上的动作写得更清楚。")).toBeInTheDocument();
  expect(screen.queryByText("旧初稿点评不应该出现")).not.toBeInTheDocument();
  expect(screen.queryByText("旧任务不应该出现")).not.toBeInTheDocument();
});

test("new essay reset is available after first draft feedback", async () => {
  await startFirstDraftFeedback();

  expect(screen.getByLabelText("下一稿")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "写新的作文" }));

  expect(screen.getByLabelText("作文题目")).toHaveValue("");
  expect(screen.getByLabelText("初稿")).toHaveValue("");
  expect(screen.queryByText("修改小任务")).not.toBeInTheDocument();
});

test("archive restore asks after comparison when visible editor fields are edited", async () => {
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  await startFirstDraftFeedback();
  await userEvent.type(screen.getByLabelText("下一稿"), "我写完了这一稿。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));
  expect(await screen.findByLabelText("修改对比")).toBeInTheDocument();

  await userEvent.clear(screen.getByLabelText("作文题目"));
  await userEvent.type(screen.getByLabelText("作文题目"), "对比后改的新题目");
  await userEvent.clear(screen.getByLabelText("初稿"));
  await userEvent.type(screen.getByLabelText("初稿"), "对比后改的新初稿。");
  await userEvent.clear(screen.getByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "对比后改的新下一稿。");
  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(window.confirm).toHaveBeenCalled();
  expect(apiMocks.fetchEssayArchiveDetail).not.toHaveBeenCalled();
  expect(screen.getByLabelText("作文题目")).toHaveValue("对比后改的新题目");
  expect(screen.getByLabelText("初稿")).toHaveValue("对比后改的新初稿。");
  expect(screen.getByLabelText("下一稿")).toHaveValue("对比后改的新下一稿。");
});

test("new essay reset is available after comparison", async () => {
  await startFirstDraftFeedback();
  await userEvent.type(screen.getByLabelText("下一稿"), "我写完了这一稿。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  const comparison = await screen.findByLabelText("修改对比");
  await userEvent.click(
    within(comparison).getByRole("button", { name: "写新的作文" }),
  );

  expect(screen.getByLabelText("作文题目")).toHaveValue("");
  expect(screen.getByLabelText("初稿")).toHaveValue("");
  expect(screen.getByLabelText("下一稿")).toHaveValue("");
  expect(screen.queryByText("修改小任务")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("修改对比")).not.toBeInTheDocument();
});

test("revision submit uses latest_version_id as base_version_id and stable idempotency_key", async () => {
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "这是接着第二稿写的下一稿。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(apiMocks.submitEssayRevision).toHaveBeenCalledWith(
    "essay-2",
    expect.objectContaining({
      base_version_id: "version-2",
      content: "这是接着第二稿写的下一稿。",
      idempotency_key: "revision-key-1",
    }),
  );
});

test("rapid duplicate revision submit is ignored synchronously", async () => {
  const revisionSubmit = deferred<Awaited<ReturnType<typeof apiMocks.submitEssayRevision>>>();
  apiMocks.submitEssayRevision.mockReturnValue(revisionSubmit.promise);
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "只应该提交一次。");

  const form = screen.getByLabelText("下一稿").closest("form");
  expect(form).not.toBeNull();
  form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

  expect(apiMocks.submitEssayRevision).toHaveBeenCalledTimes(1);

  await act(async () => {
    revisionSubmit.resolve({
      revision: {
        id: "revision-1",
        completed_tasks: [],
        skipped_tasks: [],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "这一稿更清楚了。",
        improved_dimensions: ["画面更具体"],
        evidence: [],
        next_step: "继续保留动作细节。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "first_revision",
        evidence: { completed_task_count: 0 },
      },
    });
    await revisionSubmit.promise;
  });
});

test("pending revision response is ignored after new essay reset", async () => {
  const revisionSubmit = deferred<Awaited<ReturnType<typeof apiMocks.submitEssayRevision>>>();
  apiMocks.submitEssayRevision.mockReturnValueOnce(revisionSubmit.promise);
  await startFirstDraftFeedback();

  await userEvent.type(screen.getByLabelText("下一稿"), "这次提交会很慢。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));
  await userEvent.click(screen.getByRole("button", { name: "写新的作文" }));

  await act(async () => {
    revisionSubmit.resolve({
      revision: {
        id: "revision-old",
        completed_tasks: [],
        skipped_tasks: [],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "旧请求不应该出现。",
        improved_dimensions: ["旧对比"],
        evidence: [],
        next_step: "旧建议。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "old_revision",
        evidence: { completed_task_count: 0 },
      },
    });
    await revisionSubmit.promise;
  });

  expect(screen.queryByText("旧请求不应该出现。")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("修改对比")).not.toBeInTheDocument();
  expect(screen.queryByText("完成 0 个修改任务")).not.toBeInTheDocument();
});

test("pending revision response is ignored after new draft feedback starts", async () => {
  const revisionSubmit = deferred<Awaited<ReturnType<typeof apiMocks.submitEssayRevision>>>();
  apiMocks.submitEssayRevision.mockReturnValueOnce(revisionSubmit.promise);
  await startFirstDraftFeedback();

  await userEvent.type(screen.getByLabelText("下一稿"), "这次修改还在比较。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));

  await waitFor(() => {
    expect(screen.getByLabelText("下一稿")).toHaveValue("");
  });

  await act(async () => {
    revisionSubmit.resolve({
      revision: {
        id: "revision-old-feedback",
        completed_tasks: [],
        skipped_tasks: [],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "旧修改对比不应该出现。",
        improved_dimensions: ["旧对比"],
        evidence: [],
        next_step: "旧建议。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "old_revision",
        evidence: { completed_task_count: 0 },
      },
    });
    await revisionSubmit.promise;
  });

  expect(screen.queryByText("旧修改对比不应该出现。")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("修改对比")).not.toBeInTheDocument();
  expect(screen.queryByText("完成 0 个修改任务")).not.toBeInTheDocument();
});

test("revision textarea is locked while submit is pending", async () => {
  const revisionSubmit = deferred<Awaited<ReturnType<typeof apiMocks.submitEssayRevision>>>();
  apiMocks.submitEssayRevision.mockReturnValueOnce(revisionSubmit.promise);
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "提交中的正文。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(screen.getByLabelText("下一稿")).toBeDisabled();
  await userEvent.type(screen.getByLabelText("下一稿"), "不应写入");
  expect(screen.getByLabelText("下一稿")).toHaveValue("提交中的正文。");

  await act(async () => {
    revisionSubmit.resolve({
      revision: {
        id: "revision-1",
        completed_tasks: [],
        skipped_tasks: [],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "这一稿更清楚了。",
        improved_dimensions: ["画面更具体"],
        evidence: [],
        next_step: "继续保留动作细节。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "first_revision",
        evidence: { completed_task_count: 0 },
      },
    });
    await revisionSubmit.promise;
  });
});

test("round three UI uses next draft wording instead of hardcoded second draft", async () => {
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));

  expect(await screen.findByLabelText("下一稿")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "提交下一稿" })).toBeInTheDocument();
  expect(screen.queryByLabelText("二稿")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "提交二稿" })).not.toBeInTheDocument();
});

test("pending comparison response keeps same idempotency key and revision text", async () => {
  apiMocks.submitEssayRevision
    .mockResolvedValueOnce({
      status: "pending_comparison",
      attempt_id: "attempt-1",
      message: "AI 教练还在比较，请稍等一下。",
    })
    .mockResolvedValueOnce({
      revision: {
        id: "revision-1",
        completed_tasks: [],
        skipped_tasks: [],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "这一稿更清楚了。",
        improved_dimensions: ["画面更具体"],
        evidence: [],
        next_step: "继续保留动作细节。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "first_revision",
        evidence: { completed_task_count: 0 },
      },
    });
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "这是还在比较的下一稿。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("AI 教练还在比较，请稍等一下。");
  expect(screen.getByLabelText("下一稿")).toHaveValue("这是还在比较的下一稿。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(apiMocks.submitEssayRevision).toHaveBeenCalledTimes(2);
  expect(apiMocks.submitEssayRevision.mock.calls[0][1].idempotency_key).toBe("revision-key-1");
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].idempotency_key).toBe("revision-key-1");
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].content).toBe("这是还在比较的下一稿。");
});

test("editing after pending comparison clears stale message and idempotency key", async () => {
  vi.stubGlobal("crypto", {
    randomUUID: vi
      .fn()
      .mockReturnValueOnce("revision-key-1")
      .mockReturnValueOnce("revision-key-2"),
  });
  apiMocks.submitEssayRevision
    .mockResolvedValueOnce({
      status: "pending_comparison",
      attempt_id: "attempt-1",
      message: "AI 教练还在比较，请稍等一下。",
    })
    .mockResolvedValueOnce({
      revision: {
        id: "revision-1",
        completed_tasks: [],
        skipped_tasks: [],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "这一稿更清楚了。",
        improved_dimensions: ["画面更具体"],
        evidence: [],
        next_step: "继续保留动作细节。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "first_revision",
        evidence: { completed_task_count: 0 },
      },
    });
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "这是还在比较的下一稿。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("AI 教练还在比较，请稍等一下。");
  await userEvent.type(screen.getByLabelText("下一稿"), "加一句新修改。");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(apiMocks.submitEssayRevision.mock.calls[0][1].idempotency_key).toBe("revision-key-1");
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].idempotency_key).toBe("revision-key-2");
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].content).toBe(
    "这是还在比较的下一稿。加一句新修改。",
  );
});

test("returning pending revision text to loaded content clears stale idempotency key", async () => {
  vi.stubGlobal("crypto", {
    randomUUID: vi
      .fn()
      .mockReturnValueOnce("revision-key-1")
      .mockReturnValueOnce("revision-key-2"),
  });
  apiMocks.submitEssayRevision
    .mockResolvedValueOnce({
      status: "pending_comparison",
      attempt_id: "attempt-1",
      message: "AI 教练还在比较，请稍等一下。",
    })
    .mockResolvedValueOnce({
      revision: {
        id: "revision-1",
        completed_tasks: [],
        skipped_tasks: [],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "这一稿更清楚了。",
        improved_dimensions: ["画面更具体"],
        evidence: [],
        next_step: "继续保留动作细节。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "first_revision",
        evidence: { completed_task_count: 0 },
      },
    });
  await renderEssayPage();

  await userEvent.click(screen.getByRole("button", { name: "作文档案" }));
  await userEvent.click(await screen.findByRole("button", { name: /雨天的操场/ }));
  await userEvent.clear(await screen.findByLabelText("下一稿"));
  await userEvent.type(screen.getByLabelText("下一稿"), "这是第一次提交的待比较内容。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("AI 教练还在比较，请稍等一下。");
  fireEvent.change(screen.getByLabelText("下一稿"), {
    target: { value: "上一稿正文，已经写到第二稿。" },
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(apiMocks.submitEssayRevision).toHaveBeenCalledTimes(2);
  expect(apiMocks.submitEssayRevision.mock.calls[0][1].idempotency_key).toBe("revision-key-1");
  expect(apiMocks.submitEssayRevision.mock.calls[0][1].content).toBe(
    "这是第一次提交的待比较内容。",
  );
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].idempotency_key).toBe("revision-key-2");
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].content).toBe(
    "上一稿正文，已经写到第二稿。",
  );
});

test("changing revision tasks after pending comparison clears stale idempotency key", async () => {
  vi.stubGlobal("crypto", {
    randomUUID: vi
      .fn()
      .mockReturnValueOnce("revision-key-1")
      .mockReturnValueOnce("revision-key-2"),
  });
  apiMocks.submitEssayRevision
    .mockResolvedValueOnce({
      status: "pending_comparison",
      attempt_id: "attempt-1",
      message: "AI 教练还在比较，请稍等一下。",
    })
    .mockResolvedValueOnce({
      revision: {
        id: "revision-1",
        completed_tasks: [],
        skipped_tasks: ["给第二段加一个动作描写"],
        duration_seconds: 12,
        reaction: null,
      },
      comparison: {
        encouragement: "这一稿更清楚了。",
        improved_dimensions: ["画面更具体"],
        evidence: [],
        next_step: "继续保留动作细节。",
      },
      settlement: {
        xp_delta: 60,
        level_after: 2,
        badge_code: "first_revision",
        evidence: { completed_task_count: 0 },
      },
    });
  await startFirstDraftFeedback();

  await userEvent.type(screen.getByLabelText("下一稿"), "这是还在比较的下一稿。");
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("AI 教练还在比较，请稍等一下。");
  await userEvent.click(screen.getByLabelText("给第二段加一个动作描写"));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "提交下一稿" }));

  expect(apiMocks.submitEssayRevision).toHaveBeenCalledTimes(2);
  expect(apiMocks.submitEssayRevision.mock.calls[0][1].idempotency_key).toBe("revision-key-1");
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].idempotency_key).toBe("revision-key-2");
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].completed_tasks).toEqual([]);
  expect(apiMocks.submitEssayRevision.mock.calls[1][1].skipped_tasks).toEqual([
    "给第二段加一个动作描写",
  ]);
});

function archiveItem(
  essayId: string,
  title: string,
  round: number,
  overrides: { canContinueRevision?: boolean } = {},
) {
  return {
    essay_id: essayId,
    title,
    status: "needs_revision" as const,
    hidden: false,
    hidden_by: "" as const,
    hidden_at: null,
    latest_round_index: round,
    latest_version_id: `version-${round}`,
    last_version_submitted_at: "2026-06-30T12:00:00Z",
    revision_round_count: Math.max(0, round - 1),
    needs_revision: true,
    can_continue_revision: overrides.canContinueRevision ?? true,
    can_retry_revision_attempt: false,
    summary_label: `第 ${round} 稿`,
    topic_origin: "direct_draft" as const,
    topic_type: "",
    topic_variant: "",
    scaffold_template_version: null,
    selected_topic_idea: null,
    generated_topic_metadata: null,
  };
}

function archiveDetail(
  essayId: string,
  overrides: {
    canContinueRevision?: boolean;
    latestVersionId?: string;
    latestContent?: string;
    previousAiGuidance?: string;
    nextRoundIndex?: number;
    title?: string;
  } = {},
) {
  return {
    ...archiveItem(
      essayId,
      overrides.title ?? (essayId === "essay-2" ? "雨天的操场" : "我的好朋友"),
      2,
      { canContinueRevision: overrides.canContinueRevision },
    ),
    visibility: {
      hidden: false,
      hidden_by: "" as const,
      hidden_at: null,
      visibility_changed_at: null,
    },
    versions: [],
    revision_attempt: null,
    continue_revision: {
      latest_version_id: overrides.latestVersionId ?? "version-2",
      latest_content: overrides.latestContent ?? "上一稿正文，已经写到第二稿。",
      previous_ai_guidance:
        overrides.previousAiGuidance ?? "AI 建议：把操场上的动作写得更清楚。",
      next_round_index: overrides.nextRoundIndex ?? 3,
    },
    parent_summary: null,
  };
}
