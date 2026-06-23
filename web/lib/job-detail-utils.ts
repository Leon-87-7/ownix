import type { JobDetail } from '@/lib/hooks/useJobDetail'

export type RenderType = 'text' | 'list' | 'json' | 'links'

export const ENRICHMENT_FIELDS: Array<{ key: keyof JobDetail; label: string; render: RenderType }> = [
  { key: 'ai_topic', label: 'Topic', render: 'text' },
  { key: 'ai_objective', label: 'Objective', render: 'text' },
  { key: 'ai_action_points', label: 'Action Points', render: 'list' },
  { key: 'ai_tools', label: 'Tools', render: 'list' },
  { key: 'ai_market_data', label: 'Market Data', render: 'text' },
  { key: 'promise_gap', label: 'Promise Gap', render: 'text' },
  { key: 'template_analysis', label: 'Template Analysis', render: 'json' },
]

/** Field set for short-pipeline jobs (vision summary, transcript, and persisted links). */
export const SHORT_FIELDS: Array<{ key: keyof JobDetail; label: string; render: RenderType }> = [
  { key: 'summary', label: 'Summary', render: 'text' },
  { key: 'transcript', label: 'Transcript', render: 'text' },
  { key: 'links', label: 'Links Found', render: 'links' },
]


export interface JobLink {
  url: string
  label?: string | null
  description?: string | null
}

export function parseLinks(raw: string): JobLink[] {
  let parsed: unknown
  try { parsed = JSON.parse(raw) } catch { return [] }
  if (!Array.isArray(parsed)) return []
  return parsed
    .filter((item): item is Record<string, unknown> => item !== null && typeof item === 'object' && !Array.isArray(item))
    .map((item) => ({
      url: typeof item.url === 'string' ? item.url.trim() : '',
      label: typeof item.label === 'string' ? item.label.trim() : undefined,
      description: typeof item.description === 'string' ? item.description.trim() : undefined,
    }))
    .filter((link) => /^https?:\/\//i.test(link.url))
}

export function linksToMarkdown(raw: string): string {
  return parseLinks(raw)
    .map((link) => {
      const label = link.label || link.url
      const description = link.description ? `\n  ${link.description}` : ''
      return `- [${label}](${link.url})${description}`
    })
    .join('\n')
}

export function splitPipes(value: string): string[] {
  return value.split(' | ').map((s) => s.trim()).filter(Boolean)
}

export function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value as object).length === 0
  return false
}

export function objectToInline(obj: Record<string, unknown>): string {
  return Object.entries(obj)
    .filter(([, v]) => !isEmpty(v))
    .map(([k, v]) => {
      const text = typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)
      return `${humanizeKey(k)}: ${text}`
    })
    .join('; ')
}

export function arrayToMarkdown(arr: unknown[]): string {
  const allScalar = arr.every((v) => typeof v !== 'object' || v === null)
  if (allScalar) return arr.filter((v) => !isEmpty(v)).map((v) => `- ${String(v)}`).join('\n')
  return arr.map((v, i) => `${i + 1}. ${objectToInline(v as Record<string, unknown>)}`).join('\n')
}

export function objectToMarkdown(obj: Record<string, unknown>, level: number): string {
  const heading = '#'.repeat(Math.min(level, 6))
  return Object.entries(obj)
    .filter(([, v]) => !isEmpty(v))
    .map(([key, value]) => {
      const title = `${heading} ${humanizeKey(key)}`
      if (typeof value !== 'object' || value === null) return `${title}\n${String(value)}`
      if (Array.isArray(value)) return `${title}\n${arrayToMarkdown(value)}`
      return `${title}\n${objectToInline(value as Record<string, unknown>)}`
    })
    .join('\n\n')
}

export function templateAnalysisToMarkdown(raw: string): string {
  let parsed: unknown
  try { parsed = JSON.parse(raw) } catch { return raw }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return String(parsed)
  return objectToMarkdown(parsed as Record<string, unknown>, 3)
}

export function fieldCopyText(value: string, render: RenderType): string {
  if (render === 'list') {
    const items = splitPipes(value)
    return items.length ? items.map((i) => `- ${i}`).join('\n') : value
  }
  if (render === 'json') {
    const md = templateAnalysisToMarkdown(value)
    return md.trim() ? md : value
  }
  if (render === 'links') {
    const md = linksToMarkdown(value)
    return md.trim() ? md : value
  }
  return value
}

export function buildMarkdown(job: JobDetail): string {
  const parts: string[] = [`# ${job.title ?? job.url}`, job.url]
  const fields = job.content_type === 'short' ? SHORT_FIELDS : ENRICHMENT_FIELDS
  for (const { key, label, render } of fields) {
    const value = job[key]
    if (value === null || value === undefined || String(value).trim() === '') continue
    const body = fieldCopyText(String(value), render)
    if (body.trim()) parts.push(`## ${label}\n${body}`)
  }
  return parts.join('\n\n')
}
