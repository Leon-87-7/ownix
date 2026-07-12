import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { fetchAuthStatus } from '@/lib/restricted/server';

// "Look inside" is session-aware (ADR-0035 §1): approved users go to their
// own Feed with no preview cookie; anonymous, pending, and blocked visitors
// enter Restricted mode. Approval lives server-side, so ask the backend.
// Backend unreachable falls through to Restricted mode — the safe default
// grants less, not more — and the dashboard layout re-checks approval on
// every render, so a cookie minted over a blip can't lock an approved user
// out of their own Feed.
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
  const hasSession = Boolean(request.cookies.get('vig_session')?.value);
  const status = hasSession
    ? await fetchAuthStatus(request.headers.get('cookie') ?? '')
    : 'unapproved';
  if (status === 'approved') {
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
