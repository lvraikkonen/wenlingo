import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { FamilyTopbar } from "../src/components/FamilyTopbar";
import { demoLogin, getMyAlphaChildren } from "../src/lib/api";

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
  getMyAlphaChildren: vi.fn(),
}));

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
  vi.mocked(getMyAlphaChildren).mockResolvedValue({
    parent: { id: "parent-1", email: "parent@example.com", display_name: "小星家长" },
    children: [
      {
        id: "s1",
        nickname: "小宇",
        name: "小宇",
        grade_label: "四年级",
        persona: "real_child",
        is_real_child: true,
        dashboard_url: "/children/s1",
        summary_url: "/parent/children/s1/summary",
        assessment_completed: false,
      },
    ],
  });
});

test("renders family navigation and child switcher for current student", async () => {
  vi.mocked(getMyAlphaChildren).mockRejectedValueOnce({ status: 401 });

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
  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：小宇")).toBeInTheDocument();
  expect(demoLogin).not.toHaveBeenCalled();
  expect(screen.queryByRole("link", { name: "小晴" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "返回孩子列表" })).toHaveAttribute(
    "href",
    "/parent/children",
  );
  expect(screen.getByRole("link", { name: "小文星球" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
});

test("keeps demo family navigation for canonical demo children under auth", async () => {
  vi.mocked(getMyAlphaChildren).mockResolvedValueOnce({
    parent: { id: "p1", email: "demo@wenlingo.local", display_name: "内测家长" },
    children: students.map((student) => ({
      ...student,
      nickname: student.name,
      is_real_child: student.id === "s1",
      dashboard_url: `/children/${student.id}`,
      summary_url: `/parent/children/${student.id}/summary`,
      assessment_completed: false,
    })),
  });

  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：小宇")).toBeInTheDocument();
  expect(demoLogin).not.toHaveBeenCalled();
  expect(screen.getByLabelText("主导航")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "小晴" })).toHaveAttribute(
    "href",
    "/children/s2",
  );
});

test("falls back to demo navigation when session parent has no children", async () => {
  vi.mocked(getMyAlphaChildren).mockResolvedValueOnce({
    parent: { id: "parent-empty", email: "parent@example.com", display_name: "小星家长" },
    children: [],
  });

  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：小宇")).toBeInTheDocument();
  expect(demoLogin).toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "小晴" })).toHaveAttribute(
    "href",
    "/children/s2",
  );
});

test("does not mask unexpected alpha children failures as demo navigation", async () => {
  vi.mocked(getMyAlphaChildren).mockRejectedValueOnce({ status: 500 });

  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：s1")).toBeInTheDocument();
  expect(demoLogin).not.toHaveBeenCalled();
  expect(screen.queryByRole("link", { name: "小晴" })).not.toBeInTheDocument();
});
