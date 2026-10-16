import { b64Vecs, createShapeId } from 'tldraw'
import type { Point, Style, Whiteboard, WhiteboardElement } from '../api.ts'
import { learnerTextHeight, styleFromShapeProps } from './style.ts'

export type LearnerShape = {
  id: string
  type: string
  x: number
  y: number
  meta?: { author?: unknown; elementId?: unknown }
  props?: object
}

const LEARNER_KINDS = new Set(['rectangle', 'ellipse', 'arrow', 'line', 'text', 'freehand'])

function propsOf(shape: LearnerShape): Record<string, unknown> {
  if (!shape.props || typeof shape.props !== 'object') return {}
  return shape.props as Record<string, unknown>
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function pointOf(value: unknown): Point | null {
  if (!value || typeof value !== 'object') return null
  const point = value as { x?: unknown; y?: unknown }
  const x = finite(point.x)
  const y = finite(point.y)
  if (x === null || y === null) return null
  return { x, y }
}

function add(origin: Point, point: Point): Point {
  return { x: origin.x + point.x, y: origin.y + point.y }
}

function boxSize(points: Point[]): { width: number; height: number } {
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  return {
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  }
}

function plainText(value: unknown): string {
  if (!value || typeof value !== 'object') return ''
  const node = value as { text?: unknown; type?: unknown; content?: unknown }
  if (typeof node.text === 'string') return node.text
  if (!Array.isArray(node.content)) return ''
  const parts = node.content.map((child) => plainText(child))
  if (node.type === 'doc') return parts.join('\n')
  return parts.join('')
}

function elementIdOf(shape: LearnerShape): string {
  const existing = shape.meta?.elementId
  if (typeof existing === 'string' && existing.trim()) return existing
  const raw = shape.id.startsWith('shape:') ? shape.id.slice('shape:'.length) : shape.id
  return raw ? `learner-${raw}` : ''
}

export function isCanonicalAgentShape(
  shape: LearnerShape,
  agentIds: ReadonlySet<string>,
): boolean {
  const elementId = shape.meta?.elementId
  if (shape.meta?.author !== 'agent' || typeof elementId !== 'string') return false
  if (!agentIds.has(elementId)) return false
  return shape.id === createShapeId(elementId)
}

function kindOf(shape: LearnerShape, props: Record<string, unknown>): WhiteboardElement['kind'] | null {
  if (shape.type === 'geo' && (props.geo === 'rectangle' || props.geo === 'ellipse')) {
    return props.geo
  }
  if (shape.type === 'arrow') return 'arrow'
  if (shape.type === 'line') return 'line'
  if (shape.type === 'text') return 'text'
  if (shape.type === 'draw') return 'freehand'
  return null
}

function lineEnds(props: Record<string, unknown>): [Point, Point] | null {
  if (!props.points || typeof props.points !== 'object') return null
  const points = Object.values(props.points as Record<string, unknown>)
    .map((value) => {
      if (!value || typeof value !== 'object') return null
      const record = value as { x?: unknown; y?: unknown; index?: unknown }
      const point = pointOf(record)
      if (!point || typeof record.index !== 'string') return null
      return { ...point, index: record.index }
    })
    .filter((point): point is Point & { index: string } => point !== null)
    .sort((left, right) => (left.index < right.index ? -1 : left.index > right.index ? 1 : 0))
  if (points.length < 2) return null
  const first = points[0]
  const last = points[points.length - 1]
  return [
    { x: first.x, y: first.y },
    { x: last.x, y: last.y },
  ]
}

function freehandPoints(shape: LearnerShape, props: Record<string, unknown>): Point[] | null {
  if (!Array.isArray(props.segments) || props.segments.length === 0) return null
  const segment = props.segments[0]
  if (!segment || typeof segment !== 'object') return null
  const path = (segment as { path?: unknown }).path
  if (typeof path !== 'string' || !path) return null
  try {
    const decoded = b64Vecs.decodePoints(path, 2)
    if (decoded.length === 0) return null
    return decoded.map((point) => ({ x: shape.x + point.x, y: shape.y + point.y }))
  } catch {
    return null
  }
}

function elementFromShape(
  shape: LearnerShape,
  stored: WhiteboardElement | null,
): WhiteboardElement | null {
  if (!Number.isFinite(shape.x) || !Number.isFinite(shape.y)) return stored
  const props = propsOf(shape)
  const kind = kindOf(shape, props) ?? stored?.kind ?? null
  if (!kind || !LEARNER_KINDS.has(kind)) return stored
  const id = stored?.id ?? elementIdOf(shape)
  if (!id) return stored
  const position = { x: shape.x, y: shape.y }
  const style: Style = stored?.style ?? styleFromShapeProps(props)
  const base = {
    id,
    author: 'learner' as const,
    position,
    style,
  }

  if (kind === 'rectangle' || kind === 'ellipse') {
    return {
      ...base,
      kind,
      size: {
        width: finite(props.w) ?? stored?.size.width ?? 0,
        height: finite(props.h) ?? stored?.size.height ?? 0,
      },
    }
  }

  if (kind === 'arrow') {
    const start = pointOf(props.start)
    const end = pointOf(props.end)
    if (!start || !end) return stored
    return {
      ...base,
      kind,
      size: stored?.size ?? boxSize([start, end]),
      start: add(position, start),
      end: add(position, end),
    }
  }

  if (kind === 'line') {
    const ends = lineEnds(props)
    if (!ends) return stored
    return {
      ...base,
      kind,
      size: stored?.size ?? boxSize(ends),
      start: add(position, ends[0]),
      end: add(position, ends[1]),
    }
  }

  if (kind === 'text') {
    return {
      ...base,
      kind,
      text: plainText(props.richText),
      size: {
        width: finite(props.w) ?? stored?.size.width ?? learnerTextHeight,
        height: stored?.size.height ?? learnerTextHeight,
      },
    }
  }

  const points = freehandPoints(shape, props)
  if (!points) return stored
  const relative = points.map((point) => ({
    x: point.x - position.x,
    y: point.y - position.y,
  }))
  return {
    ...base,
    kind: 'freehand',
    size: stored?.size ?? boxSize(relative),
    points,
  }
}

export function applyLearnerShapes(
  whiteboard: Whiteboard,
  shapes: readonly LearnerShape[],
): Whiteboard {
  const agentIds = new Set(
    whiteboard.steps.flatMap((step) =>
      step.elements.filter((element) => element.author === 'agent').map((element) => element.id),
    ),
  )
  const learnerIds = new Set(
    whiteboard.steps.flatMap((step) =>
      step.elements.filter((element) => element.author === 'learner').map((element) => element.id),
    ),
  )
  const byLearnerId = new Map<string, LearnerShape>()
  const fresh: LearnerShape[] = []
  for (const shape of shapes) {
    if (isCanonicalAgentShape(shape, agentIds) || shape.meta?.author === 'agent') continue
    const elementId = typeof shape.meta?.elementId === 'string' ? shape.meta.elementId : ''
    if (elementId && learnerIds.has(elementId)) byLearnerId.set(elementId, shape)
    else fresh.push(shape)
  }

  const steps = whiteboard.steps.map((step, index) => {
    const elements: WhiteboardElement[] = []
    for (const element of step.elements) {
      if (element.author === 'agent') {
        elements.push(element)
        continue
      }
      const shape = byLearnerId.get(element.id)
      if (!shape) continue
      elements.push(elementFromShape(shape, element) ?? element)
    }
    if (index === whiteboard.steps.length - 1) {
      for (const shape of fresh) {
        const created = elementFromShape(shape, null)
        if (created) elements.push(created)
      }
    }
    return { ...step, elements }
  })

  return {
    version: whiteboard.version,
    id: whiteboard.id,
    session_id: whiteboard.session_id,
    ...(typeof whiteboard.description === 'string' ? { description: whiteboard.description } : {}),
    ...(typeof whiteboard.simplifies === 'string' ? { simplifies: whiteboard.simplifies } : {}),
    steps,
    comments: whiteboard.comments,
  }
}
