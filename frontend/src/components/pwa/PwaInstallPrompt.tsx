import { useEffect, useRef, useState } from "react";
import type { InstallResult } from "../../lib/pwa/install-store";
import { isIosSafari, type Platform } from "../../lib/pwa/platform";
import { IosInstallGuide } from "./IosInstallGuide";

type Props = {
  visible: boolean;
  platform: Platform;
  embedded: boolean;
  canInstallNatively: boolean;
  busy: boolean;
  onInstall: () => Promise<InstallResult>;
  onDismiss: () => void;
};

export function PwaInstallPrompt({
  visible,
  platform,
  embedded,
  canInstallNatively,
  busy,
  onInstall,
  onDismiss,
}: Props) {
  const closeButton = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!visible) return;
    previousFocus.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onDismiss();
    };
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("keydown", escape);
      previousFocus.current?.focus();
    };
  }, [visible, onDismiss]);

  if (!visible) return null;
  const iosNeedsSafari = platform === "ios" && (embedded || !isIosSafari());
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setMessage("Link copied. Open Safari or your usual browser and paste it there.");
    } catch {
      setMessage("Copy this page’s address, then open it in Safari or your usual browser.");
    }
  };
  const shareLink = async () => {
    try {
      await navigator.share({ title: "AirSpace", url: window.location.href });
    } catch {
      // Closing the system share sheet is not an installation error.
    }
  };

  return (
    <aside
      className="pwa-install-sheet"
      role="dialog"
      aria-modal="false"
      aria-labelledby="pwa-install-title"
      aria-describedby="pwa-install-description"
    >
      <button
        ref={closeButton}
        type="button"
        className="pwa-install-close"
        aria-label="Dismiss AirSpace installation prompt"
        onClick={onDismiss}
      >
        ×
      </button>
      <div className="pwa-install-heading">
        <img src="/icons/icon-192.png" alt="" />
        <div>
          <p className="eyebrow">AIRSPACE APP</p>
          <h2 id="pwa-install-title">
            {platform === "ios" ? "Add AirSpace to your Home Screen" : "Install AirSpace"}
          </h2>
        </div>
      </div>
      <p id="pwa-install-description">
        Install AirSpace for quicker access and plane notifications. Installation and notification
        permission are separate—you stay in control of both.
      </p>

      {iosNeedsSafari ? (
        <p className="pwa-install-note">
          Open this link in Safari to install AirSpace, then use Safari’s Share menu.
        </p>
      ) : platform === "ios" ? (
        <IosInstallGuide />
      ) : embedded ? (
        <p className="pwa-install-note">
          Installation may not work inside this app. Open the link in Chrome or your normal browser.
        </p>
      ) : platform === "android" && !canInstallNatively ? (
        <p className="pwa-install-note">
          Open your browser menu and choose <strong>Install app</strong> or{" "}
          <strong>Add to Home screen</strong>.
        </p>
      ) : platform === "desktop" && !canInstallNatively ? (
        <p className="pwa-install-note">
          Your browser has not offered app installation. Look for Install in its address bar or menu.
        </p>
      ) : null}

      <div className="pwa-install-actions">
        {canInstallNatively && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void onInstall()}
          >
            {busy ? "Opening browser prompt…" : "Install AirSpace"}
          </button>
        )}
        {platform === "ios" && !iosNeedsSafari && (
          <button type="button" onClick={onDismiss}>Got it</button>
        )}
        {(embedded || iosNeedsSafari) && (
          <>
            <button type="button" onClick={() => void copyLink()}>Copy link</button>
            {typeof navigator.share === "function" && (
              <button type="button" className="quiet" onClick={() => void shareLink()}>
                Share link
              </button>
            )}
          </>
        )}
        {!canInstallNatively && platform !== "ios" && !embedded && (
          <button type="button" className="quiet" onClick={onDismiss}>Not now</button>
        )}
      </div>
      {message && <p className="pwa-install-result" role="status">{message}</p>}
    </aside>
  );
}
