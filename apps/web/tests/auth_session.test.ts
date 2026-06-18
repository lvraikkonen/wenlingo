import { afterEach, beforeEach, expect, test, vi } from "vitest";

function mockJsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.resetModules();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => mockJsonResponse({ authenticated: false })),
  );
});

afterEach(() => {
  vi.unstubAllEnvs();
});

test("getAuthSession requests current auth session with cookies and no cache", async () => {
  const { getAuthSession } = await import("../src/lib/authSession");

  await getAuthSession();

  expect(fetch).toHaveBeenCalledWith(
    "/api/auth/session",
    expect.objectContaining({
      credentials: "include",
      cache: "no-store",
    }),
  );
});

test("getAuthSession treats /api override as same-origin auth path", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "/api");
  const { getAuthSession } = await import("../src/lib/authSession");

  await getAuthSession();

  expect(fetch).toHaveBeenCalledWith(
    "/api/auth/session",
    expect.objectContaining({
      credentials: "include",
      cache: "no-store",
    }),
  );
});

test("requestMagicCode posts email request with cookies", async () => {
  const { requestMagicCode } = await import("../src/lib/authSession");

  await requestMagicCode({
    email: "parent@example.com",
    alpha_session_id: "session-1",
  });

  expect(fetch).toHaveBeenCalledWith(
    "/api/auth/magic-codes/request",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "parent@example.com",
        alpha_session_id: "session-1",
      }),
    }),
  );
});

test("verifyMagicCode posts code with cookies", async () => {
  const { verifyMagicCode } = await import("../src/lib/authSession");

  await verifyMagicCode({
    email: "parent@example.com",
    code: "123456",
  });

  expect(fetch).toHaveBeenCalledWith(
    "/api/auth/magic-codes/verify",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "parent@example.com",
        code: "123456",
      }),
    }),
  );
});
