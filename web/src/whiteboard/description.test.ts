import { expect, test } from 'vitest'
import type { Whiteboard } from '../api.ts'
import { readableDescription } from './description.ts'
import { formulaWhiteboard } from './formulaWhiteboard.ts'
import { graphWhiteboard } from './graphWhiteboard.ts'
import { sampleWhiteboard } from './sampleWhiteboard.ts'

test('an older drawing is named from its shapes and learner additions', () => {
  expect(readableDescription(sampleWhiteboard)).toBe(
    'A rectangle, an ellipse, an arrow, a line, text reading "half", a freehand line, and a rectangle. Learner added 2 shapes: an ellipse, a rectangle.',
  )
})

test('learner changes are appended to the stored description', () => {
  const agent = sampleWhiteboard.steps[0].elements[0]
  const whiteboard: Whiteboard = {
    version: 4,
    id: 'wb-1',
    session_id: 'session-1',
    description: 'Two boxes show one half of a whole.',
    comments: [{ id: 'comment-1', author: 'learner', text: 'my answer', element_id: 'box-2' }],
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [agent, { ...agent, id: 'box-2', author: 'learner' }],
      },
    ],
  }

  expect(readableDescription(whiteboard)).toBe(
    'Two boxes show one half of a whole. Learner added 1 shape and 1 comment: a rectangle, "my answer".',
  )
})

test('each formula and code block adds a readable line', () => {
  expect(readableDescription(formulaWhiteboard)).toBe(
    'The area of a circle.\nmath formula: A = \\pi r^{2}\ncode block in python, 2 lines',
  )
})

test('each graph adds a readable line', () => {
  expect(readableDescription(graphWhiteboard)).toBe(
    'A straight line.\ngraph of y = 2*x+1 from 0 to 2',
  )
  const mixed: Whiteboard = {
    ...graphWhiteboard,
    steps: [
      {
        ...graphWhiteboard.steps[0],
        elements: [
          {
            ...graphWhiteboard.steps[0].elements[0],
            series: [
              { expression: '2*x+1', sample_count: 2, plotted: [{ x: 0, y: 1 }, { x: 2, y: 5 }] },
              { points: [{ x: 0, y: 42.25 }, { x: 2, y: 1 }], plotted: [{ x: 0, y: 42.25 }, { x: 2, y: 1 }] },
            ],
          },
        ],
      },
    ],
  }
  expect(readableDescription(mixed)).toBe('A straight line.\ngraph with 2 series from 0 to 2')
})

test('a labeled box is read with its label', () => {
  const whiteboard: Whiteboard = {
    version: 7,
    id: 'wb-label',
    session_id: 'session-1',
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [
          {
            id: 'box',
            kind: 'rectangle',
            author: 'agent',
            position: { x: 0, y: 0 },
            size: { width: 100, height: 60 },
            style: { stroke: '#1d1d1d', fill: null, stroke_width: 2 },
            label: 'Heat',
          },
        ],
      },
    ],
    comments: [],
  }

  expect(readableDescription(whiteboard)).toBe('A rectangle labeled "Heat".')
})
