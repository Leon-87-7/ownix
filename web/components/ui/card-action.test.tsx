// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { Download } from 'lucide-react';
import { CardAction, CardCopyAction } from './card-action';

describe('CardAction', () => {
  it('renders a button and fires onClick when given onClick', () => {
    const onClick = vi.fn();
    render(<CardAction icon={Download} label="Download transcript" onClick={onClick} />);

    const button = screen.getByRole('button', { name: 'Download transcript' });
    expect(button.getAttribute('type')).toBe('button');
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('does not fire onClick while disabled', () => {
    const onClick = vi.fn();
    render(
      <CardAction icon={Download} label="Download transcript" onClick={onClick} disabled />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Download transcript' }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders an external anchor that opens in a new tab safely', () => {
    render(
      <CardAction
        icon={Download}
        label="Open in Drive"
        href="https://drive.google.com/file/abc"
        external
      />,
    );

    const link = screen.getByRole('link', { name: 'Open in Drive' });
    expect(link.getAttribute('href')).toBe('https://drive.google.com/file/abc');
    expect(link.getAttribute('target')).toBe('_blank');
    // Without noopener the opened tab can reach back through window.opener.
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('renders an internal link without the external tab attributes', () => {
    render(<CardAction icon={Download} label="Edit transcript" href="/jobs/1/transcript" />);

    const link = screen.getByRole('link', { name: 'Edit transcript' });
    expect(link.getAttribute('href')).toBe('/jobs/1/transcript');
    expect(link.getAttribute('target')).toBeNull();
  });

  it('keeps the accessible name fixed when a tooltip differs from it', () => {
    render(
      <CardAction icon={Download} label="Copy transcript" tooltip="Copied" onClick={vi.fn()} />,
    );

    expect(screen.getByRole('button', { name: 'Copy transcript' })).toBeTruthy();
  });
});

describe('CardCopyAction', () => {
  it('copies the value and keeps its accessible name through the copied swap', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<CardCopyAction value="transcript body" label="Copy transcript" />);

    fireEvent.click(screen.getByRole('button', { name: 'Copy transcript' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('transcript body'));
    expect(screen.getByRole('button', { name: 'Copy transcript' })).toBeTruthy();
  });
});
