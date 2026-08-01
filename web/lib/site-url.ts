// Fallback matches the pinned Telegram Login Widget domain
// (docs/ops/vercel-deploy.md) — robots.ts, sitemap.ts, and JSON-LD all need a
// guaranteed absolute URL, unlike layout.tsx's metadataBase which is allowed
// to stay undefined.
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || 'https://app.leondev.xyz';
