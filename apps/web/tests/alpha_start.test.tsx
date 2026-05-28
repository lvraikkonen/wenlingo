import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import AlphaStartPage from "../src/app/alpha/start/page";
import {
  createAlphaParent,
  recordAlphaEvent,
  validateAlphaInvite,
} from "../src/lib/api";
import { ALPHA_PARENT_STORAGE_KEY } from "../src/lib/alphaParent";
import { ALPHA_SESSION_STORAGE_KEY } from "../src/lib/alphaSession";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("../src/lib/api", () => ({
  validateAlphaInvite: vi.fn(async () => ({
    valid: true,
    invite_id: "invite-1",
    label: "家庭 01",
  })),
  createAlphaParent: vi.fn(async () => ({
    parent: { id: "parent-1", email: "alpha@example.com", display_name: "小星家长" },
    children_url: "/parent/children",
  })),
  recordAlphaEvent: vi.fn(async () => undefined),
}));

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  push.mockClear();
  vi.mocked(validateAlphaInvite).mockClear();
  vi.mocked(createAlphaParent).mockClear();
  vi.mocked(recordAlphaEvent).mockClear();
});

test("shows alpha notice before creating a parent", () => {
  render(<AlphaStartPage />);

  expect(screen.getByRole("heading", { name: /小文星球 WenLingo/ })).toBeInTheDocument();
  expect(screen.getByText(/小范围 Alpha 内测/)).toBeInTheDocument();
  expect(screen.getByText(/请不要填写孩子的真实姓名/)).toBeInTheDocument();
  expect(screen.getByText(/出生日期、照片/)).toBeInTheDocument();
  expect(screen.getByText(/孩子的写作内容可能会发送给 AI 服务/)).toBeInTheDocument();
  expect(screen.getByLabelText("内测邀请码")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "继续使用 Alpha" })).toBeInTheDocument();
});

test("creates alpha parent after validating invite stores id and routes to children page", async () => {
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
  render(<AlphaStartPage />);

  fireEvent.change(screen.getByLabelText("家长怎么称呼？"), {
    target: { value: "小星家长" },
  });
  fireEvent.change(screen.getByLabelText("内测邀请码"), {
    target: { value: "ALPHA-001" },
  });
  fireEvent.click(screen.getByRole("button", { name: "继续使用 Alpha" }));

  await waitFor(() => {
    expect(validateAlphaInvite).toHaveBeenCalledWith({
      code: "ALPHA-001",
      alpha_session_id: "session-1",
    });
    expect(createAlphaParent).toHaveBeenCalledWith({
      display_name: "小星家长",
      invite_code: "ALPHA-001",
      alpha_session_id: "session-1",
    });
  });
  expect(vi.mocked(validateAlphaInvite).mock.invocationCallOrder[0]).toBeLessThan(
    vi.mocked(createAlphaParent).mock.invocationCallOrder[0],
  );
  expect(window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY)).toBe("parent-1");
  expect(push).toHaveBeenCalledWith("/parent/children");
});

test("shows invalid invite error without creating parent", async () => {
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
  vi.mocked(validateAlphaInvite).mockRejectedValueOnce(new Error("invalid"));

  render(<AlphaStartPage />);

  fireEvent.change(screen.getByLabelText("内测邀请码"), {
    target: { value: "BAD-CODE" },
  });
  fireEvent.click(screen.getByRole("button", { name: "继续使用 Alpha" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("邀请码无效或已失效");
  expect(createAlphaParent).not.toHaveBeenCalled();
});

test("offers continuing current alpha family when parent id already exists", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-existing");
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");

  render(<AlphaStartPage />);

  expect(await screen.findByText("已经找到这个浏览器里的 Alpha 家庭。")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "继续使用当前 Alpha 家庭" }));

  expect(validateAlphaInvite).not.toHaveBeenCalled();
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
