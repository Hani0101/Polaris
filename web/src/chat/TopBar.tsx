import { IconButton, MenuIcon } from './ui.tsx'

type TopBarProps = {
  sessionTitle: string | null
  sessionListOpen: boolean
  onToggleSessions: () => void
  onLeave: () => void
  canLeave: boolean
}

export function TopBar({
  sessionTitle,
  sessionListOpen,
  onToggleSessions,
  onLeave,
  canLeave,
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
      </div>
    </header>
  )
}
