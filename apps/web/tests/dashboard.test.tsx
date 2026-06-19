import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import DashboardPage from "../src/app/children/[studentId]/page";
import { getDashboard, recordAlphaEvent } from "../src/lib/api";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("../src/lib/api", () => ({
  getDashboard: vi.fn(async () => ({
    student: {
      id: "s1",
      name: "小宇",
      grade_label: "四年级",
      persona: "real_child",
      level: 2,
      xp: 115,
    },
    ability_note: "第一张能力草图",
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
  })),
  recordAlphaEvent: vi.fn(async () => undefined),
}));

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

test("renders child dashboard as an action entry", async () => {
  const element = await DashboardPage({ params: Promise.resolve({ studentId: "s1" }) });

  expect(getDashboard).not.toHaveBeenCalled();

  render(element);

  await waitFor(() => expect(getDashboard).toHaveBeenCalledWith("s1"));
  expect(await screen.findByRole("heading", { name: "小宇的小文星球" })).toBeInTheDocument();
  expect(screen.getByText("今日推荐")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "作文城堡" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "主线：作文城堡" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "句子工坊" }),
  ).toBeInTheDocument();
  const map = within(screen.getByRole("navigation", { name: "地图" }));
  expect(map.getByRole("link", { name: "句子工坊" })).toHaveAttribute(
    "href",
    "/children/s1/sentence",
  );
  expect(map.getByRole("link", { name: "作文城堡" })).toHaveAttribute(
    "href",
    "/children/s1/essay",
  );
  expect(screen.getByText("阅读峡谷 · 即将开放")).toBeInTheDocument();
  expect(map.queryByRole("link", { name: "阅读峡谷" })).not.toBeInTheDocument();
  expect(map.queryByRole("link", { name: "阅读峡谷 · 即将开放" })).not.toBeInTheDocument();
  expect(screen.getByText("写具体力")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /去写作文/ })).toHaveAttribute(
    "href",
    "/children/s1/essay",
  );
  expect(screen.getByRole("link", { name: /开始任务/ })).toHaveAttribute(
    "href",
    "/children/s1/sentence",
  );
});

test("records dashboard viewed event without legacy parent localStorage", async () => {
  const element = await DashboardPage({ params: Promise.resolve({ studentId: "s1" }) });

  render(element);

  await waitFor(() => {
    const alphaSessionId = window.localStorage.getItem(
      "wenlingo_alpha_session_id",
    );
    expect(alphaSessionId).toEqual(expect.any(String));
    expect(alphaSessionId).not.toBe("");
    expect(vi.mocked(recordAlphaEvent)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(recordAlphaEvent)).toHaveBeenCalledWith({
      event_type: "child_dashboard_viewed",
      student_id: "s1",
      alpha_session_id: alphaSessionId,
      payload: {
        path: "/children/s1",
        status: "viewed",
      },
    });
  });
  expect(window.localStorage.getItem("wenlingo_alpha_parent_id")).toBeNull();
});
