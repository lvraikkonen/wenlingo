import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Home from "../src/app/page";

test("renders alpha entry without demo children", () => {
  render(<Home />);

  expect(screen.getByRole("main")).toHaveClass("min-h-screen");
  expect(screen.getByRole("heading", { name: "小文星球" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "进入 Alpha 登录" })).toHaveAttribute(
    "href",
    "/alpha/start",
  );
  expect(screen.queryByRole("link", { name: "小宇" })).not.toBeInTheDocument();
});
