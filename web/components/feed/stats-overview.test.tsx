// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
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
    expect(screen.getByText('42')).toBeTruthy();
  });

  it('renders done count', () => {
    render(<StatsOverview stats={makeStats()} />);
    expect(screen.getByText('20')).toBeTruthy();
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
    expect(screen.getByText('Total')).toBeTruthy();
    expect(screen.getByText('Done')).toBeTruthy();
    expect(screen.getByText('Pending')).toBeTruthy();
    expect(screen.getByText('Error')).toBeTruthy();
    expect(screen.getByText('Processing')).toBeTruthy();
  });

  it('renders overview section heading', () => {
    render(<StatsOverview stats={makeStats()} />);
    expect(screen.getByText('Overview')).toBeTruthy();
  });
});
