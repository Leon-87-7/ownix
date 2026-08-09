'use client';

import { useRestrictedMode } from '@/lib/restricted/context';
import { RestrictedFacade } from '@/components/shell/restricted-facade';

import Link from 'next/link';
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  FileCode2,
  Sparkles,
  CircleQuestionMark,
} from 'lucide-react';
import { StatusBadge } from '@/components/ui/badges';
import { DocUploadPanel } from '@/components/doc-parser/doc-upload-panel';
import { TelegramToggle } from '@/components/doc-parser/telegram-toggle';
import { FilterBar } from '@/components/ui/filter-bar';
import {
  SkeletonList,
  EmptyState,
} from '@/components/feed/feed-states';
import { PageShell, PageHeader } from '@/components/shell/page-shell';

type Job = {
  id: string;
  title?: string | null;
  url: string;
  status: string;
  created_at: string;
  telegram_delivery?: 'off' | 'on' | 'retroactive';
};

const DOC_FORMAT_TABS = [
  { label: 'All', value: '' },
  { label: 'PDF', value: 'pdf' },
  { label: 'Word', value: 'word' },
  { label: 'Spreadsheet', value: 'spreadsheet' },
  { label: 'Presentation', value: 'presentation' },
] as const;

// Map a job's stored source extension (documents/<sha>.<ext>) to a format tab.
// Mirrors the buckets the parser supports (ADR-0023); anything else is 'other'.
const FORMAT_BUCKETS: Record<string, readonly string[]> = {
  pdf: ['pdf'],
  word: ['doc', 'docx', 'docm', 'odt', 'rtf', 'epub'],
  spreadsheet: ['xls', 'xlsx', 'xlsm', 'ods', 'csv'],
  presentation: ['ppt', 'pptx', 'pptm', 'odp'],
};

function jobFormat(url: string): string {
  const ext = url.includes('.') ? url.split('.').pop()!.toLowerCase() : '';
  for (const [bucket, exts] of Object.entries(FORMAT_BUCKETS)) {
    if (exts.includes(ext)) return bucket;
  }
  return 'other';
}

// Full format list (LlamaParse multi-format). All-inline markup so it stays
// valid nested inside the header <p>; reveals on hover OR keyboard focus.
function FormatHelp() {
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label="Show all supported formats"
        aria-describedby="doc-formats-tip"
        className="inline-flex h-5 w-5 items-center justify-center rounded text-muted transition-ui hover:text-ink"
      >
        <CircleQuestionMark
          className="h-4 w-4"
          aria-hidden="true"
        />
      </button>
      <span
        id="doc-formats-tip"
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-md border border-line bg-surface p-3 font-sans text-xs leading-relaxed text-body opacity-0 shadow-overlay transition-opacity duration-150 ease-out-quart group-hover:opacity-100 group-focus-within:opacity-100"
      >
        <span className="block font-medium text-ink">
          All supported formats
        </span>
        <span className="mt-2 grid gap-1.5">
          {[
            ['PDF', '.pdf'],
            ['Word', '.doc .docx .docm .odt .rtf .pages'],
            ['PowerPoint', '.ppt .pptx .pptm .odp .key'],
            [
              'Spreadsheet',
              '.xls .xlsx .xlsm .ods .csv .tsv .numbers',
            ],
            ['Images', '.jpg .jpeg .png .gif .bmp .tiff .webp .svg'],
          ].map(([label, exts]) => (
            <span
              key={label}
              className="block"
            >
              <span className="text-muted">{label}</span>{' '}
              <span className="font-mono text-label text-body">
                {exts}
              </span>
            </span>
          ))}
        </span>
      </span>
    </span>
  );
}

export default function DocParserPage() {
  const { restricted } = useRestrictedMode();
  if (restricted) return <RestrictedFacade icon={FileCode2} title="Docs">Docs ingestion turns PDFs and other files into parsed source material. Uploads and Telegram delivery toggles are locked in this read-only preview.</RestrictedFacade>;
  return <DocParserWorkspace />;
}

function DocParserWorkspace() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState('');
  const [format, setFormat] = useState('');
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(async () => {
    setLoadError('');
    try {
      const r = await fetch(
        `/api/jobs?content_type=document&limit=100${status ? `&status=${status}` : ''}`,
      );
      if (!r.ok) throw new Error(`Documents request failed (${r.status})`);
      const d = await r.json();
      setJobs(d.items ?? []);
    } catch {
      // Surface the failure instead of falling through to EmptyState, which
      // would misread a 5xx/network error as "no documents".
      setLoadError('Failed to load documents. Please refresh.');
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  // Keep the SSE handler pointed at the latest load (with current status filter)
  // without tearing down the EventSource on every filter change.
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    const es = new EventSource('/api/parsed/events');
    const onJobs = () => loadRef.current();
    es.addEventListener('jobs', onJobs);
    return () => es.close();
  }, []);

  const filtered = useMemo(
    () =>
      jobs.filter(
        (j) =>
          (j.title || j.url).toLowerCase().includes(q.toLowerCase()) &&
          (!format || jobFormat(j.url) === format),
      ),
    [jobs, q, format],
  );
  const formatTabs = useMemo(() => {
    const counts = jobs.reduce<Record<string, number>>((acc, j) => {
      const f = jobFormat(j.url);
      acc[f] = (acc[f] ?? 0) + 1;
      return acc;
    }, {});
    return DOC_FORMAT_TABS.map((t) => ({
      ...t,
      count: t.value === '' ? jobs.length : counts[t.value] ?? 0,
    }));
  }, [jobs]);

  return (
    <PageShell>
      <PageHeader
        icon={FileCode2}
        title="Docs"
        description={
          <>
            Upload PDFs, Microsoft Office formats and Images.
            <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs text-muted">
              <span>.pdf | .docx | .xlsx | .pptx | .png | …</span>
              <FormatHelp />
            </span>
          </>
        }
      />

      <FilterBar
        tabs={formatTabs}
        tabValue={format}
        onTabChange={setFormat}
        tabsLabel="Document format"
        query={q}
        setQuery={setQ}
        searchPlaceholder="Search documents…"
        searchLabel="Search documents"
        statusValue={status}
        onStatusChange={setStatus}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <DocUploadPanel onUploaded={load} />

        <section className="space-y-2">
          {loading && <SkeletonList />}
          {!loading && loadError && (
            <p
              role="alert"
              className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error"
            >
              {loadError}
            </p>
          )}
          {!loading && !loadError && filtered.length === 0 && (
            <EmptyState
              hasFilters={Boolean(q || status || format)}
              onClear={() => {
                setQ('');
                setStatus('');
                setFormat('');
              }}
            />
          )}
          {!loading &&
            filtered.map((j) => (
              <div
                key={j.id}
                className="rounded-lg border border-line bg-surface p-4 hover:bg-raised"
              >
                <div className="flex items-center gap-3">
                  <Link
                    href={`/doc-parser/${j.id}`}
                    className="min-w-0 flex-1 truncate text-sm font-medium text-ink"
                  >
                    {j.title || j.url}
                  </Link>
                  <Sparkles className="h-4 w-4 text-muted" />
                  <StatusBadge label={j.status} />
                  <TelegramToggle
                    jobId={j.id}
                    value={j.telegram_delivery || 'on'}
                  />
                </div>
                <p className="mt-2 font-mono text-xs text-muted">
                  {j.id}
                </p>
              </div>
            ))}
        </section>
      </div>
    </PageShell>
  );
}
