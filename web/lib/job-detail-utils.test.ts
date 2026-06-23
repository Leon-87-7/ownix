import { describe, expect, it } from 'vitest'
import type { JobDetail } from '@/lib/hooks/useJobDetail'
import {
  splitPipes,
  humanizeKey,
  isEmpty,
  objectToInline,
  arrayToMarkdown,
  objectToMarkdown,
  templateAnalysisToMarkdown,
  fieldCopyText,
  buildMarkdown,
  parseLinks,
  linksToMarkdown,
} from '@/lib/job-detail-utils'

// --- splitPipes ---

describe('splitPipes', () => {
  it('splits a pipe-separated string into trimmed items', () => {
    expect(splitPipes('a | b | c')).toEqual(['a', 'b', 'c'])
  })

  it('trims whitespace around each item', () => {
    expect(splitPipes('  foo  |  bar  ')).toEqual(['foo', 'bar'])
  })

  it('filters out empty segments', () => {
    expect(splitPipes(' | a | ')).toEqual(['a'])
  })

  it('returns a single-item array when there are no pipes', () => {
    expect(splitPipes('only one')).toEqual(['only one'])
  })

  it('returns empty array for a blank string', () => {
    expect(splitPipes('   ')).toEqual([])
  })
})

// --- humanizeKey ---

describe('humanizeKey', () => {
  it('replaces underscores with spaces', () => {
    expect(humanizeKey('hello_world')).toBe('Hello World')
  })

  it('capitalizes the first letter of each word', () => {
    expect(humanizeKey('ai_topic')).toBe('Ai Topic')
  })

  it('leaves a single word as-is except capitalizing it', () => {
    expect(humanizeKey('title')).toBe('Title')
  })

  it('handles already-capitalized input', () => {
    expect(humanizeKey('Already_Done')).toBe('Already Done')
  })
})

// --- isEmpty ---

describe('isEmpty', () => {
  it('returns true for null', () => expect(isEmpty(null)).toBe(true))
  it('returns true for undefined', () => expect(isEmpty(undefined)).toBe(true))
  it('returns true for empty string', () => expect(isEmpty('')).toBe(true))
  it('returns true for whitespace-only string', () => expect(isEmpty('   ')).toBe(true))
  it('returns true for empty array', () => expect(isEmpty([])).toBe(true))
  it('returns true for empty object', () => expect(isEmpty({})).toBe(true))

  it('returns false for a non-empty string', () => expect(isEmpty('x')).toBe(false))
  it('returns false for a non-empty array', () => expect(isEmpty([1])).toBe(false))
  it('returns false for a non-empty object', () => expect(isEmpty({ a: 1 })).toBe(false))
  it('returns false for the number 0', () => expect(isEmpty(0)).toBe(false))
  it('returns false for false', () => expect(isEmpty(false)).toBe(false))
})

// --- objectToInline ---

describe('objectToInline', () => {
  it('formats scalar values as "Key: value" separated by semicolons', () => {
    expect(objectToInline({ foo_bar: 'baz', count: 42 })).toBe('Foo Bar: baz; Count: 42')
  })

  it('skips empty values', () => {
    expect(objectToInline({ a: 'x', b: null, c: '' })).toBe('A: x')
  })

  it('JSON-encodes nested objects', () => {
    const result = objectToInline({ nested: { x: 1 } })
    expect(result).toBe('Nested: {"x":1}')
  })

  it('returns empty string for all-empty object', () => {
    expect(objectToInline({ a: null, b: '' })).toBe('')
  })
})

// --- arrayToMarkdown ---

describe('arrayToMarkdown', () => {
  it('renders scalar array as a markdown bullet list', () => {
    expect(arrayToMarkdown(['alpha', 'beta', 'gamma'])).toBe('- alpha\n- beta\n- gamma')
  })

  it('filters empty scalars', () => {
    expect(arrayToMarkdown(['a', null, '', 'b'])).toBe('- a\n- b')
  })

  it('renders object array as numbered inline entries', () => {
    const result = arrayToMarkdown([{ tool: 'hammer' }, { tool: 'saw' }])
    expect(result).toBe('1. Tool: hammer\n2. Tool: saw')
  })
})

// --- objectToMarkdown ---

describe('objectToMarkdown', () => {
  it('uses ### headings at level 3', () => {
    const result = objectToMarkdown({ my_key: 'value' }, 3)
    expect(result).toBe('### My Key\nvalue')
  })

  it('clamps heading level at 6', () => {
    const result = objectToMarkdown({ x: 'y' }, 10)
    expect(result).toMatch(/^#{6} X/)
  })

  it('renders array values as markdown lists under the heading', () => {
    const result = objectToMarkdown({ items: ['a', 'b'] }, 3)
    expect(result).toBe('### Items\n- a\n- b')
  })

  it('renders nested object values as inline text', () => {
    const result = objectToMarkdown({ config: { key: 'val' } }, 3)
    expect(result).toBe('### Config\nKey: val')
  })

  it('skips empty values', () => {
    const result = objectToMarkdown({ a: 'present', b: null }, 3)
    expect(result).not.toContain('B')
    expect(result).toContain('A')
  })

  it('joins multiple entries with double newlines', () => {
    const result = objectToMarkdown({ a: '1', b: '2' }, 3)
    expect(result).toBe('### A\n1\n\n### B\n2')
  })
})

// --- templateAnalysisToMarkdown ---

describe('templateAnalysisToMarkdown', () => {
  it('converts a JSON object string to markdown', () => {
    const raw = JSON.stringify({ title: 'Hello', points: ['a', 'b'] })
    const result = templateAnalysisToMarkdown(raw)
    expect(result).toContain('### Title')
    expect(result).toContain('Hello')
    expect(result).toContain('### Points')
    expect(result).toContain('- a')
  })

  it('returns the raw string unchanged when JSON is invalid', () => {
    expect(templateAnalysisToMarkdown('not json')).toBe('not json')
  })

  it('returns String(parsed) for non-object JSON (e.g. null)', () => {
    expect(templateAnalysisToMarkdown('null')).toBe('null')
  })

  it('returns String(parsed) for a JSON array', () => {
    expect(templateAnalysisToMarkdown('["a","b"]')).toBe('a,b')
  })
})

// --- fieldCopyText ---

describe('fieldCopyText', () => {
  it('returns the value as-is for render type "text"', () => {
    expect(fieldCopyText('hello world', 'text')).toBe('hello world')
  })

  it('converts pipe-separated value to markdown list for render type "list"', () => {
    expect(fieldCopyText('a | b | c', 'list')).toBe('- a\n- b\n- c')
  })

  it('wraps a single item with no pipes as a bullet', () => {
    expect(fieldCopyText('single', 'list')).toBe('- single')
  })

  it('returns the original value when render is "list" and input is blank', () => {
    expect(fieldCopyText('   ', 'list')).toBe('   ')
  })

  it('converts JSON object to markdown for render type "json"', () => {
    const raw = JSON.stringify({ summary: 'great' })
    const result = fieldCopyText(raw, 'json')
    expect(result).toContain('### Summary')
    expect(result).toContain('great')
  })

  it('falls back to the raw value when json render produces empty markdown', () => {
    expect(fieldCopyText('plain text', 'json')).toBe('plain text')
  })
})


// --- links ---

describe('links helpers', () => {
  const raw = JSON.stringify([
    { url: 'https://example.com/tool', label: 'Example Tool', description: 'A useful tool.' },
    { url: 'ftp://ignored.example.com', label: 'Ignored' },
  ])

  it('parses persisted JSON links and filters invalid URLs', () => {
    expect(parseLinks(raw)).toEqual([
      { url: 'https://example.com/tool', label: 'Example Tool', description: 'A useful tool.' },
    ])
  })

  it('renders links as markdown label plus URL', () => {
    expect(linksToMarkdown(raw)).toBe('- [Example Tool](https://example.com/tool)\n  A useful tool.')
  })

  it('returns an empty array for invalid JSON', () => {
    expect(parseLinks('not json')).toEqual([])
  })

  it('copies link fields as markdown', () => {
    expect(fieldCopyText(raw, 'links')).toBe('- [Example Tool](https://example.com/tool)\n  A useful tool.')
  })
})

// --- buildMarkdown ---

describe('buildMarkdown', () => {
  const baseJob: JobDetail = {
    id: '1',
    url: 'https://example.com/video',
    content_type: 'long',
    status: 'done',
    title: 'My Video',
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
    completed_at: null,
    error_msg: null,
    drive_url: null,
    ai_topic: 'Finance',
    ai_objective: 'Learn investing',
    ai_action_points: 'Read books | Watch videos',
    ai_tools: null,
    ai_market_data: null,
    promise_gap: null,
    template: null,
    template_analysis: null,
    summary: null,
    transcript: null,
    links: null,
  }

  it('starts with a h1 title', () => {
    const md = buildMarkdown(baseJob)
    expect(md).toMatch(/^# My Video/)
  })

  it('uses the URL as the h1 when title is null', () => {
    const md = buildMarkdown({ ...baseJob, title: null })
    expect(md).toMatch(/^# https:\/\/example\.com\/video/)
  })

  it('includes the URL on its own line', () => {
    const md = buildMarkdown(baseJob)
    expect(md).toContain('https://example.com/video')
  })

  it('includes non-null enrichment fields as h2 sections', () => {
    const md = buildMarkdown(baseJob)
    expect(md).toContain('## Topic\nFinance')
    expect(md).toContain('## Objective\nLearn investing')
  })

  it('renders list fields as markdown bullet lists', () => {
    const md = buildMarkdown(baseJob)
    expect(md).toContain('## Action Points\n- Read books\n- Watch videos')
  })

  it('omits null and empty enrichment fields', () => {
    const md = buildMarkdown(baseJob)
    expect(md).not.toContain('## Tools')
    expect(md).not.toContain('## Market Data')
  })
})
