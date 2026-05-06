import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Home from "../src/app/page";

test("renders the parent entry", () => {
  render(<Home />);

  expect(screen.getByRole("heading", { name: "小文星球" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "进入家庭内测" })).toBeInTheDocument();
});
