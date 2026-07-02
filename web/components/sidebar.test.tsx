// @vitest-environment jsdom
import { render, screen } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Sidebar } from './sidebar';
import type { InviteUser } from './invite-gate';

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
}));

const sessionMock = vi.hoisted(() => ({
  user: null as InviteUser | null,
}));

vi.mock('@/components/invite-gate', () => ({
  useSessionUser: () => sessionMock.user,
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
});
