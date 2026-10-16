import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent, ReactNode, RefObject } from 'react'

type Stop = 'start' | 'full'

type Drag = {
  pointerId: number
  startY: number
  startHeight: number
  moved: boolean
}

// DS-GAP: how far the handle must move before a tap becomes a drag, used space.xs (8px)
const DRAG_SLOP = 8

type BottomSheetProps = {
  open: boolean
  labelledBy: string
  onClose: () => void
  returnFocus: RefObject<HTMLElement | null>
  children: ReactNode
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

/** The sheet's start height in px, read from component.bottomSheet.startHeight. */
function startHeight(node: HTMLElement, full: number): number {
  const value = getComputedStyle(node).getPropertyValue('--component-bottom-sheet-start-height')
  const percent = Number.parseFloat(value)
  return Number.isFinite(percent) ? (full * percent) / 100 : 0
}

/**
 * Phone tools sheet (DESIGN.md section 7, Bottom sheet). Two stops: the start
 * height and full screen. Tapping the handle switches stops; dragging the
 * handle follows the finger, settles at the nearest stop, and closes when
 * dragged below the start height.
 */
export function BottomSheet({ open, labelledBy, onClose, returnFocus, children }: BottomSheetProps) {
  const sheet = useRef<HTMLDivElement>(null)
  const handle = useRef<HTMLButtonElement>(null)
  const drag = useRef<Drag | null>(null)
  const dragged = useRef(false)
  const wasOpen = useRef(open)
  const [stop, setStop] = useState<Stop>('start')
  const [dragHeight, setDragHeight] = useState<number | null>(null)
  const [rendered, setRendered] = useState(open)
  const [lastOpen, setLastOpen] = useState(open)

  if (open !== lastOpen) {
    setLastOpen(open)
    if (open) {
      setRendered(true)
      setStop('start')
      setDragHeight(null)
    }
  }

  useEffect(() => {
    if (open) handle.current?.focus()
    else if (wasOpen.current) returnFocus.current?.focus()
    wasOpen.current = open
  }, [open, returnFocus])

  function onPointerDown(event: PointerEvent<HTMLButtonElement>) {
    const node = sheet.current
    if (!node) return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    drag.current = {
      pointerId: event.pointerId,
      startY: event.clientY,
      startHeight: node.getBoundingClientRect().height,
      moved: false,
    }
  }

  function onPointerMove(event: PointerEvent<HTMLButtonElement>) {
    const current = drag.current
    if (!current || current.pointerId !== event.pointerId) return
    const delta = current.startY - event.clientY
    if (!current.moved && Math.abs(delta) < DRAG_SLOP) return
    current.moved = true
    setDragHeight(clamp(current.startHeight + delta, 0, window.innerHeight))
  }

  function onPointerUp(event: PointerEvent<HTMLButtonElement>) {
    const current = drag.current
    drag.current = null
    const node = sheet.current
    if (!current || !current.moved || !node) return
    dragged.current = true
    const full = window.innerHeight
    const height = clamp(current.startHeight + current.startY - event.clientY, 0, full)
    const start = startHeight(node, full)
    if (height < start - DRAG_SLOP) {
      // Keep the dragged height so the sheet slides down from where it was let go.
      onClose()
      return
    }
    setDragHeight(null)
    setStop(height - start < full - height ? 'start' : 'full')
  }

  function onPointerCancel() {
    drag.current = null
    setDragHeight(null)
  }

  function onHandleClick() {
    if (dragged.current) {
      dragged.current = false
      return
    }
    setStop((current) => (current === 'start' ? 'full' : 'start'))
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    // The whiteboard uses Escape itself (to clear a selection); leave those presses alone.
    if (event.key !== 'Escape' || event.defaultPrevented) return
    event.stopPropagation()
    onClose()
  }

  const classes = ['bottom-sheet']
  if (open) classes.push('is-open')
  if (stop === 'full') classes.push('is-full')
  if (dragHeight !== null && open) classes.push('is-dragging')

  return (
    <div
      ref={sheet}
      className={classes.join(' ')}
      role="dialog"
      aria-labelledby={labelledBy}
      inert={open ? undefined : true}
      style={dragHeight !== null ? { height: `${dragHeight}px` } : undefined}
      onKeyDown={onKeyDown}
      onTransitionEnd={(event) => {
        if (event.target !== event.currentTarget || open) return
        setRendered(false)
        setDragHeight(null)
      }}
    >
      <button
        ref={handle}
        type="button"
        className="bottom-sheet-handle"
        aria-label={stop === 'full' ? 'Shrink tools' : 'Expand tools'}
        onClick={onHandleClick}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
      >
        <span className="bottom-sheet-grip" aria-hidden="true" />
      </button>
      <div className="bottom-sheet-body">{rendered ? children : null}</div>
    </div>
  )
}
