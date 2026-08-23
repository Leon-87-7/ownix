'use client';

import { useRestrictedMode } from '@/lib/restricted/context';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { useRouter } from 'next/navigation';

import { useEffect, useId, useRef, useState } from 'react';
import { useTagList } from '@/lib/hooks/useTagList';
import { useDomainList } from '@/lib/hooks/useDomainList';
import { apiPut } from '@/lib/fetch-utils';
import type { Tag, TagFormState } from '@/lib/hooks/useTagList';
import {
  Pin,
  PinOff,
  SlidersHorizontal,
  TagPlus,
} from 'lucide-react';
import { OwnixChevronDown } from '@/components/svg/ownix-chevron-down';
import { TagMark } from '@/components/ui/tag-picker';
import { Tooltip } from '@/components/ui/tooltip';
import { PageShell, PageHeader } from '@/components/shell/page-shell';
import { ExtensionTokensPanel } from '@/components/controls/extension-tokens-panel';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

import { TagForm, DEFAULT_COLOR } from '@/components/ui/tag-form';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';

function TagPill({
  tag,
  editing,
  onClick,
  onTogglePin,
}: {
  tag: Tag;
  editing: boolean;
  onClick: () => void;
  onTogglePin: () => void;
}) {
  return (
    <li
      className={`inline-flex items-center gap-0.5 rounded-full border bg-raised pr-1 text-xs font-medium text-ink transition-ui hover:border-line-strong ${editing ? 'border-line ring-1 ring-signal-deep' : 'border-line'}`}
    >
      <Tooltip content={tag.meaning || undefined}>
        <button
          type="button"
          onClick={onClick}
          aria-pressed={editing}
          aria-label={`Edit ${tag.name}`}
          className="inline-flex items-center gap-1.5 rounded-full py-1 pl-2.5 pr-1.5"
        >
          <TagMark
            tag={tag}
            className="h-3 w-3"
          />
          {tag.name}
        </button>
      </Tooltip>
      <Tooltip
        content={tag.pinned ? 'Unpin from GoTo' : 'Pin for GoTo'}
      >
        <button
          type="button"
          onClick={onTogglePin}
          aria-pressed={Boolean(tag.pinned)}
          aria-label={
            tag.pinned
              ? `Unpin ${tag.name} from GoTo`
              : `Pin ${tag.name} for GoTo`
          }
          className={`rounded-full p-1 transition-ui hover:bg-surface ${tag.pinned ? 'text-signal' : 'text-muted'}`}
        >
          {tag.pinned ? (
            <Pin
              className="h-3 w-3"
              aria-hidden="true"
            />
          ) : (
            <PinOff
              className="h-3 w-3"
              aria-hidden="true"
            />
          )}
        </button>
      </Tooltip>
    </li>
  );
}

function TagsTab() {
  const {
    tags,
    loading,
    fetchError,
    createTag,
    deleteTag,
    updateTag,
    toggleTagPinned,
  } = useTagList();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<
    string | undefined
  >();
  const [pinError, setPinError] = useState<string | undefined>();
  const editingTag = tags.find((t) => t.id === editingId) ?? null;
  const editPanelRef = useRef<HTMLDivElement>(null);

  // Detached edit panel can render off-screen (fixed slot, not inline at the
  // clicked pill), so pull it into view whenever the edit target changes.
  useEffect(() => {
    if (editingTag) {
      // jsdom doesn't implement scrollIntoView (undefined in tests).
      editPanelRef.current?.scrollIntoView?.({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  }, [editingTag]);

  const selectForEdit = (tagId: string) => {
    setDeleteError(undefined);
    setEditingId((current) => (current === tagId ? null : tagId));
  };

  const handleSave = async (values: TagFormState) => {
    if (!editingTag) return;
    await updateTag(editingTag.id, values);
    setEditingId(null);
  };

  const handleDelete = async () => {
    if (!editingTag) return;
    if (!confirm(`Delete tag "${editingTag.name}"?`)) return;
    setDeleteError(undefined);
    try {
      await deleteTag(editingTag.id);
      setEditingId(null);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : 'Delete failed',
      );
    }
  };

  const handleTogglePin = async (tag: Tag) => {
    setPinError(undefined);
    try {
      await toggleTagPinned(tag.id, !tag.pinned);
    } catch (err) {
      setPinError(err instanceof Error ? err.message : 'Pin failed');
    }
  };

  return (
    <div className="space-y-4">
      {/* ponytail: native <details>, open by default. Mobile = collapsible
          "Create tag" disclosure; desktop hides the summary entirely → plain card. */}
      <details
        open
        className="group"
      >
        <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-sm font-semibold text-ink [&::-webkit-details-marker]:hidden sm:hidden">
          Create tag
          <TagPlus
            className="h-4 w-4 text-muted"
            aria-hidden="true"
          />
        </summary>
        <div className="border-t border-line p-4 sm:border-t-0">
          <TagForm
            initial={{ name: '', meaning: '', color: DEFAULT_COLOR }}
            onSubmit={createTag}
            submitLabel="Create"
          />
        </div>
      </details>
      {editingTag && (
        <div
          ref={editPanelRef}
          className="rounded-lg border border-line bg-surface px-4 py-3"
        >
          <TagForm
            key={editingTag.id}
            initial={{
              name: editingTag.name,
              meaning: editingTag.meaning,
              color: editingTag.color,
              // Carried through the form untouched so saving an edit doesn't NULL it.
              icon: editingTag.icon,
            }}
            onSubmit={handleSave}
            onCancel={() => setEditingId(null)}
            submitLabel="Save"
            onDelete={handleDelete}
          />
          {deleteError && (
            <p className="mt-2 text-xs text-status-error">
              {deleteError}
            </p>
          )}
        </div>
      )}
      <div className="space-y-2">
        {loading && (
          <p className="text-sm text-body">Loading tags…</p>
        )}
        {fetchError && (
          <p className="text-sm text-status-error">{fetchError}</p>
        )}
        {!loading && !fetchError && tags.length === 0 && (
          <p className="text-sm text-muted">
            No tags yet. Create one above.
          </p>
        )}
        <ul className="flex flex-wrap justify-center gap-2">
          {tags.map((tag) => (
            <TagPill
              key={tag.id}
              tag={tag}
              editing={tag.id === editingId}
              onClick={() => selectForEdit(tag.id)}
              onTogglePin={() => {
                void handleTogglePin(tag);
              }}
            />
          ))}
        </ul>
        {pinError && (
          <p className="text-xs text-status-error">{pinError}</p>
        )}
      </div>
    </div>
  );
}

function DomainTab({
  apiPath,
  label,
}: {
  apiPath: string;
  label: string;
}) {
  const { domains, loading, fetchError, addDomain, removeDomain } =
    useDomainList(apiPath, label);
  const inputId = useId(); // both DomainTab instances render at once - IDs must be unique
  const [input, setInput] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | undefined>();
  const [removeError, setRemoveError] = useState<
    string | undefined
  >();

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setAdding(true);
    setAddError(undefined);
    try {
      await addDomain(trimmed);
      setInput('');
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : 'Add failed');
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (domain: string) => {
    setRemoveError(undefined);
    try {
      await removeDomain(domain);
    } catch (err: unknown) {
      setRemoveError(
        err instanceof Error ? err.message : 'Remove failed',
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-line bg-surface p-4">
        <h3 className="mb-3 text-sm font-semibold text-ink">
          Add domain
        </h3>
        <form
          onSubmit={handleAdd}
          className="flex flex-wrap items-end gap-3"
        >
          <div className="flex flex-col gap-1">
            <label
              htmlFor={inputId}
              className="text-xs font-medium text-body"
            >
              Domain or URL
            </label>
            <input
              id={inputId}
              type="text"
              required
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="example.com"
              className="w-full sm:w-72 rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={adding}
            className="h-8 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
          >
            {adding ? 'Adding…' : 'Add'}
          </button>
          {addError && (
            <p className="w-full text-xs text-status-error">
              {addError}
            </p>
          )}
        </form>
      </div>

      {loading && (
        <p className="px-4 text-sm text-body">
          Loading {label.toLowerCase()}…
        </p>
      )}
      {fetchError && (
        <p className="px-4 text-sm text-status-error">{fetchError}</p>
      )}
      {removeError && (
        <p className="px-4 text-sm text-status-error">
          {removeError}
        </p>
      )}
      {!loading && !fetchError && domains.length === 0 && (
        <p className="px-4 text-sm text-muted">
          No {label.toLowerCase()} yet. Add one above.
        </p>
      )}
      {domains.length > 0 && (
        <ul className="space-y-2">
          {domains.map((domain) => (
            <li
              key={domain}
              className="flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3"
            >
              <span className="min-w-0 flex-1 font-mono text-sm text-ink">
                {domain}
              </span>
              <button
                onClick={() => handleRemove(domain)}
                className="rounded px-2 py-1 text-xs font-medium text-status-error transition-ui hover:bg-raised"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RecoveryTab() {
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/controls/recovery-settings', {
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok)
          throw new Error('Failed to load recovery settings');
        return res.json() as Promise<{
          telegram_notifications: boolean;
        }>;
      })
      .then((data) => {
        if (!controller.signal.aborted)
          setEnabled(data.telegram_notifications);
      })
      .catch((err) => {
        if (
          controller.signal.aborted ||
          (err instanceof Error && err.name === 'AbortError')
        )
          return;
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to load recovery settings',
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const toggle = async (checked: boolean) => {
    const previous = enabled;
    setEnabled(checked);
    setSaving(true);
    setError(undefined);
    try {
      const result = await apiPut<{
        telegram_notifications: boolean;
      }>(
        '/api/controls/recovery-settings',
        { telegram_notifications: checked },
        'Failed to save recovery settings',
      );
      setEnabled(result.telegram_notifications);
    } catch (err) {
      setEnabled(previous);
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to save recovery settings',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <label className="flex items-center gap-3 text-sm text-ink">
        <input
          type="checkbox"
          checked={enabled}
          disabled={loading || saving}
          onChange={(e) => void toggle(e.target.checked)}
          className="h-4 w-4 accent-signal"
        />
        <span className="font-medium">
          Feed recovery Telegram notifications
        </span>
      </label>
      <p className="ml-7 mt-1.5 text-xs text-muted">
        Send a Telegram message when a stuck job is recovered from the
        Feed.
      </p>
      {error && (
        <p className="ml-7 mt-2 text-sm text-status-error">{error}</p>
      )}
    </>
  );
}

function DeleteAccountSection() {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const handleDelete = async () => {
    setDeleting(true);
    setError(undefined);
    try {
      const res = await fetch('/api/auth/me', { method: 'DELETE' });
      if (!res.ok) throw new Error('Could not delete account');
      router.replace('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete account');
      setDeleting(false);
    }
  };

  return (
    <div className="flex items-stretch gap-4 max-[620px]:flex-col">
      <div className="flex-shrink-0">
        <ConfirmDialog
          title="Permanently delete your account?"
          description="This deletes every job, Brain link, tag, and domain rule you own, disconnects Google, and revokes your session. This can't be undone."
          confirmLabel="Delete my account"
          pending={deleting}
          onConfirm={handleDelete}
          trigger={
            <button className="h-8 rounded-md border border-line px-3 text-button font-medium text-status-error transition-ui hover:bg-raised">
              Delete my account
            </button>
          }
        />
        {error && (
          <p className="mt-2 text-xs text-status-error">{error}</p>
        )}
      </div>
      <div className="border-l border-line max-[620px]:hidden" />
      <p className="text-sm text-body">
        Deletes every job, Brain link, tag, and domain rule tied to your
        account, disconnects Google, and revokes your session. This
        cannot be undone.
      </p>
    </div>
  );
}

function Section({
  title,
  defaultOpen,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const reducedMotion = useReducedMotion();

  return (
    <details
      ref={ref}
      open={defaultOpen}
      onToggle={() => {
        ref.current?.scrollIntoView?.({
          behavior: reducedMotion ? 'auto' : 'smooth',
          block: 'nearest',
        });
      }}
      className="group overflow-hidden rounded-lg border border-line bg-surface"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-semibold text-ink transition-ui hover:bg-raised [&::-webkit-details-marker]:hidden">
        {title}
        <OwnixChevronDown className="h-4 w-4 text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-line bg-canvas p-4">
        {children}
      </div>
    </details>
  );
}

export default function ControlsPage() {
  const { restricted } = useRestrictedMode();
  if (restricted)
    return (
      <RestrictedFacade
        icon={SlidersHorizontal}
        title="Settings"
      >
        Settings control domains, tags, and workspace behavior for
        your own Index. Changes are locked in this read-only preview.
      </RestrictedFacade>
    );

  return (
    <PageShell>
      <PageHeader
        icon={SlidersHorizontal}
        title="Settings"
        description="Manage the tags, domain rules, and recovery behavior that shape your Index."
      />
      <div className="space-y-3">
        <Section
          title="Tags"
          defaultOpen
        >
          <TagsTab />
        </Section>
        <Section
          title="Domains"
          defaultOpen
        >
          <p className="mb-4 text-sm text-body">
            Control which link domains Ownix processes automatically.
            Adding a domain to Allowed lets Ownix process links from
            it; adding it to Ignored skips those links - steer around
            noisy sources without touching individual saves.
          </p>
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
                Allowed
              </h4>
              <DomainTab
                apiPath="/api/controls/allowed-domains"
                label="Allowed Domains"
              />
            </div>
            <div className="md:border-l md:border-line md:pl-6">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
                Ignored
              </h4>
              <DomainTab
                apiPath="/api/controls/ignored-domains"
                label="Ignored Domains"
              />
            </div>
          </div>
        </Section>
        <div className="rounded-lg border border-line bg-surface px-4 py-3">
          <RecoveryTab />
        </div>
        <Section title="Chrome Extension">
          <ExtensionTokensPanel />
        </Section>
        <Section title="Danger zone">
          <DeleteAccountSection />
        </Section>
      </div>
    </PageShell>
  );
}
