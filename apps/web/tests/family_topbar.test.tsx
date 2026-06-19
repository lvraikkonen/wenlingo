import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { FamilyTopbar } from "../src/components/FamilyTopbar";
import { getMyAlphaChildren } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
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

test("renders simplified alpha navigation without demo children", async () => {
  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：小宇")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "小晴" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "返回孩子列表" })).toHaveAttribute(
    "href",
    "/parent/children",
  );
  expect(screen.getByRole("link", { name: "家长摘要" })).toHaveAttribute(
    "href",
    "/parent/children/s1/summary",
  );
  expect(screen.getByRole("link", { name: "家长报告" })).toHaveAttribute(
    "href",
    "/parent/s1/report",
  );
  expect(screen.getByRole("link", { name: "小文星球" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
});

test("does not fall back to demo navigation when session parent has no children", async () => {
  vi.mocked(getMyAlphaChildren).mockResolvedValueOnce({
    parent: { id: "parent-empty", email: "parent@example.com", display_name: "小星家长" },
    children: [],
  });

  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：s1")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "小晴" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "返回孩子列表" })).toHaveAttribute(
    "href",
    "/parent/children",
  );
});

test("does not render seeded demo children after unauthorized alpha children response", async () => {
  vi.mocked(getMyAlphaChildren).mockRejectedValueOnce({ status: 401 });

  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：s1")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "小晴" })).not.toBeInTheDocument();
});

test("does not mask unexpected alpha children failures as demo navigation", async () => {
  vi.mocked(getMyAlphaChildren).mockRejectedValueOnce({ status: 500 });

  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：s1")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "小晴" })).not.toBeInTheDocument();
});
