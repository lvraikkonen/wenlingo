import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import AlphaStartPage from "../src/app/alpha/start/page";
import { createAlphaParent } from "../src/lib/api";
import { ALPHA_PARENT_STORAGE_KEY } from "../src/lib/alphaParent";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("../src/lib/api", () => ({
  createAlphaParent: vi.fn(async () => ({
    parent: { id: "parent-1", display_name: "小星家长" },
    children_url: "/parent/children",
  })),
}));

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  push.mockClear();
  vi.mocked(createAlphaParent).mockClear();
});

test("shows alpha notice before creating a parent", () => {
  render(<AlphaStartPage />);

  expect(screen.getByRole("heading", { name: /小文星球 WenLingo/ })).toBeInTheDocument();
  expect(screen.getByText(/小范围 Alpha 内测/)).toBeInTheDocument();
  expect(screen.getByText(/请不要填写孩子的真实姓名/)).toBeInTheDocument();
  expect(screen.getByText(/出生日期、照片/)).toBeInTheDocument();
  expect(screen.getByText(/孩子的写作内容可能会发送给 AI 服务/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "继续使用 Alpha" })).toBeInTheDocument();
});

test("creates alpha parent stores id and routes to children page", async () => {
  render(<AlphaStartPage />);

  fireEvent.change(screen.getByLabelText("家长怎么称呼？"), {
    target: { value: "小星家长" },
  });
  fireEvent.click(screen.getByRole("button", { name: "继续使用 Alpha" }));

  await waitFor(() => {
    expect(createAlphaParent).toHaveBeenCalledWith({ display_name: "小星家长" });
  });
  expect(window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY)).toBe("parent-1");
  expect(push).toHaveBeenCalledWith("/parent/children");
});

test("offers continuing current alpha family when parent id already exists", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-existing");

  render(<AlphaStartPage />);

  expect(await screen.findByText("已经找到这个浏览器里的 Alpha 家庭。")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "继续使用当前 Alpha 家庭" }));

  expect(createAlphaParent).not.toHaveBeenCalled();
  expect(push).toHaveBeenCalledWith("/parent/children");
});

test("restart action clears current alpha family id", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-existing");

  render(<AlphaStartPage />);
  await screen.findByText("已经找到这个浏览器里的 Alpha 家庭。");
  fireEvent.click(screen.getByRole("button", { name: "重新创建 Alpha 家庭" }));

  expect(window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY)).toBeNull();
  expect(screen.getByRole("button", { name: "继续使用 Alpha" })).toBeInTheDocument();
});
