import { describe, expect, test } from "vitest";
import { parseSseFrames, reduceStreamEvent } from "../src/lib/sse";

describe("SSE transport helpers", () => {
  test("parses event name and JSON data", () => {
    expect(
      parseSseFrames('event: start\ndata: {"seq":1,"stage":"draft"}\n\n'),
    ).toEqual([
      {
        event: "start",
        data: { seq: 1, stage: "draft" },
      },
    ]);
  });

  test("ignores comment heartbeats and frames without data", () => {
    expect(
      parseSseFrames(
        ': heartbeat\n\nevent: progress\n\nevent: message\ndata: {"seq":2}\n\n',
      ),
    ).toEqual([{ event: "message", data: { seq: 2 } }]);
  });

  test("reduceStreamEvent ignores duplicate seq numbers by returning the same state object", () => {
    const current = reduceStreamEvent(undefined, {
      event: "feedback_section_preview",
      data: {
        seq: 2,
        section: "strengths",
        items: ["开头很清楚"],
      },
    });

    const duplicate = reduceStreamEvent(current, {
      event: "feedback_section_preview",
      data: {
        seq: 2,
        section: "strengths",
        items: ["不应该覆盖"],
      },
    });

    expect(duplicate).toBe(current);
  });
});
