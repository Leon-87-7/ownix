'use client';
import type { LucideIcon } from 'lucide-react';
import Link from 'next/link';
import { PageShell, PageHeader } from '@/components/page-shell';

export function RestrictedFacade({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <PageShell>
      <PageHeader icon={Icon} title={title} action={<Link href="/login?from=restricted" className="h-8 rounded-md bg-signal px-3.5 py-2 text-[13px] font-medium text-onsignal hover:bg-signal-bright">Get access</Link>} />
      <section className="rounded-lg border border-line bg-surface p-5">
        <p className="font-semibold text-ink">Restricted mode on</p>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-body">{children}</p>
      </section>
    </PageShell>
  );
}
