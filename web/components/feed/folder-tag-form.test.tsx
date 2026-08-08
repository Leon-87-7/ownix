// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FolderTagForm } from './folder-tag-form';

describe('FolderTagForm', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockTopics(
    topics: { topic: string; link_ids: string[]; count: number }[] = [
      { topic: 'rust', link_ids: ['l1'], count: 1 },
      { topic: 'screeners', link_ids: ['l2', 'l3'], count: 2 },
    ],
  ) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      if (typeof url === 'string' && url.endsWith('/link-topics')) {
        return { ok: true, json: async () => topics } as Response;
      }
      if (url === '/api/controls/tags' && method === 'POST') {
        return { ok: true, json: async () => ({ id: 'tag-1' }) } as Response;
      }
      if (url.includes('/tags/tag-1')) {
        return { ok: true, json: async () => ({}) } as Response;
      }
      throw new Error(`unexpected fetch: ${url} ${method}`);
    });
  }

  it('shows each folder checked by default with its link count', async () => {
    vi.stubGlobal('fetch', mockTopics());
    render(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={() => {}}
      />,
    );

    await waitFor(() => expect(screen.getByText('rust')).toBeTruthy());
    expect(screen.getByText('screeners')).toBeTruthy();
    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes.every((c) => c.checked)).toBe(true);
  });

  it('expands the color/icon picker when the chip is clicked', async () => {
    vi.stubGlobal('fetch', mockTopics());
    render(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={() => {}}
      />,
    );

    await waitFor(() => expect(screen.getByText('rust')).toBeTruthy());
    expect(screen.queryByText('Color')).toBeNull();

    fireEvent.click(screen.getByLabelText('Change color and icon for rust'));

    expect(screen.getByText('Color')).toBeTruthy();
    expect(screen.getByText('Icon')).toBeTruthy();
  });

  it('unchecking a folder disables it from the create count', async () => {
    vi.stubGlobal('fetch', mockTopics([{ topic: 'rust', link_ids: ['l1'], count: 1 }]));
    render(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={() => {}}
      />,
    );

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Create 1 Tag/ })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole('checkbox'));

    expect(
      screen.getByRole('button', { name: /Create Tag/ }),
    ).toHaveProperty('disabled', true);
  });

  it('Skip closes without issuing any mutation', async () => {
    const fetchMock = mockTopics();
    vi.stubGlobal('fetch', fetchMock);
    const onOpenChange = vi.fn();
    render(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={onOpenChange}
      />,
    );

    await waitFor(() => expect(screen.getByText('rust')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    // Only the initial GET — no POST calls.
    expect(fetchMock.mock.calls.every(([, init]) => !init || init.method === undefined)).toBe(
      true,
    );
  });

  it('confirming creates tags, attaches them, and closes the dialog', async () => {
    vi.stubGlobal('fetch', mockTopics([{ topic: 'rust', link_ids: ['l1', 'l2'], count: 2 }]));
    const onOpenChange = vi.fn();
    render(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={onOpenChange}
      />,
    );

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Create 1 Tag/ })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole('button', { name: /Create 1 Tag/ }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it('reloads from scratch every time it is opened', async () => {
    const fetchMock = mockTopics();
    vi.stubGlobal('fetch', fetchMock);
    const { rerender } = render(
      <FolderTagForm
        jobId="job1"
        open={false}
        onOpenChange={() => {}}
      />,
    );

    expect(fetchMock).not.toHaveBeenCalled();

    rerender(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={() => {}}
      />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });
});
