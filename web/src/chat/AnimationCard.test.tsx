import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { AnimationCard } from './AnimationCard.tsx'

afterEach(() => {
  cleanup()
})

const job = { id: 'job-1', kind: 'animation' as const, session_id: 'session-1' }

test('a failed job tells the session to try later (AN-09)', () => {
  render(<AnimationCard job={{ ...job, status: 'failed' }} />)

  expect(screen.getByRole('alert').textContent).toBe(
    'Polaris cannot create the animation right now. Try later.',
  )
  expect(screen.queryByRole('button', { name: /open animation/i })).toBeNull()
})

test('a running job shows as in progress', () => {
  render(<AnimationCard job={{ ...job, status: 'running' }} />)

  expect(screen.getByText('In progress')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
})

test('a ready animation opens again (AN-06)', () => {
  const onOpen = vi.fn()
  render(<AnimationCard job={{ ...job, status: 'ready' }} onOpen={onOpen} />)

  fireEvent.click(screen.getByRole('button', { name: /open animation/i }))

  expect(onOpen).toHaveBeenCalledWith('session-1', 'job-1')
})
