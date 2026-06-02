"use client";

import { useCallback, useEffect, useState } from "react";
import { SpaceCard, type SpaceSummary } from "@/components/SpaceCard";

export default function SpacesPage() {
  const [spaces, setSpaces] = useState<SpaceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New-space form state
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState("#6366f1");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchSpaces = useCallback(async () => {
    try {
      const res = await fetch("/api/spaces");
      if (!res.ok) throw new Error("Failed to load spaces");
      const data: SpaceSummary[] = await res.json();
      setSpaces(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSpaces();
  }, [fetchSpaces]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch("/api/spaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), color: newColor }),
      });
      if (res.status === 409) {
        setFormError("A space with that name already exists.");
        return;
      }
      if (!res.ok) throw new Error("Failed to create space");
      setNewName("");
      setNewColor("#6366f1");
      setShowForm(false);
      await fetchSpaces();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
        Loading…
      </div>
    );
  }

  if (error) {
    return (
      <p className="rounded-md bg-red-900/40 px-4 py-3 text-sm text-red-300">
        {error}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Spaces</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          {showForm ? "Cancel" : "New Space"}
        </button>
      </div>

      {/* New Space inline form */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-4"
        >
          <h2 className="text-sm font-semibold text-gray-300">Create Space</h2>

          {formError && (
            <p className="text-sm text-red-400">{formError}</p>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-gray-400" htmlFor="space-name">
                Name
              </label>
              <input
                id="space-name"
                type="text"
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="My space…"
                className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-gray-400" htmlFor="space-color">
                Color
              </label>
              <input
                id="space-color"
                type="color"
                value={newColor}
                onChange={(e) => setNewColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded border border-gray-700 bg-gray-900 p-0.5"
              />
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={submitting}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
              >
                {submitting ? "Creating…" : "Create"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setFormError(null);
                  setNewName("");
                  setNewColor("#6366f1");
                }}
                className="rounded-md border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Empty state */}
      {spaces.length === 0 && !showForm && (
        <p className="text-sm text-gray-500">
          No spaces yet. Create one to start organizing your jobs.
        </p>
      )}

      {/* Grid */}
      {spaces.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {spaces.map((space) => (
            <SpaceCard key={space.id} space={space} />
          ))}
        </div>
      )}
    </div>
  );
}
