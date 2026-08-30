import { describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';
import { config, proxy } from './proxy';

// The auth gate runs only on paths the matcher selects. Static public assets
// (svg/png/manifest) must be EXCLUDED — otherwise requests for them while
// logged out (on /login and /logout) 307 to /login and the SVGs never render.
const matches = (pathname: string) =>
  new RegExp(`^${config.matcher[0]}$`).test(pathname);

const requestFor = (pathname: string, cookie?: string) =>
  new NextRequest(`https://ownix.test${pathname}`, {
    headers: cookie ? { cookie } : undefined,
  });

const expectLoginRedirect = (response: Response) => {
  expect(response.status).toBe(307);
  expect(response.headers.get('location')).toBe('https://ownix.test/login');
};

describe('proxy matcher', () => {
  it('excludes public static assets from the auth gate', () => {
    expect(matches('/images/vig_logo_lockup.svg')).toBe(false);
    expect(matches('/backgrounds/layered-waves-log.svg')).toBe(false);
    expect(matches('/manifest.json')).toBe(false);
    expect(matches('/icon0.svg')).toBe(false);
  });

  it('still gates real app routes', () => {
    expect(matches('/')).toBe(true);
    expect(matches('/feed')).toBe(true);
    expect(matches('/doc-parser')).toBe(true);
  });
});

describe('proxy routing cutover', () => {
  it('lets logged-out visitors reach the public landing route', () => {
    const response = proxy(requestFor('/'));
    expect(response.status).toBe(200);
  });

  it('lets authenticated root visits reach the public landing route', () => {
    const response = proxy(requestFor('/', 'vig_session=abc'));
    expect(response.status).toBe(200);
  });

  it('keeps /feed behind the session gate', () => {
    expectLoginRedirect(proxy(requestFor('/feed')));
  });

  it('lets link-preview crawlers (always cookie-less) reach the OG image', () => {
    const response = proxy(requestFor('/opengraph-image'));
    expect(response.status).toBe(200);
  });

  it('lets logged-out visitors reach the share-target landing route (issue #476)', () => {
    const response = proxy(requestFor('/intake/share?url=https://example.com'));
    expect(response.status).toBe(200);
  });

  it('keeps the real /intake surface behind the session gate', () => {
    expectLoginRedirect(proxy(requestFor('/intake')));
  });
});

describe('proxy restricted mode (ADR-0035)', () => {
  it('lets the preview cookie through the dashboard gate', () => {
    const response = proxy(requestFor('/feed', 'ownix_preview=1'));
    expect(response.status).toBe(200);
  });

  it('preview cookie grants navigation to any dashboard route', () => {
    for (const path of ['/brain', '/spaces', '/controls', '/prompts']) {
      expect(proxy(requestFor(path, 'ownix_preview=1')).status).toBe(200);
    }
  });

  it('keeps /restricted itself public so the cookie can be minted', () => {
    const response = proxy(requestFor('/restricted'));
    expect(response.status).toBe(200);
  });

  it('still bounces cookie-less visitors from dashboard routes', () => {
    expectLoginRedirect(proxy(requestFor('/jobs/20260711_010101_ab12')));
  });
});

describe('proxy agent-readable 404s', () => {
  // Only verifies proxy's own pass-through contract — that an unprotected
  // path isn't redirected to /login. Whether Next.js then actually renders a
  // 404 for /pricing depends on no matching route existing under app/, which
  // this unit test can't exercise without a running server.
  it('does not redirect an unprotected, unknown path to the login wall', () => {
    const response = proxy(requestFor('/pricing'));
    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });
});
