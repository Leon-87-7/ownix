const meta = $input.item.json;
const description = meta.description || '';

const GENERIC_ROOTS = [
  'github.com',
  'claude.ai',
  'openai.com',
  'twitter.com',
  'x.com',
  'discord.gg',
  'discord.com',
  'linkedin.com',
  'youtube.com',
  'youtu.be',
  'patreon.com',
  'ko-fi.com',
  'buymeacoffee.com',
  'bit.ly',
  't.co',
  'linktr.ee',
  'instagram.com',
  'facebook.com',
  'tiktok.com',
  'reddit.com',
];

const PROMO_SUBDOMAINS = ['get', 'try', 'go', 'link', 'ref', 'promo', 'deal', 'offers', 'start'];

function isPromoLink(hostname, pathname) {
  const sub = hostname.split('.')[0];
  if (!PROMO_SUBDOMAINS.includes(sub)) return false;
  const segments = pathname.split('/').filter((s) => s.length > 0);
  return segments.length === 1;
}

function isGenericRoot(hostname, pathname) {
  const isGeneric = GENERIC_ROOTS.some(
    (root) => hostname === root || hostname.endsWith('.' + root),
  );
  if (!isGeneric) return false;
  const segments = pathname.split('/').filter((s) => s.length > 0);
  // GitHub: only block the bare root — user profiles and repos pass through
  if (hostname === 'github.com' || hostname.endsWith('.github.com')) {
    return segments.length === 0;
  }
  return segments.length < 2;
}

const urlRegex = /https?:\/\/[^\s)>"'\]]+/g;
const rawUrls = description.match(urlRegex) || [];

const seen = new Set();
const filtered = [];

for (const raw of rawUrls) {
  // Strip non-printable/non-ASCII chars YouTube embeds in URLs (zero-width spaces, soft hyphens, BOM, etc.)
  const url = raw
    .replace(/[.,;:!?]+$/, '')
    .replace(/[^\x20-\x7E]/g, '');
  if (seen.has(url)) continue;
  seen.add(url);

  // Extract hostname + pathname without relying on the URL constructor
  const m = url.match(/^https?:\/\/([^/?#\s]+)(\/[^?#\s]*)?/);
  if (!m) continue;
  const hostname = m[1].toLowerCase();
  const pathname = m[2] || '/';

  if (isGenericRoot(hostname, pathname)) continue;
  if (isPromoLink(hostname, pathname)) continue;

  filtered.push(url);
}

const LABEL_KEYWORDS = [
  'free',
  'resource',
  'github',
  'repo',
  'guide',
  'apis',
  'markdown',
  'by',
  '+',
  'docs',
  'self',
  'hosted',
  'source',
];

const links = filtered
  .map((url) => {
    const escapedUrl = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const lineMatch = description.match(
      new RegExp('([^\\n]*)' + escapedUrl),
    );
    let label = '';
    if (lineMatch) {
      label = lineMatch[1]
        .replace(/https?:\/\/\S+/g, '')
        .replace(/[^\w\s\-().+]/g, ' ')
        .trim();
    }
    return { label: label || null, url };
  })
  .filter(({ label, url }) => {
    // GitHub links (anything beyond bare root) always pass
    if (/^https?:\/\/(www\.)?github\.com\/.+/.test(url)) return true;
    if (!label) return false;
    const lower = label.toLowerCase();
    return LABEL_KEYWORDS.some((kw) => lower.includes(kw));
  });

return {
  json: {
    ...meta,
    description_links: links,
    description_links_raw: links.map((l) => l.url).join('\n'),
  },
};
