/**
 * The animation engines and the quality and frame rate each one offers (AN-21, AN-26).
 * Matches ENGINE_OPTIONS in api/polaris/animation_engines.py, which refuses anything
 * else. The dialog offers only these values, so the learner cannot pick an illegal one.
 */

import type { AnimationEngine, AnimationSettings } from '../api.ts'

export type Choice<T> = { value: T; label: string; helper?: string }

export type EngineChoice = {
  engine: AnimationEngine
  label: string
  helper: string
  qualities: Choice<string>[]
  frameRates: Choice<number>[]
  defaults: { quality: string; fps: number }
}

export const ENGINES: EngineChoice[] = [
  {
    engine: 'manim',
    label: 'Manim',
    helper: 'Best for scientific topics: maths, physics, equations, and graphs.',
    qualities: [
      { value: '480p', label: 'Low (480p)', helper: 'Renders fastest' },
      { value: '720p', label: 'Medium (720p)' },
      { value: '1080p', label: 'High (1080p)', helper: 'Sharpest, takes longest to render' },
    ],
    frameRates: [
      { value: 15, label: '15 fps', helper: 'Renders fastest' },
      { value: 24, label: '24 fps', helper: 'Film look' },
      { value: 30, label: '30 fps' },
      { value: 60, label: '60 fps', helper: 'Smoothest motion, takes longest to render' },
    ],
    defaults: { quality: '1080p', fps: 60 },
  },
  {
    engine: 'lottie',
    label: 'Lottie',
    helper: 'Best for other topics: how things work, processes, stories, and timelines.',
    qualities: [
      { value: 'low', label: 'Low', helper: 'Simpler curves, plays best on slow devices' },
      { value: 'medium', label: 'Medium' },
      { value: 'high', label: 'High', helper: 'Smoothest curves' },
    ],
    frameRates: [
      { value: 24, label: '24 fps', helper: 'Film look' },
      { value: 30, label: '30 fps' },
      { value: 60, label: '60 fps', helper: 'Smoothest motion' },
    ],
    defaults: { quality: 'high', fps: 30 },
  },
]

export function engineChoice(engine: AnimationEngine): EngineChoice {
  return ENGINES.find((choice) => choice.engine === engine) ?? ENGINES[0]
}

/** The engine's own defaults, used when the learner picks or switches engine. */
export function defaultSettings(engine: AnimationEngine): AnimationSettings {
  const { quality, fps } = engineChoice(engine).defaults
  return { engine, quality, fps }
}

/** True when the engine offers this quality and frame rate. */
export function isLegal(settings: AnimationSettings): boolean {
  const choice = ENGINES.find((item) => item.engine === settings.engine)
  return Boolean(
    choice &&
      choice.qualities.some((item) => item.value === settings.quality) &&
      choice.frameRates.some((item) => item.value === settings.fps),
  )
}

/** What a card shows for a job's settings, such as "Manim · High (1080p) · 60 fps". */
export function settingsText(settings: AnimationSettings): string {
  const choice = engineChoice(settings.engine)
  const quality =
    choice.qualities.find((item) => item.value === settings.quality)?.label ?? settings.quality
  return `${choice.label} · ${quality} · ${settings.fps} fps`
}

/** The visible learner turn the Create animation dialog sends (AN-26). */
export function animationRequest(topic: string): string {
  return `Make an animation: ${topic.trim()}`
}
