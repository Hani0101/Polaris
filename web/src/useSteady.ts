import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * A function that keeps one identity and always calls the latest handler, so a
 * memoized child that takes it is not drawn again when its parent is.
 */
export function useSteady<A extends unknown[], R>(handler: (...args: A) => R): (...args: A) => R {
  const latest = useRef(handler)
  useEffect(() => {
    latest.current = handler
  })
  return useCallback((...args: A) => latest.current(...args), [])
}

// oxlint-disable-next-line no-explicit-any -- any handler shape, called with its own arguments
type Handlers = Record<string, (...args: any[]) => unknown>

/**
 * useSteady for a set of handlers at once. The object and each function in it keep
 * one identity, and each call goes to the latest handler of that name. The names
 * are fixed by the first render.
 */
export function useSteadyHandlers<T extends Handlers>(handlers: T): T {
  const latest = useRef(handlers)
  useEffect(() => {
    latest.current = handlers
  })
  const [steady] = useState(
    () =>
      Object.fromEntries(
        Object.keys(handlers).map((name) => [
          name,
          (...args: unknown[]) => latest.current[name](...args),
        ]),
      ) as T,
  )
  return steady
}
