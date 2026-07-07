// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useRecovery } from '@/lib/hooks/useRecovery';
import { RecoveryPanel } from './recovery-panel';

vi.mock('@/lib/hooks/useRecovery', () => ({
  useRecovery: vi.fn(),
}));

const recoveryActions = {
  reload: vi.fn(),
  retryPending: vi.fn(),
  retryError: vi.fn(),
  clearFailed: vi.fn(),
};

function mockRecovery(overrides: Partial<ReturnType<typeof useRecovery>> = {}) {
  vi.mocked(useRecovery).mockReturnValue({
    summary: {
      stale_pending: 0,
      error_jobs: 0,
      stale_in_flight: 0,
    },
    loading: false,
    acting: null,
    error: null,
    ...recoveryActions,
    ...overrides,
  });
}

describe('RecoveryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when there is nothing to recover', () => {
    mockRecovery();

    render(<RecoveryPanel contentType="" onRecovered={vi.fn()} />);

    expect(screen.queryByRole('group', { name: 'Recovery' })).toBeNull();
    expect(screen.queryByText(/stale in-flight/i)).toBeNull();
  });

  it('shows one attention chip before revealing recovery actions', () => {
    mockRecovery({
      summary: {
        stale_pending: 1,
        error_jobs: 1,
        stale_in_flight: 1,
      },
    });

    render(<RecoveryPanel contentType="" onRecovered={vi.fn()} />);

    const chip = screen.getByRole('button', {
      name: '3 need attention',
    });
    expect(chip).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('group', { name: 'Recovery' })).toBeNull();

    fireEvent.click(chip);

    expect(chip).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('group', { name: 'Recovery' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry pending (1)' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry failed (2)' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Clear failed (1)' })).toBeTruthy();
  });

  it('demotes recovery summary errors to a quiet retry note', () => {
    mockRecovery({
      error: 'Failed to load recovery summary',
    });

    render(<RecoveryPanel contentType="" onRecovered={vi.fn()} />);

    expect(
      screen.getByText('Failed to load recovery summary. The feed is still usable.'),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(recoveryActions.reload).toHaveBeenCalledTimes(1);
  });
});
