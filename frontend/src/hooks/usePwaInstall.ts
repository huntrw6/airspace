import { useSyncExternalStore } from "react";
import {
  getNativeInstallSnapshot,
  promptNativeInstall,
  subscribeNativeInstall,
  type InstallResult,
} from "../lib/pwa/install-store";
import { detectPlatform, isLikelyEmbeddedBrowser, type Platform } from "../lib/pwa/platform";

export type PwaInstallState = {
  canInstallNatively: boolean;
  isInstalled: boolean;
  platform: Platform;
  isEmbeddedBrowser: boolean;
  promptInstall: () => Promise<InstallResult>;
};

const serverSnapshot = { canInstallNatively: false, isInstalled: false };

export function usePwaInstall(): PwaInstallState {
  const native = useSyncExternalStore(
    subscribeNativeInstall,
    getNativeInstallSnapshot,
    () => serverSnapshot,
  );
  return {
    ...native,
    platform: detectPlatform(),
    isEmbeddedBrowser: isLikelyEmbeddedBrowser(),
    promptInstall: promptNativeInstall,
  };
}
