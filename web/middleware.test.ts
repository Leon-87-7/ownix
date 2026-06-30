import { describe, expect, it } from 'vitest';
import { config } from './middleware';

// The auth gate runs only on paths the matcher selects. Static public assets
// (svg/png/manifest) must be EXCLUDED — otherwise requests for them while
// logged out (on /login and /logout) 307 to /login and the SVGs never render.
const matches = (pathname: string) =>
  new RegExp(`^${config.matcher[0]}$`).test(pathname);

describe('middleware matcher', () => {
  it('excludes public static assets from the auth gate', () => {
    expect(matches('/images/vig_logo_lockup.svg')).toBe(false);
    expect(matches('/backgrounds/layered-waves-log.svg')).toBe(false);
    expect(matches('/manifest.json')).toBe(false);
    expect(matches('/icon0.svg')).toBe(false);
  });

  it('still gates real app routes', () => {
    expect(matches('/')).toBe(true);
    expect(matches('/doc-parser')).toBe(true);
  });
});
