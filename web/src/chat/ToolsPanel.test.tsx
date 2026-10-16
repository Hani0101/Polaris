import { useRef, useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { AnimationArtifact, Artifact, Quiz, WhiteboardArtifact } from '../api.ts'
import { sampleWhiteboard } from '../whiteboard/sampleWhiteboard.ts'
import { BottomSheet } from './BottomSheet.tsx'
import { ToolsPanel } from './ToolsPanel.tsx'

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
      onQuizGraded={noop}
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
  expect(selectedTab()).toBe('Artifacts')
  expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Artifacts' }))

  fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowRight' })
  expect(selectedTab()).toBe('Whiteboard')

  fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowLeft' })
  expect(selectedTab()).toBe('Artifacts')

  fireEvent.keyDown(document.activeElement as Element, { key: 'Home' })
  expect(selectedTab()).toBe('Whiteboard')

  const tabs = screen.getAllByRole('tab')
  expect(tabs.map((tab) => tab.tabIndex)).toEqual([0, -1, -1])
})

test('each tab shows an empty state when the session has nothing yet', () => {
  renderPanel([])
  expect(screen.getByText('No whiteboard yet')).toBeTruthy()

  fireEvent.click(screen.getByRole('tab', { name: 'Quiz' }))
  expect(screen.getByText('No quiz yet')).toBeTruthy()

  fireEvent.click(screen.getByRole('tab', { name: 'Artifacts' }))
  expect(screen.getByText('No artifacts yet')).toBeTruthy()
})

test('the whiteboard tab shows the most recent whiteboard and opens it', () => {
  const onOpenWhiteboard = vi.fn()
  renderPanel([olderBoard, quiz, board], { onOpenWhiteboard })
  expect(screen.getByTestId('whiteboard').textContent).toBe('board-new')
  fireEvent.click(screen.getByRole('button', { name: 'Open whiteboard' }))
  expect(onOpenWhiteboard).toHaveBeenCalledWith('board-new')
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
