import type { SessionSummary } from '../api.ts'
import { CloseIcon, EmptyState, IconButton } from './ui.tsx'

type SessionPanelProps = {
  sessions: SessionSummary[]
  openId: string | null
  loading: boolean
  open: boolean
  onClose: () => void
  onStart: () => void
  onOpen: (sessionId: string) => void
}

export function SessionPanel({
  sessions,
  openId,
  loading,
  open,
  onClose,
  onStart,
  onOpen,
}: SessionPanelProps) {
  return (
    <nav
      id="session-panel"
      className={open ? 'session-panel is-open' : 'session-panel'}
      aria-label="Sessions"
      inert={open ? undefined : true}
    >
      <div className="session-panel-head">
        <h2 className="session-panel-title">Sessions</h2>
        <IconButton label="Close sessions" size="sm" onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </div>
      <div className="session-panel-action">
        <button type="button" onClick={onStart}>
          Start a session
        </button>
      </div>
      {loading ? (
        <ul className="session-list" aria-label="Loading" aria-busy="true">
          <li className="skeleton skeleton-session" />
          <li className="skeleton skeleton-session" />
          <li className="skeleton skeleton-session" />
        </ul>
      ) : null}
      {!loading && sessions.length === 0 ? (
        <EmptyState title="No sessions yet" body="Ask Polaris anything to start one." />
      ) : null}
      {!loading && sessions.length > 0 ? (
        <ul className="session-list">
          {sessions.map((session) => (
            <li key={session.id}>
              <button
                type="button"
                className="session-item"
                aria-current={openId === session.id ? 'page' : undefined}
                onClick={() => onOpen(session.id)}
              >
                <span className="session-item-title">
                  {session.preview || 'New session'}
                </span>
                {session.ended ? (
                  <span className="session-item-meta">Ended</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </nav>
  )
}
