import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { AnimationSettingsDialog } from './AnimationSettingsDialog.tsx'
import { ChooseAnimationDialog } from './ChooseAnimationDialog.tsx'
import { askForAnimationSettings } from './animationJob.ts'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function radios(group: string): string[] {
  const fieldset = screen.getByRole('group', { name: group })
  return within(fieldset)
    .getAllByRole('radio')
    .map((radio) => (radio as HTMLInputElement).value)
}

test('each engine offers only its own quality and frame rates (AN-26)', () => {
  render(<AnimationSettingsDialog open mode="choose" onCancel={vi.fn()} onSubmit={vi.fn()} />)

  // Quality and frame rate wait for the engine.
  expect(screen.queryByRole('group', { name: 'Quality' })).toBeNull()
  expect(screen.getByText(/Best for scientific topics/)).toBeTruthy()
  expect(screen.getByText(/Best for other topics/)).toBeTruthy()

  fireEvent.click(screen.getByRole('radio', { name: /Manim/ }))
  expect(radios('Quality')).toEqual(['480p', '720p', '1080p'])
  expect(radios('Frame rate')).toEqual(['15', '24', '30', '60'])
  expect((screen.getByRole('radio', { name: /High \(1080p\)/ }) as HTMLInputElement).checked).toBe(
    true,
  )

  fireEvent.click(screen.getByRole('radio', { name: /Lottie/ }))
  expect(radios('Quality')).toEqual(['low', 'medium', 'high'])
  expect(radios('Frame rate')).toEqual(['24', '30', '60'])
})

test('switching engine resets the settings to that engine, so none is illegal', async () => {
  const onSubmit = vi.fn()
  render(<AnimationSettingsDialog open mode="choose" onCancel={vi.fn()} onSubmit={onSubmit} />)

  fireEvent.click(screen.getByRole('radio', { name: /Manim/ }))
  fireEvent.click(screen.getByRole('radio', { name: /15 fps/ }))
  fireEvent.click(screen.getByRole('radio', { name: /Lottie/ }))
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Start animation' }))
  })

  expect(onSubmit).toHaveBeenCalledWith({ engine: 'lottie', quality: 'high', fps: 30 }, '')
})

test('the dialog needs an engine, and Create needs a topic', async () => {
  const onSubmit = vi.fn()
  render(<AnimationSettingsDialog open mode="create" onCancel={vi.fn()} onSubmit={onSubmit} />)

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Create animation' }))
  })
  expect(screen.getByRole('alert').textContent).toBe('Type what the animation should show.')

  fireEvent.change(screen.getByLabelText('What should the animation show?'), {
    target: { value: 'How a heart pumps blood' },
  })
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Create animation' }))
  })
  expect(screen.getByRole('alert').textContent).toBe('Choose Manim or Lottie.')

  fireEvent.click(screen.getByRole('radio', { name: /Lottie/ }))
  fireEvent.click(screen.getByRole('radio', { name: /^Low/ }))
  fireEvent.click(screen.getByRole('radio', { name: /60 fps/ }))
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Create animation' }))
  })
  expect(onSubmit).toHaveBeenCalledWith(
    { engine: 'lottie', quality: 'low', fps: 60 },
    'How a heart pumps blood',
  )
})

test('a job from the chat opens the dialog and starts with the chosen settings (AN-21)', async () => {
  const fetchMock = vi.fn(
    async () =>
      new Response(
        JSON.stringify({
          id: 'job-1',
          kind: 'animation',
          session_id: 'session-1',
          status: 'running',
          stage: 'writing',
          settings: { engine: 'manim', quality: '720p', fps: 30 },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
  )
  vi.stubGlobal('fetch', fetchMock)
  render(<ChooseAnimationDialog />)

  act(() => {
    askForAnimationSettings({
      id: 'job-1',
      kind: 'animation',
      session_id: 'session-1',
      status: 'running',
      stage: 'choosing',
    })
  })
  expect(screen.getByRole('dialog', { name: 'Choose how to animate' })).toBeTruthy()
  // No topic field: the chat already said what to animate.
  expect(screen.queryByLabelText('What should the animation show?')).toBeNull()

  fireEvent.click(screen.getByRole('radio', { name: /Manim/ }))
  fireEvent.click(screen.getByRole('radio', { name: /Medium \(720p\)/ }))
  fireEvent.click(screen.getByRole('radio', { name: /^30 fps/ }))
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Start animation' }))
  })

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/sessions/session-1/jobs/job-1/engine',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ engine: 'manim', quality: '720p', fps: 30 }),
    }),
  )
})

test('a refused choice shows the reason and keeps the dialog open', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: 'Manim frame rate must be one of 15, 24, 30, 60.' }), {
          status: 422,
          headers: { 'Content-Type': 'application/json' },
        }),
    ),
  )
  render(<ChooseAnimationDialog />)
  act(() => {
    askForAnimationSettings({
      id: 'job-1',
      kind: 'animation',
      session_id: 'session-1',
      status: 'running',
      stage: 'choosing',
    })
  })

  fireEvent.click(screen.getByRole('radio', { name: /Manim/ }))
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Start animation' }))
  })

  expect(screen.getByRole('dialog')).toBeTruthy()
  expect(screen.getByRole('alert').textContent).toContain('Manim frame rate must be one of')
})
