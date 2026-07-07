'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { FormEvent, ReactNode } from 'react';
import { SubmitUrlForm } from '@/components/submit-url-form';
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/dialog';

/** The job the API accepted, timestamped so consumers can react to repeats. */
export interface AcceptedJob {
  id: string | null;
  url: string;
  title: string | null;
  content_type: string;
  status: string;
  at: number;
}

interface SubmitJobContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  lastAccepted: AcceptedJob | null;
}

const SubmitJobContext = createContext<SubmitJobContextValue | null>(
  null,
);

function hasActiveDialog() {
  return Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).some(
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

    if (host === 'github.com') return 'repo';
    if (host.endsWith('youtube.com') && path === '/watch') return 'long';
    if (host === 'youtu.be') return 'long';
    if (host.endsWith('youtube.com') && path.startsWith('/shorts/')) return 'short';
    if (host.endsWith('instagram.com') && path.startsWith('/reel/')) return 'short';
    if (host.endsWith('tiktok.com') && path.includes('/video/')) return 'short';
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
  const [url, setUrl] = useState('');
  const [template, setTemplate] = useState('summary');
  const [freestylePrompt, setFreestylePrompt] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [lastAccepted, setLastAccepted] =
    useState<AcceptedJob | null>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key.toLowerCase() !== 'n' ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        shouldIgnoreGlobalShortcut(event.target)
      ) {
        return;
      }
      event.preventDefault();
      setOpen(true);
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
          id:
            typeof data.id === 'string' && data.id ? data.id : null,
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

  const value = useMemo(
    () => ({ open, setOpen, lastAccepted }),
    [open, lastAccepted],
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
    </SubmitJobContext.Provider>
  );
}
