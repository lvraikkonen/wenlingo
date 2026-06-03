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

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  push.mockClear();
  vi.mocked(validateAlphaInvite).mockClear();
  vi.mocked(createAlphaParent).mockClear();
  vi.mocked(recordAlphaEvent).mockClear();
  vi.unstubAllGlobals();
});

test("redirects authenticated session with linked parent to children page", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      jsonResponse({
        authenticated: true,
        account: {
          email_masked: "p***@example.com",
          phone_bound: false,
          last_login_at: null,
        },
        parent: { id: "parent-1", display_name: "小星家长" },
      }),
    ),
  );

  render(<AlphaStartPage />);

  await waitFor(() => {
    expect(push).toHaveBeenCalledWith("/parent/children");
  });
});

test("shows legacy email binding prompt for unauthenticated session with stored parent id", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "legacy-parent-1");
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ authenticated: false })));

  render(<AlphaStartPage />);

  expect(
    await screen.findByText("绑定邮箱继续使用当前 Alpha 家庭"),
  ).toBeInTheDocument();
});

test("requests code, verifies code, binds legacy parent, then routes to children page", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "legacy-parent-1");
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");
  const fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      fetchCalls.push({ url, init });

      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: false });
      }
      if (url.endsWith("/api/auth/magic-codes/request")) {
        return jsonResponse({ message: "sent" });
      }
      if (url.endsWith("/api/auth/magic-codes/verify")) {
        return jsonResponse({
          authenticated: true,
          account: {
            email_masked: "p***@example.com",
            phone_bound: false,
            last_login_at: null,
          },
          parent: null,
        });
      }
      if (url.endsWith("/api/alpha/legacy-parent-bind")) {
        return jsonResponse({
          parent: { id: "legacy-parent-1", display_name: "旧 Alpha 家庭" },
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }),
  );

  render(<AlphaStartPage />);

  fireEvent.change(await screen.findByLabelText("邮箱"), {
    target: { value: "parent@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: "获取验证码" }));

  await waitFor(() => {
    expect(
      fetchCalls.some((call) =>
        call.url.endsWith("/api/auth/magic-codes/request"),
      ),
    ).toBe(true);
  });

  fireEvent.change(await screen.findByLabelText("6 位验证码"), {
    target: { value: "123456" },
  });
  fireEvent.click(screen.getByRole("button", { name: "绑定并继续" }));

  await waitFor(() => {
    expect(push).toHaveBeenCalledWith("/parent/children");
  });

  const calledPaths = fetchCalls.map((call) => new URL(call.url).pathname);
  expect(calledPaths).toEqual([
    "/api/auth/session",
    "/api/auth/magic-codes/request",
    "/api/auth/magic-codes/verify",
    "/api/alpha/legacy-parent-bind",
  ]);
  expect(fetchCalls[3].init).toEqual(
    expect.objectContaining({
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ legacy_parent_id: "legacy-parent-1" }),
    }),
  );
});
