"use client";

/* @ds
name: SwRegister
purpose: Registers /sw.js on mount for offline support — invisible, no UI.
when-not: Disabled in mock mode (NEXT_PUBLIC_API_MOCK=1) so the service worker never interferes with MSW's own request interception.
notes: Renders null always; this is a side-effect-only component.
status: inferred
*/

import { useEffect } from "react";

const ENABLED = process.env.NEXT_PUBLIC_API_MOCK !== "1";

export default function SwRegister() {
  useEffect(() => {
    if (!ENABLED) return;
    if (!("serviceWorker" in navigator)) return;
    void navigator.serviceWorker.register("/sw.js");
  }, []);

  return null;
}
