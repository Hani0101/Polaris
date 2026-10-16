import { expect, test } from 'vitest'
import { turnBody } from '../api.ts'
import { sampleWhiteboard } from './sampleWhiteboard.ts'
import { pointedParts, pointingFromTurn } from './pointing.ts'

test('selected shapes become polaris element ids and labels', () => {
  const parts = pointedParts(sampleWhiteboard, [
    { id: 'shape:tldraw-rect', elementId: 'rect-1' },
    { id: 'shape:text-1', elementId: 'text-1' },
    { id: 'shape:rect-1', elementId: 'rect-1' },
    { id: 'shape:missing', elementId: 'no-such' },
    { id: 'shape:blank' },
  ])

  expect(parts).toEqual([
    { id: 'rect-1', label: 'rectangle' },
    { id: 'text-1', label: 'half' },
  ])
  expect(parts.map((part) => part.id)).not.toContain('shape:tldraw-rect')
})

test('a formula label is the LaTeX and a code label is the language', () => {
  const whiteboard = {
    ...sampleWhiteboard,
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [
          {
            id: 'formula-1',
            kind: 'math' as const,
            author: 'agent' as const,
            latex: 'A = \\pi r^{2}',
            position: { x: 0, y: 0 },
            size: { width: 10, height: 10 },
            style: sampleWhiteboard.steps[0].elements[0].style,
          },
          {
            id: 'snippet-1',
            kind: 'code' as const,
            author: 'agent' as const,
            language: 'python',
            code: 'return 1',
            position: { x: 0, y: 0 },
            size: { width: 10, height: 10 },
            style: sampleWhiteboard.steps[0].elements[0].style,
          },
        ],
      },
    ],
  }

  expect(
    pointedParts(whiteboard, [
      { id: 'shape:formula-1', elementId: 'formula-1' },
      { id: 'shape:snippet-1', elementId: 'snippet-1' },
    ]),
  ).toEqual([
    { id: 'formula-1', label: 'A = \\pi r^{2}' },
    { id: 'snippet-1', label: 'python' },
  ])
})

test('a blank text label falls back to the kind', () => {
  const whiteboard = {
    ...sampleWhiteboard,
    steps: [
      {
        ...sampleWhiteboard.steps[0],
        elements: [
          {
            ...sampleWhiteboard.steps[0].elements[4],
            text: '   ',
          },
        ],
      },
    ],
  }

  expect(pointedParts(whiteboard, [{ id: 'shape:text-1', elementId: 'text-1' }])).toEqual([
    { id: 'text-1', label: 'text' },
  ])
})

test('a stored turn keeps polaris ids and looks up the chip label', () => {
  expect(
    pointingFromTurn(
      { whiteboard_id: 'wb-1', element_ids: ['text-1', 'missing'] },
      [sampleWhiteboard],
    ),
  ).toEqual({
    whiteboardId: 'wb-1',
    parts: [
      { id: 'text-1', label: 'half' },
      { id: 'missing', label: 'missing' },
    ],
  })
})

test('the turn body sends polaris element ids', () => {
  expect(
    turnBody('What is this part?', {
      whiteboardId: 'wb-1',
      parts: [
        { id: 'rect-1', label: 'rectangle' },
        { id: 'text-1', label: 'half' },
      ],
    }),
  ).toEqual({
    message: 'What is this part?',
    pointing: {
      whiteboard_id: 'wb-1',
      element_ids: ['rect-1', 'text-1'],
    },
  })
  expect(turnBody('Hello', null)).toEqual({ message: 'Hello' })
})
