'use client';

/* @ds
name: Tooltip
purpose: Hover/focus reveal for a supplemental label or machine fact that would clutter the resting UI.
variants:
  side top|bottom|left|right: placement relative to the trigger.
  align start|center|end: alignment along that side.
  mono: monospace body for machine facts (IDs, counts, timestamps).
when-not: Not for information a user must read to act (put that in the UI), and not on non-focusable triggers — keyboard users can't reach it.
notes: Renders nothing when content is empty; supports controlled open.
status: inferred
*/

import * as RadixTooltip from '@radix-ui/react-tooltip';
import { cloneElement } from 'react';
import type { ComponentPropsWithoutRef, ReactElement, ReactNode } from 'react';

const FOCUSABLE_TAGS = new Set(['a', 'button', 'input', 'select', 'textarea']);

// A tooltip trigger must be focusable so keyboard users can reveal it (WCAG
// 1.4.13). Natively-interactive children already are; give non-interactive
// intrinsic elements (span, p, …) a tabIndex so focus opens the tooltip too.
function focusableTrigger(child: ReactElement): ReactElement {
  const { tabIndex } = child.props as { tabIndex?: number };
  if (typeof child.type === 'string' && !FOCUSABLE_TAGS.has(child.type) && tabIndex === undefined) {
    return cloneElement(child, { tabIndex: 0 } as { tabIndex: number });
  }
  return child;
}

type TooltipContentProps = ComponentPropsWithoutRef<typeof RadixTooltip.Content>;

type TooltipProps = {
  children: ReactElement;
  content?: ReactNode;
  side?: TooltipContentProps['side'];
  align?: TooltipContentProps['align'];
  mono?: boolean;
  /** Controlled mode — Radix tooltips are hover/focus-only; pass these to also
   * open on tap (trigger sets open=true, Radix closes on outside/escape). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <RadixTooltip.Provider delayDuration={300} skipDelayDuration={200}>
      {children}
    </RadixTooltip.Provider>
  );
}

export function Tooltip({
  children,
  content,
  side = 'top',
  align = 'center',
  mono = false,
  open,
  onOpenChange,
}: TooltipProps) {
  if (content == null || content === false || content === '') return children;

  return (
    <RadixTooltip.Root open={open} onOpenChange={onOpenChange}>
      <RadixTooltip.Trigger asChild>{focusableTrigger(children)}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side={side}
          align={align}
          sideOffset={8}
          collisionPadding={12}
          className={`z-50 max-w-xs rounded-md border border-line bg-raised px-2 py-1 text-xs leading-snug text-ink shadow-overlay data-[state=closed]:animate-tooltip-out data-[state=delayed-open]:animate-tooltip-in data-[state=instant-open]:animate-tooltip-in motion-reduce:animate-none ${
            mono ? 'break-words font-mono [text-wrap:pretty]' : 'font-sans'
          }`}
        >
          {content}
          <RadixTooltip.Arrow className="fill-raised" width={10} height={5} />
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
