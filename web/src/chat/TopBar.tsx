import { PanelRight } from 'lucide-react'
import { IconButton, MenuIcon } from './ui.tsx'

type TopBarProps = {
  sessionTitle: string | null
  sessionListOpen: boolean
  onToggleSessions: () => void
  onLeave: () => void
  canLeave: boolean
  /** 640px and up with a session open: the tools panel button on the right. */
  showToolsToggle?: boolean
  toolsOpen?: boolean
  onToggleTools?: () => void
}

export function TopBar({
  sessionTitle,
  sessionListOpen,
  onToggleSessions,
  onLeave,
  canLeave,
  showToolsToggle = false,
  toolsOpen = false,
  onToggleTools,
}: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar-start">
        <IconButton
          label={sessionListOpen ? 'Hide sessions' : 'Open sessions'}
          onClick={onToggleSessions}
        >
          <MenuIcon />
        </IconButton>
        <p className="top-bar-mark">Polaris</p>
      </div>
      <p className="top-bar-title">{sessionTitle ?? ''}</p>
      <div className="top-bar-end">
        {canLeave ? (
          <button type="button" className="ghost" onClick={onLeave}>
            Leave session
          </button>
        ) : null}
        {showToolsToggle && onToggleTools ? (
          <IconButton label={toolsOpen ? 'Hide tools' : 'Open tools'} onClick={onToggleTools}>
            <PanelRight size={24} strokeWidth={2} aria-hidden="true" />
          </IconButton>
        ) : null}
      </div>
    </header>
  )
}
