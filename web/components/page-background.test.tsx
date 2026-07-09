// @vitest-environment jsdom
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PageBackground } from './page-background';

describe('PageBackground', () => {
  it('renders a quiet tokenized canvas without page artwork', () => {
    const { container } = render(<PageBackground />);
    const layer = container.firstElementChild as HTMLElement;

    expect(layer.className).toContain('bg-canvas');
    expect(layer.getAttribute('style')).toBeNull();
  });
});
