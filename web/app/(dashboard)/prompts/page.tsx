'use client';

import { useRestrictedMode } from '@/lib/restricted/context';
import { RestrictedFacade } from '@/components/shell/restricted-facade';

import { useState } from 'react';
import { MessageSquareText } from 'lucide-react';
import { useTemplateList } from '@/lib/hooks/useTemplateList';
import { PageShell, PageHeader } from '@/components/shell/page-shell';
import { Tooltip } from '@/components/ui/tooltip';
import type {
  Template,
  TemplateFormState,
} from '@/lib/hooks/useTemplateList';

function CreateForm({
  onCreated,
}: {
  onCreated: (values: TemplateFormState) => Promise<void>;
}) {
  const [values, setValues] = useState<TemplateFormState>({
    name: '',
    description: '',
    extra_instructions: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(undefined);
    setSubmitting(true);
    try {
      await onCreated(values);
      setValues({
        name: '',
        description: '',
        extra_instructions: '',
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Create failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3"
    >
      <div className="flex flex-wrap gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-body">
            Name{' '}
            <span className="text-muted">
              (no spaces, no leading - or /)
            </span>
          </label>
          <Tooltip content="Lowercase letters, digits, hyphens, underscores only" mono>
            <input
              type="text"
              required
              maxLength={64}
              pattern="[a-z0-9_-]+"
              title="Lowercase letters, digits, hyphens, underscores only"
              value={values.name}
              onChange={(e) =>
                setValues((v) => ({
                  ...v,
                  name: e.target.value.toLowerCase(),
                }))
              }
              placeholder="e.g. startup-notes"
              className="w-full sm:w-52 rounded-md border border-line bg-canvas px-3 py-1.5 font-mono text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            />
          </Tooltip>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-body">
            Description (optional)
          </label>
          <input
            type="text"
            maxLength={500}
            value={values.description}
            onChange={(e) =>
              setValues((v) => ({
                ...v,
                description: e.target.value,
              }))
            }
            placeholder="Short description..."
            className="w-full sm:w-72 rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
          />
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-body">
          Extra instructions (optional — sent as Gemini prompt)
        </label>
        <textarea
          maxLength={4000}
          rows={4}
          value={values.extra_instructions}
          onChange={(e) =>
            setValues((v) => ({
              ...v,
              extra_instructions: e.target.value,
            }))
          }
          placeholder="Write custom Gemini analysis instructions here..."
          className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
        />
      </div>
      {error && <p className="text-xs text-status-error">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
      >
        {submitting ? 'Creating…' : 'Create template'}
      </button>
    </form>
  );
}

function UserTemplateRow({
  template,
  onUpdate,
  onDelete,
}: {
  template: Template;
  onUpdate: (
    name: string,
    values: Partial<TemplateFormState>,
  ) => Promise<void>;
  onDelete: (name: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [editValues, setEditValues] = useState({
    description: template.description,
    extra_instructions: template.extra_instructions,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | undefined>();
  const [deleteError, setDeleteError] = useState<
    string | undefined
  >();

  const handleDelete = async () => {
    if (!confirm(`Delete template "-${template.name}"?`)) return;
    setDeleteError(undefined);
    try {
      await onDelete(template.name);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : 'Delete failed',
      );
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(undefined);
    setSaving(true);
    try {
      await onUpdate(template.name, editValues);
      setEditing(false);
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : 'Save failed',
      );
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <li className="space-y-3 rounded-lg border border-line bg-surface px-4 py-3">
        <form
          onSubmit={handleSave}
          className="space-y-3"
        >
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-body">
              Description
            </label>
            <input
              type="text"
              maxLength={500}
              value={editValues.description}
              onChange={(e) =>
                setEditValues((v) => ({
                  ...v,
                  description: e.target.value,
                }))
              }
              className="w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-body">
              Extra instructions
            </label>
            <textarea
              maxLength={4000}
              rows={4}
              value={editValues.extra_instructions}
              onChange={(e) =>
                setEditValues((v) => ({
                  ...v,
                  extra_instructions: e.target.value,
                }))
              }
              className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            />
          </div>
          {saveError && (
            <p className="text-xs text-status-error">{saveError}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="h-8 rounded-md bg-signal px-3 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => {
                setEditing(false);
                setEditValues({
                  description: template.description,
                  extra_instructions: template.extra_instructions,
                });
              }}
              className="h-8 rounded-md px-3 text-[13px] font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              Cancel
            </button>
          </div>
        </form>
      </li>
    );
  }

  return (
    <li className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <span className="font-mono text-sm font-semibold text-ink">
            -{template.name}
          </span>
          {template.description && (
            <span className="ml-2 text-sm text-body">
              {template.description}
            </span>
          )}
          {template.extra_instructions && (
            <p className="mt-1 truncate text-xs text-muted">
              {template.extra_instructions.slice(0, 120)}
              {template.extra_instructions.length > 120 ? '…' : ''}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => setEditing(true)}
            className="rounded px-2 py-1 text-xs font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
          >
            Edit
          </button>
          <button
            onClick={handleDelete}
            className="rounded px-2 py-1 text-xs font-medium text-status-error transition-ui hover:bg-raised"
          >
            Delete
          </button>
        </div>
      </div>
      {deleteError && (
        <p className="mt-1 text-xs text-status-error">
          {deleteError}
        </p>
      )}
    </li>
  );
}

export default function PromptsPage() {
  const { restricted } = useRestrictedMode();
  if (restricted) return <RestrictedFacade icon={MessageSquareText} title="Recipes">Recipes shape enrichment prompts for your own Index. Creating, editing, and deleting recipes is locked in this read-only preview.</RestrictedFacade>;
  return <PromptsWorkspace />;
}

function PromptsWorkspace() {
  const {
    templates,
    loading,
    fetchError,
    createTemplate,
    deleteTemplate,
    updateTemplate,
  } = useTemplateList();

  const builtins = templates.filter((t) => t.is_builtin);
  const userTemplates = templates.filter((t) => !t.is_builtin);

  return (
    <PageShell>
      <PageHeader
        icon={MessageSquareText}
        title="Recipes"
        description="Named prompt presets that shape how Gemini analyzes what you save — invoke one by name to change what comes back."
      />

      {loading && (
        <p className="text-sm text-body">Loading templates…</p>
      )}
      {fetchError && (
        <p className="text-sm text-status-error">{fetchError}</p>
      )}

      {!loading && !fetchError && (
        <>
          <section className="mb-8">
            <h2 className="mb-3 text-sm font-semibold text-ink">
              Built-in recipes{' '}
              <span className="font-normal text-muted">
                (read-only, use as /name)
              </span>
            </h2>
            {builtins.length === 0 ? (
              <p className="text-sm text-muted">
                No built-in recipes.
              </p>
            ) : (
              <ul className="space-y-2">
                {builtins.map((t) => (
                  <li
                    key={t.name}
                    className="flex items-start gap-3 rounded-lg border border-line bg-surface px-4 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <span className="font-mono text-sm font-semibold text-ink">
                        /{t.name}
                      </span>
                      {t.description && (
                        <span className="ml-2 text-sm text-body">
                          {t.description}
                        </span>
                      )}
                    </div>
                    <span className="shrink-0 rounded border border-line px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-wider text-muted">
                      built-in
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-sm font-semibold text-ink">
              Your recipes{' '}
              <span className="font-normal text-muted">
                (use as -name &lt;url&gt; in Telegram)
              </span>
            </h2>
            <div className="mb-4 rounded-lg border border-line bg-surface p-4">
              <h3 className="mb-3 text-sm font-medium text-ink">
                Create recipe
              </h3>
              <CreateForm onCreated={createTemplate} />
            </div>
            {userTemplates.length === 0 ? (
              <p className="text-sm text-muted">
                No custom recipes yet. Create one above.
              </p>
            ) : (
              <ul className="space-y-2">
                {userTemplates.map((t) => (
                  <UserTemplateRow
                    key={t.name}
                    template={t}
                    onUpdate={updateTemplate}
                    onDelete={deleteTemplate}
                  />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </PageShell>
  );
}
