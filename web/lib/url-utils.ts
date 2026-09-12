/** Guards against `javascript:`/`data:` etc. before a raw URL is used as an
 * href. Delegates to `safeUrl` rather than keeping the second, regex-based
 * implementation this codebase used to carry alongside it. */
export function isSafeHttpUrl(url: string): boolean {
  return safeUrl(url) !== undefined;
}

/** Parses `url` and returns it unchanged if http(s), else undefined (unsafe/unparseable). */
export function safeUrl(url: string): string | undefined {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
      ? url
      : undefined;
  } catch {
    return undefined;
  }
}
