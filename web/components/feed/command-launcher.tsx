'use client';

import type { ReactNode } from 'react';
import {
  FileCode2,
  Link2,
  Pin,
  Plus,
  Search,
  Trash2,
  Waypoints,
} from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { usePressFeedback } from '@/lib/hooks/usePressFeedback';

export type IntakeActionKey = 'submit' | 'docs' | 'link';

export const INTAKE_ACTIONS: ReadonlyArray<{
  key: IntakeActionKey;
  icon: typeof Plus;
  label: string;
  description: string;
  shortcut: string;
}> = [
  {
    key: 'submit',
    icon: Plus,
    label: 'Submit URL',
    description: 'Paste a URL - auto-detects the pipeline.',
    shortcut: 'N',
  },
  {
    key: 'docs',
    icon: FileCode2,
    label: 'Ingest Docs',
    description: 'Upload a PDF or document to parse.',
    shortcut: 'D',
  },
  {
    key: 'link',
    icon: Waypoints,
    label: 'Ingest Link',
    description: 'Save a link as-is to your Brain - no processing.',
    shortcut: 'U',
  },
];

/** Recovery action the Feed registers so the launcher can drive it with the
 * live scope + availability the Feed's useRecovery already computes. (Retry
 * pending/failed stay in the contextual recovery panel, not the palette.) */
export interface FeedRecoveryCommands {
  canClearFailed: boolean;
  clearFailed: () => void;
}

/** Feed search focus, registered so the launcher can jump into the Feed's
 * search input (or switch to Links first). */
export interface FeedSearchCommands {
  focusSearch: () => void;
  focusLinkSearch: () => void;
}

export const CLEAR_FAILED_CONFIRM =
  'Clear failed jobs in this tab? This marks them cancelled; it does not delete them.';

// Space-separated keys render as individual right-aligned kbd chips so a
// chord like "R P" reads as two keys.
function CommandShortcut({ keys }: { keys: string }) {
  return (
    <span className="ml-auto flex items-center gap-1">
      {keys.split(' ').map((key, i) => (
        <kbd
          key={i}
          className="rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-micro uppercase tracking-wide text-contrasignal-deep"
        >
          {key}
        </kbd>
      ))}
    </span>
  );
}

function CommandGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="mb-2 text-xs uppercase tracking-widest text-muted">
        {label}
      </p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function CommandAction({
  icon: Icon,
  label,
  shortcut,
  onSelect,
  disabled = false,
}: {
  icon: typeof Plus;
  label: string;
  shortcut: string;
  onSelect: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      className="flex w-full items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm text-ink transition-ui hover:bg-raised focus:outline-none focus:ring-1 focus:ring-signal disabled:cursor-not-allowed disabled:text-muted disabled:hover:bg-surface"
    >
      <Icon className="h-4 w-4 text-contrasignal-deep" aria-hidden="true" />
      <span>{label}</span>
      <CommandShortcut keys={shortcut} />
    </button>
  );
}

function SheetActionButton({
  icon: Icon,
  label,
  description,
  onClick,
}: {
  icon: typeof Plus;
  label: string;
  description: string;
  onClick: () => void;
}) {
  const pressFeedback = usePressFeedback();
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-12 w-full items-start gap-3 rounded-lg border border-line bg-surface px-3 py-3 text-left transition-ui hover:bg-raised focus:outline-none focus:ring-1 focus:ring-signal"
      {...pressFeedback}
    >
      <Icon
        className="mt-0.5 h-4 w-4 shrink-0 text-contrasignal-deep"
        aria-hidden="true"
      />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink">{label}</span>
        <span className="mt-0.5 block text-xs leading-5 text-body">
          {description}
        </span>
      </span>
    </button>
  );
}

/** What both surfaces need in order to act. Passed as one object so adding a
 * command doesn't thread another prop through two components. */
export interface LauncherActions {
  runIntake: (key: IntakeActionKey, closeSurface: () => void) => void;
  openGoTo: () => void;
  navigate: (href: string) => void;
  recovery: FeedRecoveryCommands | null;
  search: FeedSearchCommands | null;
}

/** Mobile intake sheet: the three ingest actions plus the GoTo jump. */
export function IntakeSheet({
  open,
  onOpenChange,
  actions,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  actions: LauncherActions;
}) {
  const close = () => onOpenChange(false);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby={undefined}>
        <SheetTitle>Add to your Index</SheetTitle>
        <div className="mt-5 space-y-2">
          {INTAKE_ACTIONS.map((action) => (
            <SheetActionButton
              key={action.key}
              icon={action.icon}
              label={action.label}
              description={action.description}
              onClick={() => actions.runIntake(action.key, close)}
            />
          ))}
        </div>
        <div className="mt-5">
          <CommandGroup label="Navigate">
            <SheetActionButton
              icon={Pin}
              label="GoTo Links"
              description="Jump to links carrying one of your pinned tags."
              onClick={() => {
                close();
                actions.openGoTo();
              }}
            />
          </CommandGroup>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** Desktop command palette (cmd/ctrl+shift+K). Recovery and Search groups only
 * appear once the Feed has registered the commands behind them. */
export function CommandLauncher({
  open,
  onOpenChange,
  actions,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  actions: LauncherActions;
}) {
  const close = () => onOpenChange(false);
  const { recovery, search } = actions;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Command launcher</DialogTitle>
        <div className="mt-4 space-y-4">
          <CommandGroup label="Intake">
            {INTAKE_ACTIONS.map((action) => (
              <CommandAction
                key={action.key}
                icon={action.icon}
                label={action.label}
                shortcut={action.shortcut}
                onSelect={() => actions.runIntake(action.key, close)}
              />
            ))}
          </CommandGroup>
          <CommandGroup label="Navigate">
            <CommandAction
              icon={Link2}
              label="Open Links"
              shortcut="L"
              onSelect={() => actions.navigate('/feed?view=links')}
            />
            <CommandAction
              icon={Pin}
              label="GoTo Links"
              shortcut="G T"
              onSelect={() => {
                close();
                actions.openGoTo();
              }}
            />
          </CommandGroup>
          {recovery && (
            <CommandGroup label="Recovery">
              <CommandAction
                icon={Trash2}
                label="Clear Failed"
                shortcut="C"
                disabled={!recovery.canClearFailed}
                onSelect={() => {
                  if (!window.confirm(CLEAR_FAILED_CONFIRM)) return;
                  close();
                  recovery.clearFailed();
                }}
              />
            </CommandGroup>
          )}
          {search && (
            <CommandGroup label="Search">
              <CommandAction
                icon={Search}
                label="Search"
                shortcut="/"
                onSelect={() => {
                  close();
                  requestAnimationFrame(() => search.focusSearch());
                }}
              />
              <CommandAction
                icon={Search}
                label="Search Links"
                shortcut="*"
                onSelect={() => {
                  close();
                  requestAnimationFrame(() => search.focusLinkSearch());
                }}
              />
            </CommandGroup>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
