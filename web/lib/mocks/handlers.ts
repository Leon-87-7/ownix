import { http, HttpResponse } from 'msw';

// In-memory state seeded from a real DB snapshot fetched at worker start (so the
// 1.3MB file is never bundled — see browser.ts). Mutations (tag attach/detach,
// create tag, annotations) persist for the browser session only.
interface Job { id: string; content_type: string; status: string; [k: string]: unknown }
interface Tag { id: string; name: string; meaning: string; color: string; pinned?: boolean }
interface Template { id: string; name: string; description: string; extra_instructions: string; is_builtin: boolean; created_at?: string; updated_at?: string }
interface DocumentOutput { id: string; kind: string; title: string; preview: string; content_url: string; created_at: string }
export interface Seed {
  jobs: Job[];
  tags: Tag[];
  job_tags: { job_id: string; tag_id: string }[];
  annotations: { job_id: string; notes: string; updated_at: string | null }[];
}

const MOCK_DOCUMENT_SHA =
  '9a3aa177427fe1acc654db0235e999ead2d8c8f7e094e28e4ac6e13fdbe34ed5';
const MOCK_DOCUMENT_JOB_IDS = new Set([
  '20260619_214843_1A77D8D1',
  '20260707_232015_218BFDA4',
]);

// One of the two demo documents already has a 'clean' output, so the list's
// GeneratedBadge (mirrors the real /api/jobs `document_enriched_at` subquery)
// has something real to show.
const MOCK_ENRICHED_DOCUMENT_JOB_ID = '20260707_232015_218BFDA4';

function mockDocumentJob(id: string): Job {
  return {
    id,
    content_type: 'document',
    status: 'done',
    title:
      'PRE-INSTALLATION GUIDE WASSENBURG PROCESS MANAGER IIPLUS',
    url: `documents/${MOCK_DOCUMENT_SHA}.pdf`,
    telegram_delivery: 'off',
    created_at: '2026-07-07 23:20:15',
    updated_at: '2026-07-07 23:22:10',
    completed_at: '2026-07-07T23:22:10Z',
    document_enriched_at:
      id === MOCK_ENRICHED_DOCUMENT_JOB_ID ? '2026-07-08T09:00:00Z' : null,
  };
}

function mockDocumentOutputs(jobId: string): DocumentOutput[] {
  const outputs: DocumentOutput[] = [
    {
      id: 'mock-summary',
      kind: 'summary',
      title: 'Structured summary',
      preview:
        "Here's a structured Markdown briefing based on the provided Pre-Installation Guide:\n\n# WASSENBURG Process Manager II/IIPLUS Pre-Installation Guide Briefing\n\n## TL;DR\n\nThis document is a pre-installation guide for the traceability and process monitoring software.",
      content_url: `/api/parsed/${jobId}/outputs/mock-summary`,
      created_at: '2026-07-07T23:22:10Z',
    },
    {
      id: 'mock-raw',
      kind: 'raw_txt',
      title: 'Raw parse',
      preview:
        'PRE-INSTALLATION GUIDE\n\nWASSENBURG PROCESS MANAGER IIPLUS\nWASSENBURG PROCESS MANAGER II\nTRACEABILITY AND PROCESS MONITORING SOFTWARE\n\nREFERENCE : F070.099',
      content_url: `/api/parsed/${jobId}/outputs/mock-raw`,
      created_at: '2026-07-07T23:22:10Z',
    },
  ];
  if (jobId === MOCK_ENRICHED_DOCUMENT_JOB_ID) {
    outputs.push({
      id: 'mock-clean',
      kind: 'clean',
      title: 'Clean version',
      preview: 'Cleaned Markdown version of the mocked parsed document.',
      content_url: `/api/parsed/${jobId}/outputs/mock-clean`,
      created_at: '2026-07-08T09:00:00Z',
    });
  }
  return outputs;
}

function mockDocumentOutputBody(outputId: string): string {
  if (outputId === 'mock-raw') {
    return 'PRE-INSTALLATION GUIDE\n\nWASSENBURG PROCESS MANAGER IIPLUS\nWASSENBURG PROCESS MANAGER II\nTRACEABILITY AND PROCESS MONITORING SOFTWARE\n\nREFERENCE : F070.099';
  }
  return "# WASSENBURG Process Manager II/IIPLUS Pre-Installation Guide Briefing\n\n## TL;DR\n\nThis document is a pre-installation guide for the traceability and process monitoring software.";
}

export function makeHandlers(seed: Seed) {
const jobs = seed.jobs.slice();
MOCK_DOCUMENT_JOB_IDS.forEach((id) => {
  if (!jobs.some((job) => job.id === id)) {
    jobs.push(mockDocumentJob(id));
  }
});
const tags = seed.tags.slice();
const jobTags = new Set(seed.job_tags.map((jt) => `${jt.job_id}:${jt.tag_id}`));
const templates: Template[] = [
  { id: 'b1', name: 'summary', description: 'Concise summary of the video', extra_instructions: '', is_builtin: true },
  { id: 'b2', name: 'transcript', description: 'Full transcript with timestamps', extra_instructions: '', is_builtin: true },
  { id: 'b3', name: 'keypoints', description: 'Bullet-point key takeaways', extra_instructions: '', is_builtin: true },
  { id: 'u1', name: 'startup-notes', description: 'Founder takeaways', extra_instructions: 'Extract actionable startup lessons and growth tactics mentioned in the video.', is_builtin: false },
];
const annotations = new Map<string, { notes: string; updated_at: string | null }>(
  seed.annotations.map((a) => [a.job_id, { notes: a.notes, updated_at: a.updated_at }]),
);
const findJob = (id: string) => jobs.find((j) => j.id === id);
const canServeParsedDocument = (id: string) =>
  findJob(id)?.content_type === 'document';

// Order matters: more specific paths first (`/api/jobs/:id` also matches `/api/jobs/stats`).
return [
  http.get('/api/parsed/:id/outputs/:outputId', ({ params }) => {
    if (!canServeParsedDocument(params.id as string)) {
      return new HttpResponse(null, { status: 404 });
    }
    return new HttpResponse(mockDocumentOutputBody(params.outputId as string), {
      headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
    });
  }),

  http.get('/api/parsed/:id/outputs', ({ params }) => {
    if (!canServeParsedDocument(params.id as string)) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(mockDocumentOutputs(params.id as string));
  }),

  http.put('/api/parsed/:id/telegram-delivery', async ({ params, request }) => {
    if (!canServeParsedDocument(params.id as string)) {
      return new HttpResponse(null, { status: 404 });
    }
    const body = (await request.json()) as { state?: string };
    return HttpResponse.json({
      telegram_delivery: body.state === 'retroactive' ? 'on' : body.state ?? 'off',
      sent: body.state === 'retroactive' ? 2 : 0,
    });
  }),

  http.post('/api/parsed/:id/clean', ({ params }) => {
    const job = findJob(params.id as string);
    if (!job || job.content_type !== 'document') {
      return new HttpResponse(null, { status: 404 });
    }
    job.document_enriched_at = new Date().toISOString();
    return HttpResponse.json(
      {
        id: 'mock-clean',
        kind: 'clean',
        title: 'Clean version',
        preview: 'Cleaned Markdown version of the mocked parsed document.',
        content_url: `/api/parsed/${params.id}/outputs/mock-clean`,
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),

  http.post('/api/parsed/:id/freestyle', ({ params }) => {
    const job = findJob(params.id as string);
    if (!job || job.content_type !== 'document') {
      return new HttpResponse(null, { status: 404 });
    }
    job.document_enriched_at = new Date().toISOString();
    return HttpResponse.json(
      {
        id: 'mock-freestyle',
        kind: 'freestyle',
        title: 'Freestyle',
        preview: 'Freestyle response for the mocked parsed document.',
        content_url: `/api/parsed/${params.id}/outputs/mock-freestyle`,
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),

  http.get('/api/jobs/stats', ({ request }) => {
    const ct = new URL(request.url).searchParams.get('content_type') || '';
    const by_content_type: Record<string, number> = {};
    for (const j of jobs) by_content_type[j.content_type] = (by_content_type[j.content_type] ?? 0) + 1;
    const scoped = ct ? jobs.filter((j) => j.content_type === ct) : jobs;
    const by_status: Record<string, number> = {};
    for (const j of scoped) by_status[j.status] = (by_status[j.status] ?? 0) + 1;
    return HttpResponse.json({ total: scoped.length, by_status, by_content_type });
  }),

  http.get('/api/jobs/:id/tags', ({ params }) => {
    const id = params.id as string;
    return HttpResponse.json(tags.filter((t) => jobTags.has(`${id}:${t.id}`)));
  }),
  http.post('/api/jobs/:id/tags/:tagId', ({ params }) => {
    jobTags.add(`${params.id}:${params.tagId}`);
    return new HttpResponse(null, { status: 201 });
  }),
  http.delete('/api/jobs/:id/tags/:tagId', ({ params }) => {
    jobTags.delete(`${params.id}:${params.tagId}`);
    return new HttpResponse(null, { status: 204 });
  }),

  http.get('/api/jobs/:id/annotations', ({ params }) => {
    return HttpResponse.json(annotations.get(params.id as string) ?? { notes: '', updated_at: null });
  }),
  http.put('/api/jobs/:id/annotations', async ({ params, request }) => {
    const body = (await request.json()) as { notes: string };
    const a = { notes: body.notes, updated_at: new Date().toISOString() };
    annotations.set(params.id as string, a);
    return HttpResponse.json(a);
  }),

  http.put('/api/jobs/:id/title', async ({ params, request }) => {
    const job = findJob(params.id as string);
    if (!job) return new HttpResponse(null, { status: 404 });
    const body = (await request.json()) as { title: string };
    const original = job.original_title || job.title;
    job.title = body.title.trim() || original;
    if (!job.original_title) job.original_title = original;
    return HttpResponse.json({ title: job.title });
  }),

  http.get('/api/jobs/:id', ({ params }) => {
    const id = params.id as string;
    const job = findJob(id);
    if (job) return HttpResponse.json(job);
    return new HttpResponse(null, { status: 404 });
  }),
  http.get('/api/jobs', ({ request }) => {
    const p = new URL(request.url).searchParams;
    const ct = p.get('content_type');
    const st = p.get('status');
    const limit = Number(p.get('limit') ?? '1000');
    let list = jobs;
    if (ct) list = list.filter((j) => j.content_type === ct);
    if (st) list = list.filter((j) => j.status === st);
    return HttpResponse.json({ items: list.slice(0, limit), total: list.length });
  }),

  http.get('/api/controls/tags', () => HttpResponse.json(tags)),
  http.post('/api/controls/tags', async ({ request }) => {
    const body = (await request.json()) as { name: string; meaning?: string; color: string };
    if (tags.some((t) => t.name.toLowerCase() === body.name.toLowerCase())) {
      return HttpResponse.json({ detail: 'Tag name already exists' }, { status: 409 });
    }
    const tag: Tag = { id: `mock_${Date.now()}`, name: body.name, meaning: body.meaning ?? '', color: body.color };
    tags.push(tag);
    return HttpResponse.json(tag, { status: 201 });
  }),
  http.put('/api/controls/tags/:id', async ({ params, request }) => {
    const t = tags.find((x) => x.id === params.id);
    if (!t) return new HttpResponse(null, { status: 404 });
    const body = (await request.json()) as Partial<Pick<Tag, 'name' | 'meaning' | 'color'>>;
    if (typeof body.name === 'string') {
      if (tags.some((x) => x.id !== t.id && x.name.toLowerCase() === body.name!.toLowerCase())) {
        return HttpResponse.json({ detail: 'Tag name already exists' }, { status: 409 });
      }
      t.name = body.name;
    }
    if (typeof body.meaning === 'string') t.meaning = body.meaning;
    if (typeof body.color === 'string') t.color = body.color;
    return HttpResponse.json(t);
  }),
  http.delete('/api/controls/tags/:id', ({ params }) => {
    const i = tags.findIndex((x) => x.id === params.id);
    if (i >= 0) tags.splice(i, 1);
    // Drop attachments to the deleted tag so mock state stays consistent.
    jobTags.forEach((k) => { if (k.endsWith(`:${params.id}`)) jobTags.delete(k); });
    return new HttpResponse(null, { status: 204 });
  }),
  http.post('/api/controls/tags/:id/pin', ({ params }) => {
    const t = tags.find((x) => x.id === params.id);
    if (!t) return new HttpResponse(null, { status: 404 });
    t.pinned = true;
    return HttpResponse.json(t);
  }),
  http.delete('/api/controls/tags/:id/pin', ({ params }) => {
    const t = tags.find((x) => x.id === params.id);
    if (!t) return new HttpResponse(null, { status: 404 });
    t.pinned = false;
    return HttpResponse.json(t);
  }),

  http.get('/api/templates', () => HttpResponse.json(templates)),
  http.post('/api/templates', async ({ request }) => {
    const body = (await request.json()) as { name: string; description?: string; extra_instructions?: string };
    if (templates.some((t) => !t.is_builtin && t.name === body.name)) {
      return HttpResponse.json({ detail: 'Template name already exists' }, { status: 409 });
    }
    const t: Template = { id: `mock_${Date.now()}`, name: body.name, description: body.description ?? '', extra_instructions: body.extra_instructions ?? '', is_builtin: false };
    templates.push(t);
    return HttpResponse.json(t, { status: 201 });
  }),
  http.put('/api/templates/:name', async ({ params, request }) => {
    const t = templates.find((x) => x.name === params.name && !x.is_builtin);
    if (!t) return new HttpResponse(null, { status: 404 });
    const body = (await request.json()) as Partial<Pick<Template, 'description' | 'extra_instructions'>>;
    if (typeof body.description === 'string') t.description = body.description;
    if (typeof body.extra_instructions === 'string') t.extra_instructions = body.extra_instructions;
    t.updated_at = new Date().toISOString();
    return HttpResponse.json(t);
  }),
  http.delete('/api/templates/:name', ({ params }) => {
    const i = templates.findIndex((x) => x.name === params.name && !x.is_builtin);
    if (i >= 0) templates.splice(i, 1);
    return new HttpResponse(null, { status: 204 });
  }),
];
}
