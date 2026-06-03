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
import {
  getAuthSession,
  requestMagicCode,
  verifyMagicCode,
} from "../src/lib/authSession";

const push = vi.fn();
const router = { push };

vi.mock("next/navigation", () => ({
  useRouter: () => router,
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

vi.mock("../src/lib/authSession", () => ({
  getAuthSession: vi.fn(async () => ({ authenticated: false })),
  requestMagicCode: vi.fn(async () => ({ message: "sent" })),
  verifyMagicCode: vi.fn(async () => ({
    authenticated: true,
    account: {
      email_masked: "a***@example.com",
      phone_bound: false,
      last_login_at: null,
    },
    parent: null,
  })),
}));

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  push.mockClear();
  vi.mocked(getAuthSession).mockReset();
  vi.mocked(getAuthSession).mockResolvedValue({ authenticated: false });
  vi.mocked(requestMagicCode).mockClear();
  vi.mocked(verifyMagicCode).mockClear();
  vi.mocked(validateAlphaInvite).mockClear();
  vi.mocked(createAlphaParent).mockClear();
  vi.mocked(recordAlphaEvent).mockClear();
});

test("shows alpha notice before creating a parent", async () => {
  render(<AlphaStartPage />);

  expect(screen.getByRole("heading", { name: /小文星球 WenLingo/ })).toBeInTheDocument();
  expect(await screen.findByText(/小范围 Alpha 内测/)).toBeInTheDocument();
  expect(screen.getByText(/请不要填写孩子的真实姓名/)).toBeInTheDocument();
  expect(screen.getByText(/出生日期、照片/)).toBeInTheDocument();
  expect(screen.getByText(/孩子的写作内容可能会发送给 AI 服务/)).toBeInTheDocument();
  expect(screen.getByLabelText("内测邀请码")).toBeInTheDocument();
  expect(screen.getByLabelText("邮箱")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "获取验证码" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "继续使用 Alpha" })).toBeInTheDocument();
});

test("creates alpha parent after validating invite and email code stores id and routes to children page", async () => {
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
  render(<AlphaStartPage />);

  fireEvent.change(await screen.findByLabelText("家长怎么称呼？"), {
    target: { value: "小星家长" },
  });
  fireEvent.change(screen.getByLabelText("内测邀请码"), {
    target: { value: "ALPHA-001" },
  });
  fireEvent.change(screen.getByLabelText("邮箱"), {
    target: { value: "alpha@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: "获取验证码" }));

  await waitFor(() => {
    expect(validateAlphaInvite).toHaveBeenCalledWith({
      code: "ALPHA-001",
      alpha_session_id: "session-1",
    });
    expect(requestMagicCode).toHaveBeenCalledWith({
      email: "alpha@example.com",
      alpha_session_id: "session-1",
    });
  });

  fireEvent.change(await screen.findByLabelText("6 位验证码"), {
    target: { value: "123456" },
  });
  fireEvent.click(screen.getByRole("button", { name: "继续使用 Alpha" }));

  await waitFor(() => {
    expect(verifyMagicCode).toHaveBeenCalledWith({
      email: "alpha@example.com",
      code: "123456",
    });
    expect(createAlphaParent).toHaveBeenCalledWith({
      display_name: "小星家长",
      invite_code: "ALPHA-001",
      alpha_session_id: "session-1",
    });
  });
  expect(vi.mocked(validateAlphaInvite).mock.invocationCallOrder[0]).toBeLessThan(
    vi.mocked(requestMagicCode).mock.invocationCallOrder[0],
  );
  expect(vi.mocked(requestMagicCode).mock.invocationCallOrder[0]).toBeLessThan(
    vi.mocked(verifyMagicCode).mock.invocationCallOrder[0],
  );
  expect(vi.mocked(verifyMagicCode).mock.invocationCallOrder[0]).toBeLessThan(
    vi.mocked(createAlphaParent).mock.invocationCallOrder[0],
  );
  expect(window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY)).toBe("parent-1");
  expect(push).toHaveBeenCalledWith("/parent/children");
});

test("shows invalid invite error without creating parent", async () => {
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
  vi.mocked(validateAlphaInvite).mockRejectedValueOnce(new Error("invalid"));

  render(<AlphaStartPage />);

  fireEvent.change(await screen.findByLabelText("内测邀请码"), {
    target: { value: "BAD-CODE" },
  });
  fireEvent.change(screen.getByLabelText("邮箱"), {
    target: { value: "alpha@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: "获取验证码" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("邀请码无效或已失效");
  expect(requestMagicCode).not.toHaveBeenCalled();
  expect(createAlphaParent).not.toHaveBeenCalled();
});

test("offers email binding for current alpha family when parent id already exists", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-existing");
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");

  render(<AlphaStartPage />);

  expect(
    await screen.findByText("绑定邮箱继续使用当前 Alpha 家庭"),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("邮箱")).toBeInTheDocument();

  expect(validateAlphaInvite).not.toHaveBeenCalled();
  expect(createAlphaParent).not.toHaveBeenCalled();
  expect(push).not.toHaveBeenCalled();
});

test("restart action clears current alpha family id", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-existing");

  render(<AlphaStartPage />);
  await screen.findByText("绑定邮箱继续使用当前 Alpha 家庭");
  fireEvent.click(screen.getByRole("button", { name: "重新创建 Alpha 家庭" }));

  expect(window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY)).toBeNull();
  expect(screen.getByRole("button", { name: "继续使用 Alpha" })).toBeInTheDocument();
});
