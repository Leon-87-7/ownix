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
 *
 * gradientUnits="userSpaceOnUse" with fixed x1/y1/x2/y2 in the icon's own 24x24
 * viewBox — not the default objectBoundingBox — is load-bearing: a Lucide icon
 * is several sibling <path>s, and objectBoundingBox sizes the gradient to each
 * path's own bounding box, so every stroke segment would paint its own
 * independent little gradient instead of the icon showing one continuous sweep.
 */
function headerIconGradient(icon: LucideIcon) {
  const seed = icon.displayName || icon.name || 'ownix';
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  hash = Math.abs(hash);
  const angle = (hash % 180) * (Math.PI / 180);
  const radius = 17; // > half the 24x24 diagonal, so the line spans the icon at any angle
  const dx = Math.cos(angle) * radius;
  const dy = Math.sin(angle) * radius;
  return {
    id: `ownix-header-icon-${hash}`,
    x1: 12 - dx,
    y1: 12 - dy,
    x2: 12 + dx,
    y2: 12 + dy,
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
                  <linearGradient
                    id={gradient.id}
                    gradientUnits="userSpaceOnUse"
                    x1={gradient.x1}
                    y1={gradient.y1}
                    x2={gradient.x2}
                    y2={gradient.y2}
                  >
                    <stop offset="0%" stopColor="#efb566" />
                    <stop offset="100%" stopColor="#9ec9ff" />
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
