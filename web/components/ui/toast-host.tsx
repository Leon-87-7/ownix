'use client';

import { useToasts } from '@/lib/toast';

/** Mounted once near the app root; `toast()` from `@/lib/toast` pushes into it
 * from anywhere. Stacks top-center, newest on top. */
export function ToastHost() {
  const toasts = useToasts();
  if (toasts.length === 0) return null;
  return (
    <div className="pointer-events-none fixed top-4 left-1/2 z-[70] flex -translate-x-1/2 flex-col-reverse items-center gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={`pointer-events-auto max-w-sm rounded-lg border px-4 py-3 text-sm shadow-overlay ${
            t.variant === 'error'
              ? 'border-status-error/40 bg-status-error-tint text-status-error'
              : 'border-line bg-surface text-ink'
          }`}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
