// @vitest-environment jsdom
import { render, screen } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { IntakeLinksList, extractLinks } from './intake-links-list';

afterEach(() => {
  vi.restoreAllMocks();
});

const links = [
  { url: 'http://12ft.io', label: '12ft.io', description: 'Bypass any paywall' },
  { url: 'http://libgen.is', label: 'libgen.is', description: 'Free textbooks' },
];

describe('extractLinks', () => {
  it('finds the links artifact and drops malformed entries', () => {
    const found = extractLinks([
      { other: 1 },
      { links: [{ url: 'http://a.com' }, { label: 'no url' }, null] },
    ] as Array<Record<string, unknown>>);
    expect(found).toEqual([{ url: 'http://a.com', label: null, description: null }]);
  });

  it('rejects unsupported or malformed URLs', () => {
    const found = extractLinks([
      {
        links: [
          { url: 'https://safe.example/path' },
          { url: 'javascript:alert(1)' },
          { url: 'ftp://files.example/item' },
          { url: '/relative/path' },
          { url: 'not a url' },
        ],
      },
    ] as Array<Record<string, unknown>>);

    expect(found).toEqual([
      { url: 'https://safe.example/path', label: null, description: null },
    ]);
  });

  it('rejects links with malformed metadata', () => {
    const found = extractLinks([
      {
        links: [
          { url: 'https://safe.example/a', label: 'Safe', description: null },
          { url: 'https://safe.example/b', label: 12 },
          { url: 'https://safe.example/c', description: { text: 'bad' } },
        ],
      },
    ] as Array<Record<string, unknown>>);

    expect(found).toEqual([
      { url: 'https://safe.example/a', label: 'Safe', description: null },
    ]);
  });

  it('returns an empty list when no artifact carries links', () => {
    expect(extractLinks([{ note: 'x' }])).toEqual([]);
  });
});

describe('IntakeLinksList', () => {
  it('renders every URL as a real, opening-in-new-tab link', () => {
    render(<IntakeLinksList links={links} />);
    const a = screen.getByRole('link', { name: 'http://12ft.io' });
    expect(a).toHaveAttribute('href', 'http://12ft.io');
    expect(a).toHaveAttribute('target', '_blank');
    expect(screen.getByText('2 links')).toBeInTheDocument();
  });

  it('copies the plain one-per-line URL list', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    // userEvent.setup() installs its own clipboard stub, so override afterwards.
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });

    render(<IntakeLinksList links={links} />);
    await user.click(screen.getByRole('button', { name: /copy all/i }));

    expect(writeText).toHaveBeenCalledWith('http://12ft.io\nhttp://libgen.is');
    expect(await screen.findByRole('button', { name: /copied/i })).toBeInTheDocument();
  });

  it('stays silent when there are no links', () => {
    const { container } = render(<IntakeLinksList links={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
