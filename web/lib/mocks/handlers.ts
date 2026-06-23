import { http, HttpResponse } from 'msw';
import seed from './seed.json';

// In-memory state seeded from a real DB snapshot. Mutations (tag attach/detach,
// create tag, annotations) persist for the browser session only.
interface Job { id: string; content_type: string; status: string; [k: string]: unknown }
interface Tag { id: string; name: string; meaning: string; color: string }
interface Template { id: string; name: string; description: string; extra_instructions: string; is_builtin: boolean; created_at?: string; updated_at?: string }

const jobs = seed.jobs as unknown as Job[];
const tags = (seed.tags as Tag[]).slice();
const jobTags = new Set(
  (seed.job_tags as { job_id: string; tag_id: string }[]).map((jt) => `${jt.job_id}:${jt.tag_id}`),
);
const templates: Template[] = [
  { id: 'b1', name: 'summary', description: 'Concise summary of the video', extra_instructions: '', is_builtin: true },
  { id: 'b2', name: 'transcript', description: 'Full transcript with timestamps', extra_instructions: '', is_builtin: true },
  { id: 'b3', name: 'keypoints', description: 'Bullet-point key takeaways', extra_instructions: '', is_builtin: true },
  { id: 'u1', name: 'startup-notes', description: 'Founder takeaways', extra_instructions: 'Extract actionable startup lessons and growth tactics mentioned in the video.', is_builtin: false },
];
const annotations = new Map<string, { notes: string; updated_at: string | null }>(
  (seed.annotations as { job_id: string; notes: string; updated_at: string | null }[]).map((a) => [
    a.job_id,
    { notes: a.notes, updated_at: a.updated_at },
  ]),
);

// Order matters: more specific paths first (`/api/jobs/:id` also matches `/api/jobs/stats`).
export const handlers = [
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

  http.get('/api/jobs/:id', ({ params }) => {
    const job = jobs.find((j) => j.id === params.id);
    return job ? HttpResponse.json(job) : new HttpResponse(null, { status: 404 });
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
    Object.assign(t, await request.json(), { updated_at: new Date().toISOString() });
    return HttpResponse.json(t);
  }),
  http.delete('/api/templates/:name', ({ params }) => {
    const i = templates.findIndex((x) => x.name === params.name && !x.is_builtin);
    if (i >= 0) templates.splice(i, 1);
    return new HttpResponse(null, { status: 204 });
  }),
];
