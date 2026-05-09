import { afterEach, describe, expect, test, vi } from "vitest";
import { demoLogin, getDashboard } from "../src/lib/api";
import type { DashboardResponse, DemoLoginResponse } from "../src/lib/types";

const student = {
  id: "s1",
  name: "小宇",
  grade_label: "三年级",
  persona: "real_child",
  level: 3,
  xp: 120,
} satisfies DemoLoginResponse["students"][number];

const demoLoginResponse = {
  parent: {
    id: "p1",
    email: "demo@wenlingo.local",
    display_name: "Demo Parent",
  },
  students: [student],
} satisfies DemoLoginResponse;

const dashboardResponse = {
  student,
  ability_note: "阅读理解稳定，表达可以继续具体化。",
  child_abilities: {
    reading_power: 50,
    specific_writing_power: 54,
    revision_power: 20,
  },
  today_tasks: {
    main: {
      kind: "essay",
      title: "把经历写具体",
      focus: "动作和感受",
      minutes: "20",
    },
    quick: {
      kind: "reading",
      title: "读短文找线索",
      focus: "概括重点",
      minutes: "8",
    },
  },
  map: ["阅读", "表达", "修改"],
  coach_message: "今天先完成主线任务，再做快速练习。",
} satisfies DashboardResponse;

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("demoLogin reads parent and students", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => demoLoginResponse,
    }) as unknown as typeof fetch;

    const result = await demoLogin();

    expect(result.parent.email).toBe("demo@wenlingo.local");
    expect(result.students[0].name).toBe("小宇");
  });

  test("getDashboard calls student dashboard endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => dashboardResponse,
    }) as unknown as typeof fetch;

    await getDashboard("s1");

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/students/s1/dashboard",
      { cache: "no-store" },
    );
  });

  test("throws when the API response is not ok", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;

    await expect(demoLogin()).rejects.toThrow("Request failed: 500");
  });
});
