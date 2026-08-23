'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { extractSharedUrl } from '@/lib/share-target';
import { storePendingShareUrl } from '@/lib/intake-share-redirect';

/**
 * PWA share-target landing (issue #476). Public route (see `proxy.ts`
 * PUBLIC_PATHS) so it works before login - this intentionally supersedes the
 * closed #423 Feed-prefill behavior; `web/app/manifest.json`'s share_target
 * now points here instead of `/feed`.
 *
 * Default choice for the plan's open question (auto-submit vs. prefill):
 * **prefill + confirm** - this page never calls `/api/intake/message`
 * itself, it only redirects into `/intake?url=...` so the user reviews and
 * sends explicitly, same as pasting the URL by hand.
 */
export default function IntakeSharePage() {
  return (
    <Suspense fallback={null}>
      <IntakeShareRedirect />
    </Suspense>
  );
}

function IntakeShareRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Param names must match manifest.json's share_target.params mapping
    // (share_url/share_text), not the raw Web Share Target field names.
    const shareUrl = searchParams.get('share_url');
    const shareText = searchParams.get('share_text');
    const extracted = extractSharedUrl(shareUrl, shareText);
    const intakeTarget = extracted
      ? `/intake?url=${encodeURIComponent(extracted)}`
      : '/intake';

    let cancelled = false;
    fetch('/api/auth/me')
      .then((res) => {
        if (cancelled) return;
        if (res.ok) {
          router.replace(intakeTarget);
          return;
        }
        // Not authenticated: preserve the shared URL across login instead of
        // losing it - the login widget redirects back to /intake on success.
        if (extracted) storePendingShareUrl(extracted);
        router.replace('/login');
      })
      .catch(() => {
        if (cancelled) return;
        if (extracted) storePendingShareUrl(extracted);
        router.replace('/login');
      })
      .finally(() => {
        if (!cancelled) setChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  return (
    <div
      role="status"
      className="flex min-h-screen items-center justify-center bg-canvas text-sm text-body"
    >
      {checked ? 'Redirecting…' : 'Checking your session…'}
    </div>
  );
}
