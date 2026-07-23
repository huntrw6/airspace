// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import {
  installedDisplayModeQueries,
  isRunningAsInstalledPwa,
  shouldShowInstallPrompt,
} from "./install-state";
import { detectPlatform, isLikelyEmbeddedBrowser } from "./platform";
import {
  INSTALL_PROMPT_COOLDOWN_MS,
  INSTALL_PROMPT_STORAGE_KEY,
  clearDismissal,
  isDismissalActive,
  readDismissal,
  saveDismissal,
} from "./storage";

afterEach(() => {
  clearDismissal(localStorage);
  Object.defineProperty(navigator, "standalone", { configurable: true, value: undefined });
});

describe("platform detection", () => {
  it("detects iPhone and iPad user agents", () => {
    expect(detectPlatform({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)" })).toBe("ios");
    expect(detectPlatform({ userAgent: "Mozilla/5.0 (iPad; CPU OS 18_0)" })).toBe("ios");
  });

  it("detects an iPad using a desktop-style user agent", () => {
    expect(detectPlatform({ userAgent: "Mozilla/5.0 Safari", platform: "MacIntel", maxTouchPoints: 5 })).toBe("ios");
  });

  it("detects Android, desktop, and unknown platforms", () => {
    expect(detectPlatform({ userAgent: "Mozilla/5.0 (Linux; Android 15)" })).toBe("android");
    expect(detectPlatform({ userAgent: "Mozilla/5.0 (Windows NT 10.0)", platform: "Win32" })).toBe("desktop");
    expect(detectPlatform({ userAgent: "MysteryBrowser", platform: "MysteryOS" })).toBe("unknown");
  });

  it("recognizes common embedded browsers", () => {
    expect(isLikelyEmbeddedBrowser("Mozilla/5.0 Instagram 320")).toBe(true);
    expect(isLikelyEmbeddedBrowser("Mozilla/5.0 Safari/605.1")).toBe(false);
  });
});

describe("installed mode", () => {
  it("detects standalone display mode", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: (query: string) => ({ matches: query === "(display-mode: standalone)" }),
    });
    expect(isRunningAsInstalledPwa()).toBe(true);
  });

  it("detects the iOS standalone property", () => {
    Object.defineProperty(navigator, "standalone", { configurable: true, value: true });
    expect(isRunningAsInstalledPwa()).toBe(true);
  });

  it("does not classify a normal tab or missing matchMedia as installed", () => {
    Object.defineProperty(window, "matchMedia", { configurable: true, value: undefined });
    expect(isRunningAsInstalledPwa()).toBe(false);
    expect(installedDisplayModeQueries()).toContain("(display-mode: standalone)");
  });
});

describe("dismissal storage and visibility", () => {
  it("applies and expires the seven-day cooldown", () => {
    const now = new Date("2026-07-22T12:00:00Z");
    saveDismissal(localStorage, now);
    expect(isDismissalActive(localStorage, now.getTime() + INSTALL_PROMPT_COOLDOWN_MS - 1)).toBe(true);
    expect(isDismissalActive(localStorage, now.getTime() + INSTALL_PROMPT_COOLDOWN_MS)).toBe(false);
  });

  it("ignores invalid local-storage data", () => {
    localStorage.setItem(INSTALL_PROMPT_STORAGE_KEY, "not-json");
    expect(readDismissal(localStorage)).toBeNull();
    expect(isDismissalActive(localStorage)).toBe(false);
  });

  it("fails safely when storage is unavailable", () => {
    const unavailable = {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => { throw new Error("blocked"); },
      removeItem: () => { throw new Error("blocked"); },
    } as unknown as Storage;
    expect(readDismissal(unavailable)).toBeNull();
    expect(() => saveDismissal(unavailable)).not.toThrow();
    expect(() => clearDismissal(unavailable)).not.toThrow();
  });

  it("hides installed and cooled-down prompts but allows an explicit settings request", () => {
    const defaults = {
      explicit: false,
      eligible: true,
      dismissed: false,
      canInstallNatively: true,
      platform: "desktop" as const,
      embedded: false,
    };
    expect(shouldShowInstallPrompt({ ...defaults, installed: true })).toBe(false);
    expect(shouldShowInstallPrompt({ ...defaults, installed: false, dismissed: true })).toBe(false);
    expect(shouldShowInstallPrompt({ ...defaults, installed: false, dismissed: true, explicit: true })).toBe(true);
    expect(shouldShowInstallPrompt({ ...defaults, installed: false, canInstallNatively: false })).toBe(false);
  });
});
