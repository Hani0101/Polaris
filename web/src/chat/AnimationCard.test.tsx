import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
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

test('a running job shows the stage it is in (AN-19)', () => {
  render(<AnimationCard job={{ ...job, status: 'running', stage: 'fixing' }} />)

  expect(screen.getByText('In progress')).toBeTruthy()
  expect(screen.getByRole('status').textContent).toBe('Fixing the animation')
})

test('the stage updates from polling', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn(
    async () =>
      new Response(JSON.stringify({ ...job, status: 'running', stage: 'checking' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  try {
    render(<AnimationCard job={{ ...job, status: 'running', stage: 'writing' }} />)
    expect(screen.getByRole('status').textContent).toBe('Writing the animation')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/sessions/session-1/jobs/job-1', expect.anything())
    expect(screen.getByRole('status').textContent).toBe('Checking the animation')
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

test('a finished job shows no stage', () => {
  render(<AnimationCard job={{ ...job, status: 'failed', stage: 'fixing' }} />)

  expect(screen.queryByText('Fixing the animation')).toBeNull()
})
