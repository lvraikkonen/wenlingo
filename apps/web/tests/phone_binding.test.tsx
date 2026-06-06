import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import ParentChildrenPage from "../src/app/parent/children/page";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

afterEach(() => {
  cleanup();
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

test("bound phone initially hides input until edit is requested", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        parent: { id: "parent-1", display_name: "Alpha 家长" },
        account: {
          email_masked: "pa***@example.com",
          phone_bound: true,
          phone_masked: "138****1234",
        },
        children: [],
      }),
    })),
  );

  render(<ParentChildrenPage />);

  expect(await screen.findByText("已绑定 138****1234")).toBeInTheDocument();
  expect(screen.queryByLabelText("手机号（可选）")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "修改手机号" }));
  expect(screen.getByLabelText("手机号（可选）")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
});

test("phone edit failure keeps form open and preserves typed phone", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/auth/account/phone")) {
      return { ok: false, json: async () => ({ detail: "failed" }) };
    }
    return {
      ok: true,
      json: async () => ({
        parent: { id: "parent-1", display_name: "Alpha 家长" },
        account: {
          email_masked: "pa***@example.com",
          phone_bound: true,
          phone_masked: "138****1234",
        },
        children: [],
      }),
    };
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<ParentChildrenPage />);

  await screen.findByText("已绑定 138****1234");
  fireEvent.click(screen.getByRole("button", { name: "修改手机号" }));
  const input = screen.getByLabelText("手机号（可选）");
  fireEvent.change(input, { target: { value: "13900001234" } });
  fireEvent.click(screen.getByRole("button", { name: "保存手机号" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "手机号保存失败，请稍后再试。",
  );
  expect(screen.getByLabelText("手机号（可选）")).toHaveValue("13900001234");
});

test("phone edit disables cancel while save is pending", async () => {
  let resolvePhoneSave: (
    value: { phone_masked: string; phone_bound: boolean },
  ) => void = () => {};
  const phoneSave = new Promise<{ phone_masked: string; phone_bound: boolean }>(
    (resolve) => {
      resolvePhoneSave = resolve;
    },
  );
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/auth/account/phone")) {
      return {
        ok: true,
        json: async () => phoneSave,
      };
    }
    return {
      ok: true,
      json: async () => ({
        parent: { id: "parent-1", display_name: "Alpha 家长" },
        account: {
          email_masked: "pa***@example.com",
          phone_bound: true,
          phone_masked: "138****1234",
        },
        children: [],
      }),
    };
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<ParentChildrenPage />);

  await screen.findByText("已绑定 138****1234");
  fireEvent.click(screen.getByRole("button", { name: "修改手机号" }));
  fireEvent.change(screen.getByLabelText("手机号（可选）"), {
    target: { value: "13900001234" },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存手机号" }));

  expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "保存中..." })).toBeInTheDocument();

  resolvePhoneSave({ phone_masked: "139****1234", phone_bound: true });

  expect(await screen.findByText("已绑定 139****1234")).toBeInTheDocument();
});
