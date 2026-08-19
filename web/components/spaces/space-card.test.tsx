// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SpaceCard, type SpaceSummary } from './space-card';
const base: SpaceSummary = { id: 's1', name: 'Research', color: '#123456', created_at: '2024-01-01' };
describe('SpaceCard', () => {
  it('renders the icon/name fallback and keeps its controls', () => {
    render(<SpaceCard space={base} />);
    expect(screen.getByText('Research')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/spaces/s1');
    expect(screen.getByRole('button', { name: 'Delete Research' })).toBeInTheDocument();
  });
  it('renders a first-note preview and truncation marker', () => {
    render(<SpaceCard space={{ ...base, first_note: { name: 'Brief', snippet: 'Preview', updated_at: '2024-01-01T00:00:00Z', truncated: true } }} />);
    expect(screen.getByText('Brief')).toBeInTheDocument();
    expect(screen.getByText('Preview…')).toBeInTheDocument();
    expect(screen.queryByText('Research')).not.toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/spaces/s1');
    expect(screen.getByRole('button', { name: 'Delete Research' })).toBeInTheDocument();
  });
  it('treats a timezone-less SQLite timestamp as UTC', () => {
    const { container } = render(<SpaceCard space={{ ...base, first_note: { name: 'Brief', snippet: 'Preview', updated_at: '2024-01-01 00:00:00' } }} />);
    expect(container.querySelector('time')).toHaveAttribute('dateTime', '2024-01-01T00:00:00Z');
  });
});
