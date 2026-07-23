// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import {
  getNativeInstallSnapshot,
  promptNativeInstall,
} from "./install-store";

function installEvent(
  outcome: "accepted" | "dismissed",
  options: { promptRejects?: boolean; choiceRejects?: boolean } = {},
) {
  const event = new Event("beforeinstallprompt", { cancelable: true }) as BeforeInstallPromptEvent;
  const prompt = options.promptRejects
    ? vi.fn(async () => { throw new Error("prompt unavailable"); })
    : vi.fn(async () => {});
  Object.defineProperties(event, {
    platforms: { value: ["web"] },
    prompt: { value: prompt },
    userChoice: {
      value: options.choiceRejects
        ? Promise.reject(new Error("choice unavailable"))
        : Promise.resolve({ outcome, platform: "web" }),
    },
  });
  return { event, prompt };
}

it("captures, consumes, and clears each native install event exactly once", async () => {
  const dismissed = installEvent("dismissed");
  window.dispatchEvent(dismissed.event);
  expect(dismissed.event.defaultPrevented).toBe(true);
  expect(getNativeInstallSnapshot().canInstallNatively).toBe(true);
  expect(dismissed.prompt).not.toHaveBeenCalled();

  expect(await promptNativeInstall()).toBe("dismissed");
  expect(dismissed.prompt).toHaveBeenCalledTimes(1);
  expect(await promptNativeInstall()).toBe("unavailable");
  expect(dismissed.prompt).toHaveBeenCalledTimes(1);

  const failedPrompt = installEvent("accepted", { promptRejects: true });
  window.dispatchEvent(failedPrompt.event);
  expect(await promptNativeInstall()).toBe("error");
  expect(await promptNativeInstall()).toBe("unavailable");

  const failedChoice = installEvent("accepted", { choiceRejects: true });
  window.dispatchEvent(failedChoice.event);
  expect(await promptNativeInstall()).toBe("error");
  expect(await promptNativeInstall()).toBe("unavailable");

  const accepted = installEvent("accepted");
  window.dispatchEvent(accepted.event);
  expect(getNativeInstallSnapshot().canInstallNatively).toBe(true);
  expect(await promptNativeInstall()).toBe("accepted");
  expect(accepted.prompt).toHaveBeenCalledTimes(1);
  expect(getNativeInstallSnapshot().isInstalled).toBe(true);

  window.dispatchEvent(new Event("appinstalled"));
  expect(getNativeInstallSnapshot()).toEqual({
    canInstallNatively: false,
    isInstalled: true,
  });
});
