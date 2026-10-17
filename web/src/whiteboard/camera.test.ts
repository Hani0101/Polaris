import { Box } from 'tldraw'
import { afterEach, expect, test, vi } from 'vitest'
import { CAMERA_INSET, cameraMove, FOLLOW_BELOW_ZOOM, moveCamera } from './camera.ts'

afterEach(() => {
  vi.unstubAllGlobals()
})

const phone = { w: 360, h: 500 }

test('a board that fits a phone is fitted whole', () => {
  const board = new Box(0, 0, 300, 300)

  expect(cameraMove(phone, board, new Box(0, 200, 100, 100))).toEqual({ kind: 'fit' })
})

test('a board too big for a phone follows the newest step', () => {
  const board = new Box(0, 0, 1000, 1400)
  const step = new Box(40, 900, 200, 80)

  const move = cameraMove(phone, board, step)

  expect(move).toEqual({ kind: 'follow', bounds: step, zoom: 1 })
  expect(360 / (1000 + CAMERA_INSET * 2)).toBeLessThan(FOLLOW_BELOW_ZOOM)
})

test('a wide step is zoomed out only as far as it needs', () => {
  const move = cameraMove(phone, new Box(0, 0, 1000, 1400), new Box(0, 0, 700, 80))

  expect(move.kind).toBe('follow')
  if (move.kind === 'follow') expect(move.zoom).toBeCloseTo(360 / (700 + CAMERA_INSET * 2))
})

test('an unmeasured viewport fits the board', () => {
  expect(cameraMove({ w: 0, h: 0 }, new Box(0, 0, 1000, 1400), new Box(0, 0, 10, 10))).toEqual({
    kind: 'fit',
  })
})

function fakeEditor() {
  const shapes = [
    { id: 'shape:a', meta: { stepId: 'step-1' }, box: new Box(0, 0, 1000, 100) },
    { id: 'shape:b', meta: { stepId: 'step-2' }, box: new Box(40, 1200, 200, 80) },
  ]
  return {
    getCurrentPageShapes: () => shapes,
    getShapePageBounds: (id: string) => shapes.find((shape) => shape.id === id)?.box,
    getViewportScreenBounds: () => new Box(0, 0, phone.w, phone.h),
    zoomToBounds: vi.fn(),
    zoomToFit: vi.fn(),
  }
}

test('the camera moves to the new step, and jumps under reduced motion', () => {
  const editor = fakeEditor()
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: false, media: query }))

  // @ts-expect-error a partial editor is enough for the camera
  moveCamera(editor, ['step-2'])

  expect(editor.zoomToFit).not.toHaveBeenCalled()
  const [bounds, options] = editor.zoomToBounds.mock.calls[0]
  expect(bounds).toEqual(new Box(40, 1200, 200, 80))
  expect(options.animation.duration).toBe(300)

  const still = fakeEditor()
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: true, media: query }))
  // @ts-expect-error a partial editor is enough for the camera
  moveCamera(still, ['step-2'])
  expect(still.zoomToBounds.mock.calls[0][1].animation).toEqual({ duration: 0 })
})
