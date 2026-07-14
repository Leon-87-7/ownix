'use client';

import Link from 'next/link';
import { PulsingBorder } from '@paper-design/shaders-react';
import { Tooltip } from '@/components/ui/tooltip';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import OwnixLogo from '@/app/ownix-logo.svg';
import {
  Rss,
  Brain,
  LayoutGrid,
  MessageSquareText,
  SlidersHorizontal,
  ChevronRight,
  ChevronLeft,
  GripVertical,
  FileCode2,
  Handshake,
  ShieldUser,
  LogOut,
  Unplug,
  type LucideIcon,
} from 'lucide-react';
import { siGithub, siGoogle } from 'simple-icons';
import {
  useSessionUser,
  type InviteUser,
} from '@/components/invite-gate';
import { useGoogleStatus } from '@/components/google-status';
import { statusColors } from '@/lib/design-tokens';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { href: '/feed', label: 'Feed', icon: Rss },
  { href: '/doc-parser', label: 'Docs', icon: FileCode2 },
  { href: '/brain', label: 'Brain', icon: Brain },
  { href: '/spaces', label: 'Collections', icon: LayoutGrid },
  { href: '/prompts', label: 'Recipes', icon: MessageSquareText },
  { href: '/controls', label: 'Settings', icon: SlidersHorizontal },
];

const AVATAR_BORDER_COLORS = [
  statusColors.processing,
  statusColors.pending,
  statusColors.done,
  statusColors.error,
] as const;

// `trails`/`brightness` aren't real PulsingBorder props (silently dropped) —
// `roundness`+`aspectRatio` are what make the shape a circle instead of the
// library's default rounded rect.
const AVATAR_BORDER_SHADER = {
  roundness: 1,
  aspectRatio: 'square',
  scale: 0.95,
} as const;

// Ownix brand mark (web/app/ownix-logo.svg via SVGR). fill=currentColor, so it
// tints to the surrounding text color (text-ink) — visible on the dark plate.
function LogoMark({ className }: { className?: string }) {
  return (
    <OwnixLogo
      className={`text-ink ${className ?? ''}`}
      aria-hidden="true"
      focusable="false"
    />
  );
}

// GitHub mark from simple-icons (lucide-react dropped its brand icons).
// Renders the raw path with currentColor so it inherits hover/active tints.
function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d={siGithub.path} />
    </svg>
  );
}

// Google mark from simple-icons, same pattern as GithubIcon below.
function GoogleIcon({
  className,
  outline = false,
}: {
  className?: string;
  outline?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill={outline ? 'none' : 'currentColor'}
      stroke={outline ? 'currentColor' : undefined}
      strokeWidth={outline ? 1.8 : undefined}
      aria-hidden="true"
      focusable="false"
    >
      <path d={siGoogle.path} />
    </svg>
  );
}

// Telegram avatar with an initial-letter fallback — used when photo_url is
// absent or the CDN URL has gone stale (Telegram photo links expire).
function Avatar({
  user,
  className,
}: {
  user: InviteUser;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (user.photo_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- external Telegram CDN, no next/image domains configured
      <img
        src={user.photo_url}
        alt=""
        onError={() => setFailed(true)}
        className={`rounded-full object-cover ${className ?? ''}`}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`flex items-center justify-center rounded-full bg-raised font-mono text-[11px] font-medium text-body ${className ?? ''}`}
    >
      {(user.first_name?.[0] ?? '?').toUpperCase()}
    </span>
  );
}

function useReducedMotionPreference() {
  const [reducedMotion, setReducedMotion] = useState<boolean | null>(null);

  useEffect(() => {
    if (!window.matchMedia) {
      setReducedMotion(true);
      return;
    }
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  return reducedMotion;
}

function GoogleConnectedAvatar({
  user,
  connected,
  className,
  avatarClassName,
}: {
  user: InviteUser;
  connected: boolean | null;
  className?: string;
  avatarClassName?: string;
}) {
  const reducedMotion = useReducedMotionPreference();
  const colors = useMemo(() => [...AVATAR_BORDER_COLORS], []);

  return (
    <span
      className={`relative flex items-center justify-center rounded-full ${className ?? ''}`}
    >
      {connected === true && (
        <PulsingBorder
          {...AVATAR_BORDER_SHADER}
          colors={colors}
          speed={reducedMotion === false ? 1 : 0}
          className="pointer-events-none absolute inset-0 size-full rounded-full"
        />
      )}
      <Avatar
        user={user}
        className={`relative z-10 ${avatarClassName ?? ''}`}
      />
    </span>
  );
}

function isActive(pathname: string, href: string): boolean {
  if (href === '/feed')
    return (
      pathname === '/feed' ||
      pathname.startsWith('/feed/') ||
      pathname.startsWith('/jobs')
    );
  return pathname === href || pathname.startsWith(`${href}/`);
}

// One nav link, two layouts: icon-only square in the rail, icon+label row in
// the drawer. Active state earns the signal in both.
function NavLink({
  item,
  pathname,
  collapsed,
  tabbable = true,
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
  tabbable?: boolean;
}) {
  const { href, label, icon: Icon } = item;
  const active = isActive(pathname, href);
  const layout = collapsed
    ? 'flex h-9 w-9 items-center justify-center'
    : 'flex items-center gap-3 px-3 py-2';
  return (
    <Tooltip content={collapsed ? label : undefined}>
      <Link
        href={href}
        aria-label={collapsed ? label : undefined}
        aria-current={active ? 'page' : undefined}
        tabIndex={tabbable ? undefined : -1}
        className={`${layout} rounded-md text-sm font-medium transition-ui ${
          active
            ? 'bg-raised text-signal'
            : 'text-body hover:bg-raised hover:text-ink'
        }`}
      >
        <Icon
          className="h-[18px] w-[18px] shrink-0"
          strokeWidth={2}
          aria-hidden="true"
        />
        {!collapsed && label}
      </Link>
    </Tooltip>
  );
}

/**
 * Collapsible navigation for the Ownix product shell.
 * Collapsed: a slim rail showing the favicon logo + per-page icons (active in signal).
 * Expanded: a slide-in drawer with the Ownix wordmark + icon-and-label rows.
 * The wordmark only appears when expanded; collapsed shows the logo alone.
 */
export function Sidebar() {
  const pathname = usePathname();
  const user = useSessionUser();
  const { connected, disconnect } = useGoogleStatus();
  const [disconnecting, setDisconnecting] = useState(false);
  const [disconnectFailed, setDisconnectFailed] = useState(false);
  const [open, setOpen] = useState(false);

  // Clear a stale failure note if connection state changes underneath us
  // (e.g. the server revoked the token despite the disconnect call erroring).
  useEffect(() => {
    setDisconnectFailed(false);
  }, [connected]);

  // #308: Radix tooltips don't open on touch — controlled open so tapping the
  // Google glyph shows the connection-state text (Radix closes on outside/escape).
  const [googleTipOpen, setGoogleTipOpen] = useState(false);

  // The tooltip portals outside the drawer; don't let it outlive a closed drawer.
  useEffect(() => {
    if (!open) setGoogleTipOpen(false);
  }, [open]);

  const handleDisconnect = async () => {
    if (
      !window.confirm(
        'Disconnect Google? Exports to your Drive/Sheets stop until you reconnect (full consent flow).',
      )
    )
      return;
    setDisconnecting(true);
    setDisconnectFailed(false);
    const ok = await disconnect();
    if (!ok) setDisconnectFailed(true);
    setDisconnecting(false);
  };
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Close on navigation.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Close on Escape while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // Move focus into the drawer on open; return it on close (APG dialog pattern).
  useEffect(() => {
    if (open) {
      previousFocusRef.current =
        document.activeElement as HTMLElement | null;
      closeButtonRef.current?.focus();
    } else if (previousFocusRef.current) {
      previousFocusRef.current.focus();
      previousFocusRef.current = null;
    }
  }, [open]);

  // Lock body scroll behind the backdrop while open.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <>
      {/* Mobile pull-tab — the rail is hidden < sm, so this slim edge handle is the
          affordance that a nav drawer exists. Hidden while the drawer is open. */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        aria-expanded={open}
        aria-controls="ownix-nav-panel"
        tabIndex={open ? -1 : undefined}
        className={`fixed left-0 top-1/2 z-30 flex h-14 w-6 -translate-y-1/2 items-center justify-center rounded-r-xl border border-l-2 border-line bg-raised text-muted shadow-overlay transition-opacity hover:text-ink sm:hidden ${
          open ? 'pointer-events-none opacity-0' : 'opacity-100'
        }`}
      >
        <GripVertical
          className="h-5 w-5"
          strokeWidth={3}
          aria-hidden="true"
        />
      </button>

      {/* Collapsed rail — desktop only. Favicon logo + per-page icons. */}
      <div className="hidden w-16 shrink-0 flex-col items-center border-r border-line bg-surface py-5 sm:flex">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          aria-expanded={open}
          aria-controls="ownix-nav-panel"
          className="mb-6 flex h-9 w-9 items-center justify-center rounded-md transition-ui hover:bg-contrasignal-deep/60"
        >
          <LogoMark className="h-8 w-8  hover:text-signal-bright" />
        </button>

        <nav
          className="flex flex-col items-center gap-1"
          aria-label="Primary"
        >
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              pathname={pathname}
              collapsed
              tabbable={!open}
            />
          ))}
        </nav>

        <div className="mt-auto flex flex-col items-center gap-1">
          {user && (
            <Tooltip
              content={
                connected === null
                  ? (user.first_name ?? 'Signed in')
                  : `${user.first_name ?? 'Signed in'} — ${
                      connected
                        ? 'Connected to Google'
                        : 'Google not connected'
                    }`
              }
            >
              <span className="flex h-9 w-9 items-center justify-center">
                <GoogleConnectedAvatar
                  user={user}
                  connected={connected}
                  className="h-9 w-9"
                  avatarClassName="h-6 w-6"
                />
              </span>
            </Tooltip>
          )}
          <Tooltip content="GitHub repository">
            <a
              href="https://github.com/Leon-87-7/vig"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub repository"
              tabIndex={open ? -1 : undefined}
              className="flex h-9 w-9 items-center justify-center rounded-md text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              <GithubIcon className="h-[18px] w-[18px]" />
            </a>
          </Tooltip>
          <Tooltip content="Expand navigation">
            <button
              type="button"
              onClick={() => setOpen(true)}
              tabIndex={open ? -1 : undefined}
              aria-label="Expand navigation"
              aria-expanded={open}
              aria-controls="ownix-nav-panel"
              className="flex h-9 w-9 items-center justify-center rounded-md text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              <ChevronRight
                className="h-[18px] w-[18px]"
                strokeWidth={2}
                aria-hidden="true"
              />
            </button>
          </Tooltip>
        </div>
      </div>

      {/* Backdrop */}
      <div
        onClick={() => setOpen(false)}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 ease-out-quart ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      />

      {/* Expanded panel — slide-in drawer with the Ownix wordmark + icon-and-label rows. */}
      <aside
        id="ownix-nav-panel"
        aria-label="Primary navigation"
        aria-hidden={!open}
        // ponytail: close on clicks in the drawer's dead space; links/buttons
        // (closest a/button) keep their own handlers.
        onClick={(e) => {
          if (!(e.target as HTMLElement).closest('a,button'))
            setOpen(false);
        }}
        className={`fixed inset-y-0 left-0 z-50 flex w-56 flex-col border-r border-line bg-surface px-4 py-5 shadow-overlay transition-transform duration-200 ease-out-quart ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="mb-6 flex items-center px-1">
          <Link
            href="/"
            aria-label="Ownix home"
            tabIndex={open ? undefined : -1}
            className="group flex items-center gap-2 rounded-md text-lg font-semibold tracking-tight text-ink"
          >
            <LogoMark
              className={`h-8 w-8 transition-transform duration-200 ease-out-quart group-hover:scale-110 group-hover:text-signal-bright ${
                open ? 'sidebar-mark-in' : ''
              }`}
            />
            <span
              className={`transition-opacity duration-150 ease-out-quart group-hover:opacity-80 sm:group-hover:text-contrasignal ${
                open ? 'sidebar-word-in' : ''
              }`}
            >
              Ownix
            </span>
          </Link>
        </div>

        <nav
          className="flex flex-col gap-1"
          aria-label="Primary expanded"
        >
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              pathname={pathname}
              collapsed={false}
              tabbable={open}
            />
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-1">
          {user && (
            <div className="px-3 py-2">
              <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-body">
                <GoogleConnectedAvatar
                  user={user}
                  connected={connected}
                  className="relative -left-1 -top-px h-8 w-8 shrink-0"
                  avatarClassName="h-[26px] w-[26px] shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <span className="block truncate">
                    {user.first_name ?? 'Signed in'}
                  </span>
                  {user.username && (
                    <p className="truncate font-mono text-[11px] text-muted">
                      @{user.username}
                    </p>
                  )}
                </div>
                <Tooltip
                  open={googleTipOpen}
                  onOpenChange={setGoogleTipOpen}
                  content={
                    connected
                      ? 'Connected to Google'
                      : connected === false
                        ? 'Google not connected'
                        : 'Checking Google connection'
                  }
                >
                  <button
                    type="button"
                    tabIndex={open ? undefined : -1}
                    onClick={() => setGoogleTipOpen(true)}
                    className="-m-2 shrink-0 rounded p-2 text-muted transition-ui hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal"
                  >
                    <GoogleIcon
                      outline={!connected}
                      className={`h-3.5 w-3.5 ${connected ? 'text-google' : 'text-muted'}`}
                    />
                    <span className="sr-only">
                      {connected
                        ? 'Connected to Google'
                        : connected === false
                          ? 'Google not connected'
                          : 'Checking Google connection'}
                    </span>
                  </button>
                </Tooltip>
                {connected ? (
                  <>
                    <span
                      className="text-muted"
                      aria-hidden="true"
                    >
                      ·
                    </span>
                    <button
                      type="button"
                      aria-label={
                        disconnecting ? 'Disconnecting' : 'Disconnect'
                      }
                      onClick={handleDisconnect}
                      disabled={disconnecting}
                      tabIndex={open ? undefined : -1}
                      className="-m-2 rounded p-2 text-muted transition-ui hover:text-status-error focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96] disabled:opacity-50"
                    >
                      <Unplug
                        className="h-4 w-4"
                        aria-hidden="true"
                      />
                    </button>
                  </>
                ) : connected === false ? (
                  <a
                    href="/api/google/connect"
                    aria-label="Connect Google"
                    tabIndex={open ? undefined : -1}
                    className="-m-2 shrink-0 rounded p-2 text-xs text-muted transition-ui hover:text-ink"
                  >
                    Connect
                  </a>
                ) : null}
              </div>
              {disconnectFailed && (
                <p className="mt-1 pl-[34px] text-[11px] text-status-error">
                  Couldn&apos;t disconnect — try again.
                </p>
              )}
            </div>
          )}
          <a
            href="https://github.com/Leon-87-7/vig"
            target="_blank"
            rel="noopener noreferrer"
            tabIndex={open ? undefined : -1}
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
          >
            <GithubIcon className="h-[18px] w-[18px] shrink-0" />
            GitHub
          </a>
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            <Link
              href="/terms"
              tabIndex={open ? undefined : -1}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              <Handshake
                className="h-[18px] w-[18px] shrink-0"
                aria-hidden="true"
              />
              Terms
            </Link>
            <Link
              href="/privacy"
              tabIndex={open ? undefined : -1}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              <ShieldUser
                className="h-[18px] w-[18px] shrink-0"
                aria-hidden="true"
              />
              Privacy
            </Link>
          </div>
          {/* Close (left) sits under the collapsed rail's expand button, so a
              double-click on expand lands its second click here — closing the
              drawer, not firing Sign Out (right). #329 */}
          <div className="flex items-center gap-2">
            <button
              ref={closeButtonRef}
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Collapse navigation"
              tabIndex={open ? undefined : -1}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              <ChevronLeft
                className="h-[18px] w-[18px]"
                strokeWidth={2}
                aria-hidden="true"
              />
            </button>
            <form
              action="/api/auth/logout"
              method="POST"
              className="flex-1"
            >
              <button
                type="submit"
                tabIndex={open ? undefined : -1}
                className="flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
              >
                <span>Sign Out</span>
                <LogOut
                  className="h-[18px] w-[18px] text-status-error"
                  aria-hidden="true"
                />
              </button>
            </form>
          </div>
        </div>
      </aside>
    </>
  );
}
