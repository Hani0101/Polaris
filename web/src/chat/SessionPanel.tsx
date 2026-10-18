import { memo, useCallback, useState } from 'react'
import { Ellipsis, Pencil, Settings, SunMoon, Trash2, UserRound } from 'lucide-react'
import { ApiError, sessionLabel } from '../api.ts'
import type { SessionSummary } from '../api.ts'
import { AppearanceDialog } from '../AppearanceDialog.tsx'
import { ProfileDialog } from '../ProfileDialog.tsx'
import { DeleteDialog } from './DeleteDialog.tsx'
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
  onDelete: (sessionId: string) => Promise<void>
  /** Opens the sign-in page from the Profile dialog (AU-02). */
  onSignIn: () => void
}

/** The session list. Memoized, so a streamed chunk does not draw every row again. */
export const SessionPanel = memo(function SessionPanel({
  sessions,
  openId,
  loading,
  open,
  onClose,
  onStart,
  onOpen,
  onRename,
  onDelete,
  onSignIn,
}: SessionPanelProps) {
  // The session being renamed stays set while the dialog fades out.
  const [target, setTarget] = useState<SessionSummary | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [value, setValue] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [settingsDialog, setSettingsDialog] = useState<'appearance' | 'profile' | null>(null)

  const startRename = useCallback((session: SessionSummary) => {
    setTarget(session)
    setValue(session.name)
    setRenameError(null)
    setRenaming(true)
  }, [])

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

  const startDelete = useCallback((session: SessionSummary) => {
    setTarget(session)
    setDeleteError(null)
    setDeleting(true)
  }, [])

  async function confirmDelete() {
    if (!target || deleteBusy) return
    setDeleteBusy(true)
    try {
      await onDelete(target.id)
      setDeleting(false)
    } catch (caught) {
      setDeleteError(
        caught instanceof ApiError
          ? caught.message
          : "Couldn't delete the session. Check your connection and try again.",
      )
    } finally {
      setDeleteBusy(false)
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
            <SessionRow
              key={session.id}
              session={session}
              current={openId === session.id}
              onOpen={onOpen}
              onRename={startRename}
              onDelete={startDelete}
            />
          ))}
        </ul>
      ) : null}
      <div className="session-panel-footer">
        {/* ST-01: Settings opens upward from the bottom of the panel; each item opens a dialog. */}
        <DropdownMenu
          label="Settings"
          triggerClassName="ghost"
          overDrawer
          placement="above"
          items={[
            {
              id: 'appearance',
              label: 'Appearance',
              icon: <SunMoon size={20} strokeWidth={2} aria-hidden="true" />,
              onSelect: () => setSettingsDialog('appearance'),
            },
            {
              id: 'profile',
              label: 'Profile',
              icon: <UserRound size={20} strokeWidth={2} aria-hidden="true" />,
              onSelect: () => setSettingsDialog('profile'),
            },
          ]}
        >
          <Settings size={20} strokeWidth={2} aria-hidden="true" />
          Settings
        </DropdownMenu>
      </div>
      <AppearanceDialog
        open={settingsDialog === 'appearance'}
        onClose={() => setSettingsDialog(null)}
      />
      <ProfileDialog
        open={settingsDialog === 'profile'}
        onClose={() => setSettingsDialog(null)}
        onSignIn={() => {
          setSettingsDialog(null)
          onSignIn()
        }}
      />
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
      <DeleteDialog
        open={deleting}
        label={target ? sessionLabel(target) : ''}
        error={deleteError}
        onDelete={() => void confirmDelete()}
        onCancel={() => setDeleting(false)}
      />
    </nav>
  )
})

/** One session in the list, with its menu. It is drawn again only when it changes. */
const SessionRow = memo(function SessionRow({
  session,
  current,
  onOpen,
  onRename,
  onDelete,
}: {
  session: SessionSummary
  current: boolean
  onOpen: (sessionId: string) => void
  onRename: (session: SessionSummary) => void
  onDelete: (session: SessionSummary) => void
}) {
  return (
    <li className={current ? 'session-row is-current' : 'session-row'}>
      <button
        type="button"
        className="session-item"
        aria-current={current ? 'page' : undefined}
        onClick={() => onOpen(session.id)}
      >
        <span className="session-item-title">{sessionLabel(session)}</span>
        {session.ended ? <span className="session-item-meta">Ended</span> : null}
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
            onSelect: () => onRename(session),
          },
          {
            id: 'delete',
            label: 'Delete',
            icon: <Trash2 size={20} strokeWidth={2} aria-hidden="true" />,
            destructive: true,
            onSelect: () => onDelete(session),
          },
        ]}
      >
        <Ellipsis size={20} strokeWidth={2} aria-hidden="true" />
      </DropdownMenu>
    </li>
  )
})
