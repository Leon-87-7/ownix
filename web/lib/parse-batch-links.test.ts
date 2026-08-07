import { describe, expect, it } from 'vitest';
import { parseBatchLinkInput } from './parse-batch-links';

describe('parseBatchLinkInput', () => {
  it('splits a plain multi-line paste', () => {
    expect(
      parseBatchLinkInput(
        'https://land-book.com\nhttps://godly.website\nhttps://mobbin.com',
      ),
    ).toEqual([
      'https://land-book.com',
      'https://godly.website',
      'https://mobbin.com',
    ]);
  });

  it('the screenshot bug: a whitespace-joined blob splits into its URLs, not one blob', () => {
    expect(
      parseBatchLinkInput(
        'https://land-book.com https://godly.website https://mobbin.com',
      ),
    ).toEqual([
      'https://land-book.com',
      'https://godly.website',
      'https://mobbin.com',
    ]);
  });

  it('discards a label on the same line as a URL', () => {
    expect(parseBatchLinkInput('Design Systems — https://land-book.com')).toEqual([
      'https://land-book.com',
    ]);
  });

  it('a schemeless line passes through whole, for the server to accept or reject', () => {
    // Bare domain alone on a line: server-side coerce_url accepts it.
    expect(parseBatchLinkInput('land-book.com')).toEqual(['land-book.com']);
    // Prose: server-side coerce_url rejects it — the client does not guess.
    expect(parseBatchLinkInput('I checked google.com yesterday')).toEqual([
      'I checked google.com yesterday',
    ]);
  });

  it('dedupes within the paste, preserving first-seen order', () => {
    expect(
      parseBatchLinkInput(
        'https://a.com\nhttps://b.com\nhttps://a.com',
      ),
    ).toEqual(['https://a.com', 'https://b.com']);
  });

  it('ignores blank lines', () => {
    expect(parseBatchLinkInput('https://a.com\n\n\nhttps://b.com\n')).toEqual([
      'https://a.com',
      'https://b.com',
    ]);
  });

  it('empty input yields no tokens', () => {
    expect(parseBatchLinkInput('')).toEqual([]);
    expect(parseBatchLinkInput('   \n  \n')).toEqual([]);
  });

  it('a bookmark-file-style duplicate collapses to one token', () => {
    // Matches the 3 duplicate URLs found in the reference bookmark export.
    expect(
      parseBatchLinkInput(
        'https://x.com\nhttps://y.com\nhttps://x.com\nhttps://z.com\nhttps://y.com',
      ),
    ).toEqual(['https://x.com', 'https://y.com', 'https://z.com']);
  });
});
