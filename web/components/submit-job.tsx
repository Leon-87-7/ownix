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
import { SubmitUrlForm } from '@/components/submit-url-form';
import { FileCode2, Link2, Plus, Search, Trash2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/dialog';
import { DocUploadPanel } from './doc-upload-panel';

/** The job the API accepted, timestamped so consumers can react to repeats. */
export interface AcceptedJob {
  id: string | null;
  url: string;
  title: string | null;
  content_type: string;
  status: string;
  at: number;
}

const CLEAR_FAILED_CONFIRM =
  'Clear failed jobs in this tab? This marks them cancelled; it does not delete them.';

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

interface SubmitJobContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  openDocs: () => void;
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
function CommandShortcut({ keys }: { keys: string }) {
  return (
    <span className="ml-auto flex items-center gap-1">
      {keys.split(' ').map((key, i) => (
        <kbd
          key={i}
          className="rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-contrasignal-deep"
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

/**
 * Owns the one Submit URL dialog for the whole dashboard. Triggers anywhere
 * (global header on sm+, the Feed's tabs-row button below sm) call setOpen;
 * pages that care about the outcome (Feed's optimistic rows) watch
 * lastAccepted instead of owning the mutation themselves.
 */
export function SubmitJobProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [docsOpen, setDocsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [url, setUrl] = useState('');
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

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      if (
        key === 'n' &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        !shouldIgnoreGlobalShortcut(event.target)
      ) {
        event.preventDefault();
        setOpen(true);
        return;
      }
      if (
        key === 'd' &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        !shouldIgnoreGlobalShortcut(event.target)
      ) {
        event.preventDefault();
        setDocsOpen(true);
        return;
      }
      if (
        key === 'l' &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        !shouldIgnoreGlobalShortcut(event.target)
      ) {
        event.preventDefault();
        window.location.assign('/?view=links');
        return;
      }
      if (
        key === 'c' &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        !shouldIgnoreGlobalShortcut(event.target)
      ) {
        const recovery = feedRecoveryRef.current;
        if (recovery?.canClearFailed) {
          event.preventDefault();
          if (window.confirm(CLEAR_FAILED_CONFIRM))
            recovery.clearFailed();
        }
        return;
      }
      if (
        key === '/' &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        !shouldIgnoreGlobalShortcut(event.target)
      ) {
        const search = feedSearchRef.current;
        if (search) {
          event.preventDefault();
          search.focusSearch();
        }
        return;
      }
      if (
        key === '*' &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        !shouldIgnoreGlobalShortcut(event.target)
      ) {
        const search = feedSearchRef.current;
        if (search) {
          event.preventDefault();
          search.focusLinkSearch();
        }
        return;
      }
      if (
        key === 'k' &&
        (event.metaKey || event.ctrlKey) &&
        !event.altKey &&
        !shouldIgnoreGlobalShortcut(event.target)
      ) {
        event.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

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
        const res = await fetch('/api/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok)
          throw new Error(data.detail || 'Could not submit job');
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

  const openDocs = useCallback(() => setDocsOpen(true), []);
  const openCommand = useCallback(() => setCommandOpen(true), []);
  const go = useCallback((href: string) => {
    setCommandOpen(false);
    setDocsOpen(false);
    window.location.assign(href);
  }, []);

  const value = useMemo(
    () => ({
      open,
      setOpen,
      openDocs,
      openCommand,
      lastAccepted,
      feedRecovery,
      registerFeedRecovery,
      feedSearch,
      registerFeedSearch,
    }),
    [
      open,
      openDocs,
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
      <Dialog
        open={commandOpen}
        onOpenChange={setCommandOpen}
      >
        <DialogContent>
          <DialogTitle>Command launcher</DialogTitle>
          <div className="mt-4 space-y-4">
            <CommandGroup label="Intake">
              <CommandAction
                icon={Plus}
                label="Submit URL"
                shortcut="N"
                onSelect={() => {
                  setCommandOpen(false);
                  setOpen(true);
                }}
              />
              <CommandAction
                icon={FileCode2}
                label="Ingest Docs"
                shortcut="D"
                onSelect={() => {
                  setCommandOpen(false);
                  setDocsOpen(true);
                }}
              />
            </CommandGroup>
            <CommandGroup label="Navigate">
              <CommandAction
                icon={Link2}
                label="Open Links"
                shortcut="L"
                onSelect={() => go('/?view=links')}
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
    </SubmitJobContext.Provider>
  );
}
