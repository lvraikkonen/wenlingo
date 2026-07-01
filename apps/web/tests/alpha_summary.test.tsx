import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Suspense } from "react";
import { beforeEach, expect, test, vi } from "vitest";
import ParentChildSummaryPage from "../src/app/parent/children/[studentId]/summary/page";
import {
  fetchParentEssayArchive,
  fetchParentEssayArchiveDetail,
  getMyAlphaChildSummary,
  recordAlphaEvent,
  restoreParentEssay,
} from "../src/lib/api";
import { ALPHA_SESSION_STORAGE_KEY } from "../src/lib/alphaSession";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("../src/lib/api", () => ({
  fetchParentEssayArchive: vi.fn(),
  fetchParentEssayArchiveDetail: vi.fn(),
  getMyAlphaChildSummary: vi.fn(),
  isUnauthorizedError: (error: unknown) =>
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    error.status === 401,
  recordAlphaEvent: vi.fn(async () => undefined),
  restoreParentEssay: vi.fn(),
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });

  return { promise, resolve, reject };
}

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
  vi.mocked(fetchParentEssayArchive).mockReset();
  vi.mocked(fetchParentEssayArchive).mockResolvedValue({ items: [] });
  vi.mocked(fetchParentEssayArchiveDetail).mockReset();
  vi.mocked(getMyAlphaChildSummary).mockReset();
  vi.mocked(recordAlphaEvent).mockClear();
  vi.mocked(restoreParentEssay).mockReset();
  vi.mocked(restoreParentEssay).mockResolvedValue({
    essay_id: "essay-hidden",
    title: "雨天的操场",
    status: "revised_once",
    hidden: false,
    hidden_by: "",
    latest_round_index: 2,
    latest_version_id: "version-2",
    last_version_submitted_at: "2026-06-01T08:00:00Z",
    revision_round_count: 1,
    needs_revision: false,
    can_continue_revision: false,
    can_retry_revision_attempt: false,
    summary_label: "已恢复",
  });
});

function mockPopulatedSummary() {
  vi.mocked(getMyAlphaChildSummary).mockResolvedValue({
    parent_id: "parent-1",
    child,
    assessment_completed: true,
    practice_counts: {
      assessments: 1,
      sentence_trainings: 1,
      essays: 2,
    },
    ability_changes: [{ ability: "expression", label: "表达力", delta: 5 }],
    recent_highlight: "孩子完成了一次小写作。",
    sentence_training_summary: null,
    next_suggestion: "下一次继续练习把素材写具体。",
    empty_state: null,
  });
}

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

test("parent summary defaults to archive summary without full essay text", async () => {
  mockPopulatedSummary();
  vi.mocked(fetchParentEssayArchive).mockResolvedValueOnce({
    items: [
      {
        essay_id: "essay-1",
        title: "雨天的操场",
        status: "revised_once",
        hidden: false,
        hidden_by: "",
        latest_round_index: 2,
        latest_version_id: "version-2",
        last_version_submitted_at: "2026-06-01T08:00:00Z",
        revision_round_count: 1,
        needs_revision: false,
        can_continue_revision: false,
        can_retry_revision_attempt: false,
        summary_label: "修改后更具体",
      },
    ],
  });

  await renderSummaryPage();

  expect(await screen.findByText("作文档案摘要")).toBeInTheDocument();
  expect(fetchParentEssayArchive).toHaveBeenCalledWith("student-1", true, 20);
  expect(screen.getByText("雨天的操场")).toBeInTheDocument();
  expect(screen.getByText("修改后更具体")).toBeInTheDocument();
  expect(screen.getByText("最新第 2 稿")).toBeInTheDocument();
  expect(screen.queryByText("雨下得很大，我在操场边看见水花。")).not.toBeInTheDocument();
});

test("parent summary can expand essay details", async () => {
  mockPopulatedSummary();
  vi.mocked(fetchParentEssayArchive).mockResolvedValueOnce({
    items: [
      {
        essay_id: "essay-1",
        title: "雨天的操场",
        status: "revised_once",
        hidden: false,
        hidden_by: "",
        latest_round_index: 2,
        latest_version_id: "version-2",
        last_version_submitted_at: "2026-06-01T08:00:00Z",
        revision_round_count: 1,
        needs_revision: false,
        can_continue_revision: false,
        can_retry_revision_attempt: false,
        summary_label: "修改后更具体",
      },
    ],
  });
  vi.mocked(fetchParentEssayArchiveDetail).mockResolvedValueOnce({
    essay_id: "essay-1",
    title: "雨天的操场",
    status: "revised_once",
    hidden: false,
    hidden_by: "",
    latest_round_index: 2,
    latest_version_id: "version-2",
    last_version_submitted_at: "2026-06-01T08:00:00Z",
    revision_round_count: 1,
    needs_revision: false,
    can_continue_revision: false,
    can_retry_revision_attempt: false,
    summary_label: "修改后更具体",
    visibility: { hidden: false, hidden_by: "" },
    versions: [
      {
        version_id: "version-1",
        version_label: "初稿",
        round_index: 1,
        content: "雨下得很大，我在操场边看见水花。",
        ai_feedback: null,
        duration_seconds: null,
        completed_tasks: [],
        skipped_tasks: [],
        llm_call_log_id: null,
        created_at: "2026-06-01T08:00:00Z",
      },
    ],
    revision_attempt: null,
    continue_revision: null,
    parent_summary: {
      status: "revised_once",
      summary_label: "修改后更具体",
      latest_round_index: 2,
      revision_round_count: 1,
      recent_improvement: "把操场边的声音写清楚了。",
      next_suggestion: "下一稿可以补充自己的心情。",
    },
  });

  await renderSummaryPage();
  await userEvent.click(await screen.findByRole("button", { name: "展开详情：雨天的操场" }));

  expect(fetchParentEssayArchiveDetail).toHaveBeenCalledWith("essay-1");
  expect(await screen.findByText("雨下得很大，我在操场边看见水花。")).toBeInTheDocument();
  expect(screen.getByText("把操场边的声音写清楚了。")).toBeInTheDocument();
  expect(screen.getByText("下一稿可以补充自己的心情。")).toBeInTheDocument();
});

test("parent summary keeps current detail loading visible when another detail resolves first", async () => {
  mockPopulatedSummary();
  const firstDetailRequest = deferred<
    Awaited<ReturnType<typeof fetchParentEssayArchiveDetail>>
  >();
  const secondDetailRequest = deferred<
    Awaited<ReturnType<typeof fetchParentEssayArchiveDetail>>
  >();
  vi.mocked(fetchParentEssayArchive).mockResolvedValueOnce({
    items: [
      {
        essay_id: "essay-1",
        title: "雨天的操场",
        status: "revised_once",
        hidden: false,
        hidden_by: "",
        latest_round_index: 2,
        latest_version_id: "version-2",
        last_version_submitted_at: "2026-06-01T08:00:00Z",
        revision_round_count: 1,
        needs_revision: false,
        can_continue_revision: false,
        can_retry_revision_attempt: false,
        summary_label: "修改后更具体",
      },
      {
        essay_id: "essay-2",
        title: "足球场边的小发现",
        status: "needs_revision",
        hidden: false,
        hidden_by: "",
        latest_round_index: 1,
        latest_version_id: "version-1",
        last_version_submitted_at: "2026-06-02T08:00:00Z",
        revision_round_count: 0,
        needs_revision: true,
        can_continue_revision: true,
        can_retry_revision_attempt: false,
        summary_label: "等待第一次修改",
      },
    ],
  });
  vi.mocked(fetchParentEssayArchiveDetail)
    .mockReturnValueOnce(firstDetailRequest.promise)
    .mockReturnValueOnce(secondDetailRequest.promise);

  await renderSummaryPage();
  await userEvent.click(await screen.findByRole("button", { name: "展开详情：雨天的操场" }));
  expect(await screen.findByText("正在加载作文详情...")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "展开详情：足球场边的小发现" }));
  expect(screen.getByText("正在加载作文详情...")).toBeInTheDocument();

  await act(async () => {
    firstDetailRequest.resolve({
      essay_id: "essay-1",
      title: "雨天的操场",
      status: "revised_once",
      hidden: false,
      hidden_by: "",
      latest_round_index: 2,
      latest_version_id: "version-2",
      last_version_submitted_at: "2026-06-01T08:00:00Z",
      revision_round_count: 1,
      needs_revision: false,
      can_continue_revision: false,
      can_retry_revision_attempt: false,
      summary_label: "修改后更具体",
      visibility: { hidden: false, hidden_by: "" },
      versions: [],
      revision_attempt: null,
      continue_revision: null,
      parent_summary: null,
    });
  });

  expect(screen.getByText("正在加载作文详情...")).toBeInTheDocument();

  await act(async () => {
    secondDetailRequest.resolve({
      essay_id: "essay-2",
      title: "足球场边的小发现",
      status: "needs_revision",
      hidden: false,
      hidden_by: "",
      latest_round_index: 1,
      latest_version_id: "version-1",
      last_version_submitted_at: "2026-06-02T08:00:00Z",
      revision_round_count: 0,
      needs_revision: true,
      can_continue_revision: true,
      can_retry_revision_attempt: false,
      summary_label: "等待第一次修改",
      visibility: { hidden: false, hidden_by: "" },
      versions: [
        {
          version_id: "version-1",
          version_label: "初稿",
          round_index: 1,
          content: "我看见足球滚过草地。",
          ai_feedback: null,
          duration_seconds: null,
          completed_tasks: [],
          skipped_tasks: [],
          llm_call_log_id: null,
          created_at: "2026-06-02T08:00:00Z",
        },
      ],
      revision_attempt: null,
      continue_revision: null,
      parent_summary: null,
    });
  });

  expect(await screen.findByText("我看见足球滚过草地。")).toBeInTheDocument();
  expect(screen.queryByText("正在加载作文详情...")).not.toBeInTheDocument();
});

test("parent summary lists child-hidden essays and restores one", async () => {
  mockPopulatedSummary();
  const restoreRequest = deferred<Awaited<ReturnType<typeof restoreParentEssay>>>();
  vi.mocked(restoreParentEssay).mockReturnValueOnce(restoreRequest.promise);
  vi.mocked(fetchParentEssayArchive)
    .mockResolvedValueOnce({
      items: [
        {
          essay_id: "essay-hidden",
          title: "雨天的操场",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "child",
          latest_round_index: 2,
          latest_version_id: "version-2",
          last_version_submitted_at: "2026-06-01T08:00:00Z",
          revision_round_count: 1,
          needs_revision: false,
          can_continue_revision: false,
          can_retry_revision_attempt: false,
          summary_label: "孩子已隐藏",
        },
        {
          essay_id: "essay-parent-hidden",
          title: "家长隐藏的作文",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "parent",
          latest_round_index: 1,
          latest_version_id: "version-1",
          last_version_submitted_at: "2026-06-01T08:00:00Z",
          revision_round_count: 0,
          needs_revision: false,
          can_continue_revision: false,
          can_retry_revision_attempt: false,
          summary_label: "暂不显示",
        },
      ],
    })
    .mockResolvedValueOnce({ items: [] });

  await renderSummaryPage();

  expect(await screen.findByText("雨天的操场")).toBeInTheDocument();
  expect(screen.getByText("孩子已隐藏")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "恢复作文：雨天的操场" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "恢复作文：家长隐藏的作文" })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "恢复作文：雨天的操场" }));

  expect(await screen.findByRole("button", { name: "正在恢复：雨天的操场" })).toBeDisabled();
  await waitFor(() => expect(restoreParentEssay).toHaveBeenCalledWith("essay-hidden"));
  restoreRequest.resolve({
    essay_id: "essay-hidden",
    title: "雨天的操场",
    status: "revised_once",
    hidden: false,
    hidden_by: "",
    latest_round_index: 2,
    latest_version_id: "version-2",
    last_version_submitted_at: "2026-06-01T08:00:00Z",
    revision_round_count: 1,
    needs_revision: false,
    can_continue_revision: false,
    can_retry_revision_attempt: false,
    summary_label: "已恢复",
  });
  await waitFor(() => expect(fetchParentEssayArchive).toHaveBeenCalledTimes(2));
  expect(fetchParentEssayArchive).toHaveBeenLastCalledWith("student-1", true, 20);
});

test("parent summary tracks overlapping restores per essay", async () => {
  mockPopulatedSummary();
  const firstRestoreRequest = deferred<Awaited<ReturnType<typeof restoreParentEssay>>>();
  const secondRestoreRequest = deferred<Awaited<ReturnType<typeof restoreParentEssay>>>();
  vi.mocked(restoreParentEssay)
    .mockReturnValueOnce(firstRestoreRequest.promise)
    .mockReturnValueOnce(secondRestoreRequest.promise);
  vi.mocked(fetchParentEssayArchive)
    .mockResolvedValueOnce({
      items: [
        {
          essay_id: "essay-hidden-1",
          title: "雨天的操场",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "child",
          latest_round_index: 2,
          latest_version_id: "version-2",
          last_version_submitted_at: "2026-06-01T08:00:00Z",
          revision_round_count: 1,
          needs_revision: false,
          can_continue_revision: false,
          can_retry_revision_attempt: false,
          summary_label: "孩子已隐藏",
        },
        {
          essay_id: "essay-hidden-2",
          title: "足球场边的小发现",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "child",
          latest_round_index: 1,
          latest_version_id: "version-1",
          last_version_submitted_at: "2026-06-02T08:00:00Z",
          revision_round_count: 0,
          needs_revision: true,
          can_continue_revision: true,
          can_retry_revision_attempt: false,
          summary_label: "孩子已隐藏",
        },
      ],
    })
    .mockResolvedValueOnce({
      items: [
        {
          essay_id: "essay-hidden-2",
          title: "足球场边的小发现",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "child",
          latest_round_index: 1,
          latest_version_id: "version-1",
          last_version_submitted_at: "2026-06-02T08:00:00Z",
          revision_round_count: 0,
          needs_revision: true,
          can_continue_revision: true,
          can_retry_revision_attempt: false,
          summary_label: "孩子已隐藏",
        },
      ],
    })
    .mockResolvedValueOnce({ items: [] });

  await renderSummaryPage();

  await userEvent.click(await screen.findByRole("button", { name: "恢复作文：雨天的操场" }));
  await userEvent.click(screen.getByRole("button", { name: "恢复作文：足球场边的小发现" }));

  expect(screen.getByRole("button", { name: "正在恢复：雨天的操场" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "正在恢复：足球场边的小发现" })).toBeDisabled();

  await act(async () => {
    firstRestoreRequest.resolve({
      essay_id: "essay-hidden-1",
      title: "雨天的操场",
      status: "revised_once",
      hidden: false,
      hidden_by: "",
      latest_round_index: 2,
      latest_version_id: "version-2",
      last_version_submitted_at: "2026-06-01T08:00:00Z",
      revision_round_count: 1,
      needs_revision: false,
      can_continue_revision: false,
      can_retry_revision_attempt: false,
      summary_label: "已恢复",
    });
  });

  await waitFor(() => expect(fetchParentEssayArchive).toHaveBeenCalledTimes(2));
  expect(screen.getByRole("button", { name: "正在恢复：足球场边的小发现" })).toBeDisabled();

  await act(async () => {
    secondRestoreRequest.resolve({
      essay_id: "essay-hidden-2",
      title: "足球场边的小发现",
      status: "revised_once",
      hidden: false,
      hidden_by: "",
      latest_round_index: 1,
      latest_version_id: "version-1",
      last_version_submitted_at: "2026-06-02T08:00:00Z",
      revision_round_count: 0,
      needs_revision: false,
      can_continue_revision: false,
      can_retry_revision_attempt: false,
      summary_label: "已恢复",
    });
  });

  await waitFor(() => expect(fetchParentEssayArchive).toHaveBeenCalledTimes(3));
  expect(fetchParentEssayArchive).toHaveBeenLastCalledWith("student-1", true, 20);
});

test("parent summary ignores stale archive reloads after overlapping restores", async () => {
  mockPopulatedSummary();
  const firstRestoreRequest = deferred<Awaited<ReturnType<typeof restoreParentEssay>>>();
  const secondRestoreRequest = deferred<Awaited<ReturnType<typeof restoreParentEssay>>>();
  const staleReloadRequest = deferred<Awaited<ReturnType<typeof fetchParentEssayArchive>>>();
  const finalReloadRequest = deferred<Awaited<ReturnType<typeof fetchParentEssayArchive>>>();
  vi.mocked(restoreParentEssay)
    .mockReturnValueOnce(firstRestoreRequest.promise)
    .mockReturnValueOnce(secondRestoreRequest.promise);
  vi.mocked(fetchParentEssayArchive)
    .mockResolvedValueOnce({
      items: [
        {
          essay_id: "essay-hidden-1",
          title: "雨天的操场",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "child",
          latest_round_index: 2,
          latest_version_id: "version-2",
          last_version_submitted_at: "2026-06-01T08:00:00Z",
          revision_round_count: 1,
          needs_revision: false,
          can_continue_revision: false,
          can_retry_revision_attempt: false,
          summary_label: "孩子已隐藏",
        },
        {
          essay_id: "essay-hidden-2",
          title: "足球场边的小发现",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "child",
          latest_round_index: 1,
          latest_version_id: "version-1",
          last_version_submitted_at: "2026-06-02T08:00:00Z",
          revision_round_count: 0,
          needs_revision: true,
          can_continue_revision: true,
          can_retry_revision_attempt: false,
          summary_label: "孩子已隐藏",
        },
      ],
    })
    .mockReturnValueOnce(staleReloadRequest.promise)
    .mockReturnValueOnce(finalReloadRequest.promise);

  await renderSummaryPage();

  await userEvent.click(await screen.findByRole("button", { name: "恢复作文：雨天的操场" }));
  await userEvent.click(screen.getByRole("button", { name: "恢复作文：足球场边的小发现" }));

  await act(async () => {
    firstRestoreRequest.resolve({
      essay_id: "essay-hidden-1",
      title: "雨天的操场",
      status: "revised_once",
      hidden: false,
      hidden_by: "",
      latest_round_index: 2,
      latest_version_id: "version-2",
      last_version_submitted_at: "2026-06-01T08:00:00Z",
      revision_round_count: 1,
      needs_revision: false,
      can_continue_revision: false,
      can_retry_revision_attempt: false,
      summary_label: "已恢复",
    });
  });
  await waitFor(() => expect(fetchParentEssayArchive).toHaveBeenCalledTimes(2));

  await act(async () => {
    secondRestoreRequest.resolve({
      essay_id: "essay-hidden-2",
      title: "足球场边的小发现",
      status: "revised_once",
      hidden: false,
      hidden_by: "",
      latest_round_index: 1,
      latest_version_id: "version-1",
      last_version_submitted_at: "2026-06-02T08:00:00Z",
      revision_round_count: 0,
      needs_revision: false,
      can_continue_revision: false,
      can_retry_revision_attempt: false,
      summary_label: "已恢复",
    });
  });
  await waitFor(() => expect(fetchParentEssayArchive).toHaveBeenCalledTimes(3));

  await act(async () => {
    finalReloadRequest.resolve({ items: [] });
  });
  await waitFor(() => expect(screen.queryByText("足球场边的小发现")).not.toBeInTheDocument());

  await act(async () => {
    staleReloadRequest.resolve({
      items: [
        {
          essay_id: "essay-hidden-2",
          title: "足球场边的小发现",
          status: "hidden_by_child",
          hidden: true,
          hidden_by: "child",
          latest_round_index: 1,
          latest_version_id: "version-1",
          last_version_submitted_at: "2026-06-02T08:00:00Z",
          revision_round_count: 0,
          needs_revision: true,
          can_continue_revision: true,
          can_retry_revision_attempt: false,
          summary_label: "孩子已隐藏",
        },
      ],
    });
  });

  expect(screen.queryByText("足球场边的小发现")).not.toBeInTheDocument();
  expect(fetchParentEssayArchive).toHaveBeenLastCalledWith("student-1", true, 20);
});

test("parent summary preserves AI topic origin label", async () => {
  mockPopulatedSummary();
  vi.mocked(fetchParentEssayArchive).mockResolvedValueOnce({
    items: [
      {
        essay_id: "essay-ai-topic",
        title: "足球场边的小发现",
        status: "needs_revision",
        hidden: false,
        hidden_by: "",
        latest_round_index: 1,
        latest_version_id: "version-1",
        last_version_submitted_at: "2026-06-01T08:00:00Z",
        revision_round_count: 0,
        needs_revision: true,
        can_continue_revision: true,
        can_retry_revision_attempt: false,
        summary_label: "等待第一次修改",
        topic_origin: "ai_topic_idea",
        generated_topic_metadata: {
          topic_origin_label: "AI 出题灵感，孩子选择",
        },
      },
    ],
  });

  await renderSummaryPage();

  expect(await screen.findByText("足球场边的小发现")).toBeInTheDocument();
  expect(screen.getByText("题目来源：AI 出题灵感，孩子选择")).toBeInTheDocument();
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
