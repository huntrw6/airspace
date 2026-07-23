import { installedDisplayModeQueries, isRunningAsInstalledPwa } from "./install-state";
import { clearDismissal, saveDismissal } from "./storage";

export type InstallResult = "accepted" | "dismissed" | "unavailable" | "error";

export type NativeInstallSnapshot = {
  canInstallNatively: boolean;
  isInstalled: boolean;
};

let deferredPrompt: BeforeInstallPromptEvent | null = null;
let snapshot: NativeInstallSnapshot = {
  canInstallNatively: false,
  isInstalled: isRunningAsInstalledPwa(),
};
const listeners = new Set<() => void>();

function emit(): void {
  snapshot = {
    canInstallNatively: Boolean(deferredPrompt),
    isInstalled: isRunningAsInstalledPwa() || snapshot.isInstalled,
  };
  listeners.forEach((listener) => listener());
}

export function getNativeInstallSnapshot(): NativeInstallSnapshot {
  return snapshot;
}

export function subscribeNativeInstall(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function promptNativeInstall(): Promise<InstallResult> {
  const event = deferredPrompt;
  if (!event || snapshot.isInstalled) return "unavailable";
  deferredPrompt = null;
  emit();
  try {
    await event.prompt();
    const choice = await event.userChoice;
    if (choice.outcome === "accepted") {
      snapshot = { canInstallNatively: false, isInstalled: true };
      clearDismissal();
      emit();
      return "accepted";
    }
    saveDismissal();
    emit();
    return "dismissed";
  } catch (error) {
    console.warn("AirSpace native installation prompt failed", error);
    emit();
    return "error";
  }
}

export function initializeInstallEventCapture(): () => void {
  if (typeof window === "undefined") return () => {};
  const beforeInstall = (event: BeforeInstallPromptEvent) => {
    event.preventDefault();
    if (snapshot.isInstalled || isRunningAsInstalledPwa()) return;
    deferredPrompt = event;
    emit();
  };
  const installed = () => {
    deferredPrompt = null;
    snapshot = { canInstallNatively: false, isInstalled: true };
    clearDismissal();
    emit();
  };
  const mediaQueries = typeof window.matchMedia === "function"
    ? installedDisplayModeQueries().map((query) => window.matchMedia(query))
    : [];
  const displayModeChanged = () => emit();
  window.addEventListener("beforeinstallprompt", beforeInstall);
  window.addEventListener("appinstalled", installed);
  mediaQueries.forEach((query) => query.addEventListener?.("change", displayModeChanged));
  return () => {
    window.removeEventListener("beforeinstallprompt", beforeInstall);
    window.removeEventListener("appinstalled", installed);
    mediaQueries.forEach((query) => query.removeEventListener?.("change", displayModeChanged));
  };
}

initializeInstallEventCapture();
