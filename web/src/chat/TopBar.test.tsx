import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { SignInState } from '../auth.ts'
import { TopBar } from './TopBar.tsx'

afterEach(() => {
  cleanup()
})

function renderBar(account: SignInState, onSignIn = vi.fn(), onSignOut = vi.fn()) {
  render(
    <TopBar
      sessionTitle={null}
      sessionListOpen={false}
      onToggleSessions={() => {}}
      onLeave={() => {}}
      canLeave={false}
      account={account}
      onSignIn={onSignIn}
      onSignOut={onSignOut}
    />,
  )
  return { onSignIn, onSignOut }
}

test('a Sign in button opens the sign-in page [AU-02]', () => {
  const { onSignIn } = renderBar({ status: 'anonymous' })

  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(onSignIn).toHaveBeenCalled()
})

test('a signed-in learner sees their initials and can sign out [AU-11]', () => {
  const { onSignOut } = renderBar({ status: 'signed-in', username: 'ada lovelace' })

  expect(screen.queryByRole('button', { name: 'Sign in' })).toBeNull()
  const account = screen.getByRole('button', { name: 'Account' })
  expect(account.textContent).toBe('AL')
  fireEvent.click(account)
  fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }))

  expect(onSignOut).toHaveBeenCalled()
})

test('nothing shows while the page checks for an earlier sign-in', () => {
  renderBar({ status: 'checking' })

  expect(screen.queryByRole('button', { name: 'Sign in' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Account' })).toBeNull()
})
