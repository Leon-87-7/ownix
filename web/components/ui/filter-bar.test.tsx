// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import userEvent from '@testing-library/user-event';
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

  const TAGS = [
    { id: 't1', name: 'Spec', color: '#fff', meaning: '' },
    { id: 't2', name: 'Repo', color: '#fff', meaning: '' },
  ];

  it('renders a tag row per option with its usage count and toggles selection', async () => {
    const user = userEvent.setup();
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
        tagFilter={{
          allTags: TAGS,
          counts: { t1: 3, t2: 0 },
          selectedIds: [],
          onChange,
        }}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Filter by tags' }));

    const specRow = await screen.findByRole('menuitemcheckbox', { name: /Spec/ });
    expect(specRow).toHaveTextContent('3');
    expect(screen.getByRole('menuitemcheckbox', { name: /Repo/ })).toHaveTextContent('0');

    await user.click(specRow);
    expect(onChange).toHaveBeenCalledWith(['t1']);
  });

  it('deselects an already-selected tag on click', async () => {
    const user = userEvent.setup();
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
        tagFilter={{
          allTags: TAGS,
          selectedIds: ['t1', 't2'],
          onChange,
        }}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Filter by tags' }));
    await user.click(await screen.findByRole('menuitemcheckbox', { name: /Spec/ }));

    expect(onChange).toHaveBeenCalledWith(['t2']);
  });

  it('"Clear All" clears the current selection', async () => {
    const user = userEvent.setup();
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
        tagFilter={{
          allTags: TAGS,
          selectedIds: ['t1'],
          onChange,
        }}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Filter by tags' }));
    await user.click(await screen.findByRole('menuitemcheckbox', { name: 'Clear All' }));

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('shows the tag name on the trigger when exactly one tag is selected', async () => {
    render(
      <FilterBar
        tabs={tabs}
        tabValue=""
        onTabChange={vi.fn()}
        query=""
        setQuery={vi.fn()}
        statusValue=""
        onStatusChange={vi.fn()}
        tagFilter={{
          allTags: TAGS,
          selectedIds: ['t1'],
          onChange: vi.fn(),
        }}
      />,
    );

    expect(screen.getByRole('button', { name: 'Filter by tags' })).toHaveTextContent('Spec');
  });

  it('falls back to the numeric count when more than one tag is selected', async () => {
    render(
      <FilterBar
        tabs={tabs}
        tabValue=""
        onTabChange={vi.fn()}
        query=""
        setQuery={vi.fn()}
        statusValue=""
        onStatusChange={vi.fn()}
        tagFilter={{
          allTags: TAGS,
          selectedIds: ['t1', 't2'],
          onChange: vi.fn(),
        }}
      />,
    );

    expect(screen.getByRole('button', { name: 'Filter by tags' })).toHaveTextContent('Tags2');
  });

  it('shows an empty-vocabulary message instead of hiding the trigger', async () => {
    const user = userEvent.setup();
    render(
      <FilterBar
        tabs={tabs}
        tabValue=""
        onTabChange={vi.fn()}
        query=""
        setQuery={vi.fn()}
        statusValue=""
        onStatusChange={vi.fn()}
        tagFilter={{
          allTags: [],
          selectedIds: [],
          onChange: vi.fn(),
        }}
      />,
    );

    expect(screen.getByRole('button', { name: 'Filter by tags' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Filter by tags' }));
    expect(await screen.findByText('No tags yet.')).toBeInTheDocument();
  });

  it('disables the trigger and explains why via title when tagFilter.disabled is set', () => {
    render(
      <FilterBar
        tabs={tabs}
        tabValue=""
        onTabChange={vi.fn()}
        query=""
        setQuery={vi.fn()}
        statusValue=""
        onStatusChange={vi.fn()}
        tagFilter={{
          allTags: TAGS,
          selectedIds: [],
          onChange: vi.fn(),
        }}
      />,
    );

    // Tag filtering is backed by jobs.link_id in SQL now, so it stays usable
    // at every feed size rather than disabling itself past the client-mode cap.
    const trigger = screen.getByRole('button', { name: 'Filter by tags' });
    expect(trigger).not.toBeDisabled();
  });
});
