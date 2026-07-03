import { Sidebar } from "@/components/sidebar";
import { PageBackground } from "@/components/page-background";
import { ScrollToTop } from "@/components/scroll-to-top";
import { InviteGate } from "@/components/invite-gate";
import { GoogleStatusProvider } from "@/components/google-status";
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
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="relative isolate flex-1 overflow-auto p-4 sm:p-6">
              <PageBackground />
              <div className="relative z-10">{children}</div>
              <ScrollToTop />
            </main>
          </div>
        </GoogleStatusProvider>
      </InviteGate>
    </TooltipProvider>
  );
}
