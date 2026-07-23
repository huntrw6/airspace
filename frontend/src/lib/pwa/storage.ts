export const INSTALL_PROMPT_STORAGE_KEY = "airspace:pwa-install-prompt:v1";
export const INSTALL_PROMPT_VERSION = 1;
export const INSTALL_PROMPT_COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;

type DismissalRecord = { dismissedAt: string; promptVersion: number };

function availableStorage(storage?: Storage | null): Storage | null {
  if (storage !== undefined) return storage;
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readDismissal(storage?: Storage | null): DismissalRecord | null {
  try {
    const raw = availableStorage(storage)?.getItem(INSTALL_PROMPT_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const record = parsed as Partial<DismissalRecord>;
    if (
      record.promptVersion !== INSTALL_PROMPT_VERSION ||
      typeof record.dismissedAt !== "string" ||
      !Number.isFinite(Date.parse(record.dismissedAt))
    ) return null;
    return { dismissedAt: record.dismissedAt, promptVersion: record.promptVersion };
  } catch {
    return null;
  }
}

export function isDismissalActive(
  storage?: Storage | null,
  now = Date.now(),
): boolean {
  const record = readDismissal(storage);
  return Boolean(record && now - Date.parse(record.dismissedAt) < INSTALL_PROMPT_COOLDOWN_MS);
}

export function saveDismissal(storage?: Storage | null, now = new Date()): void {
  try {
    availableStorage(storage)?.setItem(
      INSTALL_PROMPT_STORAGE_KEY,
      JSON.stringify({ dismissedAt: now.toISOString(), promptVersion: INSTALL_PROMPT_VERSION }),
    );
  } catch {
    // Installation guidance must never break the application when storage is blocked.
  }
}

export function clearDismissal(storage?: Storage | null): void {
  try {
    availableStorage(storage)?.removeItem(INSTALL_PROMPT_STORAGE_KEY);
  } catch {
    // Ignore unavailable or privacy-restricted storage.
  }
}
