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

test('a Manim video plays one step at a time with its captions (experiment)', async () => {
  const manifest = {
    engine: 'manim',
    id: 'job-1',
    title: 'Slope',
    description: 'A tangent line moves along a curve.',
    steps: [
      { id: 'step-1', caption: 'Here is the curve.', start_s: 0, duration_s: 2 },
      { id: 'step-2', caption: 'The tangent moves.', start_s: 2, duration_s: 3 },
    ],
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.endsWith('/manim.json')
        ? new Response(JSON.stringify(manifest), { headers: { 'Content-Type': 'application/json' } })
        : new Response(null, { headers: { 'Content-Type': 'video/mp4' } }),
    ),
  )
  const onAskAboutStep = vi.fn()

  render(<AnimationPlayer sessionId="s-1" jobId="job-1" onAskAboutStep={onAskAboutStep} />)

  expect(await screen.findByText('Here is the curve.')).toBeTruthy()
  expect(document.querySelector('video')?.getAttribute('src')).toBe(
    '/api/sessions/s-1/jobs/job-1/manim/steps/step-01.mp4',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByText('The tangent moves.')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Ask about this step' }))
  expect(onAskAboutStep).toHaveBeenCalledWith(
    expect.objectContaining({ jobId: 'job-1', stepId: 'step-2', stepNumber: 2 }),
  )
})
