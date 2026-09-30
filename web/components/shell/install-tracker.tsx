"use client";

import { useEffect } from "react";
import { recordInstalled, safeStorage } from "@/lib/install-prompt";

/**
 * Site-wide, passive: records an install made through the browser's own UI on
 * any route (e.g. from "/"), so the dashboard's InstallPrompt never later
 * offers an app that's already installed. Unlike public/install-capture.js it
 * never touches beforeinstallprompt, so public routes keep Chrome's native offer.
 */
export default function InstallTracker() {
  useEffect(() => {
    const onInstalled = () => recordInstalled(safeStorage());
    window.addEventListener("appinstalled", onInstalled);
    return () => window.removeEventListener("appinstalled", onInstalled);
  }, []);

  return null;
}
