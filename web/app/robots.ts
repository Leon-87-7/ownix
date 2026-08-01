import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/site-url';

// No explicit disallow list for dashboard routes: proxy.ts redirects
// anonymous crawlers to /login before they ever see real content, and the
// (dashboard) layout sets its own noindex — duplicating that route list here
// would just be a second place for it to drift out of sync.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/', disallow: '/api/' },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
