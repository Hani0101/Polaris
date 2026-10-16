import { Box, EASINGS, type Editor, type TLShapeId } from 'tldraw'

// When fitting the whole board would shrink it below this zoom, the camera
// follows each new step instead, so its text stays readable on a phone (WB-06, WB-16).
export const FOLLOW_BELOW_ZOOM = 0.75
export const CAMERA_INSET = 16
// DS-GAP: no motion rule for a whiteboard camera move, used motion.duration.slow
// and an ease-out close to motion.easing.standard.
const CAMERA_DURATION_MS = 300

type Size = { w: number; h: number }

export type CameraMove = { kind: 'fit' } | { kind: 'follow'; bounds: Box; zoom: number }

function fitZoom(viewport: Size, bounds: Box): number {
  const width = bounds.w + CAMERA_INSET * 2
  const height = bounds.h + CAMERA_INSET * 2
  if (width <= 0 || height <= 0) return Infinity
  return Math.min(viewport.w / width, viewport.h / height)
}

/** Fit the whole board, or follow the newest step when the whole board would be too small. */
export function cameraMove(viewport: Size, board: Box | null, step: Box | null): CameraMove {
  if (!board || !step || viewport.w <= 0 || viewport.h <= 0) return { kind: 'fit' }
  if (fitZoom(viewport, board) >= FOLLOW_BELOW_ZOOM) return { kind: 'fit' }
  return { kind: 'follow', bounds: step, zoom: Math.min(1, fitZoom(viewport, step)) }
}

function reducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function boundsOf(editor: Editor, ids: Iterable<TLShapeId>): Box | null {
  const boxes = [...ids]
    .map((id) => editor.getShapePageBounds(id))
    .filter((box): box is Box => box !== undefined)
  return boxes.length > 0 ? Box.Common(boxes) : null
}

/** Point the camera at steps that just appeared, or fit the board when it is small enough. */
export function moveCamera(editor: Editor, newStepIds: readonly string[]) {
  const shapes = editor.getCurrentPageShapes()
  const wanted = new Set(newStepIds)
  const added = shapes.filter(
    (shape) => typeof shape.meta?.stepId === 'string' && wanted.has(shape.meta.stepId),
  )
  const viewport = editor.getViewportScreenBounds()
  const move = cameraMove(
    viewport,
    boundsOf(editor, shapes.map((shape) => shape.id)),
    boundsOf(editor, added.map((shape) => shape.id)),
  )
  const animation = reducedMotion()
    ? { duration: 0 }
    : { duration: CAMERA_DURATION_MS, easing: EASINGS.easeOutCubic }
  if (move.kind === 'fit') {
    editor.zoomToFit({ animation })
    return
  }
  editor.zoomToBounds(move.bounds, { inset: CAMERA_INSET, targetZoom: move.zoom, animation })
}
