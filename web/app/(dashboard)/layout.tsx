import { Sidebar } from '@/components/sidebar';
import { AppHeader } from '@/components/app-header';
import { PageBackground } from '@/components/page-background';
import { ScrollToTop } from '@/components/scroll-to-top';
import { InviteGate } from '@/components/invite-gate';
import { GoogleStatusProvider } from '@/components/google-status';
import { SubmitJobProvider } from '@/components/submit-job';
import { TooltipProvider } from '@/components/ui/tooltip';
import { RestrictedModeProvider } from '@/lib/restricted/context';
import DevPersonaSwitch from '@/components/ui/dev-persona-switch';
import { isRestrictedRequest } from '@/lib/restricted/server';
import { cookies, headers } from 'next/headers';

// Private user data — never indexable. The middleware session gate keeps
// crawlers out; this covers any gap.
export const metadata = { robots: { index: false, follow: false } };

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  // Cookie presence alone is NOT the restricted signal: /restricted fails
  // closed and can mint the cookie for an approved user during a backend
  // blip, which would swap their Feed for the preview corpus. When both
  // cookies are present, ask the backend — approved sessions get their own
  // Feed (ADR-0035 §1), while pending/blocked sessions stay restricted.
  const restricted = await isRestrictedRequest({
    hasPreviewCookie: cookieStore.get('ownix_preview')?.value === '1',
    hasSession: Boolean(cookieStore.get('vig_session')?.value),
    cookieHeader: (await headers()).get('cookie') ?? '',
  });
  return (
    <TooltipProvider>
      <RestrictedModeProvider restricted={restricted}>
        <InviteGate restricted={restricted}>
          <GoogleStatusProvider>
            <SubmitJobProvider>
              <div className="flex h-screen overflow-hidden">
                <Sidebar />
                <main className="relative isolate flex min-w-0 flex-1 flex-col overflow-hidden">
                  <PageBackground />
                  <AppHeader />
                  <div
                    data-dashboard-scroll
                    className="relative z-10 flex-1 overflow-auto p-4 sm:p-6"
                  >
                    {children}
                    <ScrollToTop />
                  </div>
                </main>
              </div>
            </SubmitJobProvider>
          </GoogleStatusProvider>
        </InviteGate>
        {/* Outside InviteGate so the dev switch survives the gate screen. */}
        <DevPersonaSwitch />
      </RestrictedModeProvider>
    </TooltipProvider>
  );
}
