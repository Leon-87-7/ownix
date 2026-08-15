"use client";

/* @ds
name: DateTime
purpose: Renders an ISO timestamp as UTC on first paint (SSR-safe), then reformats to the viewer's locale/timezone after hydration.
when-not: Not for durations or relative time ("2h ago") — it only formats a fixed instant.
notes: The two-pass render is deliberate, not a bug — it avoids a hydration mismatch (see the file's own comment).
status: inferred
*/

import { useEffect, useState } from "react";

// ponytail: no IP geolocation — Intl already uses the browser's locale + timezone.
// Initial render is a deterministic UTC string (identical on server and client, so the
// effect's locale value always differs and actually re-renders — a same-value setState
// would bail out and leave the server format stuck). Then reformat to the viewer's locale.
export function DateTime({ iso }: { iso: string }) {
  const [text, setText] = useState(() =>
    new Date(iso).toLocaleString("en-US", { timeZone: "UTC" }),
  );
  useEffect(() => {
    setText(new Date(iso).toLocaleString());
  }, [iso]);
  return (
    <time dateTime={iso} suppressHydrationWarning>
      {text}
    </time>
  );
}
