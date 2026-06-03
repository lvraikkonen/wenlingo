import { afterEach, describe, expect, test, vi } from "vitest";
import {
  createAlphaChild,
  createAlphaParent,
  getAlphaChildSummary,
  getAlphaChildren,
  recordAlphaEvent,
  validateAlphaInvite,
} from "../src/lib/api";
import {
  ALPHA_PARENT_STORAGE_KEY,
  clearStoredAlphaParentId,
  getStoredAlphaParentId,
  setStoredAlphaParentId,
} from "../src/lib/alphaParent";
import {
  ALPHA_SESSION_STORAGE_KEY,
  buildAlphaDashboardViewedScript,
  getStoredAlphaSessionId,
} from "../src/lib/alphaSession";

describe("alpha api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  test("createAlphaParent posts display name", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        parent: {
          id: "parent-1",
          email: "alpha-parent@example.com",
          display_name: "小星家长",
        },
        children_url: "/parent/children",
      }),
    }) as unknown as typeof fetch;

    const result = await createAlphaParent({
      display_name: "小星家长",
      invite_code: "ALPHA-001",
      alpha_session_id: "session-1",
    });

    expect(result.parent.id).toBe("parent-1");
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: "小星家长",
          invite_code: "ALPHA-001",
          alpha_session_id: "session-1",
        }),
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("getStoredAlphaSessionId creates and reuses wenlingo_alpha_session_id", () => {
    const first = getStoredAlphaSessionId();

    expect(first).toBeTruthy();
    expect(window.localStorage.getItem(ALPHA_SESSION_STORAGE_KEY)).toBe(first);
    expect(getStoredAlphaSessionId()).toBe(first);
  });

  test("validateAlphaInvite posts code and alpha_session_id", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        valid: true,
        invite_id: "invite-1",
        label: "家庭 01",
      }),
    }) as unknown as typeof fetch;

    const result = await validateAlphaInvite({
      code: "ALPHA-001",
      alpha_session_id: "session-1",
    });

    expect(result.valid).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/invites/validate",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: "ALPHA-001", alpha_session_id: "session-1" }),
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("recordAlphaEvent posts only event metadata", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => undefined,
    }) as unknown as typeof fetch;

    await recordAlphaEvent({
      event_type: "child_handoff_clicked",
      parent_id: "parent-1",
      student_id: "student-1",
      alpha_session_id: "session-1",
      payload: {
        path: "/parent/children",
        status: "clicked",
        child_count: 1,
        has_completed_assessment: false,
      },
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/events",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: "child_handoff_clicked",
          parent_id: "parent-1",
          student_id: "student-1",
          alpha_session_id: "session-1",
          payload: {
            path: "/parent/children",
            status: "clicked",
            child_count: 1,
            has_completed_assessment: false,
          },
        }),
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("recordAlphaEvent resolves without throwing when fetch fails", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down"));

    await expect(
      recordAlphaEvent({
        event_type: "summary_viewed",
        parent_id: "parent-1",
        student_id: "student-1",
        alpha_session_id: "session-1",
        payload: { path: "/summary", status: "viewed" },
      }),
    ).resolves.toBeUndefined();
  });

  test("child dashboard event script creates an alpha session when one is missing", () => {
    window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-1");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    }) as unknown as typeof fetch;

    const script = buildAlphaDashboardViewedScript({
      studentId: "student-1",
      apiBaseUrl: "http://localhost:8000",
    });

    window.eval(script);

    const alphaSessionId = window.localStorage.getItem(ALPHA_SESSION_STORAGE_KEY);
    expect(alphaSessionId).toBeTruthy();
    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/api/alpha/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: "child_dashboard_viewed",
        parent_id: "parent-1",
        student_id: "student-1",
        alpha_session_id: alphaSessionId,
        payload: {
          path: "/children/student-1",
          status: "viewed",
        },
      }),
      cache: "no-store",
    });
  });

  test("getAlphaChildren calls parent-scoped children endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        parent: {
          id: "parent-1",
          email: "alpha-parent@example.com",
          display_name: "小星家长",
        },
        children: [
          {
            id: "student-1",
            nickname: "小星",
            name: "小星",
            grade_label: "四年级",
            persona: "real_child",
            is_real_child: true,
            dashboard_url: "/children/student-1",
            summary_url: "/parent/children/student-1/summary",
            assessment_completed: false,
          },
        ],
      }),
    }) as unknown as typeof fetch;

    const result = await getAlphaChildren("parent-1");

    expect(result.children[0].id).toBe("student-1");

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents/parent-1/children",
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("createAlphaChild posts nickname and grade", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        child: {
          id: "student-1",
          nickname: "小星",
          name: "小星",
          grade_label: "四年级",
          persona: "real_child",
          is_real_child: true,
          dashboard_url: "/children/student-1",
          summary_url: "/parent/children/student-1/summary",
        },
        dashboard_url: "/children/student-1",
        summary_url: "/parent/children/student-1/summary",
      }),
    }) as unknown as typeof fetch;

    const result = await createAlphaChild("parent-1", { nickname: "小星", grade: 4 });

    expect(result.child.id).toBe("student-1");

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents/parent-1/children",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname: "小星", grade: 4 }),
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  test("getAlphaChildSummary calls parent-scoped summary endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        parent_id: "parent-1",
        child: {
          id: "student-1",
          nickname: "小星",
          name: "小星",
          grade_label: "四年级",
          persona: "real_child",
          is_real_child: true,
          dashboard_url: "/children/student-1",
          summary_url: "/parent/children/student-1/summary",
          assessment_completed: false,
        },
        assessment_completed: false,
        practice_counts: { assessments: 0, sentence_trainings: 0, essays: 0 },
        ability_changes: [
          { ability: "reading_power", label: "阅读力", delta: 0 },
        ],
        recent_highlight: null,
        next_suggestion: "先完成入门小试炼，生成第一张能力草图。",
        empty_state: "还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。",
      }),
    }) as unknown as typeof fetch;

    const result = await getAlphaChildSummary("parent-1", "student-1");

    expect(result.parent_id).toBe("parent-1");
    expect(result.child.id).toBe("student-1");
    expect(result.ability_changes[0].ability).toBe("reading_power");

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/alpha/parents/parent-1/children/student-1/summary",
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
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

  test("alpha parent storage helper degrades when localStorage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(getStoredAlphaParentId()).toBeNull();

    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(() => setStoredAlphaParentId("parent-1")).not.toThrow();
    expect(() => clearStoredAlphaParentId()).not.toThrow();
  });
});
