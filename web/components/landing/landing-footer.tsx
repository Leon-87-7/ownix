import Link from 'next/link';
import OwnixLogo from '@/app/ownix-logo.svg';
import { linkClasses } from './shared';

export function LandingFooter() {
  return (
    <footer className="z-10 border-t border-line py-6 text-sm text-muted w-11/12 max-w-7xl mx-auto">
      {/* Below 450px: logo+wordmark grid stacked above a centered nav. At
        450px and up (landing page has no width cap, unlike auth-shell's
        narrower container, so this needs its own breakpoint) they share a
        row - wordmark left, nav right - no dividers either way. */}
      <div className="flex flex-col px-3 gap-3 min-[450px]:flex-row min-[450px]:items-center min-[450px]:justify-between">
        <div className="grid grid-cols-[auto_1fr] items-center gap-x-3">
          <a
            href="#hero"
            aria-label="Back to top"
            className="hover:text-signal-bright"
          >
            <OwnixLogo
              aria-hidden="true"
              focusable="false"
              className="h-10 w-10 motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out-quart motion-safe:hover:scale-110 hover:text-contrasignal motion-safe:animate-[ownix-logo-cycle_7s_linear_infinite] motion-safe:hover:rotate-[-6deg]"
            />
          </a>
          <div className="flex flex-col">
            <span className="text-lg font-semibold text-body ">Ownix</span>
            <span className="text-sm leading-6">
              <span className="italic">your internet,</span>{' '}
              <span className="font-mono">own it.</span>
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
