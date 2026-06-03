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
  expect(screen.getByRole("link", { name: "进入孩子空间" })).toHaveAttribute(
    "href",
    "/children/student-1",
  );
});

test("summary page renders an error state when summary loading fails", async () => {
  vi.mocked(getMyAlphaChildSummary).mockRejectedValue(new Error("boom"));

  await renderSummaryPage();

  expect(await screen.findByRole("alert")).toHaveTextContent("成长摘要加载失败，请稍后再试。");
});
