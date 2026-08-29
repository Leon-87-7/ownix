"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { usePressFeedback } from "@/lib/hooks/usePressFeedback";
import type { ComponentPropsWithoutRef } from "react";

export const Sheet = RadixDialog.Root;

export function SheetContent({
  children,
  className = "",
  ...props
}: ComponentPropsWithoutRef<typeof RadixDialog.Content>) {
  const pressFeedback = usePressFeedback();
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="fixed inset-0 z-50 bg-canvas/70 backdrop-blur-sm data-[state=closed]:animate-tooltip-out data-[state=open]:animate-tooltip-in motion-reduce:animate-none" />
      <RadixDialog.Content
        className={`fixed inset-x-0 bottom-0 z-50 w-full rounded-t-2xl border border-line bg-surface p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-overlay data-[state=closed]:animate-slide-up-out data-[state=open]:animate-slide-up-in motion-reduce:animate-none focus:outline-none ${className}`}
        {...props}
      >
        {children}
        <RadixDialog.Close
          {...pressFeedback}
          className="absolute right-2 top-2 inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted transition-[background-color,color,transform] duration-150 hover:bg-raised hover:text-ink motion-reduce:transition-none"
        >
          <X className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">Close</span>
        </RadixDialog.Close>
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

export function SheetTitle({
  className = "",
  ...props
}: ComponentPropsWithoutRef<typeof RadixDialog.Title>) {
  return (
    <RadixDialog.Title
      className={`text-base font-semibold text-ink ${className}`}
      {...props}
    />
  );
}
