import { afterEach, expect, test, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ReplyText } from './ReplyText.tsx'
import { parseReply } from './replyBlocks.ts'
import { AnimationCard } from './AnimationCard.tsx'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('a reply is split into headings, steps, lists, paragraphs and code', () => {
  const blocks = parseReply(
    [
      '## Fractions',
      'A fraction is one part',
      'of a whole.',
      '',
      '1. Cut the cake.',
      '2. Take one piece.',
      '   It is a slice.',
      '',
      '- top',
      '- bottom',
      '',
      '```python',
      'print(1 / 2)',
      '```',
    ].join('\n'),
  )
  expect(blocks).toEqual([
    { kind: 'heading', text: 'Fractions' },
    { kind: 'paragraph', lines: ['A fraction is one part', 'of a whole.'] },
    { kind: 'list', ordered: true, start: 1, items: ['Cut the cake.', 'Take one piece. It is a slice.'] },
    { kind: 'list', ordered: false, start: 1, items: ['top', 'bottom'] },
    { kind: 'code', language: 'python', code: 'print(1 / 2)' },
  ])
})

test('an unfinished code block while streaming keeps the rest as code', () => {
  expect(parseReply('```\nx = 1')).toEqual([{ kind: 'code', language: '', code: 'x = 1' }])
})

test('the reply renders real headings, numbered steps, bold and code', () => {
  render(<ReplyText text={'# Steps\n\n1. Find the **top** number.\n2. Run `half()`.'} />)
  expect(screen.getByRole('heading', { name: 'Steps' })).toBeTruthy()
  const items = screen.getAllByRole('listitem')
  expect(items).toHaveLength(2)
  expect(screen.getByText('top').tagName).toBe('STRONG')
  expect(screen.getByText('half()').tagName).toBe('CODE')
})

test('single stars and maths are left as text, never italic', () => {
  render(<ReplyText text={'Use *care* with 2*3*4.'} />)
  expect(screen.getByText('Use care with 2*3*4.')).toBeTruthy()
  expect(document.querySelector('em')).toBeNull()
})

test('only web links become links, and they open outside', () => {
  render(<ReplyText text={'See [the notes](https://example.org/a) or [this](javascript:alert(1)).'} />)
  const link = screen.getByRole('link', { name: /the notes/ })
  expect(link.getAttribute('href')).toBe('https://example.org/a')
  expect(link.getAttribute('target')).toBe('_blank')
  expect(screen.getAllByRole('link')).toHaveLength(1)
})

test('raw HTML in a reply stays text', () => {
  render(<ReplyText text={'<img src=x onerror=alert(1)>'} />)
  expect(document.querySelector('img')).toBeNull()
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeTruthy()
})

test('quotes, callouts, tables and maths become their own blocks', () => {
  const blocks = parseReply(
    [
      '> A quote',
      '',
      '> [!TIP] Draw it first.',
      '> Then label it.',
      '',
      '| Name | Value |',
      '|:-----|------:|',
      '| half | 0.5 |',
      '| third |',
      '',
      '$$',
      '\\frac{1}{2}',
      '$$',
      '\\[ x^2 \\]',
    ].join('\n'),
  )
  expect(blocks).toEqual([
    { kind: 'quote', blocks: [{ kind: 'paragraph', lines: ['A quote'] }] },
    { kind: 'callout', tone: 'tip', blocks: [{ kind: 'paragraph', lines: ['Draw it first.', 'Then label it.'] }] },
    {
      kind: 'table',
      align: ['left', 'right'],
      header: ['Name', 'Value'],
      rows: [
        ['half', '0.5'],
        ['third', ''],
      ],
    },
    { kind: 'math', tex: '\\frac{1}{2}' },
    { kind: 'math', tex: 'x^2' },
  ])
})

test('a table row without its delimiter yet stays a paragraph while streaming', () => {
  expect(parseReply('| Name | Value |')).toEqual([{ kind: 'paragraph', lines: ['| Name | Value |'] }])
})

test('code in a named language gets syntax colors, other code stays plain', () => {
  render(<ReplyText text={'```python\ndef half(x):\n    return x / 2  # cut\n```\n\n```\ndef plain(): pass\n```'} />)
  const [python, plain] = Array.from(document.querySelectorAll('pre code'))
  expect(python.querySelector('.hljs-keyword')?.textContent).toBe('def')
  expect(python.querySelector('.hljs-comment')?.textContent).toBe('# cut')
  expect(python.textContent).toBe('def half(x):\n    return x / 2  # cut')
  expect(plain.querySelector('span')).toBeNull()
})

test('key terms, struck text, callouts and number cells render with their own look', () => {
  render(
    <ReplyText
      text={[
        'A ==fraction== is ~~two~~ one part.',
        '',
        '> [!WARNING]',
        '> Check the bottom number.',
        '',
        '| Part | Size |',
        '|---|---|',
        '| top | 1 |',
      ].join('\n')}
    />,
  )
  const term = screen.getByText('fraction')
  expect(term.tagName).toBe('STRONG')
  expect(term.className).toBe('reply-key')
  expect(screen.getByText('two').tagName).toBe('S')
  expect(screen.getByText('Warning').closest('.reply-callout--warning')).toBeTruthy()
  expect(screen.getByRole('columnheader', { name: 'Size' })).toBeTruthy()
  expect(screen.getByRole('cell', { name: '1' }).className).toBe('reply-number')
  expect(screen.getByRole('cell', { name: 'top' }).className).toBe('')
})

test('maths renders with KaTeX, and dollar amounts stay text', () => {
  render(<ReplyText text={'So $x^2$ grows. It costs $5 and $10, or \\$3.'} />)
  expect(document.querySelectorAll('.reply-math .katex')).toHaveLength(1)
  expect(document.querySelector('.reply')?.textContent).toContain('It costs $5 and $10, or $3.')
})

test('maths KaTeX cannot read is shown as its source', () => {
  render(<ReplyText text={'$$\n\\frac{1}{\n$$'} />)
  expect(document.querySelector('.katex')).toBeNull()
  expect(screen.getByText('\\frac{1}{')).toBeTruthy()
})

test('a running animation says it is in progress and checks the job again', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ id: 'job-1', kind: 'animation', session_id: 's-1', status: 'ready' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  const onOpen = vi.fn()
  render(
    <AnimationCard
      job={{ id: 'job-1', kind: 'animation', session_id: 's-1', status: 'running' }}
      onOpen={onOpen}
    />,
  )
  expect(screen.getByText('Animation')).toBeTruthy()
  expect(screen.getByText('In progress')).toBeTruthy()

  await act(async () => {
    await vi.advanceTimersByTimeAsync(10_000)
  })
  expect(fetchMock).toHaveBeenCalledWith('/api/sessions/s-1/jobs/job-1', expect.anything())
  expect(screen.queryByText('In progress')).toBeNull()
  expect(screen.getByRole('button', { name: /Open animation/ })).toBeTruthy()
})

test('a ready animation opens from the card', () => {
  const onOpen = vi.fn()
  render(
    <AnimationCard
      job={{ id: 'job-1', kind: 'animation', session_id: 's-1', status: 'ready' }}
      onOpen={onOpen}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: /Open animation/ }))
  expect(onOpen).toHaveBeenCalledWith('s-1', 'job-1')
})
