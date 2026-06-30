import { useState } from "react";
import { FileText } from "lucide-react";
import { siGithub, siInstagram, siTiktok, siYoutube } from "simple-icons";
import { Tooltip } from "@/components/ui/tooltip";

type Platform = "youtube" | "youtube-short" | "instagram" | "tiktok" | "github" | "article" | "unknown";

function hostFromUrl(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^(www|m)\./, "");
  } catch {
    return "";
  }
}

function pathFromUrl(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return "";
  }
}

function platformFromUrl(url: string, contentType?: string): Platform {
  const host = hostFromUrl(url);
  const path = pathFromUrl(url);
  if (host === "youtu.be" || (host.endsWith("youtube.com") && path === "/watch")) return "youtube";
  if (host.endsWith("youtube.com") && path.startsWith("/shorts/")) return "youtube-short";
  if (host.endsWith("instagram.com")) return "instagram";
  if (host.endsWith("tiktok.com")) return "tiktok";
  if (host === "github.com") return "github";
  if (contentType === "article") return "article";
  return "unknown";
}

function faviconUrl(url: string): string | null {
  const host = hostFromUrl(url);
  return host ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=32` : null;
}

function iconPath(platform: Platform): string | null {
  if (platform === "youtube" || platform === "youtube-short") return siYoutube.path;
  if (platform === "instagram") return siInstagram.path;
  if (platform === "tiktok") return siTiktok.path;
  if (platform === "github") return siGithub.path;
  return null;
}

function labelFor(platform: Platform, url: string, contentType?: string): string {
  if (platform === "youtube-short") return "YouTube Shorts";
  if (platform === "youtube") return "YouTube";
  if (platform === "instagram") return "Instagram";
  if (platform === "tiktok") return "TikTok";
  if (platform === "github") return "GitHub";
  if (platform === "article") return hostFromUrl(url) || "Article";
  return contentType || "Source";
}

export function PlatformGlyph({
  url,
  contentType,
  size = 16,
  className = "text-muted",
}: {
  url: string;
  contentType?: string;
  size?: number;
  className?: string;
}) {
  const [faviconFailed, setFaviconFailed] = useState(false);
  const platform = platformFromUrl(url, contentType);
  const path = iconPath(platform);

  if (path) {
    return (
      <svg viewBox="0 0 24 24" width={size} height={size} className={className} aria-hidden="true">
        <path d={path} fill="currentColor" />
      </svg>
    );
  }

  const favicon = platform === "article" ? faviconUrl(url) : null;
  if (favicon && !faviconFailed) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={favicon} alt="" width={size} height={size} onError={() => setFaviconFailed(true)} />;
  }

  return <FileText size={size} className={className} aria-hidden="true" />;
}

export function PlatformBadge({ url, contentType }: { url: string; contentType: string }) {
  const platform = platformFromUrl(url, contentType);
  const label = labelFor(platform, url, contentType);

  return (
    <Tooltip content={`${label} source`}>
      <span
        className="inline-flex h-6 w-6 items-center justify-center rounded border border-line bg-canvas text-muted"
        aria-label={`${label} source`}
      >
        <PlatformGlyph url={url} contentType={contentType} size={14} />
      </span>
    </Tooltip>
  );
}
