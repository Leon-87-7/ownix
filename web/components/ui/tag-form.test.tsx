import { render, screen, fireEvent } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { TagForm } from './tag-form';
import { PRESET_COLORS } from './tag-picker';

describe('TagForm color picker', () => {
  it('keeps the grid symmetric (presets + the custom-color swatch, 6 per row)', () => {
    const { container } = render(
      <TagForm
        initial={{ name: '', meaning: '', color: PRESET_COLORS[0] }}
        onSubmit={vi.fn()}
        submitLabel="Create"
      />,
    );
    const grid = container.querySelector('.grid-cols-6');
    // +1 for the custom-color swatch, which now fills the grid's last slot.
    expect(grid?.children.length).toBe(PRESET_COLORS.length + 1);
    expect(grid?.children.length % 6).toBe(0);
  });

  it('lets a custom color (outside the presets) be picked via the native color input', () => {
    render(
      <TagForm
        initial={{ name: '', meaning: '', color: PRESET_COLORS[0] }}
        onSubmit={vi.fn()}
        submitLabel="Create"
      />,
    );
    const customInput = screen.getByLabelText('Custom color') as HTMLInputElement;
    expect(customInput.type).toBe('color');

    fireEvent.change(customInput, { target: { value: '#123456' } });
    expect(customInput.value).toBe('#123456');
    // Once a non-preset color is set, none of the preset swatches read as selected.
    for (const c of PRESET_COLORS) {
      expect(screen.getByLabelText(`Color ${c}`)).toHaveAttribute('aria-pressed', 'false');
    }
  });
});
