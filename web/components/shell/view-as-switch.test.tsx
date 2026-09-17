import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ViewAsSwitch from './view-as-switch';

const { useSessionUser } = vi.hoisted(() => ({ useSessionUser: vi.fn() }));
vi.mock('@/components/shell/invite-gate', () => ({ useSessionUser }));

describe('ViewAsSwitch', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    useSessionUser.mockReset();
  });

  it('is hidden from users who cannot view as a member', () => {
    useSessionUser.mockReturnValue({ can_view_as: false });
    render(<ViewAsSwitch />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('starts viewer mode for an operator', async () => {
    useSessionUser.mockReturnValue({ can_view_as: true, viewing_as: false });
    render(<ViewAsSwitch />);
    fireEvent.click(screen.getByRole('button', { name: 'View Ownix as a member' }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith('/api/auth/view-as', { method: 'POST' }),
    );
  });

  it('exits viewer mode with DELETE', async () => {
    useSessionUser.mockReturnValue({ can_view_as: true, viewing_as: true });
    render(<ViewAsSwitch />);
    fireEvent.click(screen.getByRole('button', { name: 'Exit viewer mode' }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith('/api/auth/view-as', { method: 'DELETE' }),
    );
  });
});
