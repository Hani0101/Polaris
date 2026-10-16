import { createShapeId } from 'tldraw'
import { expect, test } from 'vitest'
import type { Whiteboard } from '../api.ts'
import { applyLearnerShapes, isCanonicalAgentShape } from './fromTldraw.ts'
import { formulaWhiteboard } from './formulaWhiteboard.ts'
import { graphWhiteboard } from './graphWhiteboard.ts'
import { sampleWhiteboard } from './sampleWhiteboard.ts'
import { whiteboardToShapes } from './toTldraw.ts'

function asLearner(whiteboard: Whiteboard): Whiteboard {
  return {
    ...whiteboard,
    steps: whiteboard.steps.map((step) => ({
      ...step,
      elements: step.elements.map((element) => ({ ...element, author: 'learner' as const })),
    })),
  }
}

test('learner shapes round trip and agent shapes stay as stored', () => {
  const learnerBoard = asLearner(sampleWhiteboard)
  const shapes = whiteboardToShapes(learnerBoard).shapes

  expect(applyLearnerShapes(learnerBoard, shapes)).toEqual(learnerBoard)

  const moved = shapes.map((shape) =>
    shape.meta?.elementId === 'rect-1' ? { ...shape, x: 500, y: 80 } : shape,
  )
  const added = {
    id: 'shape:learnerbox',
    type: 'geo',
    x: 120,
    y: 40,
    meta: { author: 'learner', elementId: 'learner-box' },
    props: {
      geo: 'rectangle',
      w: 20,
      h: 10,
      color: 'black',
      fill: 'none',
      size: 's',
    },
  }
  const next = applyLearnerShapes(sampleWhiteboard, [...moved, added])
  const rect = next.steps[0].elements[0]

  expect(rect).toEqual(sampleWhiteboard.steps[0].elements[0])
  expect(next.steps[1].elements.at(-1)).toMatchObject({
    id: 'learner-box',
    kind: 'rectangle',
    author: 'learner',
    position: { x: 120, y: 40 },
    size: { width: 20, height: 10 },
    style: { stroke: '#1d1d1d', fill: null, stroke_width: 2 },
  })
})

test('a removed learner shape is dropped and agent shapes remain', () => {
  const shapes = whiteboardToShapes(sampleWhiteboard).shapes.filter(
    (shape) => shape.meta?.elementId !== 'ellipse-1',
  )
  const next = applyLearnerShapes(sampleWhiteboard, shapes)
  const ids = next.steps.flatMap((step) => step.elements.map((element) => element.id))

  expect(ids).not.toContain('ellipse-1')
  expect(ids).toContain('rect-1')
  expect(ids).toContain('rect-2')
})

test('a moved mark stays the stored agent mark', () => {
  const learner = sampleWhiteboard.steps[0].elements[1]
  const marked: Whiteboard = {
    ...sampleWhiteboard,
    version: 3,
    steps: [
      ...sampleWhiteboard.steps,
      {
        id: 'step-mark',
        reply_part: '[[step:step-mark]]',
        elements: [
          {
            id: 'mark-1',
            kind: 'mark',
            mark: 'circle',
            author: 'agent',
            target_element_id: learner.id,
            position: { x: 30, y: 40 },
            size: { width: 100, height: 80 },
            style: learner.style,
          },
        ],
      },
    ],
  }
  const shapes = whiteboardToShapes(marked).shapes.map((shape) =>
    shape.meta?.elementId === 'mark-1' ? { ...shape, x: 400, y: 80 } : shape,
  )
  const next = applyLearnerShapes(marked, shapes)
  const mark = next.steps.at(-1)?.elements[0]

  expect(mark).toEqual(marked.steps.at(-1)?.elements[0])
  expect(next.version).toBe(3)
})

test('a learner edit keeps an agent graph', () => {
  const shapes = whiteboardToShapes(graphWhiteboard).shapes.map((shape) =>
    shape.meta?.elementId === 'graph-1' ? { ...shape, x: 500, y: 80 } : shape,
  )
  const next = applyLearnerShapes(graphWhiteboard, shapes)

  expect(next.steps[0].elements[0]).toEqual(graphWhiteboard.steps[0].elements[0])
  expect(next.version).toBe(6)
  expect(next.description).toBe(graphWhiteboard.description)
  expect(next.simplifies).toBeUndefined()
})

test('a learner edit keeps agent math and code', () => {
  const shapes = whiteboardToShapes(formulaWhiteboard).shapes.map((shape) =>
    shape.meta?.elementId === 'formula-1' ? { ...shape, x: 500, y: 80 } : shape,
  )
  const next = applyLearnerShapes(formulaWhiteboard, shapes)

  expect(next.steps[0].elements[0]).toEqual(formulaWhiteboard.steps[0].elements[0])
  expect(next.steps[0].elements[1]).toEqual(formulaWhiteboard.steps[0].elements[1])
  expect(next.version).toBe(5)
  expect(next.description).toBe(formulaWhiteboard.description)
})

test('a learner edit keeps the link to the original whiteboard', () => {
  const simpler: Whiteboard = {
    ...sampleWhiteboard,
    version: 4,
    id: 'wb-simple',
    description: 'One box stands for the whole.',
    simplifies: 'wb-1',
  }
  const shapes = whiteboardToShapes(simpler).shapes
  expect(applyLearnerShapes(simpler, shapes).simplifies).toBe('wb-1')
})

test('a learner edit keeps the agent description', () => {
  const described: Whiteboard = {
    ...sampleWhiteboard,
    version: 4,
    description: 'Two boxes show one half of a whole.',
  }
  const shapes = whiteboardToShapes(described).shapes
  expect(applyLearnerShapes(described, shapes).description).toBe(described.description)
})

test('only the canonical agent shape is locked', () => {
  const agentIds = new Set(['rect-1'])

  expect(
    isCanonicalAgentShape(
      {
        id: createShapeId('rect-1'),
        type: 'geo',
        x: 10,
        y: 20,
        meta: { author: 'agent', elementId: 'rect-1' },
      },
      agentIds,
    ),
  ).toBe(true)
  expect(
    isCanonicalAgentShape(
      {
        id: createShapeId('copy'),
        type: 'geo',
        x: 10,
        y: 20,
        meta: { author: 'agent', elementId: 'rect-1' },
      },
      agentIds,
    ),
  ).toBe(false)
})
