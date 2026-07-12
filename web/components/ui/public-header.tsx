import Link from 'next/link';
import OwnixLogo from '@/app/ownix-logo.svg';

const focusRing =
  'focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface';

export default function PublicHeader() {
  return (
    <header className="flex items-center justify-between gap-4 rounded-lg border border-line bg-surface/90 px-4 py-3 backdrop-blur-sm">
      <Link
        href="/"
        aria-label="Ownix home"
        className={`group flex items-center gap-2 rounded-md text-xl font-semibold tracking-tight text-ink ${focusRing}`}
      >
        <OwnixLogo
          aria-hidden="true"
          focusable="false"
          className="h-7 w-7 transition-transform duration-200 ease-out-quart group-hover:scale-110 group-hover:text-signal-bright group-hover:rotate-[-6deg]"
        />
        <span className="group-hover:text-contrasignal">Ownix</span>
      </Link>
      <nav
        className="flex items-center gap-1"
        aria-label="Public"
      >
        <Link
          href="/privacy"
          className={`hidden rounded-md px-3 py-2 text-sm font-medium text-body transition-ui hover:bg-raised hover:text-ink sm:inline-flex ${focusRing}`}
        >
          Privacy
        </Link>
        <Link
          href="/terms"
          className={`hidden rounded-md px-3 py-2 text-sm font-medium text-body transition-ui hover:bg-raised hover:text-ink sm:inline-flex ${focusRing}`}
        >
          Terms
        </Link>
        <Link
          href="/login"
          className={`ml-1 inline-flex h-8 items-center rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-ui duration-200 hover:bg-signal hover:text-onsignal ${focusRing}`}
        >
          Sign in
        </Link>
      </nav>
    </header>
  );
}
