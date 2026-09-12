'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { FormEvent, ReactNode } from 'react';
import { SubmitUrlForm } from '@/components/feed/submit-url-form';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { DocUploadPanel } from '@/components/doc-parser/doc-upload-panel';
import { GoToLinksPanel } from '@/components/feed/goto-links-panel';
import { IngestLinkDialog } from '@/components/feed/ingest-link-dialog';
import {
  CommandLauncher,
  IntakeSheet,
  CLEAR_FAILED_CONFIRM,
  type FeedRecoveryCommands,
  type FeedSearchCommands,
  type IntakeActionKey,
  type LauncherActions,
} from '@/components/feed/command-launcher';
import { toAcceptedJob } from '@/components/feed/accepted-job';
import type {
  AcceptedJob,
  SubmittedJob,
} from '@/components/feed/accepted-job';
import { useRestrictedMode } from '@/lib/restricted/context';
import { apiPost, describeError } from '@/lib/fetch-utils';
import { shouldIgnoreGlobalShortcut } from '@/lib/keyboard';
import { useGlobalKeydown } from '@/lib/hooks/useGlobalKeydown';
import { useHapticFeedback } from '@/lib/hooks/useHapticFeedback';

export { INTAKE_ACTIONS } from '@/components/feed/command-launcher';
export type { IntakeActionKey } from '@/components/feed/command-launcher';

// Window for the "G then T" GoTo chord — a 't' after this long is a fresh,
// unrelated keystroke, not the second half of the chord.
const GOTO_CHORD_TIMEOUT_MS = 600;

interface SubmitJobContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  openSubmitWith: (url: string) => void;
  openDocs: () => void;
  openIntake: () => void;
  openCommand: () => void;
  lastAccepted: AcceptedJob | null;
  feedRecovery: FeedRecoveryCommands | null;
  registerFeedRecovery: (cmds: FeedRecoveryCommands | null) => void;
  feedSearch: FeedSearchCommands | null;
  registerFeedSearch: (cmds: FeedSearchCommands | null) => void;
}

const SubmitJobContext = createContext<SubmitJobContextValue | null>(null);

export function useSubmitJob(): SubmitJobContextValue {
  const ctx = useContext(SubmitJobContext);
  if (!ctx)
    throw new Error('useSubmitJob must be used within SubmitJobProvider');
  return ctx;
}

/** Non-throwing variant for components that may render outside the provider
 * (e.g. RecoveryPanel's standalone unit test): returns null instead. */
export function useSubmitJobOptional(): SubmitJobContextValue | null {
  return useContext(SubmitJobContext);
}

/** A dialog-open flag that refuses to flip on (with a sign-in toast) in restricted mode. */
function useGatedOpen(
  restricted: boolean,
  showRestrictedToast: (message: string) => void,
  message: string,
): [boolean, (next: boolean) => void] {
  const [value, setValue] = useState(false);
  const setGated = useCallback(
    (next: boolean) => {
      if (next && restricted) {
        showRestrictedToast(message);
        return;
      }
      setValue(next);
    },
    [restricted, showRestrictedToast, message],
  );
  return [value, setGated];
}

/**
 * Owns the dashboard's intake surfaces: which one is open, and the Submit URL
 * mutation itself. Triggers anywhere (global header on sm+, the Feed's tabs-row
 * button below sm) call setOpen; pages that care about the outcome (Feed's
 * optimistic rows) watch `lastAccepted` instead of owning the mutation.
 *
 * Each surface owns its own body — IngestLinkDialog runs the batch-paste flow,
 * CommandLauncher/IntakeSheet render the command lists — so what lives here is
 * the open/closed state machine and the shortcuts that drive it.
 */
export function SubmitJobProvider({ children }: { children: ReactNode }) {
  const haptic = useHapticFeedback();
  const { restricted, showRestrictedToast } = useRestrictedMode();

  const [open, setOpen] = useGatedOpen(
    restricted,
    showRestrictedToast,
    'Sign in to submit URLs to your own Index.',
  );
  const [docsOpen, setDocsOpen] = useGatedOpen(
    restricted,
    showRestrictedToast,
    'Sign in to parse documents into your own Index.',
  );
  const [addLinkOpen, setAddLinkOpen] = useGatedOpen(
    restricted,
    showRestrictedToast,
    'Sign in to add links to your own Index.',
  );
  const [commandOpen, setCommandOpen] = useGatedOpen(
    restricted,
    showRestrictedToast,
    'Sign in to run commands on your own Index.',
  );
  const [intakeOpen, setIntakeOpen] = useState(false);
  // GoTo quick-jump — links carrying one of the user's pinned tags. Read-only
  // view of the user's own data, so unlike the dialogs above it isn't gated
  // behind restricted mode (same as the Navigate group's "Open Links").
  const [goToOpen, setGoToOpen] = useState(false);

  const [url, setUrl] = useState('');
  const [template, setTemplate] = useState('summary');
  const [freestylePrompt, setFreestylePrompt] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [lastAccepted, setLastAccepted] = useState<AcceptedJob | null>(null);

  const [feedRecovery, setFeedRecovery] =
    useState<FeedRecoveryCommands | null>(null);
  const [feedSearch, setFeedSearch] = useState<FeedSearchCommands | null>(null);
  const registerFeedRecovery = useCallback(
    (cmds: FeedRecoveryCommands | null) => setFeedRecovery(cmds),
    [],
  );
  const registerFeedSearch = useCallback(
    (cmds: FeedSearchCommands | null) => setFeedSearch(cmds),
    [],
  );

  // "G then T" is a sequential chord, not a simultaneous combo — remembers the
  // pending 'g' and its timestamp so a stray 'g' alone (or a stale one after
  // the timeout) never fires GoTo.
  const goToChordRef = useRef<number | null>(null);

  const openDocs = useCallback(() => setDocsOpen(true), [setDocsOpen]);
  const openIntake = useCallback(() => setIntakeOpen(true), []);
  const openCommand = useCallback(
    () => setCommandOpen(true),
    [setCommandOpen],
  );
  const openSubmitWith = useCallback(
    (nextUrl: string) => {
      // Restricted mode: setOpen refuses with the sign-in toast — don't leave
      // a stale prefill behind in that case.
      if (!restricted) setUrl(nextUrl);
      setOpen(true);
    },
    [restricted, setOpen],
  );

  const launchIntakeAction = useCallback(
    (key: IntakeActionKey, closeSurface: () => void) => {
      closeSurface();
      if (key === 'submit') setOpen(true);
      else if (key === 'docs') setDocsOpen(true);
      else setAddLinkOpen(true);
    },
    [setAddLinkOpen, setDocsOpen, setOpen],
  );

  const navigate = useCallback(
    (href: string) => {
      setCommandOpen(false);
      setDocsOpen(false);
      window.location.assign(href);
    },
    [setCommandOpen, setDocsOpen],
  );

  // ponytail: single-key shortcuts share one no-modifiers dispatch table;
  // cmd/ctrl+shift+k keeps its own branch since its modifier check differs.
  // useGlobalKeydown keeps the handler current, so these read `feedRecovery` /
  // `feedSearch` straight off the render rather than through mirror refs.
  const plainKeyShortcuts: Record<string, () => void> = {
    n: () => setOpen(true),
    d: () => setDocsOpen(true),
    u: () => setAddLinkOpen(true),
    l: () => window.location.assign('/feed?view=links'),
    c: () => {
      if (
        !restricted &&
        feedRecovery?.canClearFailed &&
        window.confirm(CLEAR_FAILED_CONFIRM)
      )
        feedRecovery.clearFailed();
    },
    '/': () => feedSearch?.focusSearch(),
    '*': () => feedSearch?.focusLinkSearch(),
  };

  useGlobalKeydown((event) => {
    const key = event.key.toLowerCase();
    const noMods =
      !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;

    // Chord bookkeeping runs on every keydown (not just the shortcut-eligible
    // branch below) so any interrupting key — modified, or typed into a field —
    // clears a pending 'g' instead of leaving it live for a later, unrelated 't'.
    const canFireGoTo = noMods && !shouldIgnoreGlobalShortcut(event.target);
    const pendingG = goToChordRef.current;
    if (
      canFireGoTo &&
      key === 't' &&
      pendingG !== null &&
      Date.now() - pendingG < GOTO_CHORD_TIMEOUT_MS
    ) {
      goToChordRef.current = null;
      event.preventDefault();
      setGoToOpen(true);
      return;
    }
    goToChordRef.current = canFireGoTo && key === 'g' ? Date.now() : null;

    if (
      key === 'k' &&
      (event.metaKey || event.ctrlKey) &&
      event.shiftKey &&
      !event.altKey
    ) {
      if (!shouldIgnoreGlobalShortcut(event.target)) {
        event.preventDefault();
        setCommandOpen(true);
      }
      return;
    }

    const handler = plainKeyShortcuts[key];
    if (noMods && handler && !shouldIgnoreGlobalShortcut(event.target)) {
      event.preventDefault();
      handler();
    }
  });

  const submitJob = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const trimmed = url.trim();
      if (!trimmed || submitting) return;
      setError(null);

      if (template === 'freestyle' && !freestylePrompt.trim()) {
        setError('Freestyle prompt cannot be empty');
        return;
      }

      setSubmitting(true);
      const payload: Record<string, string> = { url: trimmed, template };
      if (template === 'freestyle')
        payload.freestyle_prompt = freestylePrompt.trim();
      const result = await apiPost<SubmittedJob>(
        '/api/jobs',
        payload,
        'Could not submit job',
      );
      setSubmitting(false);

      if (!result.ok) {
        setError(result.detail);
        haptic('error');
        return;
      }
      setLastAccepted(toAcceptedJob(result.data, trimmed));
      setUrl('');
      setFreestylePrompt('');
      setOpen(false);
      haptic('success');
    },
    [freestylePrompt, haptic, setOpen, submitting, template, url],
  );

  const launcherActions: LauncherActions = useMemo(
    () => ({
      runIntake: launchIntakeAction,
      openGoTo: () => setGoToOpen(true),
      navigate,
      recovery: feedRecovery,
      search: feedSearch,
    }),
    [launchIntakeAction, navigate, feedRecovery, feedSearch],
  );

  const value = useMemo(
    () => ({
      open,
      setOpen,
      openSubmitWith,
      openDocs,
      openIntake,
      openCommand,
      lastAccepted,
      feedRecovery,
      registerFeedRecovery,
      feedSearch,
      registerFeedSearch,
    }),
    [
      open,
      setOpen,
      openSubmitWith,
      openDocs,
      openIntake,
      openCommand,
      lastAccepted,
      feedRecovery,
      registerFeedRecovery,
      feedSearch,
      registerFeedSearch,
    ],
  );

  return (
    <SubmitJobContext.Provider value={value}>
      {children}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>Submit URL</DialogTitle>
          <div className="mt-4">
            <SubmitUrlForm
              url={url}
              onUrlChange={setUrl}
              template={template}
              onTemplateChange={setTemplate}
              freestylePrompt={freestylePrompt}
              onFreestylePromptChange={setFreestylePrompt}
              submitting={submitting}
              error={error}
              onSubmit={submitJob}
            />
          </div>
        </DialogContent>
      </Dialog>

      <IngestLinkDialog
        open={addLinkOpen}
        onOpenChange={setAddLinkOpen}
        onAccepted={setLastAccepted}
      />

      <Dialog open={docsOpen} onOpenChange={setDocsOpen}>
        <DialogContent className="shadow-none">
          <DialogTitle>Ingest Docs</DialogTitle>
          <DocUploadPanel
            flat
            onUploaded={(jobId) =>
              navigate(jobId ? `/doc-parser/${jobId}` : '/doc-parser')
            }
          />
        </DialogContent>
      </Dialog>

      <IntakeSheet
        open={intakeOpen}
        onOpenChange={setIntakeOpen}
        actions={launcherActions}
      />
      <CommandLauncher
        open={commandOpen}
        onOpenChange={setCommandOpen}
        actions={launcherActions}
      />

      <Dialog open={goToOpen} onOpenChange={setGoToOpen}>
        <DialogContent>
          <DialogTitle>GoTo</DialogTitle>
          <div className="mt-4">
            <GoToLinksPanel />
          </div>
        </DialogContent>
      </Dialog>
    </SubmitJobContext.Provider>
  );
}
