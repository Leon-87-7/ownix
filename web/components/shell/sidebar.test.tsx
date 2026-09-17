// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor, within } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Sidebar, visibleNav, ADMIN_ONLY_HREFS } from './sidebar';
import type { InviteUser } from './invite-gate';

vi.mock('next/navigation', () => ({
  usePathname: () => '/feed',
}));

const sessionMock = vi.hoisted(() => ({
  user: null as InviteUser | null,
}));

vi.mock('@/components/shell/invite-gate', () => ({
  useSessionUser: () => sessionMock.user,
}));

const googleMock = vi.hoisted(() => ({
  connected: null as boolean | null,
  disconnect: vi.fn(async () => true),
}));

vi.mock('@/components/shell/google-status', () => ({
  useGoogleStatus: () => ({
    connected: googleMock.connected,
    disconnect: googleMock.disconnect,
    refresh: vi.fn(),
  }),
}));

const USER: InviteUser = {
  id: 1,
  first_name: 'Leon',
  username: 'leon87',
  photo_url: null,
  status: 'approved',
};

beforeEach(() => {
  sessionMock.user = USER;
  googleMock.connected = null;
  googleMock.disconnect = vi.fn(async () => true);
});

describe('Sidebar identity row', () => {
  it('renders the session identity in the drawer footer', () => {
    render(<Sidebar />);
    expect(screen.getByText('Leon')).toBeTruthy();
    expect(screen.getByText('@leon87')).toBeTruthy();
  });

  it('falls back to an initial-letter avatar without photo_url', () => {
    render(<Sidebar />);
    // Rail + drawer each render one avatar fallback with the initial.
    expect(screen.getAllByText('L').length).toBeGreaterThan(0);
  });

  it('renders nothing identity-related when no session user', () => {
    sessionMock.user = null;
    render(<Sidebar />);
    expect(screen.queryByText('Leon')).toBeNull();
  });

  it('posts sign out to the backend logout endpoint', () => {
    render(<Sidebar />);
    const signOut = screen.getByRole('button', {
      name: 'Sign Out',
      hidden: true,
    });
    expect(signOut.closest('form')?.getAttribute('action')).toBe(
      '/api/auth/logout',
    );
    expect(signOut.closest('form')?.getAttribute('method')).toBe('POST');
  });
});

describe('Sidebar Google connection state', () => {
  it('shows Connected to Google when connected', () => {
    googleMock.connected = true;
    render(<Sidebar />);
    expect(screen.getByText('Connected to Google')).toBeTruthy();
    expect(screen.queryByText('Connect Google')).toBeNull();
  });

  it('shows a Connect Google link when disconnected', () => {
    googleMock.connected = false;
    render(<Sidebar />);
    // hidden: true — the drawer is aria-hidden while closed.
    const link = screen.getByRole('link', { name: 'Connect Google', hidden: true });
    expect(link.getAttribute('href')).toBe('/api/google/connect');
    expect(screen.queryByText('Connected to Google')).toBeNull();
  });

  it('shows neither state while status is unknown', () => {
    render(<Sidebar />);
    expect(screen.queryByText('Connected to Google')).toBeNull();
    expect(screen.queryByText('Connect Google')).toBeNull();
  });

  it('disconnects only after confirming in the dialog', async () => {
    googleMock.connected = true;
    render(<Sidebar />);

    fireEvent.click(screen.getByRole('button', { name: 'Disconnect', hidden: true }));
    expect(googleMock.disconnect).not.toHaveBeenCalled();

    const dialog = await screen.findByRole('dialog');
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Disconnect' }));
    });
    expect(googleMock.disconnect).toHaveBeenCalledTimes(1);
  });

  it('surfaces a failure message when disconnect fails', async () => {
    googleMock.connected = true;
    googleMock.disconnect = vi.fn(async () => false);
    render(<Sidebar />);

    fireEvent.click(screen.getByRole('button', { name: 'Disconnect', hidden: true }));
    const dialog = await screen.findByRole('dialog');
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Disconnect' }));
    });

    await waitFor(() =>
      expect(screen.getByText(/couldn.t disconnect/i)).toBeTruthy(),
    );
    // Dialog stays open on failure (handleDisconnect rethrows) so the user can retry.
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(
      within(dialog).getByRole('button', { name: 'Disconnect' }),
    ).not.toBeDisabled();
  });
});

describe('visibleNav (admin gating)', () => {
  it('hides ADMIN_ONLY_HREFS entries for a non-admin user', () => {
    const nav = visibleNav({ ...USER, is_admin: false });
    expect(nav.some((item) => ADMIN_ONLY_HREFS.has(item.href))).toBe(false);
  });

  it('hides ADMIN_ONLY_HREFS entries when there is no session yet', () => {
    const nav = visibleNav(null);
    expect(nav.some((item) => ADMIN_ONLY_HREFS.has(item.href))).toBe(false);
  });

  it('keeps ADMIN_ONLY_HREFS entries for an admin user', () => {
    const nav = visibleNav({ ...USER, is_admin: true });
    expect(nav.some((item) => item.href === '/newsletter-digest')).toBe(true);
  });
});

describe('Sidebar nav visibility', () => {
  it('hides the Digest link for a non-admin session', () => {
    sessionMock.user = { ...USER, is_admin: false };
    render(<Sidebar />);
    expect(
      screen.queryByRole('link', { name: 'Digest', hidden: true }),
    ).not.toBeInTheDocument();
  });

  it('shows the Digest link for an admin session', () => {
    sessionMock.user = { ...USER, is_admin: true };
    render(<Sidebar />);
    expect(
      screen.getAllByRole('link', { name: 'Digest', hidden: true }).length,
    ).toBeGreaterThan(0);
  });
});
