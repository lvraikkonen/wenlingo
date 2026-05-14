import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import DashboardPage from "../src/app/children/[studentId]/page";
import { getDashboard } from "../src/lib/api";

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
  render(await DashboardPage({ params: Promise.resolve({ studentId: "s1" }) }));

  expect(getDashboard).toHaveBeenCalledWith("s1");
  expect(screen.getByRole("heading", { name: "小宇的小文星球" })).toBeInTheDocument();
  expect(screen.getByText("今日推荐")).toBeInTheDocument();
  expect(screen.getByText("作文城堡")).toBeInTheDocument();
  expect(screen.getByText("句子工坊")).toBeInTheDocument();
  expect(screen.getByText("阅读峡谷")).toBeInTheDocument();
  expect(screen.getByText("写具体力")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /去写作文/ })).toHaveAttribute(
    "href",
    "/children/s1/essay",
  );
});
