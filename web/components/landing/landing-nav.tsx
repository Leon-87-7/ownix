import Link from 'next/link';
import OwnixLogo from '@/app/ownix-logo.svg';
import { GhostLinkButton } from '@/components/ui/ghost-button';
import { touchTarget } from './shared';

export function LandingNav({ signedIn }: { signedIn: boolean }) {
  return (
    <nav
      aria-label="Main"
      className="border-b border-line bg-canvas lg:sticky lg:top-0 lg:z-40 lg:border-line/70 lg:bg-canvas/85 lg:backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-4">
        <Link
          href="/restricted"
          aria-label="Open Ownix"
          className="group flex items-center gap-2 rounded-md text-xl font-semibold tracking-tight text-ink"
        >
          <OwnixLogo
            aria-hidden="true"
            focusable="false"
            className="h-7 w-7 group-hover:text-signal-bright motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out-quart motion-safe:group-hover:scale-110 motion-safe:group-hover:rotate-[-6deg]"
          />
          <span className="group-hover:text-contrasignal">Ownix</span>
        </Link>

        <div className="flex items-center gap-2">
          {!signedIn && (
            <Link
              href="/login"
              className={`ml-1 inline-flex h-8 items-center rounded-md border border-line px-3.5 text-button font-medium text-ink transition-ui duration-200 hover:bg-signal hover:text-onsignal ${touchTarget}`}
            >
              Sign in
            </Link>
          )}
          {signedIn && (
            <GhostLinkButton
              accent="contrasignal"
              href="/logout"
              className={`h-8 bg-transparent px-3.5 text-button font-medium leading-none text-ink focus-visible:ring-offset-canvas ${touchTarget}`}
            >
              Logout
            </GhostLinkButton>
          )}
        </div>
      </div>
    </nav>
  );
}
