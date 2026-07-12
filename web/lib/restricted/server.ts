const API_URL = process.env.API_INTERNAL_URL || 'http://localhost:8000';

export type AuthStatus = 'approved' | 'unapproved' | 'unreachable';

// Server-side approval check against the backend session. 'unapproved' is a
// definitive answer (pending/blocked user, or an invalid/expired session);
// 'unreachable' means the backend couldn't answer, so callers pick their own
// safe default.
export async function fetchAuthStatus(cookieHeader: string): Promise<AuthStatus> {
  try {
    const res = await fetch(`${API_URL}/api/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return 'unapproved';
    const me = (await res.json()) as { status?: string };
    return me.status === 'approved' ? 'approved' : 'unapproved';
  } catch {
    return 'unreachable';
  }
}

// Decides whether a dashboard request renders in Restricted mode (ADR-0035 §1).
// The preview cookie alone is not authoritative: /restricted mints it whenever
// its approval check fails — including transient backend blips — so an
// approved session must outrank a stale cookie or the owner gets locked into
// the preview corpus ("Job not found" on every real job). Pending/blocked
// sessions stay restricted, and an unreachable backend fails closed to
// restricted (grants less, not more).
export async function isRestrictedRequest({
  hasPreviewCookie,
  hasSession,
  cookieHeader,
}: {
  hasPreviewCookie: boolean;
  hasSession: boolean;
  cookieHeader: string;
}): Promise<boolean> {
  if (!hasPreviewCookie) return false;
  if (!hasSession) return true;
  return (await fetchAuthStatus(cookieHeader)) !== 'approved';
}
