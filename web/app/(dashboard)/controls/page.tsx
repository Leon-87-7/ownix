'use client';

import { useEffect, useId, useState } from 'react';
import { useTagList } from '@/lib/hooks/useTagList';
import { useDomainList } from '@/lib/hooks/useDomainList';
import { apiPut } from '@/lib/fetch-utils';
import type { Tag, TagFormState } from '@/lib/hooks/useTagList';
import {
  SlidersHorizontal,
  ChevronDown,
  TagPlus,
  PenLine,
  TagX,
} from 'lucide-react';
import { PRESET_COLORS } from '@/components/TagPicker';
import { PageShell, PageHeader } from '@/components/page-shell';

const DEFAULT_COLOR = '#6366f1';

function ColorSwatch({ color }: { color: string }) {
  return (
    <span
      className="inline-block h-4 w-4 flex-shrink-0 rounded"
      style={{ backgroundColor: color }}
    />
  );
}

function TagForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial: TagFormState;
  onSubmit: (values: TagFormState) => Promise<void>;
  onCancel?: () => void;
  submitLabel: string;
}) {
  const [values, setValues] = useState<TagFormState>(initial);
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | undefined>();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setLocalError(undefined);
    try {
      await onSubmit(values);
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    'w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none';

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3"
    >
      {localError && (
        <p className="text-xs text-status-error">{localError}</p>
      )}
      {/* ponytail: 2 cols on desktop, stacked on mobile. Left = Name+Meaning
          grouped tight; right = Color with the buttons sharing the swatch row. */}
      <div className="grid gap-4 sm:grid-cols-2 sm:gap-8">
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-xs font-medium text-body">
              Name
            </span>
            <input
              type="text"
              required
              maxLength={80}
              value={values.name}
              onChange={(e) =>
                setValues((v) => ({ ...v, name: e.target.value }))
              }
              placeholder="Tag name"
              className={`${inputCls} min-w-0 flex-1`}
            />
          </label>
          <label className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-xs font-medium text-body">
              Meaning
            </span>
            <input
              type="text"
              maxLength={500}
              value={values.meaning}
              onChange={(e) =>
                setValues((v) => ({ ...v, meaning: e.target.value }))
              }
              placeholder="What this tag means…"
              className={`${inputCls} min-w-0 flex-1`}
            />
          </label>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-body">
            Color
          </label>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="grid w-fit grid-cols-6 gap-2 sm:grid-cols-9">
              {PRESET_COLORS.map((c) => {
                const selected = c === values.color;
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() =>
                      setValues((v) => ({ ...v, color: c }))
                    }
                    aria-label={`Color ${c}`}
                    aria-pressed={selected}
                    className={`h-6 w-6 rounded-full transition-ui ${selected ? 'ring-2 ring-signal ring-offset-2 ring-offset-surface' : 'hover:scale-110'}`}
                    style={{ backgroundColor: c }}
                  />
                );
              })}
            </div>
            <div className="flex gap-2">
              {onCancel && (
                <button
                  type="button"
                  onClick={onCancel}
                  className="h-8 rounded-md px-3.5 text-[13px] font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
                >
                  Cancel
                </button>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
              >
                {submitting ? 'Saving…' : submitLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </form>
  );
}

function TagRow({
  tag,
  onDelete,
  onUpdate,
}: {
  tag: Tag;
  onDelete: (id: string) => Promise<void>;
  onUpdate: (id: string, values: TagFormState) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [deleteError, setDeleteError] = useState<
    string | undefined
  >();

  const handleDelete = async () => {
    if (!confirm(`Delete tag "${tag.name}"?`)) return;
    setDeleteError(undefined);
    try {
      await onDelete(tag.id);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : 'Delete failed',
      );
    }
  };

  const handleUpdate = async (values: TagFormState) => {
    await onUpdate(tag.id, values);
    setEditing(false);
  };

  if (editing) {
    return (
      <li className="rounded-lg border border-line bg-surface px-4 py-3">
        <TagForm
          initial={{
            name: tag.name,
            meaning: tag.meaning,
            color: tag.color,
          }}
          onSubmit={handleUpdate}
          onCancel={() => setEditing(false)}
          submitLabel="Save"
        />
      </li>
    );
  }

  return (
    <li className="flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3">
      <ColorSwatch color={tag.color} />
      <span className="min-w-0 flex-1">
        <span className="font-medium text-ink">{tag.name}</span>
        {tag.meaning && (
          <span className="ml-2 truncate text-sm text-body">
            {tag.meaning}
          </span>
        )}
      </span>
      <div className="flex shrink-0 items-center gap-2">
        <button
          onClick={() => setEditing(true)}
          aria-label={`Edit ${tag.name}`}
          className="rounded p-1.5 text-muted transition-ui hover:bg-raised hover:text-ink"
        >
          <PenLine
            className="h-4 w-4"
            aria-hidden="true"
          />
        </button>
        <button
          onClick={handleDelete}
          aria-label={`Delete ${tag.name}`}
          className="rounded p-1.5 text-status-error transition-ui hover:bg-raised"
        >
          <TagX
            className="h-4 w-4"
            aria-hidden="true"
          />
        </button>
      </div>
      {deleteError && (
        <p className="w-full text-xs text-status-error">
          {deleteError}
        </p>
      )}
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
  } = useTagList();

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
        {tags.map((tag) => (
          <TagRow
            key={tag.id}
            tag={tag}
            onDelete={deleteTag}
            onUpdate={updateTag}
          />
        ))}
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
  const inputId = useId(); // both DomainTab instances render at once — IDs must be unique
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
            className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
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
          Dashboard recovery Telegram notifications
        </span>
      </label>
      <p className="ml-7 mt-1.5 text-xs text-muted">
        Send a Telegram message when a stuck job is recovered from the
        dashboard.
      </p>
      {error && (
        <p className="ml-7 mt-2 text-sm text-status-error">{error}</p>
      )}
    </>
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
  return (
    <details
      open={defaultOpen}
      className="group overflow-hidden rounded-lg border border-line bg-surface"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-semibold text-ink transition-ui hover:bg-raised [&::-webkit-details-marker]:hidden">
        {title}
        <ChevronDown className="h-4 w-4 text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-line bg-canvas p-4">
        {children}
      </div>
    </details>
  );
}

export default function ControlsPage() {
  return (
    <PageShell>
      <PageHeader icon={SlidersHorizontal} title="Controls" />
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
      </div>
    </PageShell>
  );
}
