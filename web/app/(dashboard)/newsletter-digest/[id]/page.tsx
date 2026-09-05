'use client';

import { Newspaper } from 'lucide-react';
import { NewsletterDigestDetail } from '@/components/newsletter-digest/newsletter-digest-detail';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { useRestrictedMode } from '@/lib/restricted/context';

export default function NewsletterDigestDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { restricted } = useRestrictedMode();
  if (restricted) {
    return (
      <RestrictedFacade icon={Newspaper} title="Newsletter Digest">
        Newsletter candidates are visible in the full product after sign-in.
      </RestrictedFacade>
    );
  }
  return <NewsletterDigestDetail subscriptionId={params.id} />;
}
