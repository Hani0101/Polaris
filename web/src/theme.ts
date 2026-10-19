import { useSyncExternalStore } from 'react'

/** The appearance mode (ST-02): the learner's choice, kept in this browser (ST-05). */
export type Mode = 'system' | 'light' | 'dark'
export type Tone = 'light' | 'dark'

export const MODE_KEY = 'polaris.appearance'
const DARK_QUERY = '(prefers-color-scheme: dark)'

export const MODES: readonly Mode[] = ['system', 'light', 'dark']

export function readMode(): Mode {
  try {
    const stored = window.localStorage.getItem(MODE_KEY)
    return stored === 'light' || stored === 'dark' ? stored : 'system'
  } catch {
    // The browser cannot keep the choice, so the app uses System (ST-07).
    return 'system'
  }
}

let current: Mode = readMode()
const listeners = new Set<() => void>()

/** System sets no attribute: the operating system's setting decides (ST-03). */
function applyMode(mode: Mode) {
  const root = document.documentElement
  if (mode === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', mode)
}

export function getMode(): Mode {
  return current
}

export function setMode(mode: Mode) {
  current = mode
  applyMode(mode)
  try {
    if (mode === 'system') window.localStorage.removeItem(MODE_KEY)
    else window.localStorage.setItem(MODE_KEY, mode)
  } catch {
    // The choice still applies for this visit (ST-07).
  }
  for (const listener of listeners) listener()
}

function systemTone(): Tone {
  return typeof window.matchMedia === 'function' && window.matchMedia(DARK_QUERY).matches
    ? 'dark'
    : 'light'
}

/** The colors in use now: the chosen mode, or the operating system's when it is System. */
export function resolvedTone(mode: Mode = current): Tone {
  return mode === 'system' ? systemTone() : mode
}

function subscribe(notify: () => void) {
  listeners.add(notify)
  const media = typeof window.matchMedia === 'function' ? window.matchMedia(DARK_QUERY) : null
  media?.addEventListener('change', notify)
  return () => {
    listeners.delete(notify)
    media?.removeEventListener('change', notify)
  }
}

export function useAppearance(): { mode: Mode; tone: Tone; setMode: (mode: Mode) => void } {
  const mode = useSyncExternalStore(subscribe, getMode)
  const tone = useSyncExternalStore(subscribe, () => resolvedTone())
  return { mode, tone, setMode }
}
