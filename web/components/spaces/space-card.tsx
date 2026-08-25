"use client";

import Link from "next/link";
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { spaceIcon } from "@/lib/space-icons";
import { DateTime } from "@/components/ui/date-time";
import { apiDelete } from "@/lib/fetch-utils";

// SQLite's CURRENT_TIMESTAMP has no timezone marker; without one, Date parses it
// as local time instead of UTC. Mark it explicitly so DateTime shows the right instant.
function asUtcIso(raw: string): string {
  return /[Zz]|[+-]\d\d:?\d\d$/.test(raw) ? raw : `${raw.replace(" ", "T")}Z`;
}

export interface SpaceSummary {
  id: string;
  name: string;
  color: string;
  icon?: string;
  created_at: string;
  first_note?: {
    name: string;
    snippet: string;
    updated_at: string;
    truncated?: boolean;
  };
}

export function SpaceCard({
  space,
  onDeleted,
}: {
  space: SpaceSummary;
  onDeleted?: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [failed, setFailed] = useState(false);
  const Icon = spaceIcon(space.icon);

  const handleDelete = async () => {
    setDeleting(true);
    setFailed(false);
    try {
      await apiDelete(`/api/spaces/${space.id}`);
      setDeleting(false);
      setConfirming(false);
      onDeleted?.();
      return;
    } catch {
      setFailed(true);
      setDeleting(false);
    }
  };

  if (confirming) {
    return (
      <div className="flex min-h-[100px] flex-col items-center justify-center gap-2 rounded-lg border border-line bg-surface p-4 text-center">
        <p className="text-sm text-ink">Delete {space.name}?</p>
        {failed && (
          <p className="text-xs text-status-error">
            Couldn&apos;t delete — try again.
          </p>
        )}
        <div className="flex gap-4">
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="text-button font-medium text-status-error transition-ui hover:underline disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Confirm"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            disabled={deleting}
            className="text-button font-medium text-muted transition-ui hover:text-ink"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="group relative min-h-[100px] overflow-hidden rounded-lg border border-line bg-surface transition-ui hover:bg-raised">
      {/* Low-opacity color wash from the space color (hex + "14" ≈ 0.08 alpha). */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: `linear-gradient(${space.color}14, transparent)` }}
        aria-hidden="true"
      />
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          setConfirming(true);
        }}
        aria-label={`Delete ${space.name}`}
        className="absolute right-2 top-2 z-10 rounded p-1 text-muted opacity-100 transition-ui hover:text-status-error focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
      >
        <Trash2 className="h-4 w-4" aria-hidden="true" />
      </button>
      <Link
        href={`/spaces/${space.id}`}
        className="relative flex h-full min-h-[100px] flex-col justify-center gap-2 p-4"
      >
        {space.first_note ? (
          <>
            <span className="truncate text-sm font-medium text-ink">
              {space.first_note.name}
            </span>
            <p className="line-clamp-2 text-xs text-body">
              {space.first_note.snippet}
              {space.first_note.truncated ? "…" : ""}
            </p>
            <span className="font-mono text-mono-label text-muted">
              Updated <DateTime iso={asUtcIso(space.first_note.updated_at)} />
            </span>
          </>
        ) : (
          <>
            <Icon className="h-6 w-6 text-ink" aria-hidden="true" />
            <span className="truncate text-sm font-medium text-ink">
              {space.name}
            </span>
          </>
        )}
      </Link>
    </div>
  );
}
