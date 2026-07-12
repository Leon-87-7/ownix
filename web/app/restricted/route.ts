import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const API_URL = process.env.API_INTERNAL_URL || 'http://localhost:8000';

// "Look inside" is session-aware (ADR-0035 §1): approved users go to their
// own Feed with no preview cookie; anonymous, pending, and blocked visitors
// enter Restricted mode. Approval lives server-side, so ask the backend.
async function isApprovedSession(request: NextRequest): Promise<boolean> {
  if (!request.cookies.get('vig_session')?.value) return false;
  try {
    const res = await fetch(`${API_URL}/api/auth/me`, {
      headers: { cookie: request.headers.get('cookie') ?? '' },
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return false;
    const me = (await res.json()) as { status?: string };
    return me.status === 'approved';
  } catch {
    // Backend unreachable: fall through to Restricted mode — the safe default
    // grants less, not more.
    return false;
  }
}

export async function GET(request: NextRequest) {
  const url = new URL('/feed', request.url);
  const response = NextResponse.redirect(url, 303);
  // ?exit leaves Restricted mode: drop the preview cookie and land on /feed
  // (signed-out visitors get bounced to /login by the middleware; in mock/dev
  // mode this is the switch back to the mock user).
  if (request.nextUrl.searchParams.has('exit')) {
    response.cookies.delete('ownix_preview');
    return response;
  }
  if (await isApprovedSession(request)) {
    // Self-heal a stale preview cookie (e.g. approved mid-session).
    response.cookies.delete('ownix_preview');
    return response;
  }
  response.cookies.set('ownix_preview', '1', {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
  });
  return response;
}
