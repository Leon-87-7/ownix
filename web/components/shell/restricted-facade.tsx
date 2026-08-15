'use client';
/* @ds
name: RestrictedFacade
purpose: A page-shaped placeholder shown in Restricted mode in place of a feature the unauthenticated visitor can't use — explains what's gated and offers "Get access."
when-not: Only for gating a whole page in restricted mode; for gating one control inline, don't reach for this.
notes: Built on PageShell/PageHeader, so it inherits their width/rhythm rules automatically.
status: inferred
*/

import type { LucideIcon } from 'lucide-react';
import Link from 'next/link';
import { PageShell, PageHeader } from '@/components/shell/page-shell';

export function RestrictedFacade({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <PageShell>
      <PageHeader icon={Icon} title={title} action={<Link href="/login?from=restricted" className="h-8 rounded-md bg-signal px-3.5 py-2 text-button font-medium text-onsignal hover:bg-signal-bright">Get access</Link>} />
      <section className="rounded-lg border border-line bg-surface p-5">
        <p className="font-semibold text-ink">Restricted mode on</p>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-body">{children}</p>
      </section>
    </PageShell>
  );
}
