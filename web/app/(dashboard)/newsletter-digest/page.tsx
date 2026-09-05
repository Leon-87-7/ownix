'use client';

import { Newspaper } from 'lucide-react';
import { NewsletterDigestDashboard } from '@/components/newsletter-digest/newsletter-digest-dashboard';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { useRestrictedMode } from '@/lib/restricted/context';

export default function NewsletterDigestPage() {
  const { restricted } = useRestrictedMode();
  if (restricted) {
    return (
      <RestrictedFacade icon={Newspaper} title="Newsletter Digest">
        Newsletter aliases and candidate promotion are available in the full
        product. This preview keeps inbound routing disabled.
      </RestrictedFacade>
    );
  }
  return <NewsletterDigestDashboard />;
}
