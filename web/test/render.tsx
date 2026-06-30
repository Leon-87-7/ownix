import { render as rtlRender } from '@testing-library/react';
import type { ReactElement } from 'react';
import { TooltipProvider } from '@/components/ui/tooltip';

// Components now use Radix Tooltip, which throws outside a TooltipProvider
// (the app supplies one in the dashboard layout). Wrap every test render in it
// so isolated component tests match runtime.
export * from '@testing-library/react';

export function render(ui: ReactElement, options?: Parameters<typeof rtlRender>[1]) {
  return rtlRender(ui, { wrapper: TooltipProvider, ...options });
}
