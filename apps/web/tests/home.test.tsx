import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import Home from "../src/app/page";
import { demoLogin } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  demoLogin: vi.fn(async () => ({
    parent: {
      id: "p1",
      email: "demo@wenlingo.local",
      display_name: "内测家长",
    },
    students: [
      {
        id: "s1",
        name: "小宇",
        grade_label: "四年级",
        persona: "real_child",
        level: 1,
        xp: 0,
      },
      {
        id: "s2",
        name: "小晴",
        grade_label: "四年级",
        persona: "vague_expression",
        level: 1,
        xp: 0,
      },
      {
        id: "s3",
        name: "小川",
        grade_label: "四年级",
        persona: "weak_structure",
        level: 1,
        xp: 0,
      },
      {
        id: "s4",
        name: "小禾",
        grade_label: "四年级",
        persona: "weak_reading_summary",
        level: 1,
        xp: 0,
      },
    ],
  })),
}));

test("renders the parent entry and demo children", async () => {
  render(<Home />);

  expect(screen.getByRole("main")).toHaveClass("min-h-screen");
  expect(screen.getByRole("heading", { name: "小文星球" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "进入家庭内测" }));

  expect(demoLogin).toHaveBeenCalled();
  expect(await screen.findByRole("link", { name: "小宇" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
  expect(screen.getByRole("link", { name: "小晴" })).toHaveAttribute(
    "href",
    "/children/s2",
  );
  expect(screen.getByRole("link", { name: "小川" })).toHaveAttribute(
    "href",
    "/children/s3",
  );
  expect(screen.getByRole("link", { name: "小禾" })).toHaveAttribute(
    "href",
    "/children/s4",
  );
});
