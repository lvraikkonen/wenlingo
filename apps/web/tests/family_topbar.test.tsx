import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { FamilyTopbar } from "../src/components/FamilyTopbar";

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
}));

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
