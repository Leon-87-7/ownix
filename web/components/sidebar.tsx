'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import {
  Rss,
  Brain,
  LayoutGrid,
  MessageSquareText,
  SlidersHorizontal,
  ChevronRight,
  ChevronLeft,
  Tally2,
  type LucideIcon,
} from 'lucide-react';
import { siGithub } from 'simple-icons';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { href: '/', label: 'Feed', icon: Rss },
  { href: '/brain', label: 'Brain', icon: Brain },
  { href: '/spaces', label: 'Spaces', icon: LayoutGrid },
  { href: '/prompts', label: 'Prompts', icon: MessageSquareText },
  { href: '/controls', label: 'Controls', icon: SlidersHorizontal },
];

function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 256 256"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient
          id="vig-logo-plate"
          x1="28"
          y1="18"
          x2="228"
          y2="238"
          gradientUnits="userSpaceOnUse"
        >
          <stop
            offset="0"
            stopColor="#1c1f25"
          />
          <stop
            offset="0.58"
            stopColor="#0b0c0f"
          />
          <stop
            offset="1"
            stopColor="#050607"
          />
        </linearGradient>
        <linearGradient
          id="vig-logo-aqua"
          x1="76"
          y1="44"
          x2="214"
          y2="208"
          gradientUnits="userSpaceOnUse"
        >
          <stop
            offset="0"
            stopColor="#e3fdff"
          />
          <stop
            offset="1"
            stopColor="#7deaf7"
          />
        </linearGradient>
        <filter
          id="vig-logo-lift"
          x="-20%"
          y="-20%"
          width="140%"
          height="140%"
        >
          <feDropShadow
            dx="0"
            dy="5"
            stdDeviation="5"
            floodColor="#000000"
            floodOpacity="0.55"
          />
          <feDropShadow
            dx="0"
            dy="0"
            stdDeviation="7"
            floodColor="#f6921e"
            floodOpacity="0.28"
          />
        </filter>
      </defs>
      <rect
        x="16"
        y="16"
        width="224"
        height="224"
        rx="42"
        fill="url(#vig-logo-plate)"
      />
      <rect
        x="16.5"
        y="16.5"
        width="223"
        height="223"
        rx="41.5"
        fill="none"
        stroke="#343a44"
      />
      <g filter="url(#vig-logo-lift)">
        <path
          d="M80 50 76 208 214 128"
          fill="none"
          stroke="url(#vig-logo-aqua)"
          strokeWidth="30"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M72 52 68 218"
          fill="none"
          stroke="#050607"
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.72"
        />
        <path
          d="M82 210 222 130"
          fill="none"
          stroke="#050607"
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.72"
        />
        <path
          d="M100 80 100 178 189 128Z"
          fill="#b96a06"
          opacity="0.35"
        />
        <path
          d="M106 72 106 184 202 128Z"
          fill="#f6921e"
        />
      </g>
    </svg>
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

function isActive(pathname: string, href: string): boolean {
  if (href === '/')
    return pathname === '/' || pathname.startsWith('/jobs');
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
    <Link
      href={href}
      title={collapsed ? label : undefined}
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
  );
}

/**
 * Collapsible navigation (DESIGN.md "Operator's Console").
 * Collapsed: a slim rail showing the favicon logo + per-page icons (active in signal).
 * Expanded: a slide-in drawer with the "vig" wordmark + icon-and-label rows.
 * The wordmark only appears when expanded; collapsed shows the logo alone.
 */
export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
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
      previousFocusRef.current = document.activeElement as HTMLElement | null;
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
        aria-controls="vig-nav-panel"
        tabIndex={open ? -1 : undefined}
        className={`fixed left-0 top-1/2 z-30 flex h-14 w-4 -translate-y-1/2 items-center justify-center rounded-r-md border border-l-0 border-line bg-surface text-muted shadow-overlay transition-opacity hover:text-ink sm:hidden ${
          open ? 'pointer-events-none opacity-0' : 'opacity-100'
        }`}
      >
        <Tally2 className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
      </button>

      {/* Collapsed rail — desktop only. Favicon logo + per-page icons. */}
      <div className="hidden w-16 shrink-0 flex-col items-center border-r border-line bg-surface py-5 sm:flex">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          aria-expanded={open}
          aria-controls="vig-nav-panel"
          className="mb-6 flex h-9 w-9 items-center justify-center rounded-md transition-ui hover:bg-raised"
        >
          <LogoMark className="h-8 w-8" />
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
          <a
            href="https://github.com/Leon-87-7/vig"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub repository"
            title="GitHub repository"
            tabIndex={open ? -1 : undefined}
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted transition-ui hover:bg-raised hover:text-ink"
          >
            <GithubIcon className="h-[18px] w-[18px]" />
          </a>
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Expand navigation"
            aria-expanded={open}
            aria-controls="vig-nav-panel"
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted transition-ui hover:bg-raised hover:text-ink"
          >
            <ChevronRight
              className="h-[18px] w-[18px]"
              strokeWidth={2}
              aria-hidden="true"
            />
          </button>
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

      {/* Expanded panel — slide-in drawer with the "vig" wordmark + icon-and-label rows. */}
      <aside
        id="vig-nav-panel"
        aria-label="Primary navigation"
        aria-hidden={!open}
        className={`fixed inset-y-0 left-0 z-50 flex w-56 flex-col border-r border-line bg-surface px-4 py-5 shadow-overlay transition-transform duration-200 ease-out-quart ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="mb-6 flex items-center justify-between px-1">
          <span className="flex items-center gap-2 text-lg font-semibold tracking-tight text-ink">
            <LogoMark className="h-8 w-8" />
            vig
          </span>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Collapse navigation"
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted transition-ui hover:bg-raised hover:text-ink"
          >
            <ChevronLeft
              className="h-[18px] w-[18px]"
              strokeWidth={2}
              aria-hidden="true"
            />
          </button>
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
          <form
            action="/api/auth/logout"
            method="POST"
          >
            <button
              type="submit"
              tabIndex={open ? undefined : -1}
              className="w-full rounded-md px-3 py-2 text-left text-sm font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              Sign out
            </button>
          </form>
        </div>
      </aside>
    </>
  );
}
