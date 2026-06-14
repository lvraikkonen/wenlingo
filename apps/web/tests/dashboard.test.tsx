import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import DashboardPage from "../src/app/children/[studentId]/page";
import { getDashboard } from "../src/lib/api";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("../src/lib/api", () => ({
  demoLogin: vi.fn(async () => ({
    parent: { id: "p1", email: "demo@example.com", display_name: "演示家长" },
    students: [
      {
        id: "s1",
        name: "小宇",
        grade_label: "四年级",
        persona: "real_child",
        level: 2,
        xp: 115,
      },
      {
        id: "s2",
        name: "小晴",
        grade_label: "三年级",
        persona: "vague_expression",
        level: 1,
        xp: 40,
      },
      {
        id: "s3",
        name: "小川",
        grade_label: "五年级",
        persona: "weak_structure",
        level: 1,
        xp: 35,
      },
      {
        id: "s4",
        name: "小禾",
        grade_label: "四年级",
        persona: "weak_reading_summary",
        level: 1,
        xp: 30,
      },
    ],
  })),
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
}));

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
  expect(screen.getByText("阅读峡谷")).toBeInTheDocument();
  expect(map.getByRole("link", { name: "阅读峡谷" })).toHaveAttribute(
    "href",
    "/children/s1/reading",
  );
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
