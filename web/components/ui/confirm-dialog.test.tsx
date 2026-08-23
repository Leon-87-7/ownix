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

  it('renders optional children between description and actions', async () => {
    render(
      <ConfirmDialog
        trigger={<button>Delete job</button>}
        title="Delete?"
        description="Cannot be undone"
        confirmLabel="Delete"
        onConfirm={vi.fn()}
      >
        <label>
          <input type="checkbox" /> Also remove the 3 links
        </label>
      </ConfirmDialog>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    await waitFor(() => expect(screen.getByText('Also remove the 3 links')).toBeTruthy());
  });

  it('closes on Escape', async () => {
    render(
      <ConfirmDialog trigger={<button>Open</button>} title="Delete?" description="No undo" confirmLabel="Delete" onConfirm={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByText('Delete?')).toBeNull());
  });

  it('disables the confirm button when confirmDisabled is true', async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        trigger={<button>Delete job</button>}
        title="Delete?"
        description="Cannot be undone"
        confirmLabel="Delete permanently"
        confirmDisabled
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    const confirmButton = await screen.findByRole('button', { name: 'Delete permanently' });
    expect(confirmButton).toBeDisabled();
    fireEvent.click(confirmButton);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
