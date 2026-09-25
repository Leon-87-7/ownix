import { ScrollToTop } from '@/components/shell/scroll-to-top';
import ViewAsSwitch from '@/components/shell/view-as-switch';

export function FloatingControls() {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex w-12 flex-col items-center gap-2">
      <ViewAsSwitch />
      <ScrollToTop />
    </div>
  );
}
