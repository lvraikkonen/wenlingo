import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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

describe("parent auth handling", () => {
  it("redirects to alpha start on 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 401 }),
    );

    render(<ParentChildrenPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/alpha/start"));
  });

  it("loads children from session-scoped endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        parent: { id: "parent-1", display_name: "Alpha 家长" },
        children: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ParentChildrenPage />);

    await screen.findByText("还没有孩子档案。");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/alpha/parents/me/children"),
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
