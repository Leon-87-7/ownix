"use client";

import { useEffect, useRef, useState } from "react";
import { EllipsisVertical, Share, SquarePlus, X } from "lucide-react";
import OwnixLogo from "@/app/ownix-logo.svg";
import {
  detectInstallPlatform,
  isStandalone,
  isSuppressed,
  recordDismissal,
  recordInstalled,
  safeStorage,
  takeEarlyInstallEvent,
  type BeforeInstallPromptEvent,
  type InstallPlatform,
} from "@/lib/install-prompt";

// Let the page settle before sliding in — a card racing the first paint
// reads as an interstitial ad, not an offer.
export const SHOW_DELAY_MS = 2500;

/**
 * Mobile "Add to Home Screen" card (iPhone + Android). Non-modal on purpose:
 * it never traps focus or blocks the Feed underneath.
 *
 * Android/Chromium hands us `beforeinstallprompt`, so the button opens the
 * native install dialog. iOS has no install API at all — every iOS browser
 * only installs via Share → Add to Home Screen — so there we show the steps
 * instead of a button that can't do anything. Android browsers that never
 * fire the event (Firefox, or Chrome before it deems the page installable)
 * get the equivalent browser-menu steps.
 */
export default function InstallPrompt() {
  const [platform, setPlatform] = useState<InstallPlatform>(null);
  const [visible, setVisible] = useState(false);
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(
    null,
  );
  const titleId = "install-prompt-title";
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Installs can also happen through the browser's own menu, including
    // while the card is snoozed — always record them so it never returns.
    const onInstalled = () => {
      recordInstalled(safeStorage());
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }
      setVisible(false);
    };
    window.addEventListener("appinstalled", onInstalled);

    const detected = detectInstallPlatform(navigator);
    if (
      !detected ||
      isStandalone(window) ||
      isSuppressed(safeStorage(), Date.now())
    ) {
      return () => window.removeEventListener("appinstalled", onInstalled);
    }

    const onBeforeInstall = (event: Event) => {
      // Suppress Chrome's own mini-infobar; our card is the one offer.
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    timer.current = setTimeout(() => {
      // An event that arrived live already won; only fall back to the stash.
      setDeferred((live) => live ?? takeEarlyInstallEvent(window));
      setPlatform(detected);
      setVisible(true);
    }, SHOW_DELAY_MS);

    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  if (!platform || !visible) return null;

  function dismiss() {
    recordDismissal(safeStorage(), Date.now());
    setVisible(false);
  }

  async function install() {
    if (!deferred) return;
    await deferred.prompt();
    const { outcome } = await deferred.userChoice;
    // The event is single-use either way.
    setDeferred(null);
    if (outcome === "accepted") {
      recordInstalled(safeStorage());
      setVisible(false);
    } else {
      dismiss();
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      className="fixed inset-x-3 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-[60] mx-auto max-w-md rounded-2xl border border-line bg-surface p-4 shadow-overlay contrast-more:border-line-strong motion-safe:animate-slide-up-in"
    >
      <button
        type="button"
        onClick={dismiss}
        className="absolute right-2 top-2 inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted transition-ui hover:bg-raised hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
      >
        <X className="h-4 w-4" aria-hidden="true" />
        <span className="sr-only">Not now</span>
      </button>

      <div className="flex items-center gap-3 pr-10">
        <OwnixLogo
          aria-hidden="true"
          focusable="false"
          className="h-11 w-11 shrink-0"
        />
        <h2 id={titleId} className="text-base font-semibold text-ink">
          Add Ownix to your Home Screen
        </h2>
      </div>

      <p className="mt-3 border-t border-line pt-3 text-sm leading-6 text-body">
        {platform === "android"
          ? "Open Ownix in one tap, full screen, and share links to it straight from any app."
          : "Open Ownix in one tap, full screen, like any other app."}
      </p>

      {platform === "android" && deferred ? (
        <button
          type="button"
          onClick={() => void install()}
          className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-signal px-4 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
        >
          <SquarePlus className="h-4 w-4" aria-hidden="true" />
          Add to Home Screen
        </button>
      ) : (
        <ol className="mt-3 space-y-2 text-sm text-body">
          {platform === "ios" ? (
            <>
              <Step n={1}>
                Tap
                <Share
                  className="mx-1 inline h-4 w-4 text-ink"
                  aria-label="Share"
                />
                in your browser&rsquo;s toolbar
              </Step>
              <Step n={2}>
                Choose
                <SquarePlus
                  className="mx-1 inline h-4 w-4 text-ink"
                  aria-hidden="true"
                />
                <span className="font-medium text-ink">Add to Home Screen</span>
              </Step>
            </>
          ) : (
            <>
              <Step n={1}>
                Open the browser menu
                <EllipsisVertical
                  className="mx-1 inline h-4 w-4 text-ink"
                  aria-hidden="true"
                />
              </Step>
              <Step n={2}>
                Choose <span className="font-medium text-ink">Install app</span>{" "}
                or{" "}
                <span className="font-medium text-ink">Add to Home screen</span>
              </Step>
            </>
          )}
        </ol>
      )}
    </div>
  );
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-raised font-mono text-xs text-ink">
        {n}
      </span>
      <span>{children}</span>
    </li>
  );
}
