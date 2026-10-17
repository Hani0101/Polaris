import { resolvedTone } from '../theme.ts'
import type { Tone } from '../theme.ts'

const KEY_PREFIX = 'polaris.whiteboard.tone.'

/**
 * The colors a whiteboard keeps (WB-22). A board takes the app's colors the first time this
 * browser opens it and keeps them when the mode changes, so a switch never recolors a board the
 * learner drew on. The choice is kept in this browser, like the mode (decision 0010).
 */
export function boardTone(whiteboardId: string): Tone {
  const key = KEY_PREFIX + whiteboardId
  try {
    const stored = window.localStorage.getItem(key)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    return resolvedTone()
  }
  const tone = resolvedTone()
  try {
    window.localStorage.setItem(key, tone)
  } catch {
    // Without storage the board takes the current colors each time it opens.
  }
  return tone
}
