// @vitest-environment jsdom
import { render, screen, within } from '@/test/render';
import { describe, expect, it } from 'vitest';
import { StatsOverview } from './stats-overview';

const makeStats = (overrides: Partial<{ total: number; by_status: Record<string, number>; by_content_type: Record<string, number> }> = {}) => ({
  total: 42,
  by_status: { done: 20, pending: 5, error: 3, processing: 10, enriching: 2, transcript_done: 1 },
  by_content_type: { short: 15, long: 10, article: 8, repo: 9 },
  ...overrides,
});

describe('StatsOverview', () => {
  it('renders total count', () => {
    render(<StatsOverview stats={makeStats()} />);
    // Appears in both the desktop grid and the mobile inline row (#185).
    expect(screen.getAllByText('42').length).toBeGreaterThanOrEqual(2);
  });

  it('renders done count', () => {
    render(<StatsOverview stats={makeStats()} />);
    expect(screen.getAllByText('20').length).toBeGreaterThanOrEqual(2);
  });

  it('renders processing + enriching + transcript_done combined', () => {
    render(<StatsOverview stats={makeStats()} />);
    // processing=10 + enriching=2 + transcript_done=1 = 13
    expect(screen.getByText('13')).toBeTruthy();
  });

  it('renders zero when by_status keys are missing', () => {
    render(<StatsOverview stats={makeStats({ by_status: {}, by_content_type: {} })} />);
    // All counts should be 0 except total
    const zeros = screen.getAllByText('0');
    expect(zeros.length).toBeGreaterThanOrEqual(4);
  });

  it('renders all stat card labels', () => {
    render(<StatsOverview stats={makeStats()} />);
    // Labels also appear in the always-mounted mobile breakdown, so scope to the
    // desktop card grid — this fails if the cards themselves stop rendering.
    const cards = within(screen.getByTestId('stat-cards'));
    for (const label of ['Total', 'Done', 'Pending', 'Error', 'Processing']) {
      expect(cards.getByText(label)).toBeTruthy();
    }
  });

  it('labels the overview region for assistive tech', () => {
    render(<StatsOverview stats={makeStats()} />);
    expect(screen.getByRole('region', { name: 'Overview' })).toBeTruthy();
  });
});
