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
        Give Ownix a newsletter&apos;s archive link and it follows the
        publication itself. New issues show up here, ready to promote into your
        Index. Nothing touches your inbox. This preview is read-only.
      </RestrictedFacade>
    );
  }
  return <NewsletterDigestDashboard />;
}
