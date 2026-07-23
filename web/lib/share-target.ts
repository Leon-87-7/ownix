/**
 * Resolve the URL from a Web Share Target GET hit (`share_url` / `share_text`
 * manifest params). Android apps commonly put the shared URL inside the text
 * field, so `share_text` is scanned as a fallback.
 *
 * Lives in lib/ (not the Feed page) because app-router pages reject unknown
 * exports at build time.
 */
export function extractSharedUrl(
  shareUrl: string | null,
  shareText: string | null,
): string | null {
  if (shareUrl) {
    try {
      const parsed = new URL(shareUrl);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        return parsed.toString();
      }
    } catch {
      // Fall through to Android-style URL-in-text shares.
    }
  }

  const textMatch = shareText?.match(/https?:\/\/\S+/i)?.[0];
  if (!textMatch) return null;
  // Shed sentence punctuation the regex swallowed ("see https://x.com/a."),
  // then unbalanced closing parens — but keep balanced ones, so Wikipedia-style
  // /wiki/Rust_(programming_language) URLs survive.
  let candidate = textMatch.replace(/[.,;:!?'"]+$/, '');
  while (
    candidate.endsWith(')') &&
    (candidate.match(/\(/g)?.length ?? 0) <
      (candidate.match(/\)/g)?.length ?? 0)
  ) {
    candidate = candidate.slice(0, -1);
  }
  try {
    return new URL(candidate).toString();
  } catch {
    return null;
  }
}
