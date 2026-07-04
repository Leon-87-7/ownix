'use client';

import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ComponentPropsWithoutRef, ReactNode } from 'react';

export const Dialog = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;

export function DialogContent({
  children,
  className = '',
  ...props
}: ComponentPropsWithoutRef<typeof RadixDialog.Content>) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="fixed inset-0 z-50 bg-canvas/70 backdrop-blur-sm data-[state=closed]:animate-tooltip-out data-[state=open]:animate-tooltip-in motion-reduce:animate-none" />
      <RadixDialog.Content
        className={`fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-line bg-surface p-5 shadow-overlay data-[state=closed]:animate-tooltip-out data-[state=open]:animate-tooltip-in motion-reduce:animate-none focus:outline-none ${className}`}
        {...props}
      >
        {children}
        <RadixDialog.Close className="absolute right-2 top-2 inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted transition-[background-color,color,transform] duration-150 hover:bg-raised hover:text-ink active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100">
          <X
            className="h-4 w-4"
            aria-hidden="true"
          />
          <span className="sr-only">Close</span>
        </RadixDialog.Close>
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

export function DialogTitle({
  className = '',
  ...props
}: ComponentPropsWithoutRef<typeof RadixDialog.Title>) {
  return (
    <RadixDialog.Title
      className={`text-base font-semibold text-ink ${className}`}
      {...props}
    />
  );
}

export function DialogDescription({
  children,
}: {
  children?: ReactNode;
}) {
  if (!children) return null;
  return (
    <RadixDialog.Description className="mt-1 text-sm text-body">
      {children}
    </RadixDialog.Description>
  );
}
