'use client';

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
          // Scale from the trigger, not the tooltip's own center — apple-design
          // skill §7 (anchor interactions to their source). Radix computes this
          // origin from the actual side/align/collision result each render.
          style={{ transformOrigin: 'var(--radix-tooltip-content-transform-origin)' }}
          className={`material-chip z-50 max-w-xs rounded-md border border-line bg-[rgb(32_35_41/var(--material-opacity))] px-2 py-1 text-xs leading-snug text-ink shadow-overlay contrast-more:border-line-strong data-[state=closed]:animate-material-out data-[state=delayed-open]:animate-material-in data-[state=instant-open]:animate-material-in motion-reduce:animate-none ${
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
