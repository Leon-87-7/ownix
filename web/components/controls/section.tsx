'use client';

import { OwnixChevronDown } from '@/components/svg/ownix-chevron-down';

/** One collapsible block on Settings. Native `<details>`, so the open/closed
 * state costs no React state and the open/close motion is the `.accordion`
 * rule in globals.css — no JS on the interaction path at all. */
export function Section({
  title,
  titleClassName,
  defaultOpen,
  children,
}: {
  title: string;
  titleClassName?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className="accordion group overflow-hidden rounded-lg border border-line bg-surface"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-semibold text-ink transition-ui hover:bg-raised [&::-webkit-details-marker]:hidden">
        <span className={titleClassName}>{title}</span>
        {/* Matches the content's 300ms/out-quart so chevron and panel land together. */}
        <OwnixChevronDown className="h-4 w-4 text-muted transition-transform duration-300 ease-out-quart group-open:rotate-180" />
      </summary>
      <div className="border-t border-line bg-canvas p-4">{children}</div>
    </details>
  );
}
