import { expect, test } from 'vitest'
import type { Whiteboard } from '../api.ts'
import { revealWhiteboard, visibleReply } from './reveal.ts'

const drawing: Whiteboard = {
  version: 2,
  id: 'wb-1',
  session_id: 'session-1',
  steps: [
    {
      id: 'step-1',
      reply_part: '[[step:step-1]]',
      elements: [
        {
          id: 'rect-1',
          kind: 'rectangle',
          author: 'agent',
          position: { x: 10, y: 20 },
          size: { width: 80, height: 40 },
          style: { stroke: '#1f3a5f', fill: '#f4efe6', stroke_width: 2 },
        },
      ],
    },
    {
      id: 'step-2',
      reply_part: '[[step:step-2]]',
      elements: [
        {
          id: 'rect-2',
          kind: 'rectangle',
          author: 'agent',
          position: { x: 120, y: 20 },
          size: { width: 80, height: 40 },
          style: { stroke: '#1f3a5f', fill: null, stroke_width: 2 },
        },
      ],
    },
  ],
  comments: [
    { id: 'c-whole', author: 'agent', text: 'the whole', element_id: 'rect-1' },
    { id: 'c-part', author: 'agent', text: 'the part', element_id: 'rect-2' },
    { id: 'c-here', author: 'agent', text: 'over here', position: { x: 4, y: 8 } },
  ],
}

function stepIds(raw: string, phase: 'streaming' | 'stopped' | 'done'): string[] {
  return revealWhiteboard(drawing, raw, phase)?.steps.map((step) => step.id) ?? []
}

test('steps follow the text', () => {
  // Scenario: steps follow the text [WB-06]
  expect(stepIds('', 'streaming')).toEqual([])
  expect(stepIds('[[step:step-1]] The left box is the whole.', 'streaming')).toEqual(['step-1'])
  expect(
    stepIds('[[step:step-1]] The left box is the whole. [[step:step-2]] The right box is one part.', 'streaming'),
  ).toEqual(['step-1', 'step-2'])
})

test('a step never appears before its text', () => {
  expect(stepIds('The left box is the whole.', 'streaming')).toEqual([])
  expect(stepIds('[[step:step-2]] The right box comes first in the reply.', 'streaming')).toEqual([])
})

test('a marker split across chunks does not unlock early', () => {
  let raw = ''
  raw += '[[step:ste'
  expect(stepIds(raw, 'streaming')).toEqual([])
  raw += 'p-1]] The left box is the whole.'
  expect(stepIds(raw, 'streaming')).toEqual(['step-1'])
})

test('a later step waits until the earlier step unlocks', () => {
  const early = '[[step:step-2]] then [[step:step-1]]'
  expect(stepIds('[[step:step-2]]', 'streaming')).toEqual([])
  expect(stepIds(early, 'streaming')).toEqual(['step-1', 'step-2'])
})

test('missing markers still show every step when the reply is done', () => {
  expect(stepIds('The reply ended without a marker.', 'done')).toEqual(['step-1', 'step-2'])
  expect(stepIds('', 'done')).toEqual(['step-1', 'step-2'])
})

test('a stopped turn does not flush hidden steps', () => {
  expect(stepIds('[[step:step-1]] The left box is the whole.', 'stopped')).toEqual(['step-1'])
  expect(stepIds('The learner stopped first.', 'stopped')).toEqual([])
})

test('a comment appears with its step', () => {
  const first = revealWhiteboard(drawing, '[[step:step-1]] The left box.', 'streaming')
  expect(first?.comments.map((comment) => comment.id)).toEqual(['c-whole', 'c-here'])

  const both = revealWhiteboard(
    drawing,
    '[[step:step-1]] The left box. [[step:step-2]] The right box.',
    'streaming',
  )
  expect(both?.comments.map((comment) => comment.id)).toEqual(['c-whole', 'c-part', 'c-here'])
})

test('the learner does not read the marker', () => {
  expect(visibleReply('[[step:step-1]] The left box is the whole.', true)).toBe(
    'The left box is the whole.',
  )
  expect(visibleReply('See [[step:step-2]] the part.', true)).toBe('See the part.')
  expect(visibleReply('[[step:ste', true)).toBe('')
  expect(visibleReply('[[step:step-1]] The left box is the whole.', false)).toBe(
    'The left box is the whole.',
  )
})
