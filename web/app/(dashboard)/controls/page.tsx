'use client';

import { useState } from 'react';
import { useTagList } from '@/lib/hooks/useTagList';
import { useDomainList } from '@/lib/hooks/useDomainList';
import type { Tag, TagFormState } from '@/lib/hooks/useTagList';

const DEFAULT_COLOR = '#6366f1';

function ColorSwatch({ color }: { color: string }) {
  return <span className="inline-block h-4 w-4 flex-shrink-0 rounded" style={{ backgroundColor: color }} />;
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

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Name</label>
        <input type="text" required maxLength={80} value={values.name} onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))} placeholder="Tag name" className="w-44 rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Meaning</label>
        <input type="text" maxLength={500} value={values.meaning} onChange={(e) => setValues((v) => ({ ...v, meaning: e.target.value }))} placeholder="What this tag means..." className="w-72 rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Color</label>
        <input type="color" value={values.color} onChange={(e) => setValues((v) => ({ ...v, color: e.target.value }))} className="h-9 w-14 cursor-pointer rounded-md border border-gray-700 bg-gray-800 p-1" />
      </div>
      <div className="flex items-center gap-2">
        <button type="submit" disabled={submitting} className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
          {submitting ? 'Saving…' : submitLabel}
        </button>
        {onCancel && <button type="button" onClick={onCancel} className="rounded-md px-4 py-1.5 text-sm text-gray-400 hover:text-white">Cancel</button>}
      </div>
      {localError && <p className="w-full text-xs text-red-400">{localError}</p>}
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
  const [deleteError, setDeleteError] = useState<string | undefined>();

  const handleDelete = async () => {
    if (!confirm(`Delete tag "${tag.name}"?`)) return;
    setDeleteError(undefined);
    try {
      await onDelete(tag.id);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const handleUpdate = async (values: TagFormState) => {
    await onUpdate(tag.id, values);
    setEditing(false);
  };

  if (editing) {
    return (
      <li className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
        <TagForm initial={{ name: tag.name, meaning: tag.meaning, color: tag.color }} onSubmit={handleUpdate} onCancel={() => setEditing(false)} submitLabel="Save" />
      </li>
    );
  }

  return (
    <li className="flex items-center gap-3 rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
      <ColorSwatch color={tag.color} />
      <span className="min-w-0 flex-1">
        <span className="font-medium text-white">{tag.name}</span>
        {tag.meaning && <span className="ml-2 truncate text-sm text-gray-400">{tag.meaning}</span>}
      </span>
      <div className="flex shrink-0 items-center gap-2">
        <button onClick={() => setEditing(true)} className="rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-700 hover:text-white">Edit</button>
        <button onClick={handleDelete} className="rounded px-2 py-1 text-xs text-red-400 hover:bg-gray-700 hover:text-red-300">Delete</button>
      </div>
      {deleteError && <p className="w-full text-xs text-red-400">{deleteError}</p>}
    </li>
  );
}

function TagsTab() {
  const { tags, loading, fetchError, createTag, deleteTag, updateTag } = useTagList();

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-200">Create tag</h3>
        <TagForm initial={{ name: '', meaning: '', color: DEFAULT_COLOR }} onSubmit={createTag} submitLabel="Create" />
      </div>
      {loading && <p className="text-sm text-gray-400">Loading tags…</p>}
      {fetchError && <p className="text-sm text-red-400">{fetchError}</p>}
      {!loading && !fetchError && tags.length === 0 && <p className="text-sm text-gray-500">No tags yet. Create one above.</p>}
      {tags.length > 0 && (
        <ul className="space-y-2">
          {tags.map((tag) => <TagRow key={tag.id} tag={tag} onDelete={deleteTag} onUpdate={updateTag} />)}
        </ul>
      )}
    </div>
  );
}

function DomainTab({ apiPath, label }: { apiPath: string; label: string }) {
  const { domains, loading, fetchError, addDomain, removeDomain } = useDomainList(apiPath, label);
  const [input, setInput] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | undefined>();
  const [removeError, setRemoveError] = useState<string | undefined>();

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
      setRemoveError(err instanceof Error ? err.message : 'Remove failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-200">Add domain</h3>
        <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="domain-input" className="text-xs text-gray-400">Domain or URL</label>
            <input id="domain-input" type="text" required value={input} onChange={(e) => setInput(e.target.value)} placeholder="example.com" className="w-72 rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
          </div>
          <button type="submit" disabled={adding} className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {adding ? 'Adding…' : 'Add'}
          </button>
          {addError && <p className="w-full text-xs text-red-400">{addError}</p>}
        </form>
      </div>

      {loading && <p className="text-sm text-gray-400">Loading {label.toLowerCase()}…</p>}
      {fetchError && <p className="text-sm text-red-400">{fetchError}</p>}
      {removeError && <p className="text-sm text-red-400">{removeError}</p>}
      {!loading && !fetchError && domains.length === 0 && <p className="text-sm text-gray-500">No {label.toLowerCase()} yet. Add one above.</p>}
      {domains.length > 0 && (
        <ul className="space-y-2">
          {domains.map((domain) => (
            <li key={domain} className="flex items-center gap-3 rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
              <span className="min-w-0 flex-1 font-mono text-sm text-white">{domain}</span>
              <button onClick={() => handleRemove(domain)} className="rounded px-2 py-1 text-xs text-red-400 hover:bg-gray-700 hover:text-red-300">Remove</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const TABS = ['Tags', 'Allowed Domains', 'Ignored Domains'] as const;
type Tab = (typeof TABS)[number];

export default function ControlsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('Tags');

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Controls</h2>
      <div className="mb-6 flex gap-1 border-b border-gray-700">
        {TABS.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`px-4 py-2 text-sm font-medium transition-colors ${activeTab === tab ? 'border-b-2 border-indigo-500 text-white' : 'text-gray-400 hover:text-gray-200'}`}>
            {tab}
          </button>
        ))}
      </div>
      {activeTab === 'Tags' && <TagsTab />}
      {activeTab === 'Allowed Domains' && <DomainTab apiPath="/api/controls/allowed-domains" label="Allowed Domains" />}
      {activeTab === 'Ignored Domains' && <DomainTab apiPath="/api/controls/ignored-domains" label="Ignored Domains" />}
    </div>
  );
}
