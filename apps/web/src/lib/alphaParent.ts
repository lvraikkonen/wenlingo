export const ALPHA_PARENT_STORAGE_KEY = "wenlingo_alpha_parent_id";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getStoredAlphaParentId(): string | null {
  if (!canUseStorage()) {
    return null;
  }
  return window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY);
}

export function setStoredAlphaParentId(parentId: string) {
  if (canUseStorage()) {
    window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, parentId);
  }
}

export function clearStoredAlphaParentId() {
  if (canUseStorage()) {
    window.localStorage.removeItem(ALPHA_PARENT_STORAGE_KEY);
  }
}
