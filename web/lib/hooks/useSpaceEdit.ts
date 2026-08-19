"use client";

import { useCallback, useEffect, useState } from "react";
import type { SpaceDetail } from "@/lib/hooks/useSpaceDetail";

export function useSpaceEdit(
  spaceId: string,
  space: SpaceDetail | null,
  onSaved: (updated: SpaceDetail) => void,
) {
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(space?.name ?? "");
  const [editColor, setEditColor] = useState(space?.color ?? "#6366f1");
  const [editIcon, setEditIcon] = useState(space?.icon ?? "folder");
  const [editError, setEditError] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);

  useEffect(() => {
    if (space) {
      setEditName(space.name);
      setEditColor(space.color);
      setEditIcon(space.icon ?? "folder");
    }
  }, [space]);

  const startEdit = useCallback(() => {
    if (space) {
      setEditName(space.name);
      setEditColor(space.color);
      setEditIcon(space.icon ?? "folder");
    }
    setEditing(true);
  }, [space]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
    setEditError(null);
  }, []);

  const handleEditSave = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!editName.trim()) return;
      setEditSaving(true);
      setEditError(null);
      try {
        const res = await fetch(`/api/spaces/${spaceId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: editName.trim(),
            color: editColor,
            icon: editIcon,
          }),
        });
        if (res.status === 409) {
          setEditError("A space with that name already exists.");
          return;
        }
        if (!res.ok) throw new Error("Failed to save");
        const updated: SpaceDetail = await res.json();
        onSaved(updated);
        setEditing(false);
      } catch (err) {
        setEditError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setEditSaving(false);
      }
    },
    [spaceId, editName, editColor, editIcon, onSaved],
  );

  return {
    editing,
    editName,
    setEditName,
    editColor,
    setEditColor,
    editIcon,
    setEditIcon,
    editError,
    editSaving,
    startEdit,
    cancelEdit,
    handleEditSave,
  };
}
