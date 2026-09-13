import { inferContentTypeFromUrl } from '@/lib/infer-content-type';

/** POST /api/jobs response shape, as loosely typed as the JSON it actually returns. */
export interface SubmittedJob {
  id?: string;
  title?: string;
  content_type?: string;
  status?: string;
}

/** The job the API accepted, timestamped so consumers can react to repeats. */
export interface AcceptedJob {
  id: string | null;
  url: string;
  title: string | null;
  content_type: string;
  status: string;
  at: number;
}

/** Normalizes an accepted response into the row the Feed paints optimistically.
 * `fallbackContentType` wins when the caller already knows what it submitted
 * (the Ingest Link flow always posts `link`); otherwise the URL is read. */
export function toAcceptedJob(
  data: SubmittedJob,
  url: string,
  fallbackContentType?: string,
): AcceptedJob {
  return {
    id: typeof data.id === 'string' && data.id ? data.id : null,
    url,
    title: typeof data.title === 'string' ? data.title : null,
    content_type:
      fallbackContentType ??
      (typeof data.content_type === 'string'
        ? data.content_type
        : inferContentTypeFromUrl(url)),
    status: typeof data.status === 'string' ? data.status : 'pending',
    at: Date.now(),
  };
}
