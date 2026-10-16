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
