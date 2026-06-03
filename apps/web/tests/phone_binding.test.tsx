import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import ParentChildrenPage from "../src/app/parent/children/page";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  replace.mockClear();
  window.localStorage.clear();
});

test("parent can bind an optional phone from children page", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/auth/account/phone")) {
      return {
        ok: true,
        json: async () => ({
          phone_masked: "138****1234",
          phone_bound: true,
        }),
      };
    }
    if (url.includes("/api/alpha/events")) {
      return { ok: true, json: async () => undefined };
    }
    return {
      ok: true,
      json: async () => ({
        parent: { id: "parent-1", display_name: "Alpha 家长" },
        account: { email_masked: "pa***@example.com", phone_bound: false },
        children: [],
      }),
    };
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<ParentChildrenPage />);

  const phoneInput = await screen.findByLabelText("手机号（可选）");
  fireEvent.change(phoneInput, { target: { value: "13800001234" } });
  fireEvent.click(screen.getByRole("button", { name: "保存手机号" }));

  expect(await screen.findByText("已绑定 138****1234")).toBeInTheDocument();
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/account/phone"),
      expect.objectContaining({
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: "13800001234" }),
      }),
    );
  });
});
