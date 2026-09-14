import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

/**
 * The one page container. Every dashboard page
 * roots in this so width, vertical rhythm, and header treatment are decided once
 * instead of re-typed nine times. The (dashboard) layout already owns the mobile
 * gutter (p-4 sm:p-6); this owns everything inside it.
 *
 * width="narrow" (max-w-3xl) is for detail/reading pages (a job, a space);
 * the default max-w-5xl is the house width for list pages.
 */
export function PageShell({
  width = 'default',
  className,
  children,
}: {
  width?: 'default' | 'narrow';
  className?: string;
  children: ReactNode;
}) {
  const max = width === 'narrow' ? 'max-w-3xl' : 'max-w-5xl';
  return (
    <div
      className={`mx-auto ${max} space-y-6${className ? ` ${className}` : ''}`}
    >
      {children}
    </div>
  );
}

/**
 * Deterministic per-icon gradient (DESIGN.md "Header Icon Gradient Rule"): angle
 * and midpoint are seeded from the icon's own name, so each page's header icon
 * reads as its own mark rather than a repeated template. Deterministic (not
 * Math.random()) so it doesn't flicker between server and client render.
 */
function headerIconGradient(icon: LucideIcon) {
  const seed = icon.displayName || icon.name || 'ownix';
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  hash = Math.abs(hash);
  return {
    id: `ownix-header-icon-${hash}`,
    angle: hash % 180,
    midOffset: 30 + (hash % 40),
  };
}

/**
 * The page title row. flex-wrap so the action drops below the title on a narrow
 * phone instead of crowding it off-screen (the pattern jobs/[id] already proved).
 */
export function PageHeader({
  title,
  icon: Icon,
  description,
  action,
}: {
  title: ReactNode;
  icon?: LucideIcon;
  description?: ReactNode;
  action?: ReactNode;
}) {
  const gradient = Icon ? headerIconGradient(Icon) : null;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="flex flex-1 items-center gap-2 text-2xl font-semibold tracking-tight text-ink">
          {Icon && gradient && (
            <>
              <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" focusable="false">
                <defs>
                  <linearGradient id={gradient.id} gradientTransform={`rotate(${gradient.angle}, 0.5, 0.5)`}>
                    <stop offset="0%" stopColor="#d99a45" />
                    <stop offset={`${gradient.midOffset}%`} stopColor="#c6c1b8" />
                    <stop offset="100%" stopColor="#94e6ee" />
                  </linearGradient>
                </defs>
              </svg>
              <Icon stroke={`url(#${gradient.id})`} aria-hidden="true" />
            </>
          )}
          {title}
        </h1>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {description && (
        <p className="mt-1 text-copy text-body">{description}</p>
      )}
    </div>
  );
}
