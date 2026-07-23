import { describe, expect, it } from 'vitest';
import { extractSharedUrl } from './share-target';

describe('extractSharedUrl', () => {
  it('uses a valid http(s) share_url first', () => {
    expect(
      extractSharedUrl('https://example.com/x', 'https://fallback.test'),
    ).toBe('https://example.com/x');
  });

  it('falls back to the first URL embedded in share_text', () => {
    expect(
      extractSharedUrl(
        null,
        'Check this out https://www.instagram.com/reel/abc/ 😍',
      ),
    ).toBe('https://www.instagram.com/reel/abc/');
  });

  it('returns null when no http(s) URL is present', () => {
    expect(
      extractSharedUrl('mailto:hello@example.com', 'nothing to see'),
    ).toBeNull();
  });

  it('trims trailing sentence punctuation from text-extracted URLs', () => {
    expect(extractSharedUrl(null, 'see https://example.com/a.')).toBe(
      'https://example.com/a',
    );
  });

  it('keeps balanced closing parens but sheds unbalanced ones', () => {
    expect(
      extractSharedUrl(
        null,
        'https://en.wikipedia.org/wiki/Rust_(programming_language)',
      ),
    ).toBe('https://en.wikipedia.org/wiki/Rust_(programming_language)');
    expect(extractSharedUrl(null, '(see https://example.com/a)')).toBe(
      'https://example.com/a',
    );
  });
});
