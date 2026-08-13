import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GhostButton } from './ghost-button';

describe('GhostButton', () => {
  it('renders a non-submitting contrasignal button by default', () => {
    render(<GhostButton>Keep looking</GhostButton>);

    const button = screen.getByRole('button', {
      name: 'Keep looking',
    });
    expect(button).toHaveAttribute('type', 'button');
    expect(button).toHaveClass('border-b-contrasignal-deep');
  });

  it('supports the signal edge and caller styling', () => {
    render(
      <GhostButton
        accent="signal"
        className="h-9 bg-surface"
      >
        Commands
      </GhostButton>,
    );

    expect(
      screen.getByRole('button', { name: 'Commands' }),
    ).toHaveClass('border-b-signal', 'h-9', 'bg-surface');
  });

  it('can render as a link', () => {
    render(
      <GhostButton
        as="a"
        href="#capture"
      >
        More ways to add
      </GhostButton>,
    );

    expect(
      screen.getByRole('link', { name: 'More ways to add' }),
    ).toHaveAttribute('href', '#capture');
  });

  it('preserves an explicit submit type', () => {
    render(<GhostButton type="submit">Add links</GhostButton>);

    expect(screen.getByRole('button', { name: 'Add links' })).toHaveAttribute(
      'type',
      'submit',
    );
  });
});
