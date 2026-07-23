"use client";

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
