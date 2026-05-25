import { afterEach, describe, expect, test, vi } from "vitest";
import {
  createAlphaChild,
  createAlphaParent,
  getAlphaChildSummary,
  getAlphaChildren,
} from "../src/lib/api";
import {
  ALPHA_PARENT_STORAGE_KEY,
  clearStoredAlphaParentId,
  getStoredAlphaParentId,
  setStoredAlphaParentId,
} from "../src/lib/alphaParent";

describe("alpha api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  test("createAlphaParent posts display name", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        parent: { id: "parent-1", display_name: "小星家长" },
        children_url: "/parent/children",
      }),
    }) as unknown as typeof fetch;

    const result = await createAlphaParent({ display_name: "小星家长" });

    expect(result.parent.id).toBe("parent-1");
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: "小星家长" }),
        cache: "no-store",
      },
    );
  });

  test("getAlphaChildren calls parent-scoped children endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        parent: { id: "parent-1", display_name: "小星家长" },
        children: [],
      }),
    }) as unknown as typeof fetch;

    await getAlphaChildren("parent-1");

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents/parent-1/children",
      { cache: "no-store" },
    );
  });

  test("createAlphaChild posts nickname and grade", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        student: {
          id: "student-1",
          name: "小星",
          grade_label: "四年级",
          persona: "real_child",
          level: 1,
          xp: 0,
        },
        dashboard_url: "/children/student-1",
        summary_url: "/parent/children/student-1/summary",
      }),
    }) as unknown as typeof fetch;

    await createAlphaChild("parent-1", { nickname: "小星", grade: 4 });

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents/parent-1/children",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname: "小星", grade: 4 }),
        cache: "no-store",
      },
    );
  });

  test("getAlphaChildSummary calls parent-scoped summary endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        student: {
          id: "student-1",
          name: "小星",
          grade_label: "四年级",
          persona: "real_child",
          level: 1,
          xp: 0,
        },
        assessment_completed: false,
        practice_counts: { assessments: 0, sentence_trainings: 0, essays: 0 },
        ability_changes: [],
        recent_highlight: null,
        next_suggestion: "先完成入门小试炼，生成第一张能力草图。",
        empty_state: "还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。",
      }),
    }) as unknown as typeof fetch;

    await getAlphaChildSummary("parent-1", "student-1");

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents/parent-1/children/student-1/summary",
      { cache: "no-store" },
    );
  });

  test("alpha parent storage helper stores clears and reads the parent id", () => {
    expect(getStoredAlphaParentId()).toBeNull();

    setStoredAlphaParentId("parent-1");

    expect(window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY)).toBe("parent-1");
    expect(getStoredAlphaParentId()).toBe("parent-1");

    clearStoredAlphaParentId();

    expect(getStoredAlphaParentId()).toBeNull();
  });
});
