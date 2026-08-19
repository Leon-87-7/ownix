import { OwnixShareIcon } from "@/components/svg/ownix-share-icon";
import { isSafeHttpUrl } from "@/lib/job-detail-utils";

/** External-link glyph for a job card's title row; renders nothing for unsafe/non-http URLs. */
export function ShareLinkButton({ url }: { url: string }) {
  if (!isSafeHttpUrl(url)) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(event) => event.stopPropagation()}
      aria-label={`Open ${url} in a new tab`}
      className="pointer-events-auto relative z-10 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted transition-ui hover:text-signal"
    >
      <OwnixShareIcon
        className="h-3.5 w-3.5"
        aria-hidden="true"
      />
    </a>
  );
}
