import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { LottiePlayer } from './LottiePlayer.tsx'
import { isLottieVideo } from './lottieVideo.ts'
import type { LottieVideo } from './lottieVideo.ts'

type Listener = () => void
const loaded: Array<{ data: unknown; listeners: Record<string, Listener[]> }> = []

vi.mock('lottie-web/build/player/lottie_light', () => ({
  default: {
    loadAnimation: ({ animationData }: { animationData: unknown }) => {
      const listeners: Record<string, Listener[]> = {}
      loaded.push({ data: animationData, listeners })
      return {
        totalFrames: 60,
        currentFrame: 0,
        addEventListener: (name: string, listener: Listener) => {
          ;(listeners[name] ??= []).push(listener)
        },
        play: vi.fn(),
        pause: vi.fn(),
        goToAndStop: vi.fn(),
        goToAndPlay: vi.fn(),
        destroy: vi.fn(),
      }
    },
  },
}))

afterEach(() => {
  cleanup()
  loaded.length = 0
})

const scene = (nm: string) => ({ nm, v: '5.12.0', fr: 30, ip: 0, op: 60, w: 800, h: 600, layers: [] })

const video: LottieVideo = {
  format: 'lottie',
  version: 1,
  id: 'job-1',
  title: 'A pendulum',
  description: 'A bob swings on a string',
  background: '#faf8f4',
  scenes: [
    { id: 'rest', caption: 'The bob hangs at rest.', lottie: scene('rest') },
    { id: 'swing', caption: 'It swings along its arc.', lottie: scene('swing') },
  ],
}

test('a Lottie video is recognised', () => {
  expect(isLottieVideo(video)).toBe(true)
  expect(isLottieVideo({ version: 1, steps: [] })).toBe(false)
})

test('the player describes the video and plays scenes in order', async () => {
  render(<LottiePlayer video={video} jobId="job-1" />)

  expect(screen.getByRole('img', { name: /A pendulum\. A bob swings on a string\. It has 2 steps\./ })).toBeTruthy()
  expect(screen.getByText('The bob hangs at rest.')).toBeTruthy()
  await waitFor(() => expect(loaded).toHaveLength(1))

  // The first scene finishing while playing runs on into the next one.
  loaded[0].listeners.complete.forEach((listener) => listener())
  await waitFor(() => expect(screen.getByText('It swings along its arc.')).toBeTruthy())
  await waitFor(() => expect((loaded.at(-1)?.data as { nm: string }).nm).toBe('swing'))
})

test('the learner can jump to a step and ask about it', async () => {
  const onAskAboutStep = vi.fn()
  render(<LottiePlayer video={video} jobId="job-1" onAskAboutStep={onAskAboutStep} />)

  fireEvent.click(screen.getByRole('button', { name: 'Step 2 of 2' }))
  fireEvent.click(screen.getByRole('button', { name: 'Ask about this step' }))

  expect(onAskAboutStep).toHaveBeenCalledWith({
    jobId: 'job-1',
    stepId: 'swing',
    stepNumber: 2,
    caption: 'It swings along its arc.',
  })
})
