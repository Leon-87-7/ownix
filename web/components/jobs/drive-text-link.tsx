import { OwnixShareIcon } from '@/components/svg/ownix-share-icon';

/** Bordered "open this in Drive" link. Shared by the job actions bar and the
 * screenshots section. */
export function DriveTextLink({
  href,
  label,
  ariaLabel,
}: {
  href: string;
  label: string;
  ariaLabel?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-line px-3 py-1.5 text-button font-medium text-ink transition-ui hover:bg-raised"
    >
      {label}{' '}
      <OwnixShareIcon className="h-[18px] w-[18px]" aria-hidden="true" />
    </a>
  );
}
