// @vitest-environment jsdom
import { render, waitFor } from '@/test/render';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import IntakeSharePage from './page';

const navigationMock = vi.hoisted(() => ({
  replace: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: navigationMock.replace }),
  useSearchParams: () => navigationMock.params,
}));

beforeEach(() => {
  vi.restoreAllMocks();
  navigationMock.replace.mockReset();
  navigationMock.params = new URLSearchParams();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('IntakeSharePage', () => {
  it('authenticated: redirects straight into /intake with the extracted URL prefilled', async () => {
    navigationMock.params = new URLSearchParams({ share_url: 'https://example.com/a' });
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(null, { status: 200 }));

    render(<IntakeSharePage />);

    await waitFor(() =>
      expect(navigationMock.replace).toHaveBeenCalledWith(
        '/intake?url=https%3A%2F%2Fexample.com%2Fa',
      ),
    );
  });

  it('unauthenticated: stores the shared URL and bounces to /login', async () => {
    navigationMock.params = new URLSearchParams({ share_url: 'https://example.com/b' });
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(null, { status: 401 }));

    render(<IntakeSharePage />);

    await waitFor(() => expect(navigationMock.replace).toHaveBeenCalledWith('/login'));
    expect(sessionStorage.getItem('ownix_pending_share_url')).toBe('https://example.com/b');
  });

  it('reuses extractSharedUrl to pull a URL out of Android-style share_text', async () => {
    navigationMock.params = new URLSearchParams({
      share_text: 'Check this out https://www.instagram.com/reel/abc/ nice',
    });
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(null, { status: 200 }));

    render(<IntakeSharePage />);

    await waitFor(() =>
      expect(navigationMock.replace).toHaveBeenCalledWith(
        `/intake?url=${encodeURIComponent('https://www.instagram.com/reel/abc/')}`,
      ),
    );
  });

  it('missing/unsupported share payload still lands in a useful intake state', async () => {
    navigationMock.params = new URLSearchParams();
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(null, { status: 200 }));

    render(<IntakeSharePage />);

    await waitFor(() => expect(navigationMock.replace).toHaveBeenCalledWith('/intake'));
  });
});
