/** Guesses a job's content type from its URL.
 *
 * Only used to paint an optimistic Feed row when an accepted `POST /api/jobs`
 * response omits `content_type`. The authority is the backend's own routing
 * table (`detect_pipeline` in `src/utils/validators.py`); this is a deliberate
 * client-side echo of it, so a change there wants a change here.
 */
export function inferContentTypeFromUrl(rawUrl: string): string {
  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, '');
    const path = parsed.pathname.toLowerCase();

    // Match the exact apex or a dot-separated subdomain so lookalike hosts
    // (fakeyoutube.com, eviltiktok.com) don't slip through endsWith().
    const isHost = (domain: string) =>
      host === domain || host.endsWith(`.${domain}`);

    if (host === 'github.com') return 'repo';
    if (isHost('youtube.com') && path === '/watch') return 'long';
    if (host === 'youtu.be') return 'long';
    if (isHost('youtube.com') && path.startsWith('/shorts/')) return 'short';
    if (isHost('instagram.com') && path.startsWith('/reel/')) return 'short';
    if (isHost('tiktok.com') && path.includes('/video/')) return 'short';
  } catch {
    return 'article';
  }

  return 'article';
}
