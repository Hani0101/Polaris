import { useCallback, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import './resize.css'

const STEP = 24

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function read(key: string): number | null {
  try {
    const value = Number(window.localStorage.getItem(key))
    return Number.isFinite(value) && value > 0 ? value : null
  } catch {
    return null
  }
}

function write(key: string, value: number) {
  try {
    window.localStorage.setItem(key, String(Math.round(value)))
  } catch {
    // The size just does not carry to the next visit.
  }
}

/** A size the learner drags, kept between visits. `null` means the stylesheet default. */
export function useSize(storageKey: string, min: number, max: number) {
  const [size, setSize] = useState<number | null>(() => {
    const saved = read(storageKey)
    return saved === null ? null : clamp(saved, min, max)
  })
  const update = useCallback(
    (next: number) => {
      const value = clamp(next, min, max)
      setSize(value)
      write(storageKey, value)
    },
    [storageKey, min, max],
  )
  return [size, update] as const
}

type ResizeHandleProps = {
  label: string
  /** `vertical` is a divider between side-by-side areas, `horizontal` between stacked ones. */
  orientation: 'vertical' | 'horizontal'
  /** The size now, measured when a drag starts. */
  measure: () => number
  /** Which way the pointer moving forward grows the area. */
  grows: 1 | -1
  onResize: (size: number) => void
  min: number
  max: number
}

export function ResizeHandle({
  label,
  orientation,
  measure,
  grows,
  onResize,
  min,
  max,
}: ResizeHandleProps) {
  const [dragging, setDragging] = useState(false)
  const axis = orientation === 'vertical' ? 'clientX' : 'clientY'

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    event.preventDefault()
    const target = event.currentTarget
    target.setPointerCapture(event.pointerId)
    const from = event[axis]
    const start = measure()
    setDragging(true)
    function move(moveEvent: globalThis.PointerEvent) {
      onResize(start + (moveEvent[axis] - from) * grows)
    }
    function stop() {
      setDragging(false)
      target.removeEventListener('pointermove', move)
      target.removeEventListener('pointerup', stop)
      target.removeEventListener('pointercancel', stop)
    }
    target.addEventListener('pointermove', move)
    target.addEventListener('pointerup', stop)
    target.addEventListener('pointercancel', stop)
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const forward = orientation === 'vertical' ? 'ArrowRight' : 'ArrowDown'
    const back = orientation === 'vertical' ? 'ArrowLeft' : 'ArrowUp'
    if (event.key !== forward && event.key !== back) return
    event.preventDefault()
    const direction = (event.key === forward ? 1 : -1) * grows
    onResize(measure() + direction * STEP)
  }

  return (
    <div
      role="separator"
      aria-orientation={orientation}
      aria-label={label}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={Math.round(measure())}
      tabIndex={0}
      className={`resize-handle resize-handle--${orientation}${dragging ? ' is-dragging' : ''}`}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
    />
  )
}
