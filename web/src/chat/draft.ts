import { useSyncExternalStore } from 'react'

/**
 * The message being typed. Only the composer reads it while the learner types, so
 * a key draws the composer alone, not the app around it. The app reads it on send.
 */
export type Draft = {
  get: () => string
  set: (text: string) => void
  subscribe: (listener: () => void) => () => void
}

export function createDraft(text = ''): Draft {
  let current = text
  const listeners = new Set<() => void>()
  return {
    get: () => current,
    set(next) {
      if (next === current) return
      current = next
      for (const listener of listeners) listener()
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

export function useDraftText(draft: Draft): string {
  return useSyncExternalStore(draft.subscribe, draft.get)
}
