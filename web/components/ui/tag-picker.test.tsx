// @vitest-environment jsdom
import { render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { TagChips } from './tag-picker';

const tag = {
  id: 't1',
  name: 'dev-tools',
  color: '#60a5fa',
  meaning: 'Developer tooling',
  icon: 'Cog',
};

describe('TagChips compact mode', () => {
  it('renders the mobile 3-char clip and the full name for larger screens', () => {
    render(<TagChips jobTags={[tag]} onRemove={vi.fn()} compact />);

    // Mobile-only clip: first 3 characters, hidden at the sm breakpoint.
    const clip = screen.getByText('dev', { selector: 'span.sm\\:hidden' });
    expect(clip).toBeInTheDocument();

    // Full name still present (revealed at sm+) and exposed to assistive tech.
    expect(screen.getByText('dev-tools', { selector: 'span.hidden' })).toBeInTheDocument();
    expect(screen.getByText('dev-tools', { selector: 'span.sr-only' })).toBeInTheDocument();
  });

  it('renders the full name inline when not compact', () => {
    render(<TagChips jobTags={[tag]} onRemove={vi.fn()} />);

    expect(screen.getByText('dev-tools')).toBeInTheDocument();
    expect(screen.queryByText('dev', { selector: 'span.sm\\:hidden' })).not.toBeInTheDocument();
  });
});
