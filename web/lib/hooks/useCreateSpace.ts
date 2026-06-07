'use client';

import { useCallback, useState } from 'react';

const DEFAULT_COLOR = '#6366f1';

export function useCreateSpace(onCreated: () => Promise<void>) {
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(DEFAULT_COLOR);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch('/api/spaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim(), color: newColor }),
      });
      if (res.status === 409) { setFormError('A space with that name already exists.'); return; }
      if (!res.ok) throw new Error('Failed to create space');
      setNewName('');
      setNewColor(DEFAULT_COLOR);
      setShowForm(false);
      await onCreated();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setSubmitting(false);
    }
  }, [newName, newColor, onCreated]);

  const openForm = useCallback(() => setShowForm(true), []);

  const resetForm = useCallback(() => {
    setShowForm(false);
    setFormError(null);
    setNewName('');
    setNewColor(DEFAULT_COLOR);
  }, []);

  return { showForm, openForm, newName, setNewName, newColor, setNewColor, submitting, formError, handleCreate, resetForm };
}
