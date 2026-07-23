// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PwaInstallPrompt } from "./PwaInstallPrompt";

const base = {
  visible: true,
  embedded: false,
  canInstallNatively: false,
  busy: false,
  onInstall: vi.fn(async () => "accepted" as const),
  onDismiss: vi.fn(),
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PWA installation prompt", () => {
  it("renders nothing when hidden", () => {
    render(<PwaInstallPrompt {...base} visible={false} platform="ios" />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows original iPhone instructions without a fake native install button", () => {
    Object.defineProperty(navigator, "userAgent", {
      configurable: true,
      value: "Mozilla/5.0 (iPhone) AppleWebKit/605.1 Version/18.0 Mobile Safari/604.1",
    });
    render(<PwaInstallPrompt {...base} platform="ios" />);
    expect(screen.getByText("Tap the ··· menu")).toBeTruthy();
    expect(screen.getByText("Tap Share")).toBeTruthy();
    expect(screen.getByText("Add to Home Screen")).toBeTruthy();
    expect(screen.getByText("Open AirSpace")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Install AirSpace" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(base.onDismiss).toHaveBeenCalledOnce();
  });

  it("shows Android native install only when a real event is available", () => {
    const { rerender } = render(<PwaInstallPrompt {...base} platform="android" />);
    expect(screen.queryByRole("button", { name: "Install AirSpace" })).toBeNull();
    expect(screen.getByText(/browser menu/i)).toBeTruthy();
    rerender(<PwaInstallPrompt {...base} platform="android" canInstallNatively />);
    fireEvent.click(screen.getByRole("button", { name: "Install AirSpace" }));
    expect(base.onInstall).toHaveBeenCalledOnce();
  });

  it("shows desktop native action only when supported", () => {
    const { rerender } = render(<PwaInstallPrompt {...base} platform="desktop" />);
    expect(screen.queryByRole("button", { name: "Install AirSpace" })).toBeNull();
    rerender(<PwaInstallPrompt {...base} platform="desktop" canInstallNatively />);
    expect(screen.getByRole("button", { name: "Install AirSpace" })).toBeTruthy();
  });

  it("disables the native action while a prompt is active", () => {
    render(<PwaInstallPrompt {...base} platform="android" canInstallNatively busy />);
    expect((screen.getByRole("button", { name: /Opening browser prompt/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("provides embedded-browser guidance and keyboard dismissal", () => {
    render(<PwaInstallPrompt {...base} platform="android" embedded />);
    expect(screen.getByText(/inside this app/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy link" })).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(base.onDismiss).toHaveBeenCalledOnce();
  });

  it("always exposes the textual sequence used by the reduced-motion layout", () => {
    Object.defineProperty(navigator, "userAgent", {
      configurable: true,
      value: "Mozilla/5.0 (iPad) AppleWebKit/605.1 Version/18.0 Mobile Safari/604.1",
    });
    render(<PwaInstallPrompt {...base} platform="ios" />);
    expect(screen.getByLabelText(/Five steps/).querySelectorAll("li")).toHaveLength(5);
  });
});
