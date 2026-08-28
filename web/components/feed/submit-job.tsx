'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { FormEvent, ReactNode } from 'react';
import { SubmitUrlForm } from '@/components/feed/submit-url-form';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { GhostButton } from '@/components/ui/ghost-button';
import {
  FileCode2,
  Link2,
  Pin,
  Plus,
  Search,
  Trash2,
  Waypoints,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/dialog';
import { DocUploadPanel } from '@/components/doc-parser/doc-upload-panel';
import { GoToLinksPanel } from '@/components/feed/goto-links-panel';
import { useRestrictedMode } from '@/lib/restricted/context';
import { parseBatchLinkInput } from '@/lib/parse-batch-links';
import { apiPost } from '@/lib/fetch-utils';

/** POST /api/jobs response shape, as loosely typed as the JSON it actually returns. */
interface SubmittedJob {
  id?: string;
  title?: string;
  content_type?: string;
  status?: string;
}

/** The job the API accepted, timestamped so consumers can react to repeats. */
interface AcceptedJob {
  id: string | null;
  url: string;
  title: string | null;
  content_type: string;
  status: string;
  at: number;
}

const CLEAR_FAILED_CONFIRM =
  'Clear failed jobs in this tab? This marks them cancelled; it does not delete them.';

// Window for the "G then T" GoTo chord — a 't' after this long is a fresh,
// unrelated keystroke, not the second half of the chord.
const GOTO_CHORD_TIMEOUT_MS = 600;

/** Recovery action the Feed registers so the launcher can drive it with the
 * live scope + availability the Feed's useRecovery already computes. (Retry
 * pending/failed stay in the contextual recovery panel, not the palette.) */
interface FeedRecoveryCommands {
  canClearFailed: boolean;
  clearFailed: () => void;
}

/** Feed search focus, registered so the launcher can jump into the Feed's
 * search input (or switch to Links first). */
interface FeedSearchCommands {
  focusSearch: () => void;
  focusLinkSearch: () => void;
}

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

const SubmitJobContext = createContext<SubmitJobContextValue | null>(
  null,
);

/** One row of live batch-paste progress (CONTEXT.md "Batch link paste"). */
interface BatchLinkResult {
  token: string;
  status: 'pending' | 'success' | 'error';
  message?: string;
}

const BATCH_LINK_CONCURRENCY = 6;

async function runWithConcurrency<T, R>(
  items: readonly T[],
  limit: number,
  worker: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let nextIndex = 0;
  const workerCount = Math.min(limit, items.length);

  await Promise.all(
    Array.from({ length: workerCount }, async () => {
      while (nextIndex < items.length) {
        const index = nextIndex;
        nextIndex += 1;
        results[index] = await worker(items[index], index);
      }
    }),
  );

  return results;
}

function hasActiveDialog() {
  return Array.from(
    document.querySelectorAll<HTMLElement>('[role="dialog"]'),
  ).some(
    (dialog) =>
      dialog.getAttribute('aria-hidden') !== 'true' &&
      dialog.dataset.state !== 'closed',
  );
}

function shouldIgnoreGlobalShortcut(target: EventTarget | null) {
  if (hasActiveDialog()) return true;
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    tag === 'input' ||
    tag === 'textarea' ||
    tag === 'select' ||
    target.isContentEditable ||
    Boolean(target.closest('[role="dialog"]'))
  );
}

function inferContentTypeFromUrl(rawUrl: string): string {
  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, '');
    const path = parsed.pathname.toLowerCase();

    // Match the exact apex or a dot-separated subdomain so lookalike hosts
    // (fakeyoutube.com, eviltiktok.com) don't slip through endsWith().
    const isHost = (domain: string) =>
      host === domain || host.endsWith(`.${domain}`);

    if (host === 'github.com') return 'repo';
    if (isHost('youtube.com') && path === '/watch') return 'long';
    if (host === 'youtu.be') return 'long';
    if (isHost('youtube.com') && path.startsWith('/shorts/'))
      return 'short';
    if (isHost('instagram.com') && path.startsWith('/reel/'))
      return 'short';
    if (isHost('tiktok.com') && path.includes('/video/'))
      return 'short';
  } catch {
    return 'article';
  }

  return 'article';
}

export function useSubmitJob(): SubmitJobContextValue {
  const ctx = useContext(SubmitJobContext);
  if (!ctx)
    throw new Error(
      'useSubmitJob must be used within SubmitJobProvider',
    );
  return ctx;
}

/** Non-throwing variant for components that may render outside the provider
 * (e.g. RecoveryPanel's standalone unit test): returns null instead. */
export function useSubmitJobOptional(): SubmitJobContextValue | null {
  return useContext(SubmitJobContext);
}

// Space-separated keys render as individual right-aligned kbd chips so a
// chord like "R P" reads as two keys.

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
      <Icon
        className="h-4 w-4 text-contrasignal-deep"
        aria-hidden="true"
      />
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
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-12 w-full items-start gap-3 rounded-lg border border-line bg-surface px-3 py-3 text-left transition-ui hover:bg-raised focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96] motion-reduce:active:scale-100"
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

/**
 * Owns the one Submit URL dialog for the whole dashboard. Triggers anywhere
 * (global header on sm+, the Feed's tabs-row button below sm) call setOpen;
 * pages that care about the outcome (Feed's optimistic rows) watch
 * lastAccepted instead of owning the mutation themselves.
 */
/** A dialog-open flag that refuses to flip on (with a sign-in toast) in restricted mode. */
function useGatedOpen(
  restricted: boolean,
  showRestrictedToast: (message: string) => void,
  message: string,
  onOpen?: () => void,
): [boolean, (next: boolean) => void] {
  const [value, setValue] = useState(false);
  const setGated = useCallback(
    (next: boolean) => {
      if (next && restricted) {
        showRestrictedToast(message);
        return;
      }
      if (next) onOpen?.();
      setValue(next);
    },
    [restricted, showRestrictedToast, message, onOpen],
  );
  return [value, setGated];
}

export function SubmitJobProvider({
  children,
}: {
  children: ReactNode;
}) {
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
  const [batchResults, setBatchResults] = useState<BatchLinkResult[]>(
    [],
  );
  const clearBatchResults = useCallback(() => setBatchResults([]), []);
  const [addLinkOpen, setAddLinkOpen] = useGatedOpen(
    restricted,
    showRestrictedToast,
    'Sign in to add links to your own Index.',
    clearBatchResults,
  );
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useGatedOpen(
    restricted,
    showRestrictedToast,
    'Sign in to run commands on your own Index.',
  );
  // GoTo quick-jump — links carrying one of the user's pinned tags. Read-only
  // view of the user's own data, so unlike the dialogs above it isn't gated
  // behind restricted mode (same as the Navigate group's "Open Links").
  const [goToOpen, setGoToOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [addLinkUrl, setAddLinkUrl] = useState('');
  const [addLinkError, setAddLinkError] = useState<string | null>(
    null,
  );
  const [addLinkSubmitting, setAddLinkSubmitting] = useState(false);
  const [template, setTemplate] = useState('summary');
  const [freestylePrompt, setFreestylePrompt] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [lastAccepted, setLastAccepted] =
    useState<AcceptedJob | null>(null);
  const [feedRecovery, setFeedRecovery] =
    useState<FeedRecoveryCommands | null>(null);
  const [feedSearch, setFeedSearch] =
    useState<FeedSearchCommands | null>(null);
  const registerFeedRecovery = useCallback(
    (cmds: FeedRecoveryCommands | null) => setFeedRecovery(cmds),
    [],
  );
  const registerFeedSearch = useCallback(
    (cmds: FeedSearchCommands | null) => setFeedSearch(cmds),
    [],
  );
  // Read the latest recovery commands from the (deps-free) global keydown
  // handler without re-binding the listener on every summary change.
  const feedRecoveryRef = useRef(feedRecovery);
  feedRecoveryRef.current = feedRecovery;
  const feedSearchRef = useRef(feedSearch);
  feedSearchRef.current = feedSearch;
  // "G then T" is a sequential chord, not a simultaneous combo — remembers the
  // pending 'g' and its timestamp so a stray 'g' alone (or a stale one after
  // the timeout) never fires GoTo.
  const goToChordRef = useRef<number | null>(null);

  useEffect(() => {
    // ponytail: single-key shortcuts share one no-modifiers dispatch table;
    // cmd/ctrl+shift+k keeps its own branch since its modifier check differs.
    const plainKeyShortcuts: Record<string, () => void> = {
      n: () => setOpen(true),
      d: () => setDocsOpen(true),
      u: () => setAddLinkOpen(true),
      l: () => window.location.assign('/feed?view=links'),
      c: () => {
        const recovery = feedRecoveryRef.current;
        if (!restricted && recovery?.canClearFailed && window.confirm(CLEAR_FAILED_CONFIRM))
          recovery.clearFailed();
      },
      '/': () => feedSearchRef.current?.focusSearch(),
      '*': () => feedSearchRef.current?.focusLinkSearch(),
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const noMods =
        !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;

      // Chord bookkeeping runs on every keydown (not just the shortcut-eligible
      // branch below) so any interrupting key — modified, or typed into a field —
      // clears a pending 'g' instead of leaving it live for a later, unrelated 't'.
      const canFireGoTo = noMods && !shouldIgnoreGlobalShortcut(event.target);
      const pendingG = goToChordRef.current;
      if (canFireGoTo && key === 't' && pendingG !== null && Date.now() - pendingG < GOTO_CHORD_TIMEOUT_MS) {
        goToChordRef.current = null;
        event.preventDefault();
        setGoToOpen(true);
        return;
      }
      goToChordRef.current = canFireGoTo && key === 'g' ? Date.now() : null;

      if (key === 'k' && (event.metaKey || event.ctrlKey) && event.shiftKey && !event.altKey) {
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
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    restricted,
    setAddLinkOpen,
    setCommandOpen,
    setDocsOpen,
    setGoToOpen,
    setOpen,
  ]);

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
      try {
        const payload: Record<string, string> = {
          url: trimmed,
          template,
        };
        if (template === 'freestyle')
          payload.freestyle_prompt = freestylePrompt.trim();
        const result = await apiPost<SubmittedJob>(
          '/api/jobs',
          payload,
          'Could not submit job',
        );
        if (!result.ok) throw new Error(result.detail);
        const data = result.data;
        setLastAccepted({
          id: typeof data.id === 'string' && data.id ? data.id : null,
          url: trimmed,
          title: typeof data.title === 'string' ? data.title : null,
          content_type:
            typeof data.content_type === 'string'
              ? data.content_type
              : inferContentTypeFromUrl(trimmed),
          status:
            typeof data.status === 'string' ? data.status : 'pending',
          at: Date.now(),
        });
        setUrl('');
        setFreestylePrompt('');
        setOpen(false);
      } catch (e) {
        setError(
          e instanceof Error ? e.message : 'Could not submit job',
        );
      } finally {
        setSubmitting(false);
      }
    },
    [freestylePrompt, submitting, template, url],
  );

  /** Submits one already-parsed token, updating its row in batchResults.
   * Returns true on success — plain return value, not React state, so the
   * caller can tally the batch outcome without racing setState's batching. */
  const submitOneLink = useCallback(
    async (token: string, index: number): Promise<boolean> => {
      try {
        const result = await apiPost<SubmittedJob>(
          '/api/jobs',
          { url: token, content_type: 'link' },
          'Could not add link',
        );
        if (!result.ok) {
          setBatchResults((current) =>
            current.map((row, i) =>
              i === index ? { ...row, status: 'error', message: result.detail } : row,
            ),
          );
          return false;
        }
        const data = result.data;
        setLastAccepted({
          id: typeof data.id === 'string' && data.id ? data.id : null,
          url: token,
          title: typeof data.title === 'string' ? data.title : null,
          content_type: 'link',
          status:
            typeof data.status === 'string' ? data.status : 'pending',
          at: Date.now(),
        });
        setBatchResults((current) =>
          current.map((row, i) =>
            i === index ? { ...row, status: 'success' } : row,
          ),
        );
        return true;
      } catch (e) {
        const message =
          e instanceof Error ? e.message : 'Could not add link';
        setBatchResults((current) =>
          current.map((row, i) =>
            i === index ? { ...row, status: 'error', message } : row,
          ),
        );
        return false;
      }
    },
    [setBatchResults, setLastAccepted],
  );

  const submitAddLink = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const tokens = parseBatchLinkInput(addLinkUrl);
      if (tokens.length === 0 || addLinkSubmitting) return;
      setAddLinkError(null);
      setAddLinkSubmitting(true);
      setBatchResults(
        tokens.map((token) => ({ token, status: 'pending' as const })),
      );

      const results = await runWithConcurrency(
        tokens,
        BATCH_LINK_CONCURRENCY,
        (token, index) => submitOneLink(token, index),
      );
      const failures = results.filter((ok) => !ok).length;

      setAddLinkSubmitting(false);
      if (failures === 0) {
        setAddLinkUrl('');
        setAddLinkOpen(false);
        setBatchResults([]);
      }
    },
    [
      addLinkSubmitting,
      addLinkUrl,
      setAddLinkOpen,
      submitOneLink,
      setAddLinkError,
      setAddLinkSubmitting,
      setBatchResults,
      setAddLinkUrl,
    ],
  );

  const openSubmitWith = useCallback(
    (nextUrl: string) => {
      // Restricted mode: setOpen refuses with the sign-in toast — don't leave
      // a stale prefill behind in that case.
      if (!restricted) setUrl(nextUrl);
      setOpen(true);
    },
    [restricted, setOpen, setUrl],
  );
  const openDocs = useCallback(
    () => setDocsOpen(true),
    [setDocsOpen],
  );
  const openIntake = useCallback(() => setIntakeOpen(true), []);
  const openCommand = useCallback(
    () => setCommandOpen(true),
    [setCommandOpen],
  );
  const go = useCallback((href: string) => {
    setCommandOpen(false);
    setDocsOpen(false);
    window.location.assign(href);
  }, [setCommandOpen, setDocsOpen]);

  const launchIntakeAction = useCallback(
    (key: IntakeActionKey, closeSurface: () => void) => {
      closeSurface();
      switch (key) {
        case 'submit':
          setOpen(true);
          break;
        case 'docs':
          setDocsOpen(true);
          break;
        case 'link':
          setAddLinkOpen(true);
          break;
      }
    },
    [setAddLinkOpen, setDocsOpen, setOpen],
  );

  const addLinkTokenCount = useMemo(
    () => parseBatchLinkInput(addLinkUrl).length,
    [addLinkUrl],
  );
  const addLinkButtonLabel = addLinkSubmitting
    ? `Ingesting ${batchResults.filter((r) => r.status !== 'pending').length}/${batchResults.length}…`
    : addLinkTokenCount > 1
      ? `Ingest ${addLinkTokenCount} Links`
      : 'Ingest Link';

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
      <Dialog
        open={open}
        onOpenChange={setOpen}
      >
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
      <Dialog
        open={addLinkOpen}
        onOpenChange={setAddLinkOpen}
      >
        <DialogContent>
          <DialogTitle>Ingest Link</DialogTitle>
          <form
            onSubmit={submitAddLink}
            className="mt-4 space-y-4"
          >
            <label className="block text-sm font-medium text-ink">
              URL
              <textarea
                value={addLinkUrl}
                onChange={(event) =>
                  setAddLinkUrl(event.target.value)
                }
                rows={4}
                placeholder={
                  'https://example.com\nhttps://example.com/two\n…one per line, or paste a whole list'
                }
                aria-describedby={
                  addLinkError ? 'add-link-error' : undefined
                }
                className="mt-2 w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 font-mono text-sm text-ink outline-none transition-ui placeholder:font-sans placeholder:text-muted focus:border-signal focus:ring-1 focus:ring-signal"
              />
            </label>
            <p className="text-xs text-muted">
              Ingest Link saves each link as-is; it does not process
              them through the pipeline-detection flow. Paste as many
              as you like — one job per link.
            </p>
            {addLinkError && (
              <p
                id="add-link-error"
                role="alert"
                className="text-sm text-red-400"
              >
                {addLinkError}
              </p>
            )}
            {batchResults.length > 0 && (
              <ul className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-line bg-canvas p-2 font-mono text-xs">
                {batchResults.map((row, i) => (
                  <li
                    key={`${row.token}-${i}`}
                    className="flex items-start gap-2"
                  >
                    <span
                      aria-hidden="true"
                      className={
                        row.status === 'success'
                          ? 'text-status-done'
                          : row.status === 'error'
                            ? 'text-status-error'
                            : 'text-muted'
                      }
                    >
                      {row.status === 'success'
                        ? '✓'
                        : row.status === 'error'
                          ? '✕'
                          : '…'}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-body">
                      {row.token}
                      {row.message && (
                        <span className="ml-2 text-status-error">
                          {row.message}
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <GhostButton
              type="submit"
              accent="signal"
              disabled={addLinkSubmitting || addLinkTokenCount === 0}
              className="h-9 bg-canvas px-3 text-sm font-medium text-signal"
            >
              {addLinkButtonLabel}
            </GhostButton>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={docsOpen}
        onOpenChange={setDocsOpen}
      >
        <DialogContent className="shadow-none">
          <DialogTitle>Ingest Docs</DialogTitle>
          <DocUploadPanel
            flat
            onUploaded={(jobId) =>
              go(jobId ? `/doc-parser/${jobId}` : '/doc-parser')
            }
          />
        </DialogContent>
      </Dialog>

      <Sheet
        open={intakeOpen}
        onOpenChange={setIntakeOpen}
      >
        <SheetContent aria-describedby={undefined}>
          <SheetTitle>Add to your Index</SheetTitle>
          <div className="mt-5 space-y-2">
            {INTAKE_ACTIONS.map((action) => (
              <SheetActionButton
                key={action.key}
                icon={action.icon}
                label={action.label}
                description={action.description}
                onClick={() =>
                  launchIntakeAction(action.key, () =>
                    setIntakeOpen(false),
                  )
                }
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
                  setIntakeOpen(false);
                  setGoToOpen(true);
                }}
              />
            </CommandGroup>
          </div>
        </SheetContent>
      </Sheet>
      <Dialog
        open={commandOpen}
        onOpenChange={setCommandOpen}
      >
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
                  onSelect={() =>
                    launchIntakeAction(action.key, () =>
                      setCommandOpen(false),
                    )
                  }
                />
              ))}
            </CommandGroup>
            <CommandGroup label="Navigate">
              <CommandAction
                icon={Link2}
                label="Open Links"
                shortcut="L"
                onSelect={() => go('/feed?view=links')}
              />
              <CommandAction
                icon={Pin}
                label="GoTo Links"
                shortcut="G T"
                onSelect={() => {
                  setCommandOpen(false);
                  setGoToOpen(true);
                }}
              />
            </CommandGroup>
            {feedRecovery && (
              <CommandGroup label="Recovery">
                <CommandAction
                  icon={Trash2}
                  label="Clear Failed"
                  shortcut="C"
                  disabled={!feedRecovery.canClearFailed}
                  onSelect={() => {
                    if (!window.confirm(CLEAR_FAILED_CONFIRM)) return;
                    setCommandOpen(false);
                    feedRecovery.clearFailed();
                  }}
                />
              </CommandGroup>
            )}
            {feedSearch && (
              <CommandGroup label="Search">
                <CommandAction
                  icon={Search}
                  label="Search"
                  shortcut="/"
                  onSelect={() => {
                    const search = feedSearch;
                    setCommandOpen(false);
                    requestAnimationFrame(() => search.focusSearch());
                  }}
                />
                <CommandAction
                  icon={Search}
                  label="Search Links"
                  shortcut="*"
                  onSelect={() => {
                    const search = feedSearch;
                    setCommandOpen(false);
                    requestAnimationFrame(() =>
                      search.focusLinkSearch(),
                    );
                  }}
                />
              </CommandGroup>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={goToOpen}
        onOpenChange={setGoToOpen}
      >
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
