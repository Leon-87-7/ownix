'use client';

import { useCallback } from 'react';
import { useFetchList, apiPost } from '@/lib/fetch-utils';

export interface Template {
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

export interface TemplateFormState {
  name: string;
  description: string;
  extra_instructions: string;
}

export function useTemplateList() {
  const { data: templates, setData: setTemplates, loading, fetchError } = useFetchList<Template>('/api/templates', 'templates');

  const createTemplate = useCallback(async (values: TemplateFormState): Promise<void> => {
    const result = await apiPost<Template>('/api/templates', values);
    if (!result.ok) throw new Error(result.detail);
    const created = result.data;
    setTemplates((prev) => [
      ...prev.filter((x) => x.is_builtin),
      ...[...prev.filter((x) => !x.is_builtin), created].sort((a, b) => a.name.localeCompare(b.name)),
    ]);
  }, [setTemplates]);

  const deleteTemplate = useCallback(async (name: string): Promise<void> => {
    const res = await fetch(`/api/templates/${name}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { detail?: string }).detail ?? 'Delete failed');
    }
    setTemplates((prev) => prev.filter((t) => t.name !== name));
  }, [setTemplates]);

  const updateTemplate = useCallback(async (name: string, values: Partial<TemplateFormState>): Promise<void> => {
    const res = await fetch(`/api/templates/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { detail?: string }).detail ?? 'Save failed');
    }
    const updated: Template = await res.json();
    setTemplates((prev) => prev.map((t) => (t.name === name ? { ...t, ...updated } : t)));
  }, [setTemplates]);

  return { templates, loading, fetchError, createTemplate, deleteTemplate, updateTemplate };
}
