// @vitest-environment jsdom
import { render, screen, waitFor, within } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DomainsPanel } from './domains-panel';

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('DomainsPanel', () => {
  it('adds a domain to Allowed by default, without touching the toggle', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((input, init) => {
      const url = String(input);
      if (url === '/api/controls/allowed-domains' && init?.method === 'POST')
        return Promise.resolve(jsonResponse({ domain: 'example.com' }));
      if (url.endsWith('/allowed-domains') || url.endsWith('/ignored-domains'))
        return Promise.resolve(jsonResponse([]));
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });

    render(<DomainsPanel />);
    await userEvent.type(screen.getByLabelText(/domain or url/i), 'example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));

    const allowedList = screen.getByRole('heading', { name: 'Allowed' }).nextElementSibling as HTMLElement;
    expect(await within(allowedList).findByText('example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Allowed' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('adds to Ignored when toggled, then resets the toggle back to Allowed', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((input, init) => {
      const url = String(input);
      if (url === '/api/controls/ignored-domains' && init?.method === 'POST')
        return Promise.resolve(jsonResponse({ domain: 'netflix.com' }));
      if (url.endsWith('/allowed-domains') || url.endsWith('/ignored-domains'))
        return Promise.resolve(jsonResponse([]));
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });

    render(<DomainsPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Ignored' }));
    await userEvent.type(screen.getByLabelText(/domain or url/i), 'netflix.com');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));

    expect(await screen.findByText('netflix.com')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Allowed' })).toHaveAttribute('aria-pressed', 'true'),
    );
  });

  it('removes a domain via its pill button', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith('/allowed-domains')) return Promise.resolve(jsonResponse(['example.com']));
      if (url.endsWith('/ignored-domains')) return Promise.resolve(jsonResponse([]));
      if (init?.method === 'DELETE') return Promise.resolve(jsonResponse({}));
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });

    render(<DomainsPanel />);
    expect(await screen.findByText('example.com')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Remove example.com' }));

    await waitFor(() => expect(screen.queryByText('example.com')).not.toBeInTheDocument());
  });
});
