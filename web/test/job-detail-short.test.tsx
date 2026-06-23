/**
 * Tests for issues #164/#213: short-pipeline job detail rendering.
 *
 * Verifies that:
 * - SHORT_FIELDS contains the expected short-specific field keys
 * - buildMarkdown uses SHORT_FIELDS for short jobs and ENRICHMENT_FIELDS for long/article
 * - The detail page renders short-specific fields for content_type === 'short'
 * - The detail page still renders long enrichment fields for content_type === 'long'
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'

import {
  SHORT_FIELDS,
  ENRICHMENT_FIELDS,
  buildMarkdown,
  isEmpty,
} from '@/lib/job-detail-utils'
import type { JobDetail } from '@/lib/hooks/useJobDetail'

// ---------------------------------------------------------------------------
// SHORT_FIELDS shape tests
// ---------------------------------------------------------------------------

describe('SHORT_FIELDS', () => {
  it('contains summary, transcript, links', () => {
    const keys = SHORT_FIELDS.map((f) => f.key)
    expect(keys).toEqual(['summary', 'transcript', 'links'])
    expect(keys).not.toContain('key_phrases')
  })

  it('does NOT contain long-enrichment keys', () => {
    const keys = SHORT_FIELDS.map((f) => f.key)
    expect(keys).not.toContain('ai_topic')
    expect(keys).not.toContain('ai_objective')
    expect(keys).not.toContain('promise_gap')
    expect(keys).not.toContain('template_analysis')
  })

  it('renders links with the links renderer', () => {
    const linksField = SHORT_FIELDS.find((f) => f.key === 'links')
    expect(linksField?.label).toBe('Links Found')
    expect(linksField?.render).toBe('links')
  })
})

// ---------------------------------------------------------------------------
// ENRICHMENT_FIELDS unchanged
// ---------------------------------------------------------------------------

describe('ENRICHMENT_FIELDS (long/article schema unchanged)', () => {
  it('still has all long enrichment keys', () => {
    const keys = ENRICHMENT_FIELDS.map((f) => f.key)
    expect(keys).toContain('ai_topic')
    expect(keys).toContain('ai_objective')
    expect(keys).toContain('ai_action_points')
    expect(keys).toContain('ai_tools')
    expect(keys).toContain('ai_market_data')
    expect(keys).toContain('promise_gap')
    expect(keys).toContain('template_analysis')
  })

  it('does NOT contain short-specific keys', () => {
    const keys = ENRICHMENT_FIELDS.map((f) => f.key)
    expect(keys).not.toContain('summary')
    expect(keys).not.toContain('transcript')
    expect(keys).not.toContain('key_phrases')
    expect(keys).not.toContain('links')
  })
})

// ---------------------------------------------------------------------------
// buildMarkdown — content_type-aware
// ---------------------------------------------------------------------------

const baseJob: JobDetail = {
  id: 'job1',
  url: 'https://youtube.com/shorts/abc',
  content_type: 'short',
  status: 'done',
  title: 'Test Short',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:01:00Z',
  completed_at: '2026-01-01T00:01:00Z',
  error_msg: null,
  drive_url: null,
  // short fields
  summary: 'A short clip about Python.',
  transcript: 'Hello world this is a transcript.',
  links: '[{"url":"https://python.org","label":"Python","description":"Official site"}]',
  // long fields (present in DB but should NOT appear in short markdown)
  ai_topic: 'Some topic',
  ai_objective: null,
  ai_action_points: null,
  ai_tools: null,
  ai_market_data: null,
  promise_gap: null,
  template: null,
  template_analysis: null,
}

describe('buildMarkdown', () => {
  it('uses SHORT_FIELDS for short jobs', () => {
    const md = buildMarkdown(baseJob)
    expect(md).toContain('## Summary')
    expect(md).toContain('A short clip about Python.')
    expect(md).toContain('## Transcript')
    expect(md).toContain('Hello world this is a transcript.')
    expect(md).toContain('## Links Found')
    expect(md).toContain('[Python](https://python.org)')
  })

  it('does NOT include long-enrichment headings for short jobs', () => {
    const md = buildMarkdown(baseJob)
    expect(md).not.toContain('## Topic')
    expect(md).not.toContain('Some topic')
    expect(md).not.toContain('## Objective')
  })

  it('uses ENRICHMENT_FIELDS for long jobs', () => {
    const longJob: JobDetail = {
      ...baseJob,
      content_type: 'long',
      url: 'https://youtube.com/watch?v=abc',
      ai_topic: 'Long video topic',
      ai_objective: 'Understand the topic',
      promise_gap: null,
      summary: null,
      transcript: null,
      links: null,
    }
    const md = buildMarkdown(longJob)
    expect(md).toContain('## Topic')
    expect(md).toContain('Long video topic')
    expect(md).toContain('## Objective')
    expect(md).not.toContain('## Summary')
    expect(md).not.toContain('## Transcript')
  })

  it('uses ENRICHMENT_FIELDS for article jobs', () => {
    const articleJob: JobDetail = {
      ...baseJob,
      content_type: 'article',
      url: 'https://example.com/article',
      ai_topic: 'Article topic',
      summary: null,
      transcript: null,
      links: null,
    }
    const md = buildMarkdown(articleJob)
    expect(md).toContain('## Topic')
    expect(md).not.toContain('## Summary')
  })

  it('gracefully handles null short fields (old jobs pre-migration)', () => {
    const nullShortJob: JobDetail = {
      ...baseJob,
      summary: null,
      transcript: null,
      links: null,
    }
    // Should not throw; just produces title + url
    const md = buildMarkdown(nullShortJob)
    expect(md).toContain('# Test Short')
    expect(md).not.toContain('## Summary')
    expect(md).not.toContain('## Transcript')
  })
})

// ---------------------------------------------------------------------------
// FieldCard / page integration: short fields render, long fields do not
// ---------------------------------------------------------------------------

// We test at the utils level since the page uses next/dynamic (SSR:false).
// The detail page's `fieldSet` logic is:
//   const fieldSet = job.content_type === 'short' ? SHORT_FIELDS : ENRICHMENT_FIELDS
//   const presentFields = fieldSet.filter(({ key }) => job[key] != null && ...)
// We verify the field selection logic here.

describe('Detail page field selection logic (unit)', () => {
  function selectPresentFields(
    job: JobDetail,
    fieldSet: typeof SHORT_FIELDS,
  ) {
    return fieldSet.filter(({ key }) => {
      const value = job[key]
      return value !== null && value !== undefined && String(value).trim() !== ''
    })
  }

  it('shows summary/transcript/links for a short job with data', () => {
    const fields = selectPresentFields(baseJob, SHORT_FIELDS)
    const keys = fields.map((f) => f.key)
    expect(keys).toContain('summary')
    expect(keys).toContain('transcript')
    expect(keys).toContain('links')
    expect(keys).not.toContain('key_phrases')
  })

  it('shows nothing for a short job where all short fields are null', () => {
    const emptyShort: JobDetail = { ...baseJob, summary: null, transcript: null, links: null }
    const fields = selectPresentFields(emptyShort, SHORT_FIELDS)
    expect(fields).toHaveLength(0)
  })

  it('shows ai_topic for a long job', () => {
    const longJob: JobDetail = { ...baseJob, content_type: 'long', ai_topic: 'Topic' }
    const fields = selectPresentFields(longJob, ENRICHMENT_FIELDS)
    expect(fields.map((f) => f.key)).toContain('ai_topic')
  })

  it('long job does not show short-specific fields even if non-null', () => {
    // If summary somehow exists on a long job, ENRICHMENT_FIELDS never selects it
    const longJob: JobDetail = { ...baseJob, content_type: 'long', summary: 'Should not appear' }
    const fields = selectPresentFields(longJob, ENRICHMENT_FIELDS)
    expect(fields.map((f) => f.key)).not.toContain('summary')
  })
})
