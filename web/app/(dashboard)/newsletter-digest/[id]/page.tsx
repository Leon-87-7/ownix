'use client';

import { Newspaper } from 'lucide-react';
import { useParams } from 'next/navigation';
import { NewsletterDigestDetail } from '@/components/newsletter-digest/newsletter-digest-detail';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { useRestrictedMode } from '@/lib/restricted/context';

export default function NewsletterDigestDetailPage() {
  // Next 16 params are async on page props; useParams() resolves the route id
  // client-side (see spaces/[id] for the /api/…/undefined failure this avoids).
  const { id } = useParams<{ id: string }>();
  const { restricted } = useRestrictedMode();
  if (restricted) {
    return (
      <RestrictedFacade icon={Newspaper} title="Newsletter Digest">
        Newsletter candidates are visible in the full product after sign-in.
      </RestrictedFacade>
    );
  }
  return <NewsletterDigestDetail subscriptionId={id} />;
}
