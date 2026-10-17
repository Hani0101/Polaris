import { expect, test } from 'vitest'
import type { Animation } from './format.ts'
import { readableDescription, seriesRole } from './format.ts'
import { anchor, baseBox, stateAt, stepEndState } from './playback.ts'
import sampleData from './sample-animation.json'

// The backend fixture (api/tests/fixtures/sample_animation.json) after the
// backend check, so graph series carry their plotted points.
const sample = sampleData as Animation

function tiny(overrides: Partial<Animation>): Animation {
  return {
    version: 1,
    id: 'tiny',
    title: 'Tiny',
    description: 'A small animation for tests.',
    elements: [],
    steps: [],
    ...overrides,
  }
}

test('the initial picture shows only elements visible at the start', () => {
  const scene = stepEndState(sample, -1)

  const visible = Object.entries(scene)
    .filter(([, state]) => state.visible)
    .map(([id]) => id)
  expect(visible).toEqual(['list', 'numbers', 'target', 'checks-label'])
  expect(scene.pointer.opacity).toBe(0)
})

test('appear fades in over its duration', () => {
  const scene = stateAt(sample, 0, 200)

  expect(scene.pointer.visible).toBe(true)
  expect(scene.pointer.opacity).toBeCloseTo(0.5)
  expect(scene.checks.opacity).toBeCloseTo(200 / 300)
  expect(scene.checks.text).toBeNull()
})

test('count shows the number between its values with the given decimals', () => {
  expect(stateAt(sample, 0, 700).checks.text).toBe('0')
  expect(stepEndState(sample, 0).checks.text).toBe('1')
  expect(stateAt(sample, 2, 1200).checks.text).toBe('2')
  expect(stepEndState(sample, 2).checks.text).toBe('3')
})

test('a highlight without keep lasts until the end of its step', () => {
  expect(stateAt(sample, 1, 400).numbers.color).toBe('ink')
  expect(stateAt(sample, 1, 600).numbers.color).toBe('accent')
  expect(stepEndState(sample, 1).numbers.color).toBe('ink')
})

test('a highlight with keep stays for the rest of the animation', () => {
  const animation = tiny({
    elements: [{ id: 'box', kind: 'rectangle', x: 10, y: 10, width: 50, height: 50, visible_at_start: true }],
    steps: [
      {
        id: 'one',
        caption: 'Highlight the box.',
        duration_ms: 1000,
        actions: [{ action: 'highlight', element: 'box', color: 'positive', keep: true }],
      },
      { id: 'two', caption: 'Nothing else.', duration_ms: 1000, actions: [] },
    ],
  })

  expect(stepEndState(animation, 0).box.color).toBe('positive')
  expect(stepEndState(animation, 1).box.color).toBe('positive')
})

test('move slides the anchor to its target from where the element is', () => {
  const halfway = stateAt(sample, 2, 400)
  expect(halfway.pointer.dx).toBeCloseTo(50)
  expect(halfway.pointer.dy).toBeCloseTo(0)

  const end = stepEndState(sample, 2)
  expect(end.pointer.dx).toBeCloseTo(100)
  expect(anchor(sample.elements[3])).toEqual({ x: 200, y: 180 })
})

test('disappear fades out and hides the element at the end', () => {
  const fading = stateAt(sample, 3, 150)
  expect(fading.pointer.visible).toBe(true)
  expect(fading.pointer.opacity).toBeCloseTo(0.5)

  expect(stepEndState(sample, 3).pointer.visible).toBe(false)
})

test('trace shows the graph and draws it from start to end', () => {
  expect(stateAt(sample, 3, 200).curve.visible).toBe(false)

  const drawing = stateAt(sample, 3, 1050)
  expect(drawing.curve.visible).toBe(true)
  expect(drawing.curve.drawn[0]).toBeCloseTo(0.5)

  expect(stepEndState(sample, 3).curve.drawn).toEqual([1])
})

test('tracing one series of a hidden graph leaves the other series undrawn', () => {
  const animation = tiny({
    elements: [
      {
        id: 'g',
        kind: 'graph',
        x: 20,
        y: 20,
        width: 200,
        height: 120,
        x_min: 0,
        x_max: 1,
        y_min: 0,
        y_max: 1,
        series: [
          { points: [{ x: 0, y: 0 }, { x: 1, y: 1 }], plotted: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
          { points: [{ x: 0, y: 1 }, { x: 1, y: 0 }], plotted: [{ x: 0, y: 1 }, { x: 1, y: 0 }] },
        ],
      },
    ],
    steps: [
      {
        id: 'first',
        caption: 'Draw the rising line.',
        duration_ms: 1000,
        actions: [{ action: 'trace', element: 'g', series: 0, duration_ms: 1000 }],
      },
      {
        id: 'second',
        caption: 'Draw the falling line.',
        duration_ms: 1000,
        actions: [{ action: 'trace', element: 'g', series: 1, duration_ms: 1000 }],
      },
    ],
  })

  expect(stateAt(animation, 0, 500).g.drawn).toEqual([0.5, 0])
  expect(stepEndState(animation, 0).g.drawn).toEqual([1, 0])
  expect(stateAt(animation, 1, 250).g.drawn).toEqual([1, 0.25])
  expect(stepEndState(animation, 1).g.drawn).toEqual([1, 1])
})

test('follow moves the anchor along the plotted points', () => {
  const animation = tiny({
    elements: [{ id: 'ball', kind: 'ellipse', x: 0, y: 0, width: 20, height: 20, visible_at_start: true }],
    steps: [
      {
        id: 'roll',
        caption: 'The ball rolls.',
        duration_ms: 1000,
        actions: [
          {
            action: 'follow',
            element: 'ball',
            duration_ms: 1000,
            path: {
              plotted: [
                { x: 0, y: 100 },
                { x: 100, y: 100 },
                { x: 100, y: 200 },
              ],
            },
          },
        ],
      },
    ],
  })

  expect(stateAt(animation, 0, 0).ball).toMatchObject({ dx: 0, dy: 100 })
  expect(stateAt(animation, 0, 250).ball).toMatchObject({ dx: 50, dy: 100 })
  expect(stateAt(animation, 0, 750).ball).toMatchObject({ dx: 100, dy: 150 })
  expect(stepEndState(animation, 0).ball).toMatchObject({ dx: 100, dy: 200 })
})

test('scale grows from the current scale toward its target', () => {
  const animation = tiny({
    elements: [{ id: 'dot', kind: 'ellipse', x: 100, y: 100, width: 20, height: 20, visible_at_start: true }],
    steps: [
      {
        id: 'grow',
        caption: 'The dot grows.',
        duration_ms: 2000,
        actions: [
          { action: 'scale', element: 'dot', to: 2, duration_ms: 1000 },
          { action: 'scale', element: 'dot', to: 1, start_ms: 1000, duration_ms: 1000 },
        ],
      },
    ],
  })

  expect(stateAt(animation, 0, 500).dot.scale).toBeCloseTo(1.5)
  expect(stateAt(animation, 0, 1000).dot.scale).toBeCloseTo(2)
  expect(stateAt(animation, 0, 1500).dot.scale).toBeCloseTo(1.5)
  expect(stepEndState(animation, 0).dot.scale).toBeCloseTo(1)
})

test('a step starts from the end picture of the step before', () => {
  expect(stateAt(sample, 2, 0)).toEqual(stepEndState(sample, 1))
  expect(stateAt(sample, 1, 2000)).toEqual(stepEndState(sample, 1))
})

test('text boxes follow the backend estimate', () => {
  const numbers = sample.elements[1]
  const box = baseBox(numbers)
  const width = 'text' in numbers ? numbers.text.length * 22 * 0.6 : 0
  expect(box.left).toBeCloseTo(200 - width / 2)
  expect(box.bottom).toBeCloseTo(78 + 22 * 1.25)
})

test('graph series colours start at the element role, then follow the series roles', () => {
  expect(seriesRole('ink', 0)).toBe('accent')
  expect(seriesRole('negative', 0)).toBe('negative')
  expect([1, 2, 3].map((index) => seriesRole('ink', index))).toEqual([
    'positive',
    'highlight',
    'negative',
  ])
})

test('the screen reader description matches the backend text', () => {
  expect(readableDescription(sample)).toBe(
    'Binary search halves the list. A sorted list of seven numbers. Each step checks the ' +
      'middle number and throws away the half that cannot hold 23. It has 4 steps.',
  )
})
