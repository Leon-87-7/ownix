'use client';

import { useRestrictedMode } from '@/lib/restricted/context';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { LayoutGrid } from 'lucide-react';
import { SpaceCard } from '@/components/spaces/space-card';
import { useSpaceList } from '@/lib/hooks/useSpaceList';
import { useCreateSpace } from '@/lib/hooks/useCreateSpace';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { SPACE_ICONS } from '@/lib/space-icons';
import { PageShell, PageHeader } from '@/components/shell/page-shell';

export default function SpacesPage() {
  const { restricted } = useRestrictedMode();
  if (restricted) return <RestrictedFacade icon={LayoutGrid} title="Collections">Collections are visible in the full product for grouping saved jobs into durable research sets. Creating and editing collections is locked in this read-only preview.</RestrictedFacade>;
  return <SpacesWorkspace />;
}

function SpacesWorkspace() {
  const { spaces, loading, error, reload } = useSpaceList();
  const {
    showForm,
    openForm,
    newName,
    setNewName,
    newColor,
    setNewColor,
    newIcon,
    setNewIcon,
    submitting,
    formError,
    handleCreate,
    resetForm,
  } = useCreateSpace(reload);

  if (loading) {
    return (
      <PageShell>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <SkeletonBlock className="h-[100px]" />
          <SkeletonBlock className="h-[100px]" />
          <SkeletonBlock className="h-[100px]" />
        </div>
      </PageShell>
    );
  }

  if (error) {
    return (
      <p className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
        {error}
      </p>
    );
  }

  return (
    <PageShell>
      <PageHeader
        icon={LayoutGrid}
        title="Collections"
        description="Group saved items into durable sets you can revisit, add context to, and export together."
        action={
          <button
            onClick={showForm ? resetForm : openForm}
            className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
          >
            {showForm ? 'Cancel' : 'New Collection'}
          </button>
        }
      />

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-lg border border-line bg-surface p-4"
        >
          <h2 className="text-sm font-semibold text-ink">
            Create Collection
          </h2>
          {formError && (
            <p className="text-sm text-status-error">{formError}</p>
          )}
          <div>
            <span className="mb-1 block text-xs font-medium text-body">
              Icon
            </span>
            <div className="flex flex-wrap gap-1">
              {SPACE_ICONS.map(({ name, Icon }) => {
                const active = newIcon === name;
                return (
                  <button
                    key={name}
                    type="button"
                    onClick={() => setNewIcon(name)}
                    aria-label={name}
                    aria-pressed={active}
                    className={`flex h-8 w-8 items-center justify-center rounded-md transition-ui ${
                      active
                        ? 'bg-signal text-onsignal hover:bg-signal-bright'
                        : 'border border-line bg-surface text-body hover:bg-raised hover:text-ink'
                    }`}
                  >
                    <Icon
                      className="h-4 w-4"
                      aria-hidden="true"
                    />
                  </button>
                );
              })}
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label
                className="mb-1 block text-xs font-medium text-body"
                htmlFor="space-name"
              >
                Name
              </label>
              <input
                id="space-name"
                type="text"
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="My space…"
                className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
              />
            </div>
            <div>
              <label
                className="mb-1 block text-xs font-medium text-body"
                htmlFor="space-color"
              >
                Color
              </label>
              <input
                id="space-color"
                type="color"
                value={newColor}
                onChange={(e) => setNewColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded-md border border-line bg-canvas p-0.5"
              />
            </div>
            <div className="flex gap-2 sm:self-end">
              <button
                type="submit"
                disabled={submitting}
                className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
              >
                {submitting ? 'Creating…' : 'Create'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="h-8 rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-ui hover:bg-raised"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {spaces.length === 0 && !showForm && (
        <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
          <p className="text-sm font-medium text-ink">
            No collections yet
          </p>
          <p className="mt-1 text-sm text-body">
            Create one to group related saves, add context, and export
            them together.
          </p>
        </div>
      )}

      {spaces.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {spaces.map((space) => (
            <SpaceCard
              key={space.id}
              space={space}
              onDeleted={reload}
            />
          ))}
        </div>
      )}
    </PageShell>
  );
}
