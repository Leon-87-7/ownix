// @vitest-environment jsdom
import { render } from '@testing-library/react';
import { Brain, Inbox } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { PageHeader } from './page-shell';

function gradientStroke(container: HTMLElement) {
  const icon = container.querySelector('svg[stroke^="url(#"]');
  return icon?.getAttribute('stroke') ?? null;
}

describe('PageHeader icon gradient', () => {
  it('is deterministic for the same icon', () => {
    const a = render(<PageHeader title="Brain" icon={Brain} />);
    const b = render(<PageHeader title="Brain" icon={Brain} />);
    expect(gradientStroke(a.container)).not.toBeNull();
    expect(gradientStroke(a.container)).toBe(gradientStroke(b.container));
  });

  it('differs between icons so no two headers look the same', () => {
    const a = render(<PageHeader title="Brain" icon={Brain} />);
    const b = render(<PageHeader title="Intake" icon={Inbox} />);
    expect(gradientStroke(a.container)).not.toBe(gradientStroke(b.container));
  });
});
