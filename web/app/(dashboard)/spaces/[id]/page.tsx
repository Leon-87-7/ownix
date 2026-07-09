"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ExportModal from "@/components/ExportModal";
import { useSpaceDetail } from "@/lib/hooks/useSpaceDetail";
import { useSpaceEdit } from "@/lib/hooks/useSpaceEdit";
import { UrlsTab } from "./UrlsTab";
import { ContextTab } from "./ContextTab";
import { TabBar } from "@/components/ui";
import { PageShell } from "@/components/page-shell";
import { SkeletonBlock } from "@/components/feed/feed-states";

type ActiveTab = "urls" | "context";

export default function SpaceDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { space, setSpace, fetchState } = useSpaceDetail(params.id);
  const { editing, editName, setEditName, editColor, setEditColor, editError, editSaving, startEdit, cancelEdit, handleEditSave } =
    useSpaceEdit(params.id, space, setSpace);
  const [activeTab, setActiveTab] = useState<ActiveTab>("urls");
  const [showExport, setShowExport] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);

  const handleDelete = useCallback(async () => {
    if (!window.confirm("Delete this collection? Saved items will not be deleted.")) return;
    setDeleting(true);
    setDeleteFailed(false);
    try {
      const res = await fetch(`/api/spaces/${params.id}`, { method: "DELETE" });
      if (res.ok || res.status === 204) {
        // Navigating away — skip state updates so nothing fires mid-unmount.
        router.push("/spaces");
        return;
      }
      setDeleteFailed(true);
    } catch {
      setDeleteFailed(true);
    }
    setDeleting(false);
  }, [params.id, router]);

  if (fetchState === "loading") {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-8 w-32" />
          <SkeletonBlock className="h-40" />
        </div>
      </PageShell>
    );
  }
  if (fetchState === "not_found") return <div className="text-sm text-body">Collection not found. <Link href="/spaces" className="text-signal hover:underline">Back to collections</Link></div>;
  if (fetchState === "forbidden") return <div className="text-sm text-body">Access denied. <Link href="/spaces" className="text-signal hover:underline">Back to collections</Link></div>;
  if (fetchState === "error" || !space) return <div className="text-sm text-body">Failed to load collection. <Link href="/spaces" className="text-signal hover:underline">Back to collections</Link></div>;

  return (
    <PageShell width="narrow">
      <Link href="/spaces" className="inline-flex items-center gap-1 text-xs text-muted transition-ui hover:text-ink">
        <span aria-hidden="true">&#8592;</span> Back to collections
      </Link>

      {!editing ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="inline-block h-4 w-4 flex-shrink-0 rounded-full" style={{ backgroundColor: space.color }} />
            <h1 className="text-2xl font-semibold tracking-tight text-ink">{space.name}</h1>
          </div>
          <div className="space-y-2">
            <div className="flex gap-2">
              <button onClick={() => setShowExport(true)} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised">Export</button>
              <button onClick={startEdit} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised">Edit</button>
              <button onClick={handleDelete} disabled={deleting} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-status-error transition-ui hover:bg-raised disabled:opacity-50">{deleting ? "Deleting…" : "Delete"}</button>
            </div>
            {deleteFailed && <p className="text-xs text-status-error">Couldn&apos;t delete — try again.</p>}
          </div>
        </div>
      ) : (
        <form onSubmit={handleEditSave} className="space-y-4">
          <h2 className="text-sm font-semibold text-ink">Edit Collection</h2>
          {editError && <p className="text-sm text-status-error">{editError}</p>}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-body" htmlFor="edit-name">Name</label>
              <input id="edit-name" type="text" required value={editName} onChange={(e) => setEditName(e.target.value)} className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-body" htmlFor="edit-color">Color</label>
              <input id="edit-color" type="color" value={editColor} onChange={(e) => setEditColor(e.target.value)} className="h-9 w-12 cursor-pointer rounded-md border border-line bg-canvas p-0.5" />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={editSaving} className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted">{editSaving ? "Saving…" : "Save"}</button>
              <button type="button" onClick={cancelEdit} className="h-8 rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-ui hover:bg-raised">Cancel</button>
            </div>
          </div>
        </form>
      )}

      <TabBar
        tabs={["urls", "context"] as const}
        active={activeTab}
        onChange={setActiveTab}
        labels={{ urls: "URLs", context: "Context" }}
      />

      {activeTab === "urls" && <UrlsTab spaceId={params.id} />}
      {activeTab === "context" && <ContextTab spaceId={params.id} />}

      {showExport && <ExportModal spaceId={params.id} spaceName={space.name} onClose={() => setShowExport(false)} />}
    </PageShell>
  );
}
