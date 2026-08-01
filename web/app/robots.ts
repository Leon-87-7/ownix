import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/site-url';

// No explicit disallow list for dashboard routes: proxy.ts redirects
// anonymous crawlers to /login before they ever see real content, and the
// (dashboard) layout sets its own noindex — duplicating that route list here
// would just be a second place for it to drift out of sync.
export default function robots(): MetadataRoute.Robots {
  // Preview/staging Vercel deployments without NEXT_PUBLIC_SITE_URL set would
  // otherwise serve a sitemap/robots pointing at the production domain —
  // block crawling outright rather than let that leak into search results.
  // Unset VERCEL_ENV (local dev, self-hosted) falls through to normal rules.
  if (process.env.VERCEL_ENV && process.env.VERCEL_ENV !== 'production') {
    return { rules: { userAgent: '*', disallow: '/' } };
  }

  return {
    rules: { userAgent: '*', allow: '/', disallow: '/api/' },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
