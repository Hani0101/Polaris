import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { AnimationPage } from './AnimationPage.tsx'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('a ready animation page loads the playback media', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    const url = String(input)
    if (url.endsWith('/jobs/job-1')) {
      return new Response(
        JSON.stringify({
          id: 'job-1',
          kind: 'animation',
          session_id: 's-1',
          status: 'ready',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }
    if (url.endsWith('/jobs/job-1/media')) {
      return new Response(null, {
        status: 200,
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      })
    }
    return new Response('missing', { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<AnimationPage sessionId="s-1" jobId="job-1" onBack={() => {}} />)

  await waitFor(() => {
    expect(screen.getByTitle('Animation')).toBeTruthy()
  })
  const frame = screen.getByTitle('Animation') as HTMLIFrameElement
  expect(frame.getAttribute('src')).toBe('/api/sessions/s-1/jobs/job-1/media')
  expect(frame.getAttribute('sandbox')).toBe('allow-scripts')
})
