// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from './confirm-dialog';

describe('ConfirmDialog', () => {
  it('focuses Cancel and confirms from a trapped dialog', async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        trigger={<button>Delete job</button>}
        title="Delete?"
        description="Cannot be undone"
        confirmLabel="Delete permanently"
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus());
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledOnce());
  });

  it('closes on Escape', async () => {
    render(
      <ConfirmDialog trigger={<button>Open</button>} title="Delete?" description="No undo" confirmLabel="Delete" onConfirm={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByText('Delete?')).toBeNull());
  });
});
