/**
 * The Polaris animation format, version 1 (decision 0006).
 *
 * Mirrors the Pydantic models in api/polaris/animation_format.py, which are
 * the source of truth. The backend checks the data before it is stored, so
 * the player trusts its shape. Graph series and follow paths arrive with
 * their points already plotted; the browser never evaluates an expression.
 */

export const CANVAS_WIDTH = 400
export const CANVAS_HEIGHT = 300

// Text boxes are estimates, the same ones the backend check uses.
export const TEXT_WIDTH_RATIO = 0.6
export const TEXT_LINE_HEIGHT = 1.25
export const CODE_LINE_HEIGHT = 1.4
export const CODE_PADDING = 8

export type ColorRole = 'ink' | 'muted' | 'accent' | 'positive' | 'negative' | 'highlight'

// Graph series after the first take these roles in order (GRAPH_SERIES_ROLES).
export const GRAPH_SERIES_ROLES: readonly ColorRole[] = ['accent', 'positive', 'highlight', 'negative']

export type AnimationPoint = {
  x: number
  y: number
}

type ElementBase = {
  id: string
  color?: ColorRole
  visible_at_start?: boolean
}

type BoxPosition = {
  x: number
  y: number
  width: number
  height: number
}

export type RectangleElement = ElementBase &
  BoxPosition & {
    kind: 'rectangle'
    filled?: boolean
  }

export type EllipseElement = ElementBase &
  BoxPosition & {
    kind: 'ellipse'
    filled?: boolean
  }

export type LineElement = ElementBase & {
  kind: 'line'
  start: AnimationPoint
  end: AnimationPoint
}

export type ArrowElement = ElementBase & {
  kind: 'arrow'
  start: AnimationPoint
  end: AnimationPoint
}

export type PathElement = ElementBase & {
  kind: 'path'
  points: AnimationPoint[]
  closed?: boolean
}

/** Text whose top-left (or top-centre, or top-right) is at x, y. */
export type TextElement = ElementBase & {
  kind: 'text'
  x: number
  y: number
  text: string
  size?: number
  align?: 'start' | 'middle' | 'end'
}

export type MathElement = ElementBase &
  BoxPosition & {
    kind: 'math'
    latex: string
    size?: number
  }

export type CodeElement = ElementBase & {
  kind: 'code'
  x: number
  y: number
  language: string
  code: string
  size?: number
}

export type AnimationGraphSeries =
  | { expression: string; sample_count: number; plotted?: AnimationPoint[] }
  | { points: AnimationPoint[]; plotted?: AnimationPoint[] }

export type GraphElement = ElementBase &
  BoxPosition & {
    kind: 'graph'
    x_label?: string
    y_label?: string
    x_min: number
    x_max: number
    y_min: number
    y_max: number
    series: AnimationGraphSeries[]
  }

export type AnimationElement =
  | RectangleElement
  | EllipseElement
  | LineElement
  | ArrowElement
  | PathElement
  | TextElement
  | MathElement
  | CodeElement
  | GraphElement

type ActionBase = {
  element: string
  start_ms?: number
  duration_ms?: number
}

export type AppearAction = ActionBase & { action: 'appear' }
export type DisappearAction = ActionBase & { action: 'disappear' }
export type MoveAction = ActionBase & { action: 'move'; to: AnimationPoint }
export type FollowAction = ActionBase & {
  action: 'follow'
  path: { plotted?: AnimationPoint[]; points?: AnimationPoint[] | null }
}
export type TraceAction = ActionBase & { action: 'trace'; series?: number | null }
export type HighlightAction = ActionBase & {
  action: 'highlight'
  color?: ColorRole
  keep?: boolean
}
export type CountAction = ActionBase & {
  action: 'count'
  from_value: number
  to_value: number
  decimals?: number
}
export type ScaleAction = ActionBase & { action: 'scale'; to: number }

export type AnimationAction =
  | AppearAction
  | DisappearAction
  | MoveAction
  | FollowAction
  | TraceAction
  | HighlightAction
  | CountAction
  | ScaleAction

export type AnimationStep = {
  id: string
  caption: string
  duration_ms: number
  actions: AnimationAction[]
}

export type Animation = {
  version: 1
  id: string
  title: string
  description: string
  elements: AnimationElement[]
  steps: AnimationStep[]
}

export const DEFAULT_TEXT_SIZE = 22
export const DEFAULT_ACTION_MS = 600

export function actionStart(action: AnimationAction): number {
  return action.start_ms ?? 0
}

export function actionDuration(action: AnimationAction): number {
  return action.duration_ms ?? DEFAULT_ACTION_MS
}

export function elementRole(element: AnimationElement): ColorRole {
  return element.color ?? 'ink'
}

/** The role for graph series ``index``: the element's own role first, unless it is ink. */
export function seriesRole(role: ColorRole, index: number): ColorRole {
  if (index === 0) return role === 'ink' ? GRAPH_SERIES_ROLES[0] : role
  return GRAPH_SERIES_ROLES[index % GRAPH_SERIES_ROLES.length]
}

/**
 * A loose shape check before the player draws data from the media route.
 * The backend already checked it (AN-10); this only guards against a
 * response that is not an animation at all.
 */
export function isAnimation(value: unknown): value is Animation {
  if (typeof value !== 'object' || value === null) return false
  const data = value as Record<string, unknown>
  return (
    data.version === 1 &&
    typeof data.title === 'string' &&
    Array.isArray(data.elements) &&
    Array.isArray(data.steps) &&
    data.steps.length > 0
  )
}

/** Text a screen reader reads for the whole animation (AN-15). Mirrors the backend. */
export function readableDescription(animation: Animation): string {
  const title = animation.title.trim()
  let description = animation.description.trim()
  if (!/[.!?]$/.test(description)) description += '.'
  const count = animation.steps.length
  const noun = count === 1 ? 'step' : 'steps'
  return `${title}. ${description} It has ${count} ${noun}.`
}
