import { useState } from 'react';
import { FileText } from 'lucide-react';
import { YouTubeIcon } from '@/components/svg/youtube-icon';
import { YouTubeShortsIcon } from '@/components/svg/youtube-shorts-icon';
import { InstagramIcon } from '@/components/svg/instagram-icon';
import { TikTokIcon } from '@/components/svg/tiktok-icon';
import { GitHubIcon } from '@/components/svg/github-icon';
import { Tooltip } from '@/components/ui/tooltip';

type Platform =
  | 'youtube'
  | 'youtube-short'
  | 'instagram'
  | 'tiktok'
  | 'github'
  | 'article'
  | 'unknown';

function parseUrl(url: string): { host: string; path: string } {
  try {
    const parsed = new URL(url);
    return {
      host: parsed.hostname.toLowerCase().replace(/^(www|m)\./, ''),
      path: parsed.pathname,
    };
  } catch {
    return { host: '', path: '' };
  }
}

function platformFromUrl(
  url: string,
  contentType?: string,
): Platform {
  const { host, path } = parseUrl(url);
  if (
    host === 'youtu.be' ||
    (host.endsWith('youtube.com') && path === '/watch')
  )
    return 'youtube';
  if (host.endsWith('youtube.com') && path.startsWith('/shorts/'))
    return 'youtube-short';
  if (host.endsWith('instagram.com')) return 'instagram';
  if (host.endsWith('tiktok.com')) return 'tiktok';
  if (host === 'github.com') return 'github';
  if (contentType === 'article' || contentType === 'link') return 'article';
  return 'unknown';
}

function faviconUrl(url: string): string | null {
  const { host } = parseUrl(url);
  return host
    ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=32`
    : null;
}

const platformIcons: Partial<Record<Platform, React.ComponentType<React.SVGProps<SVGSVGElement>>>> = {
  youtube: YouTubeIcon,
  'youtube-short': YouTubeShortsIcon,
  instagram: InstagramIcon,
  tiktok: TikTokIcon,
  github: GitHubIcon,
};

function labelFor(
  platform: Platform,
  url: string,
  contentType?: string,
): string {
  if (platform === 'youtube-short') return 'YouTube Shorts';
  if (platform === 'youtube') return 'YouTube';
  if (platform === 'instagram') return 'Instagram';
  if (platform === 'tiktok') return 'TikTok';
  if (platform === 'github') return 'GitHub';
  if (platform === 'article') return parseUrl(url).host || 'Article';
  return contentType || 'Source';
}

export function PlatformGlyph({
  url,
  contentType,
  size = 16,
  className = 'text-muted',
}: {
  url: string;
  contentType?: string;
  size?: number;
  className?: string;
}) {
  const [faviconFailed, setFaviconFailed] = useState(false);
  const platform = platformFromUrl(url, contentType);
  const Icon = platformIcons[platform];

  if (Icon) {
    return (
      <Icon
        width={size}
        height={size}
        className={className}
        aria-hidden="true"
      />
    );
  }

  const favicon = faviconUrl(url);
  if (favicon && !faviconFailed) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={favicon}
        alt=""
        width={size}
        height={size}
        onError={() => setFaviconFailed(true)}
      />
    );
  }

  return (
    <FileText
      size={size}
      className={className}
      aria-hidden="true"
    />
  );
}

export function PlatformBadge({
  url,
  contentType,
}: {
  url: string;
  contentType: string;
}) {
  const platform = platformFromUrl(url, contentType);
  const label = labelFor(platform, url, contentType);

  return (
    <Tooltip content={`${label} source`}>
      <span
        className="inline-flex h-6 w-6 items-center justify-center rounded border border-line bg-canvas text-muted"
        aria-label={`${label} source`}
      >
        <PlatformGlyph
          url={url}
          contentType={contentType}
          size={14}
        />
      </span>
    </Tooltip>
  );
}
