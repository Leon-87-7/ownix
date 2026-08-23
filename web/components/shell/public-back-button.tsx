'use client';

import { useRouter } from 'next/navigation';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';

// Same icon-back pattern as the job detail page (#192) — history.back() with
// a fallback for a page opened directly (no prior entry), landing on the
// public marketing home rather than a dashboard route these pages don't
// require auth for.
export function PublicBackButton() {
  const router = useRouter();

  const handleBack = () => {
    if (window.history.length > 1) router.back();
    else router.push('/');
  };

  return (
    <button
      type="button"
      onClick={handleBack}
      aria-label="Back"
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-muted transition-ui hover:text-ink focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface"
    >
      <OwnixChevronRight
        aria-hidden="true"
        className="h-3.5 w-3.5 rotate-180"
      />
    </button>
  );
}
