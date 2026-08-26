'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';
import {
  useParams,
  usePathname,
  useRouter,
  useSearchParams,
} from 'next/navigation';
import ExportModal from '@/components/ui/export-modal';
import { useSpaceDetail } from '@/lib/hooks/useSpaceDetail';
import { useSpaceEdit } from '@/lib/hooks/useSpaceEdit';
import { UrlsTab } from './UrlsTab';
import { ContextTab } from './ContextTab';
import { TabBar } from '@/components/ui/tab-bar';
import { PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { IconPicker } from '@/components/spaces/icon-picker';
import { DEFAULT_SPACE_ICON, SPACE_ICON_BY_NAME } from '@/lib/space-icons';
import { apiDelete } from '@/lib/fetch-utils';

type ActiveTab = 'urls' | 'context';

export default function SpaceDetailPage() {
  // Next 16 params are async on page props; useParams() resolves the route id
  // client-side (see jobs/[id] for the /api/…/undefined failure this avoids).
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { space, setSpace, fetchState } = useSpaceDetail(id);
  const {
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
  } = useSpaceEdit(id, space, setSpace);
  const activeTab: ActiveTab =
    searchParams.get('tab') === 'urls' ? 'urls' : 'context';
  const setActiveTab = useCallback(
    (tab: ActiveTab) => {
      const params = new URLSearchParams(searchParams.toString());
      if (tab === 'urls') params.set('tab', 'urls');
      else params.delete('tab');
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );
  const [showExport, setShowExport] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);

  const handleDelete = useCallback(async () => {
    if (
      !window.confirm(
        'Delete this collection? Saved items will not be deleted.',
      )
    )
      return;
    setDeleting(true);
    setDeleteFailed(false);
    try {
      await apiDelete(`/api/spaces/${id}`);
      // Navigating away - skip state updates so nothing fires mid-unmount.
      router.push('/spaces');
      return;
    } catch {
      setDeleteFailed(true);
    }
    setDeleting(false);
  }, [id, router]);

  if (fetchState === 'loading') {
    return (
      <PageShell>
        <div className="space-y-3">
          <SkeletonBlock className="h-8 w-32" />
          <SkeletonBlock className="h-40" />
        </div>
      </PageShell>
    );
  }
  if (fetchState === 'not_found')
    return (
      <div className="text-sm text-body">
        Collection not found.{' '}
        <Link
          href="/spaces"
          className="text-signal hover:underline"
        >
          Back to collections
        </Link>
      </div>
    );
  if (fetchState === 'forbidden')
    return (
      <div className="text-sm text-body">
        Access denied.{' '}
        <Link
          href="/spaces"
          className="text-signal hover:underline"
        >
          Back to collections
        </Link>
      </div>
    );
  if (fetchState === 'error' || !space)
    return (
      <div className="text-sm text-body">
        Failed to load collection.{' '}
        <Link
          href="/spaces"
          className="text-signal hover:underline"
        >
          Back to collections
        </Link>
      </div>
    );

  // Plain lookup, not a spaceIcon() call: react-hooks/static-components flags
  // a component variable assigned from a CallExpression as "created during
  // render" (see lib/space-icons.ts).
  const Icon = (space.icon && SPACE_ICON_BY_NAME[space.icon]) || DEFAULT_SPACE_ICON;

  return (
    <PageShell>
      <Link
        href="/spaces"
        className="inline-flex items-center gap-1 text-xs text-muted transition-ui hover:text-ink"
      >
        <span aria-hidden="true">&#8592;</span> Back to collections
      </Link>

      {!editing ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Icon
              data-testid={`space-icon-${space.icon ?? 'folder'}`}
              className="h-5 w-5 flex-shrink-0"
              style={{ color: space.color }}
              aria-hidden="true"
            />
            <h1 className="text-2xl font-semibold tracking-tight text-ink">
              {space.name}
            </h1>
          </div>
          <div className="space-y-2">
            <div className="flex gap-2">
              <button
                onClick={() => setShowExport(true)}
                className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised"
              >
                Export
              </button>
              <button
                onClick={startEdit}
                className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised"
              >
                Edit
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="h-8 rounded-md border border-line px-3 text-button font-medium text-status-error transition-ui hover:bg-raised disabled:opacity-50"
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
            {deleteFailed && (
              <p className="text-xs text-status-error">
                Couldn&apos;t delete - try again.
              </p>
            )}
          </div>
        </div>
      ) : (
        <form
          onSubmit={handleEditSave}
          className="space-y-4"
        >
          <h2 className="text-sm font-semibold text-ink">
            Edit Collection
          </h2>
          {editError && (
            <p className="text-sm text-status-error">{editError}</p>
          )}
          <IconPicker
            value={editIcon}
            onChange={setEditIcon}
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label
                className="mb-1 block text-xs font-medium text-body"
                htmlFor="edit-name"
              >
                Name
              </label>
              <input
                id="edit-name"
                type="text"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
              />
            </div>
            <div>
              <label
                className="mb-1 block text-xs font-medium text-body"
                htmlFor="edit-color"
              >
                Color
              </label>
              <input
                id="edit-color"
                type="color"
                value={editColor}
                onChange={(e) => setEditColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded-md border border-line bg-canvas p-0.5"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={editSaving}
                className="h-8 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
              >
                {editSaving ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                onClick={cancelEdit}
                className="h-8 rounded-md border border-line px-3.5 text-button font-medium text-ink transition-ui hover:bg-raised"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      <TabBar
        tabs={['context', 'urls'] as const}
        active={activeTab}
        onChange={setActiveTab}
        labels={{ context: 'Context', urls: 'URLs' }}
      />

      {activeTab === 'context' && <ContextTab spaceId={id} />}
      {activeTab === 'urls' && <UrlsTab spaceId={id} />}

      {showExport && (
        <ExportModal
          spaceId={id}
          spaceName={space.name}
          onClose={() => setShowExport(false)}
        />
      )}
    </PageShell>
  );
}
