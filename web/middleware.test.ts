import { describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';
import { config, middleware } from './middleware';

// The auth gate runs only on paths the matcher selects. Static public assets
// (svg/png/manifest) must be EXCLUDED — otherwise requests for them while
// logged out (on /login and /logout) 307 to /login and the SVGs never render.
const matches = (pathname: string) =>
  new RegExp(`^${config.matcher[0]}$`).test(pathname);

const requestFor = (pathname: string, cookie?: string) =>
  new NextRequest(`https://ownix.test${pathname}`, {
    headers: cookie ? { cookie } : undefined,
  });

describe('middleware matcher', () => {
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

describe('middleware routing cutover', () => {
  it('lets logged-out visitors reach the public landing route', () => {
    const response = middleware(requestFor('/'));
    expect(response.status).toBe(200);
  });

  it('lets authenticated root visits reach the public landing route', () => {
    const response = middleware(requestFor('/', 'vig_session=abc'));
    expect(response.status).toBe(200);
  });

  it('keeps /feed behind the session gate', () => {
    const response = middleware(requestFor('/feed'));
    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe('https://ownix.test/login');
  });
});

describe('middleware restricted mode (ADR-0035)', () => {
  it('lets the preview cookie through the dashboard gate', () => {
    const response = middleware(requestFor('/feed', 'ownix_preview=1'));
    expect(response.status).toBe(200);
  });

  it('preview cookie grants navigation to any dashboard route', () => {
    for (const path of ['/brain', '/spaces', '/controls', '/prompts']) {
      expect(middleware(requestFor(path, 'ownix_preview=1')).status).toBe(200);
    }
  });

  it('keeps /restricted itself public so the cookie can be minted', () => {
    const response = middleware(requestFor('/restricted'));
    expect(response.status).toBe(200);
  });

  it('still bounces cookie-less visitors from dashboard routes', () => {
    const response = middleware(requestFor('/jobs/20260711_010101_ab12'));
    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe('https://ownix.test/login');
  });
});
