/** CONTEXT.md "Paste parsing": per line, extract every scheme'd URL; a line
 * with none contributes its whole trimmed text as one token instead. The
 * server (validators.coerce_url) is the only thing that decides what's
 * actually a URL — this only splits, it never validates or rejects. */
const URL_TOKEN_RE = /https?:\/\/\S+/g;

export function parseBatchLinkInput(text: string): string[] {
  const seen = new Set<string>();
  const tokens: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const matches = line.match(URL_TOKEN_RE);
    for (const token of matches && matches.length > 0 ? matches : [line]) {
      if (!seen.has(token)) {
        seen.add(token);
        tokens.push(token);
      }
    }
  }
  return tokens;
}
