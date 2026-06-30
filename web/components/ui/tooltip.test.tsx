import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Tooltip, TooltipProvider } from './tooltip';

function renderTooltip(node: React.ReactNode) {
  return render(<TooltipProvider>{node}</TooltipProvider>);
}

describe('Tooltip', () => {
  it('shows content on hover and associates the trigger with the tooltip', async () => {
    const user = userEvent.setup();
    renderTooltip(
      <Tooltip content="GitHub repository">
        <button type="button">GitHub</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole('button', { name: 'GitHub' });
    await user.hover(trigger);

    const tooltip = await screen.findByRole('tooltip');
    expect(tooltip).toHaveTextContent('GitHub repository');
    expect(trigger).toHaveAttribute('aria-describedby', tooltip.id);
  });

  it('shows content on focus and hides after Escape', async () => {
    const user = userEvent.setup();
    renderTooltip(
      <Tooltip content="Copy full output">
        <button type="button">Copy</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole('button', { name: 'Copy' });
    await user.tab();
    expect(trigger).toHaveFocus();
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Copy full output');

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('makes a non-interactive trigger focusable so keyboard users can reveal it', async () => {
    const user = userEvent.setup();
    renderTooltip(
      <Tooltip content="Full label">
        <span>Truncated</span>
      </Tooltip>,
    );

    const trigger = screen.getByText('Truncated');
    expect(trigger).toHaveAttribute('tabindex', '0');
    await user.tab();
    expect(trigger).toHaveFocus();
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Full label');
  });

  it('renders the child bare when content is nullish', () => {
    const { container } = renderTooltip(
      <Tooltip content={undefined}>
        <button type="button">No tooltip</button>
      </Tooltip>,
    );

    expect(screen.getByRole('button', { name: 'No tooltip' })).not.toHaveAttribute('aria-describedby');
    expect(container.querySelector('[data-radix-popper-content-wrapper]')).not.toBeInTheDocument();
  });

  it('applies the mono variant to machine-fact content', async () => {
    const user = userEvent.setup();
    renderTooltip(
      <Tooltip content="https://example.com/some/really/long/path" mono>
        <button type="button">URL</button>
      </Tooltip>,
    );

    await user.hover(screen.getByRole('button', { name: 'URL' }));
    // role="tooltip" sits on Radix's visually-hidden a11y node; the styled
    // content is its nearest ancestor carrying data-side.
    const tip = await screen.findByRole('tooltip');
    expect(tip.closest('[data-side]')).toHaveClass('font-mono');
  });
});
