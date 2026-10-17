/**
 * Where every element is at a moment of an animation. Pure, so the player
 * and the tests share it.
 *
 * Follows the playback in api/polaris/animation_format.py (`_apply`,
 * `_states_at`, `anchor`, `base_box`): a step starts from the picture at
 * the end of the step before, its actions run in start order, and each
 * action works on the state left by the ones before it. The player adds
 * what the check does not need: opacity, colour, and how much of a stroke
 * is drawn.
 */

import {
  CODE_LINE_HEIGHT,
  CODE_PADDING,
  DEFAULT_TEXT_SIZE,
  TEXT_LINE_HEIGHT,
  TEXT_WIDTH_RATIO,
  actionDuration,
  actionStart,
  elementRole,
} from './format.ts'
import type {
  Animation,
  AnimationAction,
  AnimationElement,
  AnimationPoint,
  AnimationStep,
  ColorRole,
} from './format.ts'

export type ElementState = {
  visible: boolean
  opacity: number
  dx: number
  dy: number
  scale: number
  /** Shown text after a count, or null for the element's own text. */
  text: string | null
  color: ColorRole
  /** How much of each stroke is drawn, 0 to 1: one entry, or one per graph series. */
  drawn: number[]
}

export type SceneState = Record<string, ElementState>

export type Box = {
  left: number
  top: number
  right: number
  bottom: number
}

/** The point that move and follow place. */
export function anchor(element: AnimationElement): AnimationPoint {
  if (element.kind === 'line' || element.kind === 'arrow') return element.start
  if (element.kind === 'path') return element.points[0]
  return { x: element.x, y: element.y }
}

function textExtent(text: string, size: number, lineHeight: number): { width: number; height: number } {
  const lines = text.split('\n')
  const longest = Math.max(...lines.map((line) => line.length))
  return { width: longest * size * TEXT_WIDTH_RATIO, height: lines.length * size * lineHeight }
}

/** The element's box before any move or scale. Text boxes are estimates. */
export function baseBox(element: AnimationElement, text: string | null = null): Box {
  switch (element.kind) {
    case 'text': {
      const size = element.size ?? DEFAULT_TEXT_SIZE
      const { width, height } = textExtent(text ?? element.text, size, TEXT_LINE_HEIGHT)
      let left = element.x
      if (element.align === 'middle') left = element.x - width / 2
      if (element.align === 'end') left = element.x - width
      return { left, top: element.y, right: left + width, bottom: element.y + height }
    }
    case 'code': {
      const size = element.size ?? DEFAULT_TEXT_SIZE
      const { width, height } = textExtent(element.code, size, CODE_LINE_HEIGHT)
      return {
        left: element.x,
        top: element.y,
        right: element.x + width + 2 * CODE_PADDING,
        bottom: element.y + height + 2 * CODE_PADDING,
      }
    }
    case 'line':
    case 'arrow':
      return pointsBox([element.start, element.end])
    case 'path':
      return pointsBox(element.points)
    default:
      return {
        left: element.x,
        top: element.y,
        right: element.x + element.width,
        bottom: element.y + element.height,
      }
  }
}

function pointsBox(points: AnimationPoint[]): Box {
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  return {
    left: Math.min(...xs),
    top: Math.min(...ys),
    right: Math.max(...xs),
    bottom: Math.max(...ys),
  }
}

function strokeCount(element: AnimationElement): number {
  return element.kind === 'graph' ? element.series.length : 1
}

function initialState(element: AnimationElement): ElementState {
  const visible = Boolean(element.visible_at_start)
  return {
    visible,
    opacity: visible ? 1 : 0,
    dx: 0,
    dy: 0,
    scale: 1,
    text: null,
    color: elementRole(element),
    drawn: new Array<number>(strokeCount(element)).fill(1),
  }
}

function copyScene(scene: SceneState): SceneState {
  const copy: SceneState = {}
  for (const [id, state] of Object.entries(scene)) {
    copy[id] = { ...state, drawn: [...state.drawn] }
  }
  return copy
}

function countText(value: number, decimals: number): string {
  return value.toFixed(decimals)
}

function followPoint(points: AnimationPoint[], progress: number): AnimationPoint {
  if (points.length === 1) return points[0]
  const position = Math.min(1, Math.max(0, progress)) * (points.length - 1)
  const index = Math.min(points.length - 2, Math.floor(position))
  const within = position - index
  const from = points[index]
  const to = points[index + 1]
  return { x: from.x + (to.x - from.x) * within, y: from.y + (to.y - from.y) * within }
}

/**
 * Apply ``action`` at ``progress`` (0 to 1) to the state it starts from.
 * ``startedHidden`` is whether the element was hidden when this action began.
 */
function apply(
  state: ElementState,
  element: AnimationElement,
  action: AnimationAction,
  progress: number,
  startedHidden: boolean,
): void {
  switch (action.action) {
    case 'appear': {
      const from = startedHidden ? 0 : state.opacity
      state.visible = true
      state.opacity = from + (1 - from) * progress
      if (startedHidden) state.drawn = state.drawn.map(() => 1)
      return
    }
    case 'disappear':
      state.opacity = state.opacity * (1 - progress)
      if (progress >= 1) {
        state.visible = false
        state.opacity = 0
      }
      return
    case 'trace': {
      const target = action.series ?? null
      state.visible = true
      state.opacity = 1
      state.drawn = state.drawn.map((amount, index) => {
        if (target === null || index === target) return progress
        // A hidden graph shows only the series being traced.
        return startedHidden ? 0 : amount
      })
      return
    }
    case 'move': {
      const origin = anchor(element)
      state.dx += (action.to.x - origin.x - state.dx) * progress
      state.dy += (action.to.y - origin.y - state.dy) * progress
      return
    }
    case 'follow': {
      const points = action.path.plotted ?? action.path.points ?? []
      if (points.length === 0) return
      const origin = anchor(element)
      const point = followPoint(points, progress)
      state.dx = point.x - origin.x
      state.dy = point.y - origin.y
      return
    }
    case 'scale':
      state.scale += (action.to - state.scale) * progress
      return
    case 'count': {
      const value = action.from_value + (action.to_value - action.from_value) * progress
      state.text = countText(value, action.decimals ?? 0)
      return
    }
    case 'highlight':
      state.color = action.color ?? 'highlight'
      return
  }
}

function byStart(step: AnimationStep): AnimationAction[] {
  // Array.prototype.sort is stable, like Python's sorted.
  return [...step.actions].sort((a, b) => actionStart(a) - actionStart(b))
}

function playStep(
  step: AnimationStep,
  elements: Map<string, AnimationElement>,
  start: SceneState,
  timeMs: number,
): SceneState {
  const scene = copyScene(start)
  for (const action of byStart(step)) {
    const begin = actionStart(action)
    if (begin > timeMs) continue
    const element = elements.get(action.element)
    const state = scene[action.element]
    if (!element || !state) continue
    const duration = actionDuration(action)
    const end = begin + duration
    const progress = timeMs >= end || duration === 0 ? 1 : (timeMs - begin) / duration
    apply(state, element, action, progress, !state.visible)
  }
  return scene
}

function endOfStep(
  step: AnimationStep,
  elements: Map<string, AnimationElement>,
  start: SceneState,
): SceneState {
  const scene = playStep(step, elements, start, step.duration_ms)
  // A highlight without keep lasts only for the rest of its step.
  const kept = new Map<string, ColorRole>()
  const reverted = new Set<string>()
  for (const action of byStart(step)) {
    if (action.action !== 'highlight') continue
    if (action.keep) kept.set(action.element, action.color ?? 'highlight')
    else reverted.add(action.element)
  }
  for (const id of reverted) {
    const state = scene[id]
    if (state) state.color = kept.get(id) ?? start[id].color
  }
  return scene
}

const endStates = new WeakMap<Animation, SceneState[]>()

function allEndStates(animation: Animation): SceneState[] {
  const cached = endStates.get(animation)
  if (cached) return cached
  const elements = new Map(animation.elements.map((element) => [element.id, element]))
  let scene = initialScene(animation)
  const ends: SceneState[] = []
  for (const step of animation.steps) {
    scene = endOfStep(step, elements, scene)
    ends.push(scene)
  }
  endStates.set(animation, ends)
  return ends
}

/** Every element as the animation opens, from visible_at_start. */
export function initialScene(animation: Animation): SceneState {
  const scene: SceneState = {}
  for (const element of animation.elements) scene[element.id] = initialState(element)
  return scene
}

/** The picture at the end of step ``stepIndex``. -1 is the picture before step 1. */
export function stepEndState(animation: Animation, stepIndex: number): SceneState {
  if (stepIndex < 0) return initialScene(animation)
  const ends = allEndStates(animation)
  const index = Math.min(stepIndex, ends.length - 1)
  return copyScene(ends[index])
}

/** The picture ``timeMs`` into step ``stepIndex``. At or past its duration, the step's end. */
export function stateAt(animation: Animation, stepIndex: number, timeMs: number): SceneState {
  const step = animation.steps[stepIndex]
  if (!step) return stepEndState(animation, stepIndex)
  if (timeMs >= step.duration_ms) return stepEndState(animation, stepIndex)
  const elements = new Map(animation.elements.map((element) => [element.id, element]))
  return playStep(step, elements, stepEndState(animation, stepIndex - 1), Math.max(0, timeMs))
}
