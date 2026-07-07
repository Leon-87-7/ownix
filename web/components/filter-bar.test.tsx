// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
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
});
