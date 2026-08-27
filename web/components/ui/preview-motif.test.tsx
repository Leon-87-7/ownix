import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PreviewMotif from './preview-motif';

describe('PreviewMotif', () => {
  it('default treatment renders one textPath ring with the accessible name', () => {
    const { container } = render(
      <PreviewMotif label="LINK" className="h-10 w-10" />,
    );
    expect(container.querySelector('[role="status"]')).toHaveAttribute(
      'aria-label',
      'LINK',
    );
    expect(container.querySelector('textPath')?.textContent).toBe(
      '◉ LINK ◉ LINK',
    );
  });

  it('hero treatment renders one letter per character, no textPath', () => {
    const label = 'COLLECT OWN RECALL';
    const { container } = render(
      <PreviewMotif
        label={label}
        treatment="hero"
        size="fill"
        className="h-10 w-10"
      />,
    );
    const expectedText = `◉ ${label} ◉ ${label}`;
    const letterNodes = container.querySelectorAll('svg[viewBox] text');
    expect(container.querySelector('textPath')).toBeNull();
    expect(letterNodes).toHaveLength(expectedText.length);
    expect(Array.from(letterNodes, (el) => el.textContent).join('')).toBe(
      expectedText,
    );
  });
});
