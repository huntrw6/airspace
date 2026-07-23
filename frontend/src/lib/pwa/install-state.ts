const INSTALLED_DISPLAY_MODES = [
  "standalone",
  "fullscreen",
  "minimal-ui",
  "window-controls-overlay",
] as const;

export function isRunningAsInstalledPwa(): boolean {
  if (typeof window === "undefined" || typeof navigator === "undefined") return false;
  if (navigator.standalone === true) return true;
  if (typeof window.matchMedia !== "function") return false;
  return INSTALLED_DISPLAY_MODES.some(
    (mode) => window.matchMedia(`(display-mode: ${mode})`).matches,
  );
}

export function installedDisplayModeQueries(): string[] {
  return INSTALLED_DISPLAY_MODES.map((mode) => `(display-mode: ${mode})`);
}

export function shouldShowInstallPrompt(options: {
  installed: boolean;
  explicit: boolean;
  eligible: boolean;
  dismissed: boolean;
  canInstallNatively: boolean;
  platform: "ios" | "android" | "desktop" | "unknown";
  embedded: boolean;
}): boolean {
  if (options.installed) return false;
  const useful =
    options.canInstallNatively ||
    options.platform === "ios" ||
    options.platform === "android" ||
    options.embedded ||
    options.explicit;
  return useful && (options.explicit || (options.eligible && !options.dismissed));
}

export function requiresInstalledPwaForLocation(
  platform: "ios" | "android" | "desktop" | "unknown",
  installed: boolean,
): boolean {
  return platform === "ios" && !installed;
}
