/**
 * Carries a shared URL across the login round-trip for `/intake/share`
 * (issue #476). An unauthenticated share-target hit stores the extracted URL
 * here before bouncing to `/login`; `TelegramLoginWidget` consumes it on
 * successful sign-in instead of its default `/feed` redirect, so the shared
 * URL is never lost.
 */

const STORAGE_KEY = 'ownix_pending_share_url';

export function storePendingShareUrl(url: string): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, url);
  } catch {
    // Private-mode/SSR sessionStorage access can throw — the share is lost,
    // same failure mode as any other client-only persistence.
  }
}

/** Returns the post-login redirect target, consuming (and clearing) any pending share. */
export function consumePostLoginRedirect(): string {
  try {
    const pending = sessionStorage.getItem(STORAGE_KEY);
    if (pending) {
      sessionStorage.removeItem(STORAGE_KEY);
      return `/intake?url=${encodeURIComponent(pending)}`;
    }
  } catch {
    // ignore — fall through to the default destination
  }
  return '/feed';
}
