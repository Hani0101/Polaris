import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import sample from './animation/sample-animation.json'
import { AnimationPlayer } from './AnimationPlayer.tsx'

beforeEach(() => {
  vi.stubGlobal('requestAnimationFrame', () => 0)
  vi.stubGlobal('cancelAnimationFrame', () => {})
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function serveMedia(body: BodyInit | null, contentType: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body, { status: 200, headers: { 'Content-Type': contentType } })),
  )
}

test('animation data plays in Polaris\'s own player, with no iframe (AN-04)', async () => {
  serveMedia(JSON.stringify(sample), 'application/json')

  render(<AnimationPlayer sessionId="s-1" jobId="job-1" />)

  await waitFor(() => {
    expect(screen.getByRole('img', { name: /Binary search halves the list/ })).toBeTruthy()
  })
  expect(screen.getByText('Look at the middle number, 17.')).toBeTruthy()
  expect(document.querySelector('iframe')).toBeNull()
})

test('the player passes on asking about a step', async () => {
  serveMedia(JSON.stringify(sample), 'application/json')
  const onAskAboutStep = vi.fn()

  render(<AnimationPlayer sessionId="s-1" jobId="job-1" onAskAboutStep={onAskAboutStep} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Ask about this step' }))
  expect(onAskAboutStep).toHaveBeenCalledWith(
    expect.objectContaining({ jobId: 'job-1', stepId: 'middle', stepNumber: 1 }),
  )
})

test('an older video animation still opens in the browser player (AN-06)', async () => {
  serveMedia(null, 'video/mp4')

  render(<AnimationPlayer sessionId="s-1" jobId="job-1" />)

  await waitFor(() => {
    expect(document.querySelector('video')).toBeTruthy()
  })
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/sessions/s-1/jobs/job-1/media',
  )
})

test('JSON that is not an animation is not drawn', async () => {
  serveMedia(JSON.stringify({ hello: 'world' }), 'application/json')

  render(<AnimationPlayer sessionId="s-1" jobId="job-1" />)

  expect(
    await screen.findByText('This animation format cannot be shown in the browser.'),
  ).toBeTruthy()
  expect(screen.queryByRole('img')).toBeNull()
})
