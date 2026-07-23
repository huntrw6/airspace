import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { usePwaInstall } from "../../hooks/usePwaInstall";
import { shouldShowInstallPrompt } from "../../lib/pwa/install-state";
import {
  INSTALL_PROMPT_STORAGE_KEY,
  clearDismissal,
  isDismissalActive,
  saveDismissal,
} from "../../lib/pwa/storage";
import { PwaInstallPrompt } from "./PwaInstallPrompt";

type InstallUiContext = {
  isInstalled: boolean;
  platform: ReturnType<typeof usePwaInstall>["platform"];
  setInstallPromptEligible: (eligible: boolean) => void;
  showInstallPrompt: () => void;
};

const Context = createContext<InstallUiContext | null>(null);

export function PwaInstallProvider({ children }: { children: ReactNode }) {
  const install = usePwaInstall();
  const [eligible, setEligible] = useState(false);
  const [explicit, setExplicit] = useState(false);
  const [dismissed, setDismissed] = useState(() => isDismissalActive());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const storageChanged = (event: StorageEvent) => {
      if (event.key === INSTALL_PROMPT_STORAGE_KEY) setDismissed(isDismissalActive());
    };
    window.addEventListener("storage", storageChanged);
    return () => window.removeEventListener("storage", storageChanged);
  }, []);
  useEffect(() => {
    if (install.isInstalled) {
      clearDismissal();
      setDismissed(false);
      setExplicit(false);
    }
  }, [install.isInstalled]);

  const showInstallPrompt = useCallback(() => {
    setExplicit(true);
  }, []);
  const dismiss = useCallback(() => {
    saveDismissal();
    setDismissed(true);
    setExplicit(false);
  }, []);
  const runNativeInstall = useCallback(async () => {
    if (busy) return "unavailable" as const;
    setBusy(true);
    const result = await install.promptInstall();
    setBusy(false);
    if (result === "accepted") {
      clearDismissal();
      setExplicit(false);
    } else if (result === "dismissed") {
      setDismissed(true);
      setExplicit(false);
    }
    return result;
  }, [busy, install]);

  const visible = shouldShowInstallPrompt({
    installed: install.isInstalled,
    explicit,
    eligible,
    dismissed,
    canInstallNatively: install.canInstallNatively,
    platform: install.platform,
    embedded: install.isEmbeddedBrowser,
  });
  const value = useMemo(
    () => ({
      isInstalled: install.isInstalled,
      platform: install.platform,
      setInstallPromptEligible: setEligible,
      showInstallPrompt,
    }),
    [install.isInstalled, install.platform, showInstallPrompt],
  );

  return (
    <Context.Provider value={value}>
      {children}
      <PwaInstallPrompt
        visible={visible}
        platform={install.platform}
        embedded={install.isEmbeddedBrowser}
        canInstallNatively={install.canInstallNatively}
        busy={busy}
        onInstall={runNativeInstall}
        onDismiss={dismiss}
      />
    </Context.Provider>
  );
}

export function usePwaInstallUi(): InstallUiContext {
  const value = useContext(Context);
  if (!value) throw new Error("usePwaInstallUi must be used inside PwaInstallProvider");
  return value;
}
