// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { BookmarkCheck } from 'lucide-react';
import { FilterBar } from './filter-bar';

const tabs = [
  { label: 'All', value: '', count: 2 },
  { label: 'Short', value: 'short', count: 1 },
];

function renderFilterBar() {
  render(
    <FilterBar
      tabs={tabs}
      tabValue=""
      onTabChange={vi.fn()}
      query=""
      setQuery={vi.fn()}
      statusValue=""
      onStatusChange={vi.fn()}
    />,
  );
}

describe('FilterBar', () => {
  it('focuses search with the slash shortcut', () => {
    renderFilterBar();

    fireEvent.keyDown(window, { key: '/' });

    expect(screen.getByLabelText('Search')).toHaveFocus();
  });

  it('does not steal slash while editing another field', () => {
    render(
      <>
        <input aria-label="External editor" />
        <FilterBar
          tabs={tabs}
          tabValue=""
          onTabChange={vi.fn()}
          query=""
          setQuery={vi.fn()}
          statusValue=""
          onStatusChange={vi.fn()}
        />
      </>,
    );

    const external = screen.getByLabelText('External editor');
    external.focus();
    fireEvent.keyDown(external, { key: '/' });

    expect(external).toHaveFocus();
  });

  it('renders toggle filters and reports the flipped value', () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        tabs={tabs}
        tabValue=""
        onTabChange={vi.fn()}
        query=""
        setQuery={vi.fn()}
        statusValue=""
        onStatusChange={vi.fn()}
        toggleFilters={[
          { label: 'Checklist', active: false, onChange },
        ]}
      />,
    );

    const chip = screen.getByRole('button', { name: 'Checklist' });
    expect(chip).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(chip);

    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('keeps an icon-only toggle named and pressable', () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        tabs={tabs}
        tabValue=""
        onTabChange={vi.fn()}
        query=""
        setQuery={vi.fn()}
        statusValue=""
        onStatusChange={vi.fn()}
        toggleFilters={[
          {
            label: 'Checklist generated',
            icon: BookmarkCheck,
            active: true,
            onChange,
          },
        ]}
      />,
    );

    // Icon-only in pixels, still named for AT — the accessible name has to
    // survive dropping the visible text.
    const chip = screen.getByRole('button', {
      name: 'Checklist generated',
    });
    expect(chip).toHaveTextContent('');
    expect(chip).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(chip);

    expect(onChange).toHaveBeenCalledWith(false);
  });
});
