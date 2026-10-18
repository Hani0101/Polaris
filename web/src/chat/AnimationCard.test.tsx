import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { AnimationCard } from './AnimationCard.tsx'
import { _stopJobPolling } from './animationJob.ts'
import { _clearNoticeWatchers, _setNoticeWatchers, watchAnimationJob } from './animationNotices.ts'

afterEach(() => {
  cleanup()
  _clearNoticeWatchers()
  _setNoticeWatchers(null)
  _stopJobPolling()
})

const job = { id: 'job-1', kind: 'animation' as const, session_id: 'session-1' }

function jobResponse(fields: { status: string; stage?: string }) {
  return async () =>
    new Response(JSON.stringify({ ...job, ...fields }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
}

async function waitForPoll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10_000)
  })
}

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

test('a queued job says it is waiting for another animation (AN-25)', () => {
  render(<AnimationCard job={{ ...job, status: 'running', stage: 'queued' }} />)

  expect(screen.getByText('In progress')).toBeTruthy()
  expect(screen.getByRole('status').textContent).toBe('Waiting for another animation to finish')
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

test('two cards and the notice watcher share one poll of the job', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn(jobResponse({ status: 'running', stage: 'checking' }))
  vi.stubGlobal('fetch', fetchMock)
  _setNoticeWatchers({ askPermission: vi.fn().mockResolvedValue('granted'), showReady: vi.fn() })
  try {
    watchAnimationJob('session-1', 'job-1')
    render(
      <>
        <AnimationCard job={{ ...job, status: 'running', stage: 'writing' }} />
        <AnimationCard job={{ ...job, status: 'running', stage: 'writing' }} />
      </>,
    )

    await waitForPoll()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getAllByRole('status').map((line) => line.textContent)).toEqual([
      'Checking the animation',
      'Checking the animation',
    ])

    await waitForPoll()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

test('a finished job stops the shared poll for every card and the watcher', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn(jobResponse({ status: 'ready' }))
  vi.stubGlobal('fetch', fetchMock)
  const showReady = vi.fn()
  const watched = vi.fn()
  const onStatus = vi.fn()
  _setNoticeWatchers({ askPermission: vi.fn().mockResolvedValue('granted'), showReady })
  try {
    watchAnimationJob('session-1', 'job-1', watched)
    render(
      <>
        <AnimationCard job={{ ...job, status: 'running' }} onOpen={vi.fn()} onStatus={onStatus} />
        <AnimationCard job={{ ...job, status: 'running' }} onOpen={vi.fn()} />
      </>,
    )

    await waitForPoll()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getAllByRole('button', { name: /open animation/i })).toHaveLength(2)
    expect(onStatus).toHaveBeenCalledWith('job-1', 'ready')
    expect(watched).toHaveBeenCalledWith('job-1', 'ready')
    expect(showReady).toHaveBeenCalledTimes(1)

    await waitForPoll()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

test('the poll stops when the last card leaves', async () => {
  vi.useFakeTimers()
  const fetchMock = vi.fn(jobResponse({ status: 'running' }))
  vi.stubGlobal('fetch', fetchMock)
  try {
    const first = render(<AnimationCard job={{ ...job, status: 'running' }} />)
    const second = render(<AnimationCard job={{ ...job, status: 'running' }} />)

    first.unmount()
    await waitForPoll()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    second.unmount()
    await waitForPoll()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  } finally {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  }
})

test('a finished job shows no stage', () => {
  render(<AnimationCard job={{ ...job, status: 'failed', stage: 'fixing' }} />)

  expect(screen.queryByText('Fixing the animation')).toBeNull()
})

test('a job waiting for a choice offers Manim and Lottie (AN-21)', () => {
  render(<AnimationCard job={{ ...job, status: 'running', stage: 'choosing' }} />)

  expect(screen.getByText('Waiting for you')).toBeTruthy()
  expect(screen.getByRole('group', { name: 'How should Polaris draw this animation?' })).toBeTruthy()
  const manim = screen.getByRole('button', { name: /animate with manim/i })
  const lottie = screen.getByRole('button', { name: /animate with lottie/i })
  expect(manim.textContent).toContain('Best for scientific topics')
  expect(lottie.textContent).toContain('Best for other topics')
  expect(screen.queryByText('In progress')).toBeNull()
})

test('choosing an engine starts the job once (AN-21)', async () => {
  let answer: (response: Response) => void = () => {}
  const fetchMock = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        answer = resolve
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  try {
    render(<AnimationCard job={{ ...job, status: 'running', stage: 'choosing' }} />)

    fireEvent.click(screen.getByRole('button', { name: /animate with lottie/i }))
    fireEvent.click(screen.getByRole('button', { name: /animate with manim/i }))
    await act(async () => {})

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/sessions/session-1/jobs/job-1/engine',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ engine: 'lottie' }) }),
    )
    expect(screen.getByText('Starting the animation')).toBeTruthy()

    await act(async () => {
      answer(
        new Response(JSON.stringify({ ...job, status: 'running', stage: 'writing' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    expect(screen.queryByRole('group')).toBeNull()
    expect(screen.getByRole('status').textContent).toBe('Writing the animation')
    expect(screen.getByText('In progress')).toBeTruthy()
  } finally {
    vi.unstubAllGlobals()
  }
})

test('a failed choice says so and lets the learner choose again', async () => {
  const fetchMock = vi.fn(async () => new Response('{}', { status: 500 }))
  vi.stubGlobal('fetch', fetchMock)
  try {
    render(<AnimationCard job={{ ...job, status: 'running', stage: 'choosing' }} />)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /animate with manim/i }))
    })

    expect(screen.getByRole('alert').textContent).toBe(
      "Couldn't start the animation. Check your connection and try again.",
    )
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /animate with manim/i }))
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  } finally {
    vi.unstubAllGlobals()
  }
})
