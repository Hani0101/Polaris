import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { CloseIcon, IconButton } from './ui.tsx'
import './overlay.css'

type ModalProps = {
  open: boolean
  title: string
  children: ReactNode
  /**
   * The main action, a verb such as "Clear board". Leave it out for a dialog
   * whose choices apply at once, such as Appearance: it then has only the
   * cancel button, labelled by cancelLabel.
   */
  mainLabel?: string
  onMain?: () => void
  /** Called for Cancel, the close button, Escape, and the dim layer. Closing always means cancel. */
  onCancel: () => void
  /** confirm: before a destructive action, the main button is destructive. */
  variant?: 'default' | 'confirm'
  cancelLabel?: string
}

const FOCUSABLE =
  'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'

function focusables(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)]
}

function exitDuration(): number {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--motion-duration-fast')
    .trim()
  const value = Number.parseFloat(raw)
  if (!Number.isFinite(value)) return 0
  if (raw.endsWith('ms')) return value
  if (raw.endsWith('s')) return value * 1000
  return value
}

/** Keeps the dialog mounted while it fades out. */
function useShown(open: boolean): boolean {
  const [shown, setShown] = useState(open)
  if (open && !shown) setShown(true)
  useEffect(() => {
    if (open || !shown) return
    const timer = window.setTimeout(() => setShown(false), exitDuration())
    return () => window.clearTimeout(timer)
  }, [open, shown])
  return shown
}

export function Modal({
  open,
  title,
  children,
  mainLabel,
  onMain,
  onCancel,
  variant = 'default',
  cancelLabel = 'Cancel',
}: ModalProps) {
  const shown = useShown(open)
  const titleId = useId()
  const bodyId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const first = bodyRef.current ? focusables(bodyRef.current)[0] : undefined
    ;(first ?? cancelRef.current)?.focus()

    const keepInside = (event: FocusEvent) => {
      const panel = panelRef.current
      if (!panel || !(event.target instanceof Node) || panel.contains(event.target)) return
      // A dialog opened from this one, such as a confirm, holds focus while it is open.
      if (event.target instanceof Element && event.target.closest('.modal-layer')) return
      ;(focusables(panel)[0] ?? panel).focus()
    }
    document.addEventListener('focusin', keepInside)
    return () => {
      document.removeEventListener('focusin', keepInside)
      if (opener?.isConnected) opener.focus()
    }
  }, [open])

  if (!shown) return null

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onCancel()
      return
    }
    if (event.key !== 'Tab' || !panelRef.current) return
    const items = focusables(panelRef.current)
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return createPortal(
    <div className="modal-layer" data-state={open ? 'open' : 'closing'}>
      <div className="modal-dim" aria-hidden="true" onClick={onCancel} />
      <div
        ref={panelRef}
        className="modal"
        role={variant === 'confirm' ? 'alertdialog' : 'dialog'}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <div className="modal-head">
          <h2 id={titleId} className="modal-title">
            {title}
          </h2>
          <IconButton label="Close" size="sm" onClick={onCancel}>
            <CloseIcon />
          </IconButton>
        </div>
        <div ref={bodyRef} id={bodyId} className="modal-body">
          {children}
        </div>
        <div className="modal-actions">
          <button ref={cancelRef} type="button" className="secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          {mainLabel && onMain ? (
            <button
              type="button"
              className={variant === 'confirm' ? 'destructive' : undefined}
              onClick={onMain}
            >
              {mainLabel}
            </button>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  )
}
