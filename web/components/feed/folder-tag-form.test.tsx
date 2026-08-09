// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { FolderTagForm } from './folder-tag-form';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  vi.unstubAllGlobals();
});
afterAll(() => server.close());

function useTopics(
  topics: { topic: string; link_ids: string[]; count: number }[] = [
    { topic: 'rust', link_ids: ['l1'], count: 1 },
    { topic: 'screeners', link_ids: ['l2', 'l3'], count: 2 },
  ],
) {
  server.use(http.get('/api/jobs/:jobId/link-topics', () => HttpResponse.json(topics)));
}

describe('FolderTagForm', () => {
  it('shows each folder checked by default with its link count', async () => {
    useTopics();
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
    useTopics();
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
    useTopics([{ topic: 'rust', link_ids: ['l1'], count: 1 }]);
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

    expect(screen.getByRole('button', { name: /Create Tag/ })).toHaveProperty(
      'disabled',
      true,
    );
  });

  it('Skip closes without issuing any mutation', async () => {
    const mutations: string[] = [];
    useTopics();
    server.use(
      http.post('/api/controls/tags', ({ request }) => {
        mutations.push(`${request.method} ${new URL(request.url).pathname}`);
        return HttpResponse.json({ id: 'tag-1' }, { status: 201 });
      }),
    );
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
    expect(mutations).toEqual([]);
  });

  it('confirming creates tags, attaches them, and closes the dialog', async () => {
    const calls: { url: string; body?: unknown }[] = [];
    useTopics([{ topic: 'rust', link_ids: ['l1', 'l2'], count: 2 }]);
    server.use(
      http.post('/api/controls/tags', async ({ request }) => {
        calls.push({ url: new URL(request.url).pathname, body: await request.json() });
        return HttpResponse.json({ id: 'tag-1' }, { status: 201 });
      }),
      http.post('/api/brain/links/:linkId/tags/:tagId', ({ request }) => {
        calls.push({ url: new URL(request.url).pathname });
        return new HttpResponse(null, { status: 201 });
      }),
    );
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
    expect(calls.find((call) => call.url === '/api/controls/tags')?.body).toMatchObject({
      name: 'rust',
    });
    expect(calls.filter((call) => call.url.includes('/tags/tag-1')).map((call) => call.url).sort())
      .toEqual(['/api/brain/links/l1/tags/tag-1', '/api/brain/links/l2/tags/tag-1'].sort());
  });

  it('reloads from scratch every time it is opened', async () => {
    let loads = 0;
    server.use(
      http.get('/api/jobs/:jobId/link-topics', () => {
        loads += 1;
        return HttpResponse.json([{ topic: 'rust', link_ids: ['l1'], count: 1 }]);
      }),
    );
    const { rerender } = render(
      <FolderTagForm
        jobId="job1"
        open={false}
        onOpenChange={() => {}}
      />,
    );

    expect(loads).toBe(0);

    rerender(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={() => {}}
      />,
    );

    await waitFor(() => expect(loads).toBe(1));

    rerender(
      <FolderTagForm
        jobId="job1"
        open={false}
        onOpenChange={() => {}}
      />,
    );
    rerender(
      <FolderTagForm
        jobId="job1"
        open={true}
        onOpenChange={() => {}}
      />,
    );

    await waitFor(() => expect(loads).toBe(2));
  });
});
