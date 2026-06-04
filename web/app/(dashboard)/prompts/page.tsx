'use client';

import { useEffect, useState } from 'react';

interface Template {
  id: string;
  name: string;
  description: string;
  extra_instructions: string;
  trigger_patterns?: string;
  brave_search?: boolean | number;
  content_type_scope?: string;
  is_builtin: boolean;
  created_at?: string;
  updated_at?: string;
}

interface TemplateFormState {
  name: string;
  description: string;
  extra_instructions: string;
}

// ---------------------------------------------------------------------------
// Create form (user templates only)
// ---------------------------------------------------------------------------

function CreateForm({
  onCreated,
}: {
  onCreated: (t: Template) => void;
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
      const res = await fetch('/api/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = (data as { detail?: string }).detail ?? 'Create failed';
        setError(detail);
        return;
      }
      const created: Template = await res.json();
      onCreated(created);
      setValues({ name: '', description: '', extra_instructions: '' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">
            Name <span className="text-gray-500">(no spaces, no leading - or /)</span>
          </label>
          <input
            type="text"
            required
            maxLength={64}
            pattern="[a-z0-9_-]+"
            title="Lowercase letters, digits, hyphens, underscores only"
            value={values.name}
            onChange={(e) =>
              setValues((v) => ({ ...v, name: e.target.value.toLowerCase() }))
            }
            placeholder="e.g. startup-notes"
            className="w-52 rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">Description (optional)</label>
          <input
            type="text"
            maxLength={500}
            value={values.description}
            onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
            placeholder="Short description..."
            className="w-72 rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">
          Extra instructions (optional — sent as Gemini prompt)
        </label>
        <textarea
          maxLength={4000}
          rows={4}
          value={values.extra_instructions}
          onChange={(e) =>
            setValues((v) => ({ ...v, extra_instructions: e.target.value }))
          }
          placeholder="Write custom Gemini analysis instructions here..."
          className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
      >
        {submitting ? 'Creating…' : 'Create template'}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// User template row (editable)
// ---------------------------------------------------------------------------

function UserTemplateRow({
  template,
  onUpdated,
  onDeleted,
}: {
  template: Template;
  onUpdated: (t: Template) => void;
  onDeleted: (name: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValues, setEditValues] = useState({
    description: template.description,
    extra_instructions: template.extra_instructions,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | undefined>();
  const [deleteError, setDeleteError] = useState<string | undefined>();

  const handleDelete = async () => {
    if (!confirm(`Delete template "-${template.name}"?`)) return;
    setDeleteError(undefined);
    const res = await fetch(`/api/templates/${template.name}`, { method: 'DELETE' });
    if (res.ok || res.status === 204) {
      onDeleted(template.name);
    } else {
      const data = await res.json().catch(() => ({}));
      setDeleteError((data as { detail?: string }).detail ?? 'Delete failed');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(undefined);
    setSaving(true);
    try {
      const res = await fetch(`/api/templates/${template.name}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editValues),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setSaveError((data as { detail?: string }).detail ?? 'Save failed');
        return;
      }
      const updated: Template = await res.json();
      onUpdated({ ...template, ...updated });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <li className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 space-y-3">
        <form onSubmit={handleSave} className="space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Description</label>
            <input
              type="text"
              maxLength={500}
              value={editValues.description}
              onChange={(e) =>
                setEditValues((v) => ({ ...v, description: e.target.value }))
              }
              className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Extra instructions</label>
            <textarea
              maxLength={4000}
              rows={4}
              value={editValues.extra_instructions}
              onChange={(e) =>
                setEditValues((v) => ({ ...v, extra_instructions: e.target.value }))
              }
              className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
            />
          </div>
          {saveError && <p className="text-xs text-red-400">{saveError}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
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
              className="rounded-md px-3 py-1.5 text-sm text-gray-400 hover:text-white"
            >
              Cancel
            </button>
          </div>
        </form>
      </li>
    );
  }

  return (
    <li className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <span className="font-mono text-sm font-semibold text-indigo-400">
            -{template.name}
          </span>
          {template.description && (
            <span className="ml-2 text-sm text-gray-400">{template.description}</span>
          )}
          {template.extra_instructions && (
            <p className="mt-1 truncate text-xs text-gray-500">
              {template.extra_instructions.slice(0, 120)}
              {template.extra_instructions.length > 120 ? '…' : ''}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => setEditing(true)}
            className="rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-700 hover:text-white"
          >
            Edit
          </button>
          <button
            onClick={handleDelete}
            className="rounded px-2 py-1 text-xs text-red-400 hover:bg-gray-700 hover:text-red-300"
          >
            Delete
          </button>
        </div>
      </div>
      {deleteError && <p className="mt-1 text-xs text-red-400">{deleteError}</p>}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PromptsPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | undefined>();

  useEffect(() => {
    fetch('/api/templates')
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load templates');
        return res.json() as Promise<Template[]>;
      })
      .then(setTemplates)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        setFetchError(msg);
      })
      .finally(() => setLoading(false));
  }, []);

  const builtins = templates.filter((t) => t.is_builtin);
  const userTemplates = templates.filter((t) => !t.is_builtin);

  const handleCreated = (t: Template) => {
    setTemplates((prev) => [
      ...prev.filter((x) => x.is_builtin),
      ...([...prev.filter((x) => !x.is_builtin), t].sort((a, b) =>
        a.name.localeCompare(b.name),
      )),
    ]);
  };

  const handleUpdated = (updated: Template) => {
    setTemplates((prev) =>
      prev.map((t) => (t.name === updated.name ? { ...t, ...updated } : t)),
    );
  };

  const handleDeleted = (name: string) => {
    setTemplates((prev) => prev.filter((t) => t.name !== name));
  };

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Prompts</h2>

      {loading && <p className="text-sm text-gray-400">Loading templates…</p>}
      {fetchError && <p className="text-sm text-red-400">{fetchError}</p>}

      {!loading && !fetchError && (
        <>
          {/* Built-ins section */}
          <section className="mb-8">
            <h3 className="mb-3 text-sm font-semibold text-gray-300">
              Built-in templates{' '}
              <span className="font-normal text-gray-500">(read-only, use as /name)</span>
            </h3>
            {builtins.length === 0 ? (
              <p className="text-sm text-gray-500">No built-in templates.</p>
            ) : (
              <ul className="space-y-2">
                {builtins.map((t) => (
                  <li
                    key={t.name}
                    className="flex items-start gap-3 rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <span className="font-mono text-sm font-semibold text-gray-200">
                        /{t.name}
                      </span>
                      {t.description && (
                        <span className="ml-2 text-sm text-gray-400">{t.description}</span>
                      )}
                    </div>
                    <span className="shrink-0 rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-400">
                      built-in
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* User templates section */}
          <section>
            <h3 className="mb-3 text-sm font-semibold text-gray-300">
              Your templates{' '}
              <span className="font-normal text-gray-500">(use as -name &lt;url&gt; in Telegram)</span>
            </h3>

            {/* Create form */}
            <div className="mb-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4">
              <h4 className="mb-3 text-sm font-medium text-gray-200">Create template</h4>
              <CreateForm onCreated={handleCreated} />
            </div>

            {userTemplates.length === 0 ? (
              <p className="text-sm text-gray-500">
                No custom templates yet. Create one above.
              </p>
            ) : (
              <ul className="space-y-2">
                {userTemplates.map((t) => (
                  <UserTemplateRow
                    key={t.name}
                    template={t}
                    onUpdated={handleUpdated}
                    onDeleted={handleDeleted}
                  />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
