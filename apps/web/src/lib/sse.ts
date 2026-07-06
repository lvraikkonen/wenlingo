export type SseFrame = { event: string; data: Record<string, unknown> };

export function parseSseFrames(chunk: string): SseFrame[] {
  const normalized = chunk.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  return normalized
    .split("\n\n")
    .map((frame) => frame.trimEnd())
    .filter((frame) => frame.length > 0)
    .flatMap((frame) => {
      const lines = frame.split("\n");
      if (lines.every((line) => line.startsWith(":"))) {
        return [];
      }

      let event = "message";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith(":")) {
          continue;
        }
        if (line.startsWith("event:")) {
          event = line.slice("event:".length).trim();
          continue;
        }
        if (line.startsWith("data:")) {
          dataLines.push(line.slice("data:".length).trimStart());
        }
      }

      if (dataLines.length === 0) {
        return [];
      }

      return [{ event, data: JSON.parse(dataLines.join("\n")) }];
    });
}

export type StreamReducerState = {
  lastSeq: number;
  sections: Record<string, string[]>;
  done: boolean;
  fetchUrl: string | null;
};

const initialState: StreamReducerState = {
  lastSeq: 0,
  sections: {},
  done: false,
  fetchUrl: null,
};

function getSeq(data: Record<string, unknown>, fallback: number): number {
  return typeof data.seq === "number" ? data.seq : fallback;
}

export function reduceStreamEvent(
  state: StreamReducerState | undefined,
  frame: SseFrame,
): StreamReducerState {
  const current = state ?? initialState;
  const seq = getSeq(frame.data, current.lastSeq);

  if (seq <= current.lastSeq) {
    return current;
  }

  if (frame.event === "feedback_section_preview") {
    const section =
      typeof frame.data.section === "string" ? frame.data.section : "";
    const items = Array.isArray(frame.data.items)
      ? frame.data.items.filter((item): item is string => typeof item === "string")
      : [];

    return {
      ...current,
      lastSeq: seq,
      sections: {
        ...current.sections,
        [section]: items,
      },
    };
  }

  if (frame.event === "done") {
    const result =
      typeof frame.data.result === "object" && frame.data.result !== null
        ? frame.data.result
        : {};
    const fetchUrl =
      "fetch_url" in result && typeof result.fetch_url === "string"
        ? result.fetch_url
        : null;

    return {
      ...current,
      lastSeq: seq,
      done: true,
      fetchUrl,
    };
  }

  return {
    ...current,
    lastSeq: seq,
  };
}
