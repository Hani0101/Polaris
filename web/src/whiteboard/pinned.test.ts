import { expect, test } from 'vitest'
import type { Whiteboard } from '../api.ts'
import { applyLearnerShapes } from './fromTldraw.ts'
import { revealAddedSteps } from './reveal.ts'
import { agentAddedLook } from './style.ts'
import { whiteboardToShapes } from './toTldraw.ts'

// A learner board with one learner box, and a step the agent added beside it (WB-20).
const pinned: Whiteboard = {
  version: 7,
  id: 'wb-1',
  session_id: 'session-1',
  description: 'Blank whiteboard',
  steps: [
    {
      id: 'learner',
      reply_part: '[[step:learner]]',
      elements: [
        {
          id: 'learner-box',
          kind: 'rectangle',
          author: 'learner',
          position: { x: 0, y: 0 },
          size: { width: 300, height: 200 },
          style: { stroke: 'blue', fill: null, stroke_width: 2 },
        },
      ],
    },
    {
      id: 'hint',
      reply_part: '[[step:hint]]',
      extension: true,
      elements: [
        {
          id: 'hint-box',
          kind: 'rectangle',
          author: 'agent',
          position: { x: 380, y: 0 },
          size: { width: 200, height: 100 },
          style: { stroke: '#dc2626', fill: null, stroke_width: 2 },
        },
      ],
    },
  ],
  comments: [],
}

test('an added step waits for its marker, and steps the board had stay', () => {
  // WB-06, WB-20
  const known = new Set(['learner'])

  const before = revealAddedSteps(pinned, known, 'Look at your box. ')
  const after = revealAddedSteps(pinned, known, 'Look at your box. [[step:hint]] Here')

  expect(before.steps.map((step) => step.id)).toEqual(['learner'])
  expect(after.steps.map((step) => step.id)).toEqual(['learner', 'hint'])
})

test("the agent's added parts use the tutor pen, dashed, whatever stroke they stored", () => {
  // WB-20
  const shapes = whiteboardToShapes(pinned).shapes
  const added = shapes.find((shape) => shape.meta?.elementId === 'hint-box')
  const learner = shapes.find((shape) => shape.meta?.elementId === 'learner-box')

  expect(added?.props).toMatchObject({ color: agentAddedLook.color, dash: agentAddedLook.dash })
  expect(learner?.props).toMatchObject({ dash: 'solid' })
  expect(learner?.props).not.toMatchObject({ dash: agentAddedLook.dash })
})

test("a new learner shape joins the learner's step, not the agent's added step", () => {
  // WB-20, WB-21
  const shapes = whiteboardToShapes(pinned).shapes
  const fresh = {
    id: 'shape:circle',
    type: 'geo',
    x: 40,
    y: 260,
    meta: { author: 'learner', elementId: 'learner-circle' },
    props: { geo: 'ellipse', w: 60, h: 60, color: 'blue', fill: 'none', size: 's' },
  }

  const next = applyLearnerShapes(pinned, [...shapes, fresh])

  expect(next.steps[0].elements.map((element) => element.id)).toEqual([
    'learner-box',
    'learner-circle',
  ])
  expect(next.steps[1]).toEqual(pinned.steps[1])
})
