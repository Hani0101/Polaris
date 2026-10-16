import {
  b64Vecs,
  createShapeId,
  toRichText,
  type IndexKey,
  type TLArrowBinding,
  type TLBindingCreate,
  type TLShapePartial,
} from 'tldraw'
import type { Point, Style, Whiteboard } from '../api.ts'
import { GRAPH_SHAPE_TYPE } from './graphShapes.tsx'
import { CODE_SHAPE_TYPE, MATH_SHAPE_TYPE } from './mathCodeShapes.tsx'
import { agentMarkLook, mapStyle, whiteboardMarks } from './style.ts'

const KNOWN_KINDS = new Set([
  'rectangle',
  'ellipse',
  'arrow',
  'line',
  'text',
  'freehand',
  'mark',
  'math',
  'code',
  'graph',
])

type DrawingElement = {
  id: string
  kind: string
  author: 'agent' | 'learner'
  position: Point
  size: { width: number; height: number }
  style: Style
  start?: Point
  end?: Point
  label?: string
  start_element_id?: string
  end_element_id?: string
  text?: string
  points?: Point[]
  mark?: 'circle' | 'arrow' | 'note'
  target_element_id?: string
  latex?: string
  language?: string
  code?: string
  x_label?: string
  y_label?: string
  x_min?: number
  x_max?: number
  y_min?: number
  y_max?: number
  series?: Array<{ plotted?: Point[] }>
}

export type DrawingWhiteboard = {
  version: number
  id: string
  session_id: string
  steps: Array<{
    id: string
    reply_part: string
    elements: DrawingElement[]
  }>
}

export type SkippedElement = {
  id: string
  kind: string
  stepId: string
  stepIndex: number
}

export type WhiteboardShapes = {
  shapes: TLShapePartial[]
  // Attached arrow ends. Created after the shapes, since a binding needs both ends.
  bindings: TLBindingCreate<TLArrowBinding>[]
  skipped: SkippedElement[]
}

function relative(origin: Point, point: Point): Point {
  return { x: point.x - origin.x, y: point.y - origin.y }
}

function hasPoint(point: Point | undefined): point is Point {
  return point !== undefined && Number.isFinite(point.x) && Number.isFinite(point.y)
}

function metaFor(
  element: DrawingElement,
  stepId: string,
  stepIndex: number,
  elementIndex: number,
) {
  return {
    elementId: element.id,
    author: element.author,
    stepId,
    stepIndex,
    elementIndex,
  }
}

function strokeProps(style: Style) {
  const mapped = mapStyle(style)
  return { color: mapped.color, dash: mapped.dash, size: mapped.size }
}

function markStroke(style: Style) {
  const mapped = mapStyle(style)
  return {
    color: agentMarkLook.color,
    dash: agentMarkLook.dash,
    fill: agentMarkLook.fill,
    size: mapped.size,
    font: mapped.font,
  }
}

function paintProps(style: Style) {
  const mapped = mapStyle(style)
  return { ...strokeProps(style), fill: mapped.fill, font: mapped.font }
}

function linePoints(origin: Point, start: Point, end: Point) {
  const from = relative(origin, start)
  const to = relative(origin, end)
  return {
    a1: { id: 'a1', index: 'a1' as IndexKey, x: from.x, y: from.y },
    a2: { id: 'a2', index: 'a2' as IndexKey, x: to.x, y: to.y },
  }
}

function shapeFor(
  element: DrawingElement,
  stepId: string,
  stepIndex: number,
  elementIndex: number,
): TLShapePartial | SkippedElement {
  const meta = metaFor(element, stepId, stepIndex, elementIndex)
  const id = createShapeId(element.id)
  const x = element.position.x
  const y = element.position.y

  if (element.kind === 'mark') {
    const paint = markStroke(element.style)
    if (element.mark === 'circle') {
      return {
        id,
        type: 'geo',
        x,
        y,
        meta,
        props: {
          geo: 'ellipse',
          w: element.size.width,
          h: element.size.height,
          ...paint,
          richText: toRichText(''),
        },
      }
    }
    if (element.mark === 'arrow') {
      if (!hasPoint(element.start) || !hasPoint(element.end)) {
        return { id: element.id, kind: element.kind, stepId, stepIndex }
      }
      return {
        id,
        type: 'arrow',
        x,
        y,
        meta,
        props: {
          ...paint,
          kind: whiteboardMarks.arrowKind,
          bend: whiteboardMarks.arrowBend,
          arrowheadStart: whiteboardMarks.arrowheadStart,
          arrowheadEnd: whiteboardMarks.arrowheadEnd,
          start: relative(element.position, element.start),
          end: relative(element.position, element.end),
          scale: whiteboardMarks.scale,
          richText: toRichText(''),
        },
      }
    }
    if (element.mark === 'note') {
      return {
        id,
        type: 'geo',
        x,
        y,
        meta,
        props: {
          geo: 'rectangle',
          w: element.size.width,
          h: element.size.height,
          ...paint,
          richText: toRichText(element.text ?? ''),
        },
      }
    }
    return { id: element.id, kind: element.kind, stepId, stepIndex }
  }

  if (element.kind === 'rectangle' || element.kind === 'ellipse') {
    return {
      id,
      type: 'geo',
      x,
      y,
      meta,
      props: {
        geo: element.kind,
        w: element.size.width,
        h: element.size.height,
        ...paintProps(element.style),
        align: whiteboardMarks.labelAlign,
        verticalAlign: whiteboardMarks.labelVerticalAlign,
        richText: toRichText(element.label ?? ''),
      },
    }
  }

  if (element.kind === 'arrow') {
    if (!hasPoint(element.start) || !hasPoint(element.end)) {
      return { id: element.id, kind: element.kind, stepId, stepIndex }
    }
    return {
      id,
      type: 'arrow',
      x,
      y,
      meta,
      props: {
        ...paintProps(element.style),
        kind: whiteboardMarks.arrowKind,
        bend: whiteboardMarks.arrowBend,
        arrowheadStart: whiteboardMarks.arrowheadStart,
        arrowheadEnd: whiteboardMarks.arrowheadEnd,
        start: relative(element.position, element.start),
        end: relative(element.position, element.end),
        scale: whiteboardMarks.scale,
        richText: toRichText(element.label ?? ''),
      },
    }
  }

  if (element.kind === 'line') {
    if (!hasPoint(element.start) || !hasPoint(element.end)) {
      return { id: element.id, kind: element.kind, stepId, stepIndex }
    }
    return {
      id,
      type: 'line',
      x,
      y,
      meta,
      props: {
        ...strokeProps(element.style),
        spline: whiteboardMarks.lineSpline,
        points: linePoints(element.position, element.start, element.end),
        scale: whiteboardMarks.scale,
      },
    }
  }

  if (element.kind === 'math') {
    if (typeof element.latex !== 'string' || !element.latex) {
      return { id: element.id, kind: element.kind, stepId, stepIndex }
    }
    return {
      id,
      type: MATH_SHAPE_TYPE,
      x,
      y,
      meta,
      props: {
        w: element.size.width,
        h: element.size.height,
        latex: element.latex,
      },
    }
  }

  if (element.kind === 'code') {
    if (
      typeof element.language !== 'string' ||
      !element.language ||
      typeof element.code !== 'string' ||
      !element.code
    ) {
      return { id: element.id, kind: element.kind, stepId, stepIndex }
    }
    return {
      id,
      type: CODE_SHAPE_TYPE,
      x,
      y,
      meta,
      props: {
        w: element.size.width,
        h: element.size.height,
        language: element.language,
        code: element.code,
      },
    }
  }

  if (element.kind === 'graph') {
    const xMin = element.x_min
    const xMax = element.x_max
    const yMin = element.y_min
    const yMax = element.y_max
    if (
      typeof element.x_label !== 'string' ||
      typeof element.y_label !== 'string' ||
      typeof xMin !== 'number' ||
      typeof xMax !== 'number' ||
      typeof yMin !== 'number' ||
      typeof yMax !== 'number' ||
      !(xMax > xMin) ||
      !(yMax > yMin)
    ) {
      return { id: element.id, kind: element.kind, stepId, stepIndex }
    }
    const series = (element.series ?? [])
      .map((item) => item.plotted)
      .filter(
        (points): points is Point[] =>
          Array.isArray(points) && points.length > 0 && points.every((point) => hasPoint(point)),
      )
      .map((points) => ({ plotted: points }))
    return {
      id,
      type: GRAPH_SHAPE_TYPE,
      x,
      y,
      meta,
      props: {
        w: element.size.width,
        h: element.size.height,
        xLabel: element.x_label,
        yLabel: element.y_label,
        xMin,
        xMax,
        yMin,
        yMax,
        stroke: element.style.stroke,
        series,
      },
    }
  }

  if (element.kind === 'text') {
    const mapped = mapStyle(element.style)
    return {
      id,
      type: 'text',
      x,
      y,
      meta,
      props: {
        color: mapped.color,
        size: mapped.size,
        font: mapped.font,
        textAlign: whiteboardMarks.textAlign,
        w: element.size.width,
        autoSize: whiteboardMarks.textAutoSize,
        scale: whiteboardMarks.scale,
        richText: toRichText(element.text ?? ''),
      },
    }
  }

  if (element.kind === 'freehand') {
    const points = element.points ?? []
    if (points.length === 0 || points.some((point) => !hasPoint(point))) {
      return { id: element.id, kind: element.kind, stepId, stepIndex }
    }
    return {
      id,
      type: 'draw',
      x,
      y,
      meta,
      props: {
        ...strokeProps(element.style),
        fill: mapStyle(element.style).fill,
        segments: [
          {
            type: 'free',
            path: b64Vecs.encodePoints(
              points.map((point) => relative(element.position, point)),
              2,
            ),
            dim: 2,
          },
        ],
        isComplete: whiteboardMarks.freehandComplete,
        isClosed: whiteboardMarks.freehandClosed,
        isPen: whiteboardMarks.freehandPen,
        scale: whiteboardMarks.scale,
        scaleX: whiteboardMarks.scale,
        scaleY: whiteboardMarks.scale,
      },
    }
  }

  return { id: element.id, kind: element.kind, stepId, stepIndex }
}

function isSkipped(value: TLShapePartial | SkippedElement): value is SkippedElement {
  return !('type' in value)
}

function arrowBinding(
  arrow: TLShapePartial,
  terminal: 'start' | 'end',
  elementId: string,
): TLBindingCreate<TLArrowBinding> {
  return {
    type: 'arrow',
    fromId: arrow.id,
    toId: createShapeId(elementId),
    props: {
      terminal,
      normalizedAnchor: { x: 0.5, y: 0.5 },
      isExact: false,
      isPrecise: false,
      snap: 'none',
    },
  }
}

/** Bindings for attached arrow ends. An end whose part is not drawn stays loose. */
function arrowBindings(
  elements: DrawingElement[],
  shapes: TLShapePartial[],
): TLBindingCreate<TLArrowBinding>[] {
  const drawn = new Set(shapes.map((shape) => shape.id))
  const bindings: TLBindingCreate<TLArrowBinding>[] = []
  for (const element of elements) {
    if (element.kind !== 'arrow') continue
    const arrow = shapes.find((shape) => shape.id === createShapeId(element.id))
    if (!arrow) continue
    const ends = [
      ['start', element.start_element_id],
      ['end', element.end_element_id],
    ] as const
    for (const [terminal, elementId] of ends) {
      if (!elementId || elementId === element.id) continue
      if (!drawn.has(createShapeId(elementId))) continue
      bindings.push(arrowBinding(arrow, terminal, elementId))
    }
  }
  return bindings
}

export function whiteboardToShapes(whiteboard: DrawingWhiteboard | Whiteboard): WhiteboardShapes {
  const shapes: TLShapePartial[] = []
  const skipped: SkippedElement[] = []
  const elements: DrawingElement[] = []

  whiteboard.steps.forEach((step, stepIndex) => {
    step.elements.forEach((element, elementIndex) => {
      elements.push(element)
      if (!KNOWN_KINDS.has(element.kind)) {
        skipped.push({ id: element.id, kind: element.kind, stepId: step.id, stepIndex })
        return
      }
      const shape = shapeFor(element, step.id, stepIndex, elementIndex)
      if (isSkipped(shape)) skipped.push(shape)
      else shapes.push(shape)
    })
  })

  return { shapes, bindings: arrowBindings(elements, shapes), skipped }
}
