import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { FamilyTopbar } from "../src/components/FamilyTopbar";
import { demoLogin, getAlphaChildren } from "../src/lib/api";
import { ALPHA_PARENT_STORAGE_KEY } from "../src/lib/alphaParent";

const students = vi.hoisted(() => [
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
    name: "小林",
    grade_label: "四年级",
    persona: "weak_reading_summary",
    level: 1,
    xp: 30,
  },
]);

vi.mock("../src/lib/api", () => ({
  demoLogin: vi.fn(async () => ({
    parent: { id: "p1", email: "demo@example.com", display_name: "演示家长" },
    students,
  })),
  getAlphaChildren: vi.fn(async () => ({
    parent: { id: "alpha-parent-1", display_name: "小星家长" },
    children: [
      {
        id: "alpha-student-1",
        name: "小星",
        grade_label: "四年级",
        persona: "real_child",
        level: 1,
        xp: 0,
        assessment_completed: false,
        dashboard_url: "/children/alpha-student-1",
        summary_url: "/parent/children/alpha-student-1/summary",
      },
    ],
  })),
}));

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

test("renders family navigation and child switcher for current student", async () => {
  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：小宇")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "小文星球" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
  expect(screen.getByRole("link", { name: "作文城堡" })).toHaveAttribute(
    "href",
    "/children/s1/essay",
  );
  expect(screen.getByRole("link", { name: "句子工坊" })).toHaveAttribute(
    "href",
    "/children/s1/sentence",
  );
  expect(screen.getByRole("link", { name: "家长报告" })).toHaveAttribute(
    "href",
    "/parent/s1/report",
  );
  expect(screen.getByRole("link", { name: "小晴" })).toHaveAttribute(
    "href",
    "/children/s2",
  );
});

test("renders simplified alpha navigation without demo children", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "alpha-parent-1");

  render(<FamilyTopbar currentStudentId="alpha-student-1" />);

  expect(await screen.findByText("当前孩子：小星")).toBeInTheDocument();
  expect(getAlphaChildren).toHaveBeenCalledWith("alpha-parent-1");
  expect(demoLogin).not.toHaveBeenCalled();
  expect(screen.queryByRole("link", { name: "小晴" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "返回孩子列表" })).toHaveAttribute(
    "href",
    "/parent/children",
  );
  expect(screen.getByRole("link", { name: "小文星球" })).toHaveAttribute(
    "href",
    "/children/alpha-student-1",
  );
});
