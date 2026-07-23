export type Platform = "ios" | "android" | "desktop" | "unknown";

export type PlatformSignals = {
  userAgent?: string;
  platform?: string;
  maxTouchPoints?: number;
  mobileHint?: boolean;
};

export function browserSignals(): PlatformSignals {
  if (typeof navigator === "undefined") return {};
  return {
    userAgent: navigator.userAgent,
    platform: navigator.userAgentData?.platform || navigator.platform,
    maxTouchPoints: navigator.maxTouchPoints,
    mobileHint: navigator.userAgentData?.mobile,
  };
}

export function detectPlatform(signals: PlatformSignals = browserSignals()): Platform {
  const userAgent = signals.userAgent || "";
  const platform = signals.platform || "";
  const iPadDesktopMode = /Mac/i.test(platform) && (signals.maxTouchPoints || 0) > 1;
  if (/iPhone|iPad|iPod/i.test(userAgent) || iPadDesktopMode) return "ios";
  if (/Android/i.test(userAgent) || /Android/i.test(platform)) return "android";
  if (
    signals.mobileHint === false ||
    /Windows|Mac|Linux|CrOS|X11/i.test(`${userAgent} ${platform}`)
  ) return "desktop";
  return "unknown";
}

export function isLikelyEmbeddedBrowser(userAgent?: string): boolean {
  const value = userAgent ?? (typeof navigator === "undefined" ? "" : navigator.userAgent);
  return /FBAN|FBAV|Instagram|Line\/|LinkedInApp|MicroMessenger|Snapchat|TikTok|Twitter|GSA\/|wv\)/i.test(value);
}

export function isIosSafari(userAgent?: string): boolean {
  const value = userAgent ?? (typeof navigator === "undefined" ? "" : navigator.userAgent);
  return /Safari/i.test(value) && !/CriOS|FxiOS|EdgiOS|OPiOS|DuckDuckGo/i.test(value);
}
