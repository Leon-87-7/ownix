'use client';

import { useRef, useState, type ReactNode } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import * as RadixDialog from '@radix-ui/react-dialog';

type ConfirmDialogProps = {
  trigger: ReactNode;
  title: string;
  description: string;
  confirmLabel: string;
  pending?: boolean;
  onConfirm: () => void | Promise<void>;
};

export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel,
  pending = false,
  onConfirm,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent
        hideClose
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          cancelRef.current?.focus();
        }}
      >
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
        <div className="mt-5 flex justify-end gap-2">
          <RadixDialog.Close asChild>
            <button
              ref={cancelRef}
              type="button"
              disabled={pending}
              className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised disabled:opacity-50"
            >
              Cancel
            </button>
          </RadixDialog.Close>
          <button
            type="button"
            disabled={pending}
            onClick={async () => {
              await onConfirm();
              setOpen(false);
            }}
            className="h-8 rounded-md bg-status-error px-3 text-[13px] font-medium text-[#1b1309] transition-ui hover:brightness-110 disabled:opacity-50"
          >
            {pending ? 'Deleting…' : confirmLabel}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
