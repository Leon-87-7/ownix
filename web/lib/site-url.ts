// Fallback matches the pinned Telegram Login Widget domain
// (docs/ops/vercel-deploy.md) — robots.ts, sitemap.ts, and JSON-LD all need a
// guaranteed absolute URL, unlike layout.tsx's metadataBase which is allowed
// to stay undefined. Trailing slash stripped so consumers can safely do
// `${SITE_URL}/path` without risking `//path`.
const configuredSiteUrl =
  process.env.NEXT_PUBLIC_SITE_URL?.trim() || 'https://app.leondev.xyz';

export const SITE_URL = configuredSiteUrl.replace(/\/+$/, '');
