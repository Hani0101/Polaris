import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import './overlay.css'

export type MenuItem = {
  id: string
  label: string
  /** An icon next to the label. Destructive items always have one (Dropdown menu rules). */
  icon?: ReactNode
  onSelect: () => void
  destructive?: boolean
  disabled?: boolean
}

type DropdownMenuProps = {
  /** Screen reader name of the button that opens the menu. */
  label: string
  /** What the button shows, usually an icon. */
  children: ReactNode
  items: MenuItem[]
  triggerClassName?: string
  /** The menu opens from inside the drawer, so it must sit above it. */
  overDrawer?: boolean
  /** Shows the button as the selected tool. */
  pressed?: boolean
  disabled?: boolean
  /** "above" opens upward whenever it fits, as from a button at the bottom of a panel. */
  placement?: 'auto' | 'above'
}

type Place = { left: number; top: number; above: boolean }

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

/** Keeps the menu mounted while it fades out. */
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

function rows(menu: HTMLElement | null): HTMLButtonElement[] {
  if (!menu) return []
  return [...menu.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')]
}

export function DropdownMenu({
  label,
  children,
  items,
  triggerClassName,
  overDrawer,
  pressed,
  disabled,
  placement = 'auto',
}: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const shown = useShown(open)
  const [place, setPlace] = useState<Place>({ left: 0, top: 0, above: false })
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const menuId = useId()
  const regular = items.filter((item) => !item.destructive)
  const destructive = items.filter((item) => item.destructive)

  useLayoutEffect(() => {
    if (!open) return
    const trigger = triggerRef.current
    const menu = menuRef.current
    if (!trigger || !menu) return
    const rect = trigger.getBoundingClientRect()
    const width = menu.offsetWidth
    const height = menu.offsetHeight
    const fitsAbove = rect.top - height >= 0
    const above =
      placement === 'above'
        ? fitsAbove
        : rect.bottom + height > window.innerHeight && fitsAbove
    const left = Math.max(0, Math.min(rect.left, window.innerWidth - width))
    setPlace({ left, top: above ? rect.top : rect.bottom, above })
    rows(menu)[0]?.focus()
  }, [open, placement])

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (menuRef.current?.contains(target) || triggerRef.current?.contains(target)) return
      setOpen(false)
    }
    const closeOnResize = () => setOpen(false)
    document.addEventListener('pointerdown', closeOutside, true)
    window.addEventListener('resize', closeOnResize)
    return () => {
      document.removeEventListener('pointerdown', closeOutside, true)
      window.removeEventListener('resize', closeOnResize)
    }
  }, [open])

  function close() {
    setOpen(false)
    triggerRef.current?.focus()
  }

  function choose(item: MenuItem) {
    if (item.disabled) return
    close()
    item.onSelect()
  }

  function onMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const list = rows(menuRef.current)
    const at = list.indexOf(document.activeElement as HTMLButtonElement)
    let next: HTMLButtonElement | undefined
    if (event.key === 'ArrowDown') next = list[(at + 1) % list.length]
    else if (event.key === 'ArrowUp') next = list[(at - 1 + list.length) % list.length]
    else if (event.key === 'Home') next = list[0]
    else if (event.key === 'End') next = list[list.length - 1]
    else if (event.key === 'Escape' || event.key === 'Tab') {
      event.preventDefault()
      event.stopPropagation()
      close()
      return
    } else return
    event.preventDefault()
    event.stopPropagation()
    next?.focus()
  }

  function onTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
    }
  }

  function row(item: MenuItem) {
    return (
      <button
        key={item.id}
        type="button"
        role="menuitem"
        tabIndex={-1}
        className={item.destructive ? 'dropdown-item is-destructive' : 'dropdown-item'}
        disabled={item.disabled}
        onClick={() => choose(item)}
      >
        {item.icon}
        <span>{item.label}</span>
      </button>
    )
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={triggerClassName}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={shown ? menuId : undefined}
        aria-pressed={pressed}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={onTriggerKeyDown}
      >
        {children}
      </button>
      {shown
        ? createPortal(
            <div
              ref={menuRef}
              id={menuId}
              role="menu"
              aria-label={label}
              className={[
                'dropdown-menu',
                place.above ? 'is-above' : '',
                overDrawer ? 'is-over-drawer' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              data-state={open ? 'open' : 'closing'}
              style={{ left: place.left, top: place.top }}
              onKeyDown={onMenuKeyDown}
            >
              {regular.map(row)}
              {regular.length > 0 && destructive.length > 0 ? (
                <div role="separator" className="dropdown-separator" />
              ) : null}
              {destructive.map(row)}
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
