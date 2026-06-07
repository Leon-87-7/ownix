"use client";

import { SpaceCard } from "@/components/SpaceCard";
import { useSpaceList } from "@/lib/hooks/useSpaceList";
import { useCreateSpace } from "@/lib/hooks/useCreateSpace";

export default function SpacesPage() {
  const { spaces, loading, error, reload } = useSpaceList();
  const { showForm, openForm, newName, setNewName, newColor, setNewColor, submitting, formError, handleCreate, resetForm } = useCreateSpace(reload);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
        Loading…
      </div>
    );
  }

  if (error) {
    return <p className="rounded-md bg-red-900/40 px-4 py-3 text-sm text-red-300">{error}</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Spaces</h1>
        <button
          onClick={showForm ? resetForm : openForm}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          {showForm ? "Cancel" : "New Space"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300">Create Space</h2>
          {formError && <p className="text-sm text-red-400">{formError}</p>}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-gray-400" htmlFor="space-name">Name</label>
              <input id="space-name" type="text" required value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="My space…" className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400" htmlFor="space-color">Color</label>
              <input id="space-color" type="color" value={newColor} onChange={(e) => setNewColor(e.target.value)} className="h-9 w-12 cursor-pointer rounded border border-gray-700 bg-gray-900 p-0.5" />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={submitting} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                {submitting ? "Creating…" : "Create"}
              </button>
              <button type="button" onClick={resetForm} className="rounded-md border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {spaces.length === 0 && !showForm && (
        <p className="text-sm text-gray-500">No spaces yet. Create one to start organizing your jobs.</p>
      )}

      {spaces.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {spaces.map((space) => <SpaceCard key={space.id} space={space} />)}
        </div>
      )}
    </div>
  );
}
