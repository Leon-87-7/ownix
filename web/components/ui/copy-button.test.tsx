// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { CopyButton } from './copy-button';

describe('CopyButton', () => {
  it('copies the value and shows confirmation', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<CopyButton value="hello" ariaLabel="Copy text" label="Copy" />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy text' }));
    await waitFor(() => expect(screen.getByText('Copied!')).toBeInTheDocument());
    expect(writeText).toHaveBeenCalledWith('hello');
  });

  it('does not warn about setState after unmount when copy timer is pending', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    const { unmount } = render(<CopyButton value="hello" ariaLabel="Copy text" label="Copy" />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy text' }));
    await waitFor(() => expect(screen.getByText('Copied!')).toBeInTheDocument());
    unmount();
    await new Promise((resolve) => setTimeout(resolve, 1600));
    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('unmounted component'));
    errorSpy.mockRestore();
  });
});
