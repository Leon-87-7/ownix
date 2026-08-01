import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/site-url';

// No lastModified: new Date() would report build/request time, not real
// content revision — a false-freshness signal is worse than none.
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: SITE_URL, changeFrequency: 'weekly', priority: 1 },
    { url: `${SITE_URL}/privacy`, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${SITE_URL}/terms`, changeFrequency: 'yearly', priority: 0.3 },
  ];
}
