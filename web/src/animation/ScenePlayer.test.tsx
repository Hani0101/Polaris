import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Animation } from './format.ts'
import sampleData from './sample-animation.json'
import { ScenePlayer } from './ScenePlayer.tsx'

const sample = sampleData as Animation
const originalMatchMedia = window.matchMedia

function mockReducedMotion(reduce: boolean) {
  window.matchMedia = (query: string) =>
    ({
      matches: reduce && query.includes('prefers-reduced-motion'),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

type FakeVoice = Pick<SpeechSynthesisVoice, 'name' | 'lang' | 'localService' | 'default'>

function mockSpeech(voices: FakeVoice[]) {
  const spoken: { text: string; voice: FakeVoice | null }[] = []
  const speech = {
    getVoices: () => voices,
    speak: vi.fn((utterance: { text: string; voice: FakeVoice | null }) => {
      spoken.push({ text: utterance.text, voice: utterance.voice })
    }),
    cancel: vi.fn(),
    addEventListener: () => {},
    removeEventListener: () => {},
  }
  class Utterance {
    text: string
    voice: FakeVoice | null = null
    lang = ''
    constructor(text: string) {
      this.text = text
    }
  }
  vi.stubGlobal('speechSynthesis', speech)
  vi.stubGlobal('SpeechSynthesisUtterance', Utterance)
  return { speech, spoken }
}

beforeEach(() => {
  // Frames never run, so each test sees the picture at the start of a step.
  vi.stubGlobal('requestAnimationFrame', () => 0)
  vi.stubGlobal('cancelAnimationFrame', () => {})
  mockReducedMotion(false)
  try {
    window.localStorage.clear()
  } catch {
    // Storage may be unavailable.
  }
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.matchMedia = originalMatchMedia
})

function caption(): string {
  return document.querySelector('.an-caption-text')?.textContent ?? ''
}

function element(id: string): Element | null {
  return document.querySelector(`[data-element="${id}"]`)
}

test('the canvas has a text description and the caption shows below it (AN-15)', () => {
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  const picture = screen.getByRole('img')
  expect(picture.getAttribute('aria-label')).toBe(
    'Binary search halves the list. A sorted list of seven numbers. Each step checks the ' +
      'middle number and throws away the half that cannot hold 23. It has 4 steps.',
  )
  expect(picture.getAttribute('viewBox')).toBe('0 0 400 300')
  expect(caption()).toBe('Look at the middle number, 17.')
  expect(document.querySelector('.an-caption')?.getAttribute('aria-live')).toBe('polite')
})

test('the learner moves through the steps (AN-12)', () => {
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
  expect(caption()).toBe('23 is bigger than 17, so the left half cannot hold it.')

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))

  expect(caption()).toBe('Check the middle of what is left: 31. Then 23 is found.')
  expect(screen.getByRole('button', { name: 'Pause' })).toBeTruthy()
  const steps = within(screen.getByRole('list', { name: 'Steps' }))
  expect(steps.getByRole('button', { name: 'Step 3 of 4' }).getAttribute('aria-current')).toBe(
    'step',
  )
  expect(steps.getByRole('button', { name: 'Step 2 of 4' }).getAttribute('aria-current')).toBeNull()
})

test('Back shows the finished picture of the step before, paused', () => {
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))

  expect(caption()).toBe('Look at the middle number, 17.')
  expect(screen.getByRole('button', { name: 'Play' })).toBeTruthy()
  // At the end of step 1 the pointer is fully shown and one check is counted.
  expect(element('pointer')?.getAttribute('opacity')).toBeNull()
  expect(element('checks')?.textContent).toBe('1')
})

test('a step button jumps to that step', () => {
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  fireEvent.click(screen.getByRole('button', { name: 'Step 4 of 4' }))

  expect(caption()).toBe('Doubling the list adds only one more check.')
  expect(screen.getByRole('button', { name: 'Next' })).toHaveProperty('disabled', true)
})

test('reduced motion shows each finished picture without play controls (AN-13)', () => {
  mockReducedMotion(true)
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  expect(screen.queryByRole('button', { name: 'Play' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Pause' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Replay step' })).toBeNull()
  expect(caption()).toBe('Look at the middle number, 17.')
  expect(element('pointer')?.getAttribute('opacity')).toBeNull()
  expect(element('checks')?.textContent).toBe('1')
  expect(element('left-half')).toBeNull()

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))

  expect(caption()).toBe('23 is bigger than 17, so the left half cannot hold it.')
  expect(element('left-half')?.getAttribute('opacity')).toBeNull()
})

test('colour roles become design-system classes (AN-14)', () => {
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  expect(element('target')?.getAttribute('class')).toContain('an-role-accent')
  expect(element('list')?.getAttribute('class')).toContain('an-role-muted')
  expect(element('numbers')?.querySelector('text')?.getAttribute('class')).toBe('an-text')
  expect(element('numbers')?.querySelector('text')?.getAttribute('font-family')).toBeNull()
})

test('narration is not offered without speech synthesis', () => {
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  expect(screen.queryByRole('checkbox', { name: 'Read captions aloud' })).toBeNull()
})

test('narration is not offered when no voice is local (AN-18)', () => {
  mockSpeech([{ name: 'Cloud', lang: 'en-US', localService: false, default: true }])
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  expect(screen.queryByRole('checkbox', { name: 'Read captions aloud' })).toBeNull()
})

test('narration is off by default and reads captions with a local voice (AN-18)', () => {
  const local = { name: 'Local', lang: 'en-GB', localService: true, default: false }
  const { spoken } = mockSpeech([
    { name: 'Cloud', lang: 'en-US', localService: false, default: true },
    local,
  ])
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  const toggle = screen.getByRole('checkbox', { name: 'Read captions aloud' })
  expect(toggle).toHaveProperty('checked', false)
  expect(spoken).toEqual([])

  fireEvent.click(toggle)
  expect(spoken.at(-1)).toEqual({ text: 'Look at the middle number, 17.', voice: local })

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(spoken.at(-1)?.text).toBe('23 is bigger than 17, so the left half cannot hold it.')
  expect(caption()).toBe('23 is bigger than 17, so the left half cannot hold it.')
})

test('ask about this step names the animation and the step (AN-17)', () => {
  const onAskAboutStep = vi.fn()
  render(<ScenePlayer animation={sample} jobId="job-1" onAskAboutStep={onAskAboutStep} />)

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  fireEvent.click(screen.getByRole('button', { name: 'Ask about this step' }))

  expect(onAskAboutStep).toHaveBeenCalledWith({
    jobId: 'job-1',
    stepId: 'discard',
    stepNumber: 2,
    caption: '23 is bigger than 17, so the left half cannot hold it.',
  })
})

test('ask about this step is hidden without a handler', () => {
  render(<ScenePlayer animation={sample} jobId="job-1" />)

  expect(screen.queryByRole('button', { name: 'Ask about this step' })).toBeNull()
})
