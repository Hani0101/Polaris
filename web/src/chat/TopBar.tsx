import { memo } from 'react'
import { LogIn, LogOut, PanelRight } from 'lucide-react'
import type { SignInState } from '../auth.ts'
import { DropdownMenu } from './Menu.tsx'
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
  /** Sign-in is optional (AU-01). Anonymous shows Sign in; signed in shows the account. */
  account?: SignInState
  onSignIn?: () => void
  onSignOut?: () => void
}

/** Up to two letters: the first of each word, else the first of the name. */
function initials(username: string): string {
  const words = username.trim().split(/[\s._-]+/).filter(Boolean)
  const letters = words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? '?')[0]
  return letters.toUpperCase()
}

export const TopBar = memo(function TopBar({
  sessionTitle,
  sessionListOpen,
  onToggleSessions,
  onLeave,
  canLeave,
  showToolsToggle = false,
  toolsOpen = false,
  onToggleTools,
  account,
  onSignIn,
  onSignOut,
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
        {account?.status === 'anonymous' && onSignIn ? (
          <button type="button" className="ghost" onClick={onSignIn}>
            <LogIn size={20} strokeWidth={2} aria-hidden="true" />
            Sign in
          </button>
        ) : null}
        {account?.status === 'signed-in' && onSignOut ? (
          <DropdownMenu
            label="Account"
            triggerClassName="avatar-btn"
            items={[
              {
                id: 'sign-out',
                label: 'Sign out',
                icon: <LogOut size={20} strokeWidth={2} aria-hidden="true" />,
                onSelect: onSignOut,
              },
            ]}
          >
            <span className="avatar" aria-hidden="true">
              {initials(account.username)}
            </span>
          </DropdownMenu>
        ) : null}
      </div>
    </header>
  )
})
