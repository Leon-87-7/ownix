import Link from 'next/link';
import OwnixLogo from '@/app/ownix-logo.svg';

const linkClasses =
  'transition-ui hover:text-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface';

export default function Footer() {
  return (
    <footer className="z-10 border-t border-line py-6 text-sm text-muted w-5/12 min-w-[300px] mx-auto">
      {/* Below 450px: logo+wordmark grid stacked above a centered nav. At
          450px and up (landing page has no width cap, unlike auth-shell's
          narrower container, so this needs its own breakpoint) they share a
          row — wordmark left, nav right — no dividers either way. */}
      <div className="flex flex-col gap-3 min-[450px]:flex-row min-[450px]:items-center min-[450px]:justify-between">
        <div className="grid grid-cols-[auto_1fr] items-center gap-x-3">
          <OwnixLogo
            aria-hidden="true"
            focusable="false"
            className="h-10 w-10 "
          />
          <div className="flex flex-col">
            <span className="text-lg font-semibold text-body">
              Ownix
            </span>
            <span className="text-sm leading-6">
              <span className="italic">your internet,</span>{' '}
              <span className="font-mono">indexed.</span>
            </span>
          </div>
        </div>
        <nav className="flex text-body justify-center gap-4 min-[450px]:justify-end">
          <Link
            href="/privacy"
            className={linkClasses}
          >
            Privacy
          </Link>
          <Link
            href="/terms"
            className={linkClasses}
          >
            Terms
          </Link>
        </nav>
      </div>
    </footer>
  );
}
