'use client';

import { useEffect, useState } from 'react';
import { CopyButton } from '@/components/ui/copy-button';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { OwnixShareIcon } from '@/components/svg/ownix-share-icon';
import { useGoogleStatus } from '@/components/shell/google-status';
import { DriveTextLink } from '@/components/jobs/drive-text-link';
import { isSafeHttpUrl } from '@/lib/url-utils';
import { buildMarkdown } from '@/lib/job-markdown';
import type { JobDetail } from '@/lib/hooks/useJobDetail';

export function JobActionsBar({
  job,
  hasFields,
  enrich,
}: {
  job: JobDetail;
  hasFields: boolean;
  enrich?: { open: boolean; onToggle: () => void };
}) {
  const { connected } = useGoogleStatus();
  const [folderUrl, setFolderUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!connected) {
      setFolderUrl(null);
      return;
    }
    let cancelled = false;
    void fetch('/api/google/folder')
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { folder_url: string } | null) => {
        if (!cancelled) setFolderUrl(data?.folder_url ?? null);
      })
      .catch(() => {
        if (!cancelled) setFolderUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connected]);

  if (!job.drive_url && !hasFields && !folderUrl && !enrich) return null;
  return (
    <div className="flex items-start gap-2">
      <div className="flex flex-col items-start gap-2">
        {job.drive_url && isSafeHttpUrl(job.drive_url) && (
          <DriveTextLink href={job.drive_url} label="Open in Drive" />
        )}
        {folderUrl && (
          <a
            href={folderUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-button font-medium text-ink transition-ui hover:bg-raised"
          >
            <GoogleDriveIcon className="h-3.5 w-3.5" />
            Ownix folder{' '}
            <OwnixShareIcon className="h-[18px] w-[18px]" aria-hidden="true" />
          </a>
        )}
      </div>
      {(hasFields || enrich) && (
        <div className="ml-auto flex flex-col items-end gap-2">
          {hasFields && (
            <CopyButton
              value={buildMarkdown(job)}
              ariaLabel="Copy all fields as Markdown"
              label="Copy all"
            />
          )}
          {enrich && (
            <button
              type="button"
              onClick={enrich.onToggle}
              aria-expanded={enrich.open}
              className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
            >
              Enrich
            </button>
          )}
        </div>
      )}
    </div>
  );
}
