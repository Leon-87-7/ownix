'use client';

import Link from 'next/link';
import { Check, Copy, type LucideIcon } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';
import { useCopyFeedback } from '@/lib/hooks/useCopyFeedback';
import { usePressFeedback } from '@/lib/hooks/usePressFeedback';

/** Borderless icon buttons shared by the job detail page's preview cards, so
 * every card carries the same copy/edit/download/open affordances. */
export const CARD_ACTION_BUTTON =
  'inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted transition-ui hover:text-ink';

type CardActionProps = {
  icon: LucideIcon | ((props: { className?: string }) => React.ReactNode);
  /** Accessible name. Stays fixed even when `tooltip` changes. */
  label: string;
  /** Hover text, when it should differ from the accessible name (e.g. the copy
   * button's transient "Copied"). Defaults to `label`. */
  tooltip?: string;
  disabled?: boolean;
  className?: string;
} & (
  | { onClick: () => void; href?: never; external?: never }
  /** Internal route → next/link. Add `external` for an off-site target. */
  | { href: string; external?: boolean; onClick?: never }
);

/** One card affordance. Renders a `<button>`, a `<Link>`, or an external
 * `<a>` depending on which of `onClick` / `href` is supplied — previously four
 * near-identical components that differed only in icon and element. */
export function CardAction({
  icon: Icon,
  label,
  tooltip,
  disabled,
  className,
  onClick,
  href,
  external,
}: CardActionProps) {
  const pressFeedback = usePressFeedback();
  const classes = `${className ? `${className} ` : ''}${CARD_ACTION_BUTTON}`;
  const glyph = <Icon className="h-4 w-4" aria-hidden="true" />;

  const control =
    href === undefined ? (
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        className={classes}
        {...pressFeedback}
      >
        {glyph}
      </button>
    ) : external ? (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={label}
        className={classes}
        {...pressFeedback}
      >
        {glyph}
      </a>
    ) : (
      <Link
        href={href}
        aria-label={label}
        className={classes}
        {...pressFeedback}
      >
        {glyph}
      </Link>
    );

  return <Tooltip content={tooltip ?? label}>{control}</Tooltip>;
}

/** CardAction plus the copied/not-copied swap. Kept as its own component rather
 * than a flag on CardAction: the copy state belongs to this button, not to the
 * shared chrome. */
export function CardCopyAction({
  value,
  label,
  className,
}: {
  value: string;
  label: string;
  className?: string;
}) {
  const { copied, copy } = useCopyFeedback(value);
  return (
    <CardAction
      icon={copied ? Check : Copy}
      label={label}
      tooltip={copied ? 'Copied' : label}
      onClick={copy}
      className={className}
    />
  );
}
