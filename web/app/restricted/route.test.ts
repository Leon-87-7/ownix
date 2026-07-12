import { afterEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET } from './route';

const requestFor = (cookie?: string) =>
  new NextRequest('https://ownix.test/restricted', {
    headers: cookie ? { cookie } : undefined,
  });

const previewCookie = (response: Response) =>
  response.headers
    .getSetCookie()
    .find((c) => c.startsWith('ownix_preview='));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('/restricted entry route (ADR-0035 §1 session-aware CTA)', () => {
  it('sends anonymous visitors to the Feed with the preview cookie', async () => {
    const response = await GET(requestFor());
    expect(response.status).toBe(303);
    expect(response.headers.get('location')).toBe('https://ownix.test/feed');
    expect(previewCookie(response)).toContain('ownix_preview=1');
  });

  it('sends approved users to their own Feed without the preview cookie', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ status: 'approved' })),
    );
    const response = await GET(requestFor('vig_session=abc'));
    expect(response.status).toBe(303);
    const cookie = previewCookie(response);
    // Approved users get a deletion (self-heal), never ownix_preview=1.
    expect(cookie ?? '').not.toContain('ownix_preview=1');
  });

  it('keeps pending users in Restricted mode', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ status: 'pending' })),
    );
    const response = await GET(requestFor('vig_session=abc'));
    expect(previewCookie(response)).toContain('ownix_preview=1');
  });

  it('falls back to Restricted mode when the backend is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('backend down');
      }),
    );
    const response = await GET(requestFor('vig_session=abc'));
    expect(previewCookie(response)).toContain('ownix_preview=1');
  });

  it('?exit clears the preview cookie without asking the backend', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const response = await GET(
      new NextRequest('https://ownix.test/restricted?exit=1'),
    );
    expect(response.status).toBe(303);
    expect(response.headers.get('location')).toBe('https://ownix.test/feed');
    const cookie = previewCookie(response);
    // A deletion (Max-Age=0 / empty value), never ownix_preview=1.
    expect(cookie ?? '').not.toContain('ownix_preview=1');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('never calls the backend for anonymous visitors', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    await GET(requestFor());
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
