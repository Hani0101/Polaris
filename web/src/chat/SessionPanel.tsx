import { useState } from 'react'
import { Ellipsis, Pencil, Settings } from 'lucide-react'
import { ApiError, sessionLabel } from '../api.ts'
import type { SessionSummary } from '../api.ts'
import { DropdownMenu } from './Menu.tsx'
import { RenameDialog } from './RenameDialog.tsx'
import { CloseIcon, EmptyState, IconButton } from './ui.tsx'

type SessionPanelProps = {
  sessions: SessionSummary[]
  openId: string | null
  loading: boolean
  open: boolean
  onClose: () => void
  onStart: () => void
  onOpen: (sessionId: string) => void
  onRename: (sessionId: string, name: string) => Promise<void>
  onOpenSettings: () => void
}

export function SessionPanel({
  sessions,
  openId,
  loading,
  open,
  onClose,
  onStart,
  onOpen,
  onRename,
  onOpenSettings,
}: SessionPanelProps) {
  // The session being renamed stays set while the dialog fades out.
  const [target, setTarget] = useState<SessionSummary | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [value, setValue] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)

  function startRename(session: SessionSummary) {
    setTarget(session)
    setValue(session.name)
    setRenameError(null)
    setRenaming(true)
  }

  async function saveRename() {
    if (!target) return
    try {
      await onRename(target.id, value)
      setRenaming(false)
    } catch (caught) {
      setRenameError(
        caught instanceof ApiError
          ? caught.message
          : "Couldn't rename the session. Check your connection and try again.",
      )
    }
  }

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
            <li
              key={session.id}
              className={openId === session.id ? 'session-row is-current' : 'session-row'}
            >
              <button
                type="button"
                className="session-item"
                aria-current={openId === session.id ? 'page' : undefined}
                onClick={() => onOpen(session.id)}
              >
                <span className="session-item-title">{sessionLabel(session)}</span>
                {session.ended ? (
                  <span className="session-item-meta">Ended</span>
                ) : null}
              </button>
              <DropdownMenu
                label={`Actions for ${sessionLabel(session)}`}
                triggerClassName="icon-btn icon-btn--ghost icon-btn--sm"
                overDrawer
                items={[
                  {
                    id: 'rename',
                    label: 'Rename',
                    icon: <Pencil size={20} strokeWidth={2} aria-hidden="true" />,
                    onSelect: () => startRename(session),
                  },
                ]}
              >
                <Ellipsis size={20} strokeWidth={2} aria-hidden="true" />
              </DropdownMenu>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="session-panel-footer">
        <button type="button" className="ghost" onClick={onOpenSettings}>
          <Settings size={20} strokeWidth={2} aria-hidden="true" />
          Settings
        </button>
      </div>
      <RenameDialog
        open={renaming}
        value={value}
        error={renameError}
        onChange={(next) => {
          setValue(next)
          setRenameError(null)
        }}
        onSave={() => void saveRename()}
        onCancel={() => setRenaming(false)}
      />
    </nav>
  )
}
