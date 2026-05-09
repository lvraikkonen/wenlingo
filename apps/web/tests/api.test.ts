import { describe, expect, test, vi } from "vitest";
import { demoLogin, getDashboard } from "../src/lib/api";

describe("api client", () => {
  test("demoLogin reads parent and students", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        parent: { id: "p1", email: "demo@wenlingo.local" },
        students: [{ id: "s1", name: "小宇" }],
      }),
    }) as unknown as typeof fetch;

    const result = await demoLogin();

    expect(result.students[0].name).toBe("小宇");
  });

  test("getDashboard calls student dashboard endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        child_abilities: {
          reading_power: 50,
          specific_writing_power: 54,
          revision_power: 20,
        },
      }),
    }) as unknown as typeof fetch;

    await getDashboard("s1");

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/students/s1/dashboard",
      { cache: "no-store" },
    );
  });
});
