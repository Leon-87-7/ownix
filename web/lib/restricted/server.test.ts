import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchAuthStatus, isRestrictedRequest } from './server';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchAuthStatus', () => {
  it('returns approved for an approved session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ status: 'approved' })),
    );
    expect(await fetchAuthStatus('vig_session=abc')).toBe('approved');
  });

  it('returns unapproved for pending users and invalid sessions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ status: 'pending' })),
    );
    expect(await fetchAuthStatus('vig_session=abc')).toBe('unapproved');

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('nope', { status: 401 })),
    );
    expect(await fetchAuthStatus('vig_session=stale')).toBe('unapproved');
  });

  it('returns unreachable when the backend cannot answer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('backend down');
      }),
    );
    expect(await fetchAuthStatus('vig_session=abc')).toBe('unreachable');
  });
});

describe('isRestrictedRequest (ADR-0035 §1 dashboard decision)', () => {
  it('is never restricted without the preview cookie', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    expect(
      await isRestrictedRequest({
        hasPreviewCookie: false,
        hasSession: true,
        cookieHeader: 'vig_session=abc',
      }),
    ).toBe(false);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('is restricted for anonymous preview visitors without asking the backend', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    expect(
      await isRestrictedRequest({
        hasPreviewCookie: true,
        hasSession: false,
        cookieHeader: 'ownix_preview=1',
      }),
    ).toBe(true);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('lets an approved session outrank a stale preview cookie', async () => {
    // The regression: a fail-closed /restricted mint must not swap the
    // owner's Feed for the preview corpus ("Job not found" on every job).
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ status: 'approved' })),
    );
    expect(
      await isRestrictedRequest({
        hasPreviewCookie: true,
        hasSession: true,
        cookieHeader: 'vig_session=abc; ownix_preview=1',
      }),
    ).toBe(false);
  });

  it('keeps pending sessions restricted', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ status: 'pending' })),
    );
    expect(
      await isRestrictedRequest({
        hasPreviewCookie: true,
        hasSession: true,
        cookieHeader: 'vig_session=abc; ownix_preview=1',
      }),
    ).toBe(true);
  });

  it('fails closed to restricted when the backend is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('backend down');
      }),
    );
    expect(
      await isRestrictedRequest({
        hasPreviewCookie: true,
        hasSession: true,
        cookieHeader: 'vig_session=abc; ownix_preview=1',
      }),
    ).toBe(true);
  });
});
