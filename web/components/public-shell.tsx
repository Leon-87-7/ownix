import Link from "next/link";
import type { ReactNode } from "react";

type PublicPage = "terms" | "privacy";

const navItems: Array<{ href: string; label: string; page: PublicPage }> = [
  { href: "/terms", label: "Terms", page: "terms" },
  { href: "/privacy", label: "Privacy", page: "privacy" },
];

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
            className="flex items-center gap-3 rounded-md transition-ui hover:text-signal focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/vig_logo_lockup.svg"
              alt=""
              className="h-9 w-auto"
            />
            <span className="sr-only">VIG console</span>
          </Link>

          <nav className="flex items-center gap-1" aria-label="Public">
            {navItems.map((item) => {
              const current = active === item.page;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={current ? "page" : undefined}
                  className={`rounded-md px-3 py-2 text-sm font-medium transition-ui ${
                    current
                      ? "bg-raised text-signal"
                      : "text-body hover:bg-raised hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
            <Link
              href="/login"
              className="ml-1 rounded-md border border-line px-3 py-2 text-sm font-medium text-ink transition-ui hover:border-line-strong hover:bg-raised"
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
        <p className="font-mono text-[11px] font-medium text-muted">
          Legal document
        </p>
        <nav className="mt-3 flex flex-col gap-1" aria-label="Legal documents">
          {navItems.map((item) => {
            const current = active === item.page;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={`rounded-md px-3 py-2 text-sm font-medium transition-ui ${
                  current
                    ? "bg-raised text-signal"
                    : "text-body hover:bg-raised hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <p className="mt-6 text-sm leading-6 text-muted">
          Public terms for VIG&apos;s Telegram bot, dashboard, and Google
          connection.
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
      <p className="mb-3 font-mono text-[11px] font-medium text-muted">
        Public legal
      </p>
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
      <h2 className="text-lg font-semibold tracking-tight text-ink">{title}</h2>
      <div className="mt-3 space-y-3">
        {children}
      </div>
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
  const external = href.startsWith("http");
  return (
    <a
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
      className="font-medium text-signal transition-ui hover:text-signal-bright hover:underline"
    >
      {children}
    </a>
  );
}
