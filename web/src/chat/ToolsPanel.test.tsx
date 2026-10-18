import { useRef, useState } from 'react'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { AnimationArtifact, Artifact, Quiz, WhiteboardArtifact } from '../api.ts'
import type { AskAboutStep } from '../animation/ScenePlayer.tsx'
import { sampleWhiteboard } from '../whiteboard/sampleWhiteboard.ts'
import { BottomSheet } from './BottomSheet.tsx'
import { ToolsPanel } from './ToolsPanel.tsx'

vi.mock('../AnimationPlayer.tsx', () => ({
  AnimationPlayer: ({
    jobId,
    onAskAboutStep,
  }: {
    jobId: string
    onAskAboutStep?: (ask: AskAboutStep) => void
  }) => (
    <>
      <div data-testid="animation-player">{jobId}</div>
      {onAskAboutStep ? (
        <button
          type="button"
          onClick={() =>
            onAskAboutStep({ jobId, stepId: 'discard', stepNumber: 2, caption: 'Drop the left half.' })
          }
        >
          Ask about this step
        </button>
      ) : null}
    </>
  ),
}))

vi.mock('../whiteboard/Whiteboard.tsx', () => ({
  Whiteboard: ({ whiteboard }: { whiteboard: { id: string } }) => (
    <div data-testid="whiteboard">{whiteboard.id}</div>
  ),
}))

afterEach(() => {
  cleanup()
})

const noop = () => {}

const quiz: Quiz = {
  id: 'quiz-1',
  kind: 'quiz',
  session_id: 'session-1',
  title: 'Fractions check',
  questions: [
    {
      id: 'q1',
      prompt: 'What is one half of four?',
      choices: [
        { id: 'a', text: 'Two' },
        { id: 'b', text: 'Three' },
      ],
    },
  ],
  score: null,
}

const olderBoard: WhiteboardArtifact = {
  ...sampleWhiteboard,
  id: 'board-old',
  kind: 'whiteboard',
  description: 'An older drawing.',
}

const board: WhiteboardArtifact = {
  ...sampleWhiteboard,
  id: 'board-new',
  kind: 'whiteboard',
  description: 'A pie cut into four parts. Each part is one quarter.',
}

const animation: AnimationArtifact = {
  id: 'job-1',
  kind: 'animation',
  session_id: 'session-1',
  status: 'running',
}

function renderPanel(
  artifacts: Artifact[],
  callbacks: Partial<{
    onOpenQuiz: (id: string) => void
    onOpenWhiteboard: (id: string) => void
    onOpenAnimation: (sessionId: string, jobId: string) => void
    onClose: () => void
    onAskAboutStep: (ask: AskAboutStep) => void
    whiteboards: WhiteboardArtifact[]
    pinnedWhiteboardId: string | null
    onNewWhiteboard: () => void
  }> = {},
) {
  return render(
    <ToolsPanel
      artifacts={artifacts}
      headingId="tools-heading"
      onClose={callbacks.onClose ?? noop}
      onOpenQuiz={callbacks.onOpenQuiz ?? noop}
      onOpenWhiteboard={callbacks.onOpenWhiteboard ?? noop}
      onOpenAnimation={callbacks.onOpenAnimation ?? noop}
      onQuizChecked={noop}
      onAskAboutStep={callbacks.onAskAboutStep}
      whiteboards={callbacks.whiteboards}
      pinnedWhiteboardId={callbacks.pinnedWhiteboardId}
      onNewWhiteboard={callbacks.onNewWhiteboard}
    />,
  )
}

function selectedTab(): string | null {
  return screen
    .getAllByRole('tab')
    .find((tab) => tab.getAttribute('aria-selected') === 'true')?.textContent ?? null
}

test('tabs switch with a click and with arrow keys', () => {
  renderPanel([])
  expect(screen.getByRole('tablist', { name: 'Tools' })).toBeTruthy()
  expect(selectedTab()).toBe('Whiteboard')

  fireEvent.click(screen.getByRole('tab', { name: 'Quiz' }))
  expect(selectedTab()).toBe('Quiz')
  expect(screen.getByRole('tabpanel', { name: 'Quiz' })).toBeTruthy()

  const quizTab = screen.getByRole('tab', { name: 'Quiz' })
  fireEvent.keyDown(quizTab, { key: 'ArrowRight' })
  expect(selectedTab()).toBe('Flashcards')

  fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowRight' })
  expect(selectedTab()).toBe('Animation')
  expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Animation' }))

  fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowRight' })
  expect(selectedTab()).toBe('Resources')

  fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowRight' })
  expect(selectedTab()).toBe('Artifacts')

  fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowRight' })
  expect(selectedTab()).toBe('Whiteboard')

  fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowLeft' })
  expect(selectedTab()).toBe('Artifacts')

  fireEvent.keyDown(document.activeElement as Element, { key: 'Home' })
  expect(selectedTab()).toBe('Whiteboard')

  const tabs = screen.getAllByRole('tab')
  expect(tabs.map((tab) => tab.tabIndex)).toEqual([0, -1, -1, -1, -1, -1])
})

test('each tab shows an empty state when the session has nothing yet', () => {
  renderPanel([])
  expect(screen.getByText('No whiteboard yet')).toBeTruthy()

  fireEvent.click(screen.getByRole('tab', { name: 'Quiz' }))
  expect(screen.getByText('No quiz yet')).toBeTruthy()

  fireEvent.click(screen.getByRole('tab', { name: 'Flashcards' }))
  expect(screen.getByText('No flashcards yet')).toBeTruthy()

  fireEvent.click(screen.getByRole('tab', { name: 'Animation' }))
  expect(screen.getByText('No animation yet')).toBeTruthy()

  fireEvent.click(screen.getByRole('tab', { name: 'Artifacts' }))
  expect(screen.getByText('No artifacts yet')).toBeTruthy()
})

test('the animation tab plays the most recent ready animation and opens it', () => {
  const onOpenAnimation = vi.fn()
  const older: AnimationArtifact = { ...animation, id: 'job-old', status: 'ready' }
  const newest: AnimationArtifact = { ...animation, id: 'job-new', status: 'ready' }
  renderPanel([older, quiz, newest], { onOpenAnimation })
  fireEvent.click(screen.getByRole('tab', { name: 'Animation' }))

  expect(screen.getByTestId('animation-player').textContent).toBe('job-new')
  fireEvent.click(screen.getByRole('button', { name: 'Open animation' }))
  expect(onOpenAnimation).toHaveBeenCalledWith('session-1', 'job-new')
})

test('the animation tab shows a running job and a failed one', () => {
  const { rerender } = renderPanel([animation])
  fireEvent.click(screen.getByRole('tab', { name: 'Animation' }))
  expect(screen.getByText('In progress')).toBeTruthy()
  expect(screen.queryByTestId('animation-player')).toBeNull()

  rerender(
    <ToolsPanel
      artifacts={[{ ...animation, status: 'failed' }]}
      headingId="tools-heading"
      onClose={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onOpenAnimation={noop}
      onQuizChecked={noop}
    />,
  )
  expect(screen.getByRole('alert').textContent).toBe(
    'Polaris cannot create the animation right now. Try later.',
  )
})

test('the animation tab passes on asking about a step (AN-17)', () => {
  const onAskAboutStep = vi.fn()
  renderPanel([{ ...animation, status: 'ready' }], { onAskAboutStep })
  fireEvent.click(screen.getByRole('tab', { name: 'Animation' }))

  fireEvent.click(screen.getByRole('button', { name: 'Ask about this step' }))

  expect(onAskAboutStep).toHaveBeenCalledWith({
    jobId: 'job-1',
    stepId: 'discard',
    stepNumber: 2,
    caption: 'Drop the left half.',
  })
})

test('a running job in the animation tab shows its stage (AN-19)', () => {
  renderPanel([{ ...animation, stage: 'checking' }])
  fireEvent.click(screen.getByRole('tab', { name: 'Animation' }))

  expect(screen.getByRole('status').textContent).toBe('Checking the animation')
})

test('the whiteboard tab lists every board, newest first, and opening one pins it', () => {
  // WB-18, WB-19
  const onOpenWhiteboard = vi.fn()
  renderPanel([quiz], {
    onOpenWhiteboard,
    whiteboards: [olderBoard, board],
    pinnedWhiteboardId: 'board-old',
  })
  const list = screen.getByRole('list', { name: 'Whiteboards in this session' })
  const cards = Array.from(list.querySelectorAll('button'))
  expect(cards.map((card) => card.textContent)).toEqual([
    'WhiteboardA pie cut into four parts.',
    'WhiteboardPinnedAn older drawing.',
  ])
  expect(cards[1].getAttribute('aria-current')).toBe('true')
  expect(cards[0].getAttribute('aria-current')).toBeNull()
  fireEvent.click(cards[0])
  expect(onOpenWhiteboard).toHaveBeenCalledWith('board-new')
})

test('New whiteboard makes a board, with or without boards already', () => {
  // WB-18
  const onNewWhiteboard = vi.fn()
  const { unmount } = renderPanel([], { onNewWhiteboard })
  expect(screen.getByRole('heading', { name: 'No whiteboard yet' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'New whiteboard' }))
  unmount()
  renderPanel([], { onNewWhiteboard, whiteboards: [board] })
  fireEvent.click(screen.getByRole('button', { name: 'New whiteboard' }))
  expect(onNewWhiteboard).toHaveBeenCalledTimes(2)
})

test('the quiz tab shows the most recent quiz', () => {
  renderPanel([quiz, board])
  fireEvent.click(screen.getByRole('tab', { name: 'Quiz' }))
  expect(screen.getByRole('heading', { name: 'Fractions check' })).toBeTruthy()
})

test('the artifacts list opens a quiz, whiteboard, or ready animation', () => {
  const onOpenQuiz = vi.fn()
  const onOpenWhiteboard = vi.fn()
  const onOpenAnimation = vi.fn()
  const readyAnimation: AnimationArtifact = {
    ...animation,
    id: 'job-ready',
    status: 'ready',
  }
  renderPanel([quiz, board, animation, readyAnimation], {
    onOpenQuiz,
    onOpenWhiteboard,
    onOpenAnimation,
  })
  fireEvent.click(screen.getByRole('tab', { name: 'Artifacts' }))

  fireEvent.click(screen.getByRole('button', { name: /Fractions check/ }))
  expect(onOpenQuiz).toHaveBeenCalledWith('quiz-1')

  const whiteboardCard = screen.getByRole('button', { name: /A pie cut into four parts\./ })
  expect(whiteboardCard.textContent).not.toContain('Each part is one quarter')
  fireEvent.click(whiteboardCard)
  expect(onOpenWhiteboard).toHaveBeenCalledWith('board-new')

  expect(screen.getByText('In progress')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /Open the finished animation/ }))
  expect(onOpenAnimation).toHaveBeenCalledWith('session-1', 'job-ready')
})

test('the close button closes the tools', () => {
  const onClose = vi.fn()
  renderPanel([], { onClose })
  fireEvent.click(screen.getByRole('button', { name: 'Close tools' }))
  expect(onClose).toHaveBeenCalled()
})

function SheetHarness() {
  const [open, setOpen] = useState(false)
  const opener = useRef<HTMLButtonElement>(null)
  return (
    <>
      <button ref={opener} type="button" onClick={() => setOpen(true)}>
        Open tools
      </button>
      <BottomSheet
        open={open}
        labelledBy="sheet-title"
        onClose={() => setOpen(false)}
        returnFocus={opener}
      >
        <h2 id="sheet-title">Tools</h2>
        <button type="button" onClick={() => setOpen(false)}>
          Close tools
        </button>
      </BottomSheet>
    </>
  )
}

test('the bottom sheet takes focus, switches stops from the handle, and gives focus back', () => {
  render(<SheetHarness />)
  const opener = screen.getByRole('button', { name: 'Open tools' })
  fireEvent.click(opener)

  const handle = screen.getByRole('button', { name: 'Expand tools' })
  expect(document.activeElement).toBe(handle)
  const sheet = screen.getByRole('dialog', { name: 'Tools' })
  expect(sheet.className).not.toContain('is-full')

  fireEvent.click(handle)
  expect(sheet.className).toContain('is-full')
  fireEvent.click(screen.getByRole('button', { name: 'Shrink tools' }))
  expect(sheet.className).not.toContain('is-full')

  fireEvent.click(screen.getByRole('button', { name: 'Close tools' }))
  expect(document.activeElement).toBe(opener)
})

test('Create animation sends a turn with the chosen topic and settings (AN-26)', async () => {
  const onCreateAnimation = vi.fn()
  render(
    <ToolsPanel
      artifacts={[]}
      headingId="tools-heading"
      onClose={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onOpenAnimation={noop}
      onQuizChecked={noop}
      onCreateAnimation={onCreateAnimation}
    />,
  )
  fireEvent.click(screen.getByRole('tab', { name: 'Animation' }))
  fireEvent.click(screen.getByRole('button', { name: 'Create animation' }))

  fireEvent.change(screen.getByLabelText('What should the animation show?'), {
    target: { value: 'The derivative as the slope of a tangent' },
  })
  fireEvent.click(screen.getByRole('radio', { name: /Manim/ }))
  fireEvent.click(screen.getByRole('radio', { name: /Low \(480p\)/ }))
  await act(async () => {
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Create animation' }))
  })

  expect(onCreateAnimation).toHaveBeenCalledWith(
    'Make an animation: The derivative as the slope of a tangent',
    { engine: 'manim', quality: '480p', fps: 60 },
  )
})

test('a ready animation shows its settings in the animation tab (AN-26)', () => {
  const ready: AnimationArtifact = {
    ...animation,
    status: 'ready',
    settings: { engine: 'lottie', quality: 'medium', fps: 24 },
  }
  renderPanel([ready])
  fireEvent.click(screen.getByRole('tab', { name: 'Animation' }))

  expect(screen.getByText('Lottie · Medium · 24 fps')).toBeTruthy()
})
