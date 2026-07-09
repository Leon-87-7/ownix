import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

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
  width = "default",
  className,
  children,
}: {
  width?: "default" | "narrow";
  className?: string;
  children: ReactNode;
}) {
  const max = width === "narrow" ? "max-w-3xl" : "max-w-5xl";
  return (
    <div className={`mx-auto ${max} space-y-6${className ? ` ${className}` : ""}`}>
      {children}
    </div>
  );
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
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="flex flex-1 items-center gap-2 text-2xl font-semibold tracking-tight text-ink">
          {Icon && <Icon className="text-signal" aria-hidden="true" />}
          {title}
        </h1>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {description && <p className="mt-1 text-sm text-body">{description}</p>}
    </div>
  );
}
