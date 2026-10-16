import { b64Vecs } from 'tldraw'
import { expect, test } from 'vitest'
import type { Whiteboard } from '../api.ts'
import { formulaWhiteboard } from './formulaWhiteboard.ts'
import { graphWhiteboard } from './graphWhiteboard.ts'
import { linkedWhiteboard } from './linkedWhiteboard.ts'
import { sampleWhiteboard } from './sampleWhiteboard.ts'
import { agentMarkLook } from './style.ts'
import { whiteboardToShapes } from './toTldraw.ts'

function shapeFor(whiteboard: Whiteboard, elementId: string) {
  const found = whiteboardToShapes(whiteboard).shapes.find(
    (shape) => shape.meta?.elementId === elementId,
  )
  if (!found) throw new Error(`No shape for ${elementId}`)
  return found
}

function lineCoordinates(points: Record<string, { index: string; x: number; y: number }>) {
  return Object.values(points)
    .sort((left, right) => (left.index < right.index ? -1 : left.index > right.index ? 1 : 0))
    .map((point) => ({ x: point.x, y: point.y }))
}

test('a rectangle keeps its id, author, step, and box', () => {
  const shape = shapeFor(sampleWhiteboard, 'rect-1')

  expect(shape.id).toBe('shape:rect-1')
  expect(shape.type).toBe('geo')
  expect(shape.x).toBe(10)
  expect(shape.y).toBe(20)
  expect(shape.meta).toEqual({
    elementId: 'rect-1',
    author: 'agent',
    stepId: 'step-1',
    stepIndex: 0,
    elementIndex: 0,
  })
  expect(shape.props).toMatchObject({
    geo: 'rectangle',
    w: 80,
    h: 40,
    color: 'black',
    fill: 'semi',
    size: 's',
    dash: 'solid',
  })
})

test('an ellipse maps to a geo ellipse and keeps a learner author', () => {
  const shape = shapeFor(sampleWhiteboard, 'ellipse-1')

  expect(shape.type).toBe('geo')
  expect(shape.props).toMatchObject({ geo: 'ellipse', w: 80, h: 40 })
  expect(shape.meta).toMatchObject({
    elementId: 'ellipse-1',
    author: 'learner',
    stepId: 'step-1',
    stepIndex: 0,
    elementIndex: 1,
  })
})

test('an arrow runs from its start point to its end point', () => {
  const shape = shapeFor(sampleWhiteboard, 'arrow-1')

  expect(shape.type).toBe('arrow')
  expect(shape.x).toBe(10)
  expect(shape.y).toBe(20)
  expect(shape.props).toMatchObject({
    kind: 'arc',
    bend: 0,
    arrowheadStart: 'none',
    arrowheadEnd: 'arrow',
    start: { x: 0, y: 0 },
    end: { x: 80, y: 40 },
  })
  expect(shape.meta).toMatchObject({ elementId: 'arrow-1', author: 'agent', stepIndex: 0 })
})

test('a line keeps its endpoints relative to the element position', () => {
  const shape = shapeFor(sampleWhiteboard, 'line-1')
  const points = (shape.props as { points?: Record<string, { index: string; x: number; y: number }> })
    .points

  expect(shape.type).toBe('line')
  expect(shape.x).toBe(10)
  expect(shape.y).toBe(20)
  expect(points).toBeTruthy()
  expect(lineCoordinates(points ?? {})).toEqual([
    { x: 2, y: 2 },
    { x: 60, y: 2 },
  ])
})

test('text stays real text on a text shape', () => {
  const shape = shapeFor(sampleWhiteboard, 'text-1')

  expect(shape.type).toBe('text')
  expect(shape.props).toMatchObject({
    w: 80,
    autoSize: false,
    font: 'sans',
    textAlign: 'start',
    color: 'black',
    size: 's',
    richText: {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: 'half' }] }],
    },
  })
})

test('a freehand stroke keeps its points relative to the element position', () => {
  const shape = shapeFor(sampleWhiteboard, 'freehand-1')
  const segments = (
    shape.props as { segments?: Array<{ type: string; path: string; dim?: number }> }
  ).segments
  const segment = segments?.[0]

  expect(shape.type).toBe('draw')
  expect(shape.x).toBe(10)
  expect(shape.y).toBe(20)
  expect(segment?.type).toBe('free')
  expect(segment?.dim).toBe(2)
  const decoded = b64Vecs.decodePoints(segment?.path ?? '', 2)
  expect(decoded.map((point) => ({ x: point.x, y: point.y }))).toEqual([
    { x: 4, y: 4 },
    { x: 30, y: 30 },
  ])
})

test('step order and step identity stay on the shapes', () => {
  const { shapes, skipped } = whiteboardToShapes(sampleWhiteboard)

  expect(skipped).toEqual([])
  expect(shapes.map((shape) => shape.meta?.elementId)).toEqual([
    'rect-1',
    'ellipse-1',
    'arrow-1',
    'line-1',
    'text-1',
    'freehand-1',
    'rect-2',
  ])
  expect(shapes.map((shape) => shape.meta?.stepId)).toEqual([
    'step-1',
    'step-1',
    'step-1',
    'step-1',
    'step-1',
    'step-1',
    'step-2',
  ])
  expect(shapes.map((shape) => shape.meta?.stepIndex)).toEqual([0, 0, 0, 0, 0, 0, 1])
  expect(shapes[6]?.meta).toMatchObject({
    elementId: 'rect-2',
    author: 'learner',
    stepId: 'step-2',
    stepIndex: 1,
    elementIndex: 0,
  })
})

test('an unknown element kind is skipped and reported', () => {
  const whiteboard = {
    version: 1,
    id: 'wb-1',
    session_id: 'session-1',
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [
          sampleWhiteboard.steps[0].elements[0],
          {
            ...sampleWhiteboard.steps[0].elements[0],
            id: 'tri-1',
            kind: 'triangle',
          },
          sampleWhiteboard.steps[0].elements[1],
        ],
      },
    ],
  }
  const { shapes, skipped } = whiteboardToShapes(whiteboard)

  expect(shapes.map((shape) => shape.meta?.elementId)).toEqual(['rect-1', 'ellipse-1'])
  expect(skipped).toEqual([
    { id: 'tri-1', kind: 'triangle', stepId: 'step-1', stepIndex: 0 },
  ])
})

test('a rectangle with no fill is not filled', () => {
  const source = sampleWhiteboard.steps[0].elements[0]
  if (source.kind !== 'rectangle') throw new Error('expected a rectangle')
  const whiteboard: Whiteboard = {
    version: 2,
    id: 'wb-1',
    session_id: 'session-1',
    comments: [],
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [{ ...source, style: { ...source.style, fill: null } }],
      },
    ],
  }

  expect(shapeFor(whiteboard, 'rect-1').props).toMatchObject({ fill: 'none' })
})

function markedBoard(): Whiteboard {
  const learner = sampleWhiteboard.steps[0].elements[1]
  return {
    version: 3,
    id: 'wb-1',
    session_id: 'session-1',
    comments: [],
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [learner],
      },
      {
        id: 'step-mark',
        reply_part: '[[step:step-mark]]',
        elements: [
          {
            id: 'mark-circle',
            kind: 'mark',
            mark: 'circle',
            author: 'agent',
            target_element_id: learner.id,
            position: { x: 30, y: 40 },
            size: { width: 100, height: 80 },
            style: learner.style,
          },
          {
            id: 'mark-arrow',
            kind: 'mark',
            mark: 'arrow',
            author: 'agent',
            target_element_id: learner.id,
            position: { x: 30, y: 40 },
            size: { width: 90, height: 40 },
            style: learner.style,
            start: { x: 30, y: 40 },
            end: { x: 120, y: 80 },
          },
          {
            id: 'mark-note',
            kind: 'mark',
            mark: 'note',
            author: 'agent',
            target_element_id: learner.id,
            position: { x: 140, y: 40 },
            size: { width: 120, height: 48 },
            style: learner.style,
            text: 'check the sign',
          },
        ],
      },
    ],
  }
}

test('a graph shape draws plotted points and not the expression', () => {
  const mismatched = {
    ...graphWhiteboard,
    steps: [
      {
        ...graphWhiteboard.steps[0],
        elements: [
          {
            ...graphWhiteboard.steps[0].elements[0],
            series: [
              {
                expression: '2*x+1',
                sample_count: 3,
                plotted: [
                  { x: 0, y: 0 },
                  { x: 2, y: 2 },
                ],
              },
            ],
          },
        ],
      },
    ],
  }
  const graph = shapeFor(mismatched, 'graph-1')

  expect(graph.type).toBe('graph')
  expect(graph.props).toMatchObject({
    w: 200,
    h: 100,
    xLabel: 'x',
    yLabel: 'y',
    xMin: 0,
    xMax: 2,
    yMin: -1,
    yMax: 6,
    series: [{ plotted: [{ x: 0, y: 0 }, { x: 2, y: 2 }] }],
  })
  expect(JSON.stringify(graph.props)).not.toContain('2*x+1')
  expect(whiteboardToShapes(graphWhiteboard).skipped).toEqual([])
})

test('a graph series without plotted points is left out of the shape', () => {
  const missing = {
    ...graphWhiteboard,
    steps: [
      {
        ...graphWhiteboard.steps[0],
        elements: [
          {
            ...graphWhiteboard.steps[0].elements[0],
            series: [{ expression: '2*x+1', sample_count: 3 }],
          },
        ],
      },
    ],
  }
  const graph = shapeFor(missing, 'graph-1')
  expect(graph.props).toMatchObject({ series: [] })
  expect(JSON.stringify(graph.props)).not.toContain('2*x+1')
})

test('math and code become text shapes, not geo shapes', () => {
  const math = shapeFor(formulaWhiteboard, 'formula-1')
  const code = shapeFor(formulaWhiteboard, 'snippet-1')

  expect(math.type).toBe('math')
  expect(math.props).toMatchObject({ w: 80, h: 40, latex: 'A = \\pi r^{2}' })
  expect(code.type).toBe('code')
  expect(code.props).toMatchObject({
    w: 160,
    h: 64,
    language: 'python',
    code: 'def area(r):\n    return r * r',
  })
  expect(whiteboardToShapes(formulaWhiteboard).skipped).toEqual([])
})

test('marks render with the agent style and stay locked to the agent', () => {
  const board = markedBoard()
  const learner = shapeFor(board, board.steps[0].elements[0].id)
  const circle = shapeFor(board, 'mark-circle')
  const arrow = shapeFor(board, 'mark-arrow')
  const note = shapeFor(board, 'mark-note')

  expect(learner.props).toMatchObject({ dash: 'solid' })
  for (const shape of [circle, arrow, note]) {
    expect(shape.meta).toMatchObject({ author: 'agent' })
    expect(shape.props).toMatchObject({
      color: agentMarkLook.color,
      dash: agentMarkLook.dash,
      fill: agentMarkLook.fill,
    })
  }
  expect(circle.type).toBe('geo')
  expect(circle.props).toMatchObject({ geo: 'ellipse', w: 100, h: 80 })
  expect(arrow.type).toBe('arrow')
  expect(arrow.props).toMatchObject({
    start: { x: 0, y: 0 },
    end: { x: 90, y: 40 },
  })
  expect(note.type).toBe('geo')
  expect(note.props).toMatchObject({
    geo: 'rectangle',
    richText: {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: 'check the sign' }] }],
    },
  })
  expect(learner.props).not.toMatchObject({ dash: agentMarkLook.dash, color: agentMarkLook.color })
})

function plain(richText: unknown): string {
  return JSON.stringify(richText).match(/"text":"([^"]*)"/)?.[1] ?? ''
}

test('a box label is drawn inside the box, centered', () => {
  const box = shapeFor(linkedWhiteboard, 'heat')
  const ellipse = shapeFor(linkedWhiteboard, 'ice')

  expect(plain((box.props as { richText: unknown }).richText)).toBe('Heat')
  expect(box.props).toMatchObject({ align: 'middle', verticalAlign: 'middle' })
  expect(plain((ellipse.props as { richText: unknown }).richText)).toBe('Ice melts')
})

test('an attached arrow end becomes a binding to the drawn part', () => {
  const [heat, ice, link] = linkedWhiteboard.steps[0].elements
  const loose: Whiteboard = {
    ...linkedWhiteboard,
    steps: [{ ...linkedWhiteboard.steps[0], elements: [heat, ice, { ...link, end_element_id: 'missing' }] }],
  }
  const converted = whiteboardToShapes(loose)
  const arrow = shapeFor(loose, 'heat-to-ice')

  expect(plain((arrow.props as { richText: unknown }).richText)).toBe('causes')
  // The end names a part that is not drawn, so only the start is attached.
  expect(converted.bindings).toEqual([
    {
      type: 'arrow',
      fromId: 'shape:heat-to-ice',
      toId: 'shape:heat',
      props: {
        terminal: 'start',
        normalizedAnchor: { x: 0.5, y: 0.5 },
        isExact: false,
        isPrecise: false,
        snap: 'none',
      },
    },
  ])
})

test('an older drawing has no bindings and empty box labels', () => {
  const converted = whiteboardToShapes(sampleWhiteboard)

  expect(converted.bindings).toEqual([])
  const box = shapeFor(sampleWhiteboard, 'rect-1')
  expect(plain((box.props as { richText: unknown }).richText)).toBe('')
})
