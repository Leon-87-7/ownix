'use client';

import { useRef } from 'react';
import { OwnixChevronDown } from '@/components/svg/ownix-chevron-down';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';

/** One collapsible block on Settings. Native `<details>`, so the open/closed
 * state costs no React state; the only scripted part is pulling a section back
 * into view when opening one pushes it off-screen. */
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
  const ref = useRef<HTMLDetailsElement>(null);
  const reducedMotion = useReducedMotion();

  return (
    <details
      ref={ref}
      open={defaultOpen}
      onToggle={() => {
        // `toggle` fires on close too — scrolling then yanks the page while the
        // user is collapsing a section.
        if (!ref.current?.open) return;
        ref.current.scrollIntoView?.({
          behavior: reducedMotion ? 'auto' : 'smooth',
          block: 'nearest',
        });
      }}
      className="group overflow-hidden rounded-lg border border-line bg-surface"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-semibold text-ink transition-ui hover:bg-raised [&::-webkit-details-marker]:hidden">
        <span className={titleClassName}>{title}</span>
        <OwnixChevronDown className="h-4 w-4 text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-line bg-canvas p-4">{children}</div>
    </details>
  );
}
