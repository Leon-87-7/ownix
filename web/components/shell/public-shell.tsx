import {
  Accessibility,
  Handshake,
  ShieldUser,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';
import OwnixLogo from '@/app/ownix-logo.svg';
import { PublicBackButton } from '@/components/shell/public-back-button';

type PublicPage = 'terms' | 'privacy' | 'accessibility';

const focusRing =
  'focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface';

const navItems: Array<{
  href: string;
  label: string;
  page: PublicPage;
  icon: LucideIcon;
}> = [
  {
    href: '/privacy',
    label: 'Privacy',
    page: 'privacy',
    icon: ShieldUser,
  },
  { href: '/terms', label: 'Terms', page: 'terms', icon: Handshake },
  {
    href: '/accessibility',
    label: 'Accessibility',
    page: 'accessibility',
    icon: Accessibility,
  },
];

function PublicNavLink({
  item,
  current,
  showIcon = false,
}: {
  item: { href: string; label: string; icon: LucideIcon };
  current: boolean;
  showIcon?: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={current ? 'page' : undefined}
      className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-ui ${focusRing} ${
        current
          ? 'bg-raised text-signal'
          : 'text-body hover:bg-raised hover:text-ink'
      }`}
    >
      {showIcon && (
        <Icon
          className="h-[18px] w-[18px] shrink-0"
          aria-hidden="true"
        />
      )}
      {item.label}
    </Link>
  );
}

export function PublicShell({
  active,
  children,
}: {
  active: PublicPage;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex min-h-16 max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
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
            <span className="group-hover:text-contrasignal">
              Ownix
            </span>
          </Link>

          <nav
            className="flex items-center gap-1"
            aria-label="Public"
          >
            {navItems.map((item) => (
              <PublicNavLink
                key={item.href}
                item={item}
                current={active === item.page}
              />
            ))}
            <Link
              href="/login"
              className={`ml-1 inline-flex h-8 items-center rounded-md border border-line px-3.5 text-button font-medium text-ink transition-ui duration-200 hover:bg-signal-deep hover:text-onsignal ${focusRing}`}
            >
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
        {children}
      </div>
    </main>
  );
}

export function LegalLayout({
  active,
  children,
}: {
  active: PublicPage;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_15rem] lg:items-start">
      <div className="min-w-0">{children}</div>
      <aside className="hidden border-l border-line pl-6 lg:sticky lg:top-8 lg:block">
        <p className="font-mono text-label font-medium text-muted">
          Legal document
        </p>
        <nav
          className="mt-3 flex flex-col gap-1"
          aria-label="Legal documents"
        >
          {navItems.map((item) => (
            <PublicNavLink
              key={item.href}
              item={item}
              current={active === item.page}
              showIcon
            />
          ))}
        </nav>
        <p className="mt-6 text-sm leading-6 text-muted">
          Public terms for Ownix, your personal Index, the shared
          Brain, and connected services.
        </p>
      </aside>
    </div>
  );
}

export function LegalArticle({ children }: { children: ReactNode }) {
  return (
    <article className="max-w-[70ch] text-sm leading-6 text-body [&_code]:rounded [&_code]:border [&_code]:border-line [&_code]:bg-surface [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_code]:text-ink">
      {children}
    </article>
  );
}

export function LegalTitle({
  title,
  updated,
}: {
  title: string;
  updated: string;
}) {
  return (
    <header className="mb-8 border-b border-line pb-7">
      <div className="mb-3 flex items-center gap-2">
        <PublicBackButton />
        <p className="font-mono text-label font-medium text-muted">
          Ownix legal policies
        </p>
      </div>
      <h1 className="max-w-2xl text-balance text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
        {title}
      </h1>
      <p className="mt-4 font-mono text-xs text-muted">{updated}</p>
    </header>
  );
}

export function LegalSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mt-7 border-t border-line pt-7 first:border-t-0 first:pt-0">
      <h2 className="text-lg font-semibold tracking-tight text-ink">
        {title}
      </h2>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

export function LegalList({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-2 pl-5">{children}</ul>;
}

export function LegalLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  const external = href.startsWith('http');
  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      className="font-medium text-signal transition-ui hover:text-signal-bright hover:underline"
    >
      {children}
    </a>
  );
}
