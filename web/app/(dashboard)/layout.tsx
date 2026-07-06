import { Sidebar } from "@/components/sidebar";
import { AppHeader } from "@/components/app-header";
import { PageBackground } from "@/components/page-background";
import { ScrollToTop } from "@/components/scroll-to-top";
import { InviteGate } from "@/components/invite-gate";
import { GoogleStatusProvider } from "@/components/google-status";
import { SubmitJobProvider } from "@/components/submit-job";
import { TooltipProvider } from "@/components/ui/tooltip";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <TooltipProvider>
      <InviteGate>
        <GoogleStatusProvider>
          <SubmitJobProvider>
            <div className="flex h-screen overflow-hidden">
              <Sidebar />
              <main className="relative isolate flex-1 overflow-auto">
                <PageBackground />
                <AppHeader />
                <div className="relative z-10 p-4 sm:p-6">{children}</div>
                <ScrollToTop />
              </main>
            </div>
          </SubmitJobProvider>
        </GoogleStatusProvider>
      </InviteGate>
    </TooltipProvider>
  );
}
