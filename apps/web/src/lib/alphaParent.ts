export const ALPHA_PARENT_STORAGE_KEY = "wenlingo_alpha_parent_id";

function getStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

export function getStoredAlphaParentId(): string | null {
  const storage = getStorage();
  if (!storage) {
    return null;
  }

  try {
    return storage.getItem(ALPHA_PARENT_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredAlphaParentId(parentId: string) {
  const storage = getStorage();
  if (!storage) {
    return;
  }

  try {
    storage.setItem(ALPHA_PARENT_STORAGE_KEY, parentId);
  } catch {
    // Ignore storage failures so blocked/private storage does not break alpha entry.
  }
}

export function clearStoredAlphaParentId() {
  const storage = getStorage();
  if (!storage) {
    return;
  }

  try {
    storage.removeItem(ALPHA_PARENT_STORAGE_KEY);
  } catch {
    // Ignore storage failures so blocked/private storage does not break alpha entry.
  }
}
