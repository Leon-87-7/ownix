import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
  isSafeHttpUrl,
  downloadMarkdownFile,
  ENRICHMENT_FIELDS,
  SHORT_FIELDS,
  stripMarkdown,
  isSpeakable,
} from '@/lib/job-detail-utils'

// --- downloadMarkdownFile ---

describe('downloadMarkdownFile', () => {
  beforeEach(() => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:download')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('creates an object URL, clicks a download anchor with the given filename, then revokes it', () => {
    downloadMarkdownFile('job-notes.md', '# Notes')

    expect(URL.createObjectURL).toHaveBeenCalledOnce()
    const blob = vi.mocked(URL.createObjectURL).mock.calls[0][0] as Blob
    expect(blob.type).toBe('text/markdown;charset=utf-8')

    const clickMock = vi.mocked(HTMLAnchorElement.prototype.click)
    expect(clickMock).toHaveBeenCalledOnce()
    const anchor = clickMock.mock.instances[0] as HTMLAnchorElement
    expect(anchor.download).toBe('job-notes.md')
    expect(anchor.href).toContain('blob:download')

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:download')
  })
})

// --- field config ---

describe('ENRICHMENT_FIELDS / SHORT_FIELDS', () => {
  it('has the exact key/label/render shape long-form jobs render', () => {
    expect(ENRICHMENT_FIELDS).toEqual([
      { key: 'transcript', label: 'Transcript', render: 'text' },
      { key: 'links', label: 'Links Found', render: 'links' },
      { key: 'ai_topic', label: 'Topic', render: 'text' },
      { key: 'ai_objective', label: 'Objective', render: 'text' },
      { key: 'ai_action_points', label: 'Action Points', render: 'list' },
      { key: 'ai_tools', label: 'Tools', render: 'list' },
      { key: 'ai_market_data', label: 'Market Data', render: 'text' },
      { key: 'promise_gap', label: 'Promise Gap', render: 'json' },
      { key: 'template_analysis', label: 'Template Analysis', render: 'json' },
    ])
  })

  it('has the exact key/label/render shape short-pipeline jobs render', () => {
    expect(SHORT_FIELDS).toEqual([
      { key: 'summary', label: 'Summary', render: 'text' },
      { key: 'transcript', label: 'Transcript', render: 'text' },
      { key: 'code', label: 'Code', render: 'code' },
      { key: 'links', label: 'Links Found', render: 'links' },
    ])
  })
})

// --- isSafeHttpUrl ---

describe('isSafeHttpUrl', () => {
  it('accepts an http URL', () => expect(isSafeHttpUrl('http://example.com')).toBe(true))
  it('accepts an https URL', () => expect(isSafeHttpUrl('https://example.com')).toBe(true))
  it('accepts an uppercase scheme (case-insensitive)', () =>
    expect(isSafeHttpUrl('HTTPS://example.com')).toBe(true))
  it('rejects javascript: URLs', () => expect(isSafeHttpUrl('javascript:alert(1)')).toBe(false))
  it('rejects data: URLs', () => expect(isSafeHttpUrl('data:text/html,<script>')).toBe(false))
  it('rejects a scheme-less string', () => expect(isSafeHttpUrl('example.com')).toBe(false))
  it('rejects ftp URLs', () => expect(isSafeHttpUrl('ftp://example.com')).toBe(false))
  it('rejects a dangerous scheme even when "http://" appears later in the string', () => {
    // Guards against a regex missing its ^ anchor: a javascript: URL that merely
    // *contains* "http://" must not be treated as safe.
    expect(isSafeHttpUrl('javascript:alert(1)//http://evil.com')).toBe(false)
  })
})

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

  it('parses a JSON array string into items (repo jobs)', () => {
    expect(splitPipes('["Build a CLI", "Write a dashboard"]')).toEqual([
      'Build a CLI',
      'Write a dashboard',
    ])
  })

  it('falls back to pipe splitting on malformed JSON', () => {
    expect(splitPipes('[broken | json')).toEqual(['[broken', 'json'])
  })

  it('ignores a JSON array with items containing pipes', () => {
    expect(splitPipes('["a | b"]')).toEqual(['a | b'])
  })

  it('trims surrounding whitespace before detecting a JSON array', () => {
    expect(splitPipes('  ["a", "b"]  ')).toEqual(['a', 'b'])
  })

  it('trims and drops blank items inside a JSON array', () => {
    expect(splitPipes('[" a ", "", "b "]')).toEqual(['a', 'b'])
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

  it('treats a mixed scalar/object array as an object array once any item is an object', () => {
    const result = arrayToMarkdown([42, { tool: 'hammer' }])
    expect(result).toBe('1. \n2. Tool: hammer')
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

  it('renders a JSON array as markdown', () => {
    expect(templateAnalysisToMarkdown('["a","b"]')).toBe('- a\n- b')
  })

  it('renders a top-level object array without stringifying the objects', () => {
    const result = templateAnalysisToMarkdown(
      JSON.stringify([{ tool: 'hammer' }, { tool: 'saw' }]),
    )
    expect(result).toBe('1. Tool: hammer\n2. Tool: saw')
    expect(result).not.toContain('[object Object]')
  })

  it('stringifies a top-level JSON primitive (not null, not object, not array)', () => {
    expect(templateAnalysisToMarkdown('42')).toBe('42')
    expect(templateAnalysisToMarkdown('"just text"')).toBe('just text')
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

  it('falls back to the raw value when an empty JSON object renders to blank markdown', () => {
    expect(fieldCopyText('{}', 'json')).toBe('{}')
  })

  it('falls back to the raw value when a JSON string primitive is whitespace-only', () => {
    // templateAnalysisToMarkdown('"   "') returns the 3-space string itself (via
    // String(parsed)), which is truthy-but-blank — distinct from a genuinely empty
    // markdown result, so this exercises md.trim() rather than plain truthiness.
    expect(fieldCopyText('"   "', 'json')).toBe('"   "')
  })

  it('falls back to the raw value when render is "links" and no links parse out', () => {
    expect(fieldCopyText('[]', 'links')).toBe('[]')
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

  it('returns an empty array when the top-level JSON value is not an array', () => {
    expect(parseLinks('{}')).toEqual([])
  })

  it('drops null, array, and non-object items from the list', () => {
    const withJunk = JSON.stringify([
      null,
      ['nested', 'array'],
      { url: 'https://example.com/kept' },
    ])
    expect(parseLinks(withJunk)).toEqual([{ url: 'https://example.com/kept' }])
  })

  it('defaults non-string url/label/description fields', () => {
    const oddTypes = JSON.stringify([{ url: 123, label: 456, description: true }])
    expect(parseLinks(oddTypes)).toEqual([])
  })

  it('accepts an uppercase-scheme URL (case-insensitive match)', () => {
    const upper = JSON.stringify([{ url: 'HTTPS://example.com/caps' }])
    expect(parseLinks(upper)).toEqual([{ url: 'HTTPS://example.com/caps' }])
  })

  it('accepts a plain http (non-s) URL', () => {
    const plainHttp = JSON.stringify([{ url: 'http://example.com/plain' }])
    expect(parseLinks(plainHttp)).toEqual([{ url: 'http://example.com/plain' }])
  })

  it('rejects a link whose url merely contains "http://" without starting with it', () => {
    // Same anchor-regex guard as isSafeHttpUrl, duplicated in this file's own filter.
    const sneaky = JSON.stringify([{ url: 'javascript:alert(1)//http://evil.com' }])
    expect(parseLinks(sneaky)).toEqual([])
  })

  it('trims whitespace around url/label/description', () => {
    const padded = JSON.stringify([
      { url: '  https://example.com/pad  ', label: '  Padded  ', description: '  desc  ' },
    ])
    expect(parseLinks(padded)).toEqual([
      { url: 'https://example.com/pad', label: 'Padded', description: 'desc' },
    ])
  })

  it('renders a link with no description on a single line', () => {
    const noDescription = JSON.stringify([{ url: 'https://example.com/x', label: 'X' }])
    expect(linksToMarkdown(noDescription)).toBe('- [X](https://example.com/x)')
  })

  it('joins multiple links with a newline', () => {
    const two = JSON.stringify([
      { url: 'https://example.com/a', label: 'A' },
      { url: 'https://example.com/b', label: 'B' },
    ])
    expect(linksToMarkdown(two)).toBe(
      '- [A](https://example.com/a)\n- [B](https://example.com/b)',
    )
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
    code: null,
    code_lang: null,
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

  it('omits a field whose value is whitespace-only', () => {
    const md = buildMarkdown({ ...baseJob, ai_topic: '   ' })
    expect(md).not.toContain('## Topic')
  })

  it('omits a field whose value is undefined', () => {
    const md = buildMarkdown({ ...baseJob, ai_topic: undefined } as JobDetail)
    expect(md).not.toContain('## Topic')
  })

  it('joins sections with a blank line between them', () => {
    const md = buildMarkdown(baseJob)
    expect(md).toContain('## Topic\nFinance\n\n## Objective\nLearn investing')
  })
})

describe('stripMarkdown', () => {
  it('strips heading markers', () => expect(stripMarkdown('### Heading')).toBe('Heading'))
  it('strips bullet markers', () => expect(stripMarkdown('- One\n* Two\n+ Three')).toBe('One. Two. Three'))
  it('strips numbered-list markers', () => expect(stripMarkdown('1. One\n2. Two')).toBe('One. Two'))
  it('strips bold asterisks', () => expect(stripMarkdown('**bold**')).toBe('bold'))
  it('strips bold underscores', () => expect(stripMarkdown('__bold__')).toBe('bold'))
  it('strips italic asterisks', () => expect(stripMarkdown('*italic*')).toBe('italic'))
  it('strips italic underscores', () => expect(stripMarkdown('_italic_')).toBe('italic'))
  it('strips inline-code backticks', () => expect(stripMarkdown('Use `npm test` now')).toBe('Use npm test now'))
  it('replaces links with their labels', () => expect(stripMarkdown('[Ownix](https://ownix.dev)')).toBe('Ownix'))
  it('joins non-blank lines with sentence separators', () => expect(stripMarkdown('One\n\nTwo')).toBe('One. Two'))
  it('does not strip a mid-line hyphen', () => expect(stripMarkdown('well-known fact')).toBe('well-known fact'))
  it('does not strip an unpaired asterisk', () => expect(stripMarkdown('value * unknown')).toBe('value * unknown'))
  it('does not strip a non-list-marker number', () => expect(stripMarkdown('2026 results')).toBe('2026 results'))
  it('strips a numbered marker before bold markup', () => expect(stripMarkdown('1. **First**')).toBe('First'))
  it('does not strip underscores from a snake_case identifier', () => expect(stripMarkdown('foo_bar_baz')).toBe('foo_bar_baz'))
  it('does not strip underscores from a snake_case file name', () => expect(stripMarkdown('see my_file_name.py')).toBe('see my_file_name.py'))
})

describe('isSpeakable', () => {
  it.each([
    ['text', true],
    ['list', true],
    ['json', true],
    ['links', false],
    ['code', false],
  ] as const)('returns %s for %s fields', (render, expected) => {
    expect(isSpeakable(render)).toBe(expected)
  })
})
