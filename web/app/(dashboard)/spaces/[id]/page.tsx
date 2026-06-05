"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { JobSummary } from "@/components/job-card";
import MarkdownEditor from "@/components/MarkdownEditor";
import ExportModal from "@/components/ExportModal";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SpaceDetail {
  id: string;
  chat_id: number;
  name: string;
  color: string;
  created_at: string;
  updated_at: string;
}

interface SpaceUrl {
  id: string;
  title: string | null;
  url: string;
  content_type: string;
  status: string;
  sort_order: number;
  added_at: string;
}

interface ContextBlob {
  id: string;
  space_id: string;
  name: string;
  content: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

type FetchState = "loading" | "ok" | "not_found" | "forbidden" | "error";
type ActiveTab = "urls" | "context";

// ---------------------------------------------------------------------------
// Badge (reuse job-card style)
// ---------------------------------------------------------------------------

const CONTENT_TYPE_COLORS: Record<string, string> = {
  short: "bg-purple-900 text-purple-200",
  long: "bg-blue-900 text-blue-200",
  article: "bg-teal-900 text-teal-200",
  repo: "bg-orange-900 text-orange-200",
};

function Badge({ label, colorClass }: { label: string; colorClass: string }) {
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SpaceDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const router = useRouter();
  const spaceId = params.id;

  const [space, setSpace] = useState<SpaceDetail | null>(null);
  const [fetchState, setFetchState] = useState<FetchState>("loading");
  const [activeTab, setActiveTab] = useState<ActiveTab>("urls");

  // Edit form
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editColor, setEditColor] = useState("#6366f1");
  const [editError, setEditError] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);

  // URLs tab
  const [spaceUrls, setSpaceUrls] = useState<SpaceUrl[]>([]);
  const [urlsLoading, setUrlsLoading] = useState(false);

  // Add job
  const [allJobs, setAllJobs] = useState<JobSummary[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [addingJob, setAddingJob] = useState(false);

  // Context tab
  const [blobs, setBlobs] = useState<ContextBlob[]>([]);
  const [blobsLoading, setBlobsLoading] = useState(false);
  const [addingBlob, setAddingBlob] = useState(false);
  const [newBlobName, setNewBlobName] = useState("");
  const [blobError, setBlobError] = useState<string | null>(null);

  // Export modal
  const [showExport, setShowExport] = useState(false);

  // ---------------------------------------------------------------------------
  // Fetch space
  // ---------------------------------------------------------------------------

  const fetchSpace = useCallback(async () => {
    const controller = new AbortController();
    try {
      const res = await fetch(`/api/spaces/${spaceId}`, {
        signal: controller.signal,
      });
      if (res.status === 404) { setFetchState("not_found"); return; }
      if (res.status === 403 || res.status === 401) { setFetchState("forbidden"); return; }
      if (!res.ok) { setFetchState("error"); return; }
      const data: SpaceDetail = await res.json();
      setSpace(data);
      setEditName(data.name);
      setEditColor(data.color);
      setFetchState("ok");
    } catch (err) {
      if ((err as Error).name !== "AbortError") setFetchState("error");
    }
    return () => controller.abort();
  }, [spaceId]);

  // ---------------------------------------------------------------------------
  // Fetch URLs
  // ---------------------------------------------------------------------------

  const fetchUrls = useCallback(async () => {
    setUrlsLoading(true);
    try {
      const res = await fetch(`/api/spaces/${spaceId}/urls`);
      if (!res.ok) return;
      const data: SpaceUrl[] = await res.json();
      setSpaceUrls(data);
    } finally {
      setUrlsLoading(false);
    }
  }, [spaceId]);

  // ---------------------------------------------------------------------------
  // Fetch all jobs (for the add-job selector)
  // ---------------------------------------------------------------------------

  const fetchAllJobs = useCallback(async () => {
    try {
      const res = await fetch("/api/jobs?limit=50");
      if (!res.ok) return;
      const data: { items: JobSummary[] } = await res.json();
      setAllJobs(data.items);
    } catch {
      // ignore
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Fetch context blobs
  // ---------------------------------------------------------------------------

  const fetchBlobs = useCallback(async () => {
    setBlobsLoading(true);
    try {
      const res = await fetch(`/api/spaces/${spaceId}/blobs`);
      if (!res.ok) return;
      const data: ContextBlob[] = await res.json();
      setBlobs(data);
    } finally {
      setBlobsLoading(false);
    }
  }, [spaceId]);

  useEffect(() => {
    fetchSpace();
  }, [fetchSpace]);

  useEffect(() => {
    if (fetchState === "ok") {
      fetchUrls();
      fetchAllJobs();
      fetchBlobs();
    }
  }, [fetchState, fetchUrls, fetchAllJobs, fetchBlobs]);

  // ---------------------------------------------------------------------------
  // Edit save
  // ---------------------------------------------------------------------------

  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editName.trim()) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const res = await fetch(`/api/spaces/${spaceId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editName.trim(), color: editColor }),
      });
      if (res.status === 409) {
        setEditError("A space with that name already exists.");
        return;
      }
      if (!res.ok) throw new Error("Failed to save");
      const updated: SpaceDetail = await res.json();
      setSpace(updated);
      setEditing(false);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setEditSaving(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Delete space
  // ---------------------------------------------------------------------------

  const handleDelete = async () => {
    if (!window.confirm("Delete this space? Jobs will not be deleted.")) return;
    const res = await fetch(`/api/spaces/${spaceId}`, { method: "DELETE" });
    if (res.ok || res.status === 204) {
      router.push("/spaces");
    }
  };

  // ---------------------------------------------------------------------------
  // Remove URL
  // ---------------------------------------------------------------------------

  const handleRemoveUrl = async (jobId: string) => {
    await fetch(`/api/spaces/${spaceId}/urls/${jobId}`, { method: "DELETE" });
    await fetchUrls();
  };

  // ---------------------------------------------------------------------------
  // Reorder (swap adjacent sort_order values)
  // ---------------------------------------------------------------------------

  const handleMove = async (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= spaceUrls.length) return;

    const a = spaceUrls[index];
    const b = spaceUrls[targetIndex];

    // Optimistic swap so rapid clicks use the updated order.
    setSpaceUrls((prev) => {
      const next = [...prev];
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return next;
    });

    await Promise.all([
      fetch(`/api/spaces/${spaceId}/urls/${a.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: b.sort_order }),
      }),
      fetch(`/api/spaces/${spaceId}/urls/${b.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: a.sort_order }),
      }),
    ]);

    await fetchUrls();
  };

  // ---------------------------------------------------------------------------
  // Blob handlers
  // ---------------------------------------------------------------------------

  const handleAddBlob = async () => {
    const name = newBlobName.trim() || "New context";
    setAddingBlob(true);
    try {
      const res = await fetch(`/api/spaces/${spaceId}/blobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) { setBlobError("Failed to add context document. Please try again."); return; }
      setBlobError(null);
      setNewBlobName("");
      await fetchBlobs();
    } finally {
      setAddingBlob(false);
    }
  };

  const handleBlobSave = async (blobId: string, name: string, content: string) => {
    const res = await fetch(`/api/spaces/${spaceId}/blobs/${blobId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, content }),
    });
    if (!res.ok) setBlobError("Failed to save. Please try again.");
    else setBlobError(null);
  };

  const handleDeleteBlob = async (blobId: string) => {
    const res = await fetch(`/api/spaces/${spaceId}/blobs/${blobId}`, { method: "DELETE" });
    if (!res.ok) { setBlobError("Failed to remove context document. Please try again."); return; }
    setBlobError(null);
    await fetchBlobs();
  };

  const handleMoveBlob = async (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= blobs.length) return;
    const a = blobs[index];
    const b = blobs[targetIndex];
    await Promise.all([
      fetch(`/api/spaces/${spaceId}/blobs/${a.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: b.sort_order }),
      }),
      fetch(`/api/spaces/${spaceId}/blobs/${b.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: a.sort_order }),
      }),
    ]);
    await fetchBlobs();
  };

  // ---------------------------------------------------------------------------
  // Add job
  // ---------------------------------------------------------------------------

  const handleAddJob = async () => {
    if (!selectedJobId) return;
    setAddingJob(true);
    try {
      await fetch(`/api/spaces/${spaceId}/urls`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: selectedJobId }),
      });
      setSelectedJobId("");
      await fetchUrls();
    } finally {
      setAddingJob(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (fetchState === "loading") {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
        Loading…
      </div>
    );
  }

  if (fetchState === "not_found") {
    return (
      <div className="text-sm text-gray-400">
        Space not found.{" "}
        <Link href="/spaces" className="text-blue-400 hover:underline">
          Back to spaces
        </Link>
      </div>
    );
  }

  if (fetchState === "forbidden") {
    return (
      <div className="text-sm text-gray-400">
        Access denied.{" "}
        <Link href="/spaces" className="text-blue-400 hover:underline">
          Back to spaces
        </Link>
      </div>
    );
  }

  if (fetchState === "error" || !space) {
    return (
      <div className="text-sm text-gray-400">
        Failed to load space.{" "}
        <Link href="/spaces" className="text-blue-400 hover:underline">
          Back to spaces
        </Link>
      </div>
    );
  }

  const pinnedIds = new Set(spaceUrls.map((u) => u.id));
  const availableJobs = allJobs.filter((j) => !pinnedIds.has(j.id));

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Back link */}
      <Link
        href="/spaces"
        className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
      >
        <span aria-hidden="true">&#8592;</span> Back to spaces
      </Link>

      {/* Header */}
      {!editing ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className="inline-block h-4 w-4 flex-shrink-0 rounded-full"
              style={{ backgroundColor: space.color }}
            />
            <h1 className="text-xl font-semibold text-white">{space.name}</h1>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowExport(true)}
              className="rounded-md border border-gray-600 px-3 py-1.5 text-sm text-gray-300 hover:border-gray-400 hover:text-white transition-colors"
            >
              Export
            </button>
            <button
              onClick={() => {
                setEditName(space.name);
                setEditColor(space.color);
                setEditing(true);
              }}
              className="rounded-md border border-gray-600 px-3 py-1.5 text-sm text-gray-300 hover:border-gray-400 hover:text-white transition-colors"
            >
              Edit
            </button>
            <button
              onClick={handleDelete}
              className="rounded-md border border-red-700 px-3 py-1.5 text-sm text-red-400 hover:border-red-500 hover:text-red-300 transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleEditSave} className="space-y-4">
          <h2 className="text-sm font-semibold text-gray-300">Edit Space</h2>
          {editError && <p className="text-sm text-red-400">{editError}</p>}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-gray-400" htmlFor="edit-name">
                Name
              </label>
              <input
                id="edit-name"
                type="text"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400" htmlFor="edit-color">
                Color
              </label>
              <input
                id="edit-color"
                type="color"
                value={editColor}
                onChange={(e) => setEditColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded border border-gray-700 bg-gray-900 p-0.5"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={editSaving}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
              >
                {editSaving ? "Saving…" : "Save"}
              </button>
              <button
                type="button"
                onClick={() => { setEditing(false); setEditError(null); }}
                className="rounded-md border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-700">
        {(["urls", "context"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab
                ? "border-b-2 border-indigo-500 text-white"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab === "urls" ? "URLs" : "Context"}
          </button>
        ))}
      </div>

      {/* URLs tab */}
      {activeTab === "urls" && (
        <section className="space-y-4">
          {urlsLoading ? (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
              Loading…
            </div>
          ) : spaceUrls.length === 0 ? (
            <p className="text-sm text-gray-500">No jobs added yet.</p>
          ) : (
            <ul className="space-y-2">
              {spaceUrls.map((item, idx) => {
                const display = item.title?.trim() || item.url;
                const ctColor =
                  CONTENT_TYPE_COLORS[item.content_type] ??
                  "bg-gray-700 text-gray-300";
                return (
                  <li
                    key={item.id}
                    className="flex items-center gap-3 rounded-lg bg-gray-800 px-4 py-3"
                  >
                    <div className="flex flex-col gap-0.5">
                      <button
                        onClick={() => handleMove(idx, "up")}
                        disabled={idx === 0}
                        className="rounded px-1 py-0.5 text-xs text-gray-500 hover:text-white disabled:opacity-30 transition-colors"
                        aria-label="Move up"
                      >
                        &#9650;
                      </button>
                      <button
                        onClick={() => handleMove(idx, "down")}
                        disabled={idx === spaceUrls.length - 1}
                        className="rounded px-1 py-0.5 text-xs text-gray-500 hover:text-white disabled:opacity-30 transition-colors"
                        aria-label="Move down"
                      >
                        &#9660;
                      </button>
                    </div>
                    <Link
                      href={`/jobs/${item.id}`}
                      className="flex-1 min-w-0 text-sm text-gray-100 hover:text-white truncate"
                      title={display}
                    >
                      {display}
                    </Link>
                    <Badge label={item.content_type} colorClass={ctColor} />
                    <button
                      onClick={() => handleRemoveUrl(item.id)}
                      className="ml-1 rounded border border-red-700 px-2 py-0.5 text-xs text-red-400 hover:border-red-500 hover:text-red-300 transition-colors"
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="flex items-center gap-3 pt-2">
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="flex-1 rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-indigo-500 focus:outline-none"
            >
              <option value="">Select a job to add…</option>
              {availableJobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title?.trim() || j.url} ({j.content_type})
                </option>
              ))}
            </select>
            <button
              onClick={handleAddJob}
              disabled={!selectedJobId || addingJob}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {addingJob ? "Adding…" : "Add"}
            </button>
          </div>
        </section>
      )}

      {/* Export modal */}
      {showExport && (
        <ExportModal
          spaceId={spaceId}
          spaceName={space.name}
          onClose={() => setShowExport(false)}
        />
      )}

      {/* Context tab */}
      {activeTab === "context" && (
        <section className="space-y-4">
          {blobsLoading ? (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
              Loading…
            </div>
          ) : blobs.length === 0 ? (
            <p className="text-sm text-gray-500">
              No context documents yet. Add one to frame how sources should be read.
            </p>
          ) : (
            <div className="space-y-6">
              {blobs.map((blob, idx) => (
                <div key={blob.id} className="space-y-2">
                  {/* Blob header row */}
                  <div className="flex items-center gap-2">
                    <div className="flex flex-col gap-0.5">
                      <button
                        onClick={() => handleMoveBlob(idx, "up")}
                        disabled={idx === 0}
                        className="rounded px-1 py-0.5 text-xs text-gray-500 hover:text-white disabled:opacity-30 transition-colors"
                        aria-label="Move up"
                      >
                        &#9650;
                      </button>
                      <button
                        onClick={() => handleMoveBlob(idx, "down")}
                        disabled={idx === blobs.length - 1}
                        className="rounded px-1 py-0.5 text-xs text-gray-500 hover:text-white disabled:opacity-30 transition-colors"
                        aria-label="Move down"
                      >
                        &#9660;
                      </button>
                    </div>
                    <input
                      type="text"
                      value={blob.name}
                      onChange={(e) => {
                        setBlobs((prev) =>
                          prev.map((b) =>
                            b.id === blob.id ? { ...b, name: e.target.value } : b
                          )
                        );
                      }}
                      onBlur={(e) =>
                        handleBlobSave(blob.id, e.target.value, blob.content)
                      }
                      className="flex-1 rounded-md border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-gray-100 focus:border-indigo-500 focus:outline-none"
                      placeholder="Context name"
                    />
                    <button
                      onClick={() => handleDeleteBlob(blob.id)}
                      className="rounded border border-red-700 px-2 py-0.5 text-xs text-red-400 hover:border-red-500 hover:text-red-300 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                  {/* WYSIWYG editor — no raw markdown shown */}
                  <MarkdownEditor
                    initialMarkdown={blob.content}
                    onSave={(md) => handleBlobSave(blob.id, blob.name, md)}
                  />
                </div>
              ))}
            </div>
          )}

          {blobError && (
            <p className="text-sm text-red-400">{blobError}</p>
          )}

          {/* Add context document */}
          <div className="flex items-center gap-3 pt-2">
            <input
              type="text"
              value={newBlobName}
              onChange={(e) => setNewBlobName(e.target.value)}
              placeholder="Context document name…"
              className="flex-1 rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-indigo-500 focus:outline-none"
            />
            <button
              onClick={handleAddBlob}
              disabled={addingBlob}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {addingBlob ? "Adding…" : "Add context"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
