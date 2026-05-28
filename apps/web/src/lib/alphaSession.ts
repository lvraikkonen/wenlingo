export const ALPHA_SESSION_STORAGE_KEY = "wenlingo_alpha_session_id";

function randomSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `alpha-session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getStoredAlphaSessionId(): string {
  if (typeof window === "undefined") {
    return "";
  }

  try {
    const existing = window.localStorage.getItem(ALPHA_SESSION_STORAGE_KEY);
    if (existing) {
      return existing;
    }

    const next = randomSessionId();
    window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, next);
    return next;
  } catch {
    return "";
  }
}

export function buildAlphaDashboardViewedScript({
  studentId,
  apiBaseUrl,
}: {
  studentId: string;
  apiBaseUrl: string;
}) {
  return `
(() => {
  function randomSessionId() {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
      return crypto.randomUUID();
    }
    return "alpha-session-" + Date.now() + "-" + Math.random().toString(36).slice(2);
  }

  function getStoredAlphaSessionId() {
    try {
      const existing = window.localStorage.getItem("wenlingo_alpha_session_id");
      if (existing) {
        return existing;
      }
      const next = randomSessionId();
      window.localStorage.setItem("wenlingo_alpha_session_id", next);
      return next;
    } catch {
      return "";
    }
  }

  try {
    const parentId = window.localStorage.getItem("wenlingo_alpha_parent_id");
    if (!parentId) {
      return;
    }
    const alphaSessionId = getStoredAlphaSessionId();
    window.fetch(${JSON.stringify(`${apiBaseUrl}/api/alpha/events`)}, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: "child_dashboard_viewed",
        parent_id: parentId,
        student_id: ${JSON.stringify(studentId)},
        alpha_session_id: alphaSessionId,
        payload: {
          path: ${JSON.stringify(`/children/${studentId}`)},
          status: "viewed",
        },
      }),
      cache: "no-store",
    }).catch(() => undefined);
  } catch {
  }
})();
`;
}
