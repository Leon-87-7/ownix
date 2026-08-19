// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SPACE_ICONS } from '@/lib/space-icons';
import { IconPicker } from './icon-picker';

describe('IconPicker', () => {
  it('renders every icon, marks the value, and reports changes', () => {
    const onChange = vi.fn();
    render(<IconPicker value="star" onChange={onChange} />);
    expect(screen.getAllByRole('button')).toHaveLength(SPACE_ICONS.length);
    expect(screen.getByRole('button', { name: 'star' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'rocket' }));
    expect(onChange).toHaveBeenCalledWith('rocket');
  });
});
