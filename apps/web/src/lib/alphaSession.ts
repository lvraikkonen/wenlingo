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
