import type {
  ComponentPropsWithoutRef,
  ElementType,
  ReactNode,
} from 'react';

type GhostButtonAccent = 'signal' | 'contrasignal' | 'body';
type GhostButtonBorderLine = '1' | '2';

type GhostButtonProps<T extends ElementType = 'button'> = {
  as?: T;
  accent?: GhostButtonAccent;
  borderLine?: GhostButtonBorderLine;
  children: ReactNode;
  className?: string;
} & Omit<
  ComponentPropsWithoutRef<T>,
  'as' | 'children' | 'className'
>;

const baseClasses =
  'inline-flex items-center justify-center rounded-md border border-line border-b-2 transition-ui hover:bg-raised active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:active:scale-100';

const accentClasses: Record<GhostButtonAccent, string> = {
  signal: 'border-b-signal',
  contrasignal: 'border-b-contrasignal-deep',
  body: 'border-b-body',
};

const borderLineClasses: Record<GhostButtonBorderLine, string> = {
  '1': 'border-b-1',
  '2': 'border-b-2',
};

/**
 * Ownix's recessed ghost action. The accent controls only the lower edge;
 * sizing, surface, and text color remain explicit at each call site.
 */
export function GhostButton<T extends ElementType = 'button'>({
  as,
  accent = 'contrasignal',
  borderLine = '2',
  className,
  children,
  ...props
}: GhostButtonProps<T>) {
  const Component = as ?? 'button';
  const buttonDefaults =
    Component === 'button' ? { type: 'button' as const } : {};

  return (
    <Component
      {...buttonDefaults}
      {...props}
      className={`${baseClasses} ${accentClasses[accent]} ${borderLineClasses[borderLine]} ${className ?? ''}`.trim()}
    >
      {children}
    </Component>
  );
}
