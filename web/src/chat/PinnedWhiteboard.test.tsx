import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { WhiteboardArtifact } from '../api.ts'
import { PinnedWhiteboard } from './PinnedWhiteboard.tsx'
import type { PinnedTurn } from './PinnedWhiteboard.tsx'

vi.mock('../whiteboard/Whiteboard.tsx', () => ({
  Whiteboard: ({ whiteboard, mode }: { whiteboard: WhiteboardArtifact; mode: string }) => (
    <div data-testid="board" data-mode={mode}>
      {whiteboard.steps.map((step) => step.id).join(',')}
    </div>
  ),
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const stored: WhiteboardArtifact = {
  kind: 'whiteboard',
  version: 7,
  id: 'wb-1',
  session_id: 's-1',
  description: 'Blank whiteboard',
  steps: [{ id: 'learner', reply_part: '[[step:learner]]', elements: [] }],
  comments: [],
}

const extended: WhiteboardArtifact = {
  ...stored,
  steps: [
    ...stored.steps,
    {
      id: 'hint',
      reply_part: '[[step:hint]]',
      extension: true,
      elements: [
        {
          id: 'hint-box',
          kind: 'rectangle',
          author: 'agent',
          position: { x: 0, y: 0 },
          size: { width: 100, height: 50 },
          style: { stroke: '#000', fill: null, stroke_width: 2 },
        },
      ],
    },
  ],
}

function stubLoad() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(stored), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
}

function renderPinned(turn: PinnedTurn | null, onClose = vi.fn()) {
  return render(
    <PinnedWhiteboard sessionId="s-1" whiteboardId="wb-1" turn={turn} onClose={onClose} />,
  )
}

test('the pinned board opens for drawing above the chat', async () => {
  // WB-19
  stubLoad()
  renderPinned(null)

  const board = await screen.findByTestId('board')

  expect(board.dataset.mode).toBe('draw')
  expect(screen.getByRole('heading', { name: 'Whiteboard' })).toBeTruthy()
})

test("the agent's step appears when the reply reaches it, and stays when the reply ends", async () => {
  // WB-20, WB-06
  stubLoad()
  const turn: PinnedTurn = { key: 't-1', reply: 'Look. ', phase: 'streaming', board: extended }
  const { rerender } = renderPinned(null)
  await screen.findByTestId('board')

  rerender(<PinnedWhiteboard sessionId="s-1" whiteboardId="wb-1" turn={turn} onClose={vi.fn()} />)
  expect(screen.getByTestId('board').textContent).toBe('learner')

  rerender(
    <PinnedWhiteboard
      sessionId="s-1"
      whiteboardId="wb-1"
      turn={{ ...turn, reply: 'Look. [[step:hint]] Here.' }}
      onClose={vi.fn()}
    />,
  )
  expect(screen.getByTestId('board').textContent).toBe('learner,hint')

  rerender(
    <PinnedWhiteboard
      sessionId="s-1"
      whiteboardId="wb-1"
      turn={{ ...turn, reply: 'Look. [[step:hint]] Here.', phase: 'done' }}
      onClose={vi.fn()}
    />,
  )
  rerender(<PinnedWhiteboard sessionId="s-1" whiteboardId="wb-1" turn={null} onClose={vi.fn()} />)
  expect(screen.getByTestId('board').textContent).toBe('learner,hint')
})

test('the pinned board expands, collapses, and closes', async () => {
  // WB-19, WB-16
  stubLoad()
  const onClose = vi.fn()
  const { container } = renderPinned(null, onClose)
  await screen.findByTestId('board')

  fireEvent.click(screen.getByRole('button', { name: 'Expand whiteboard' }))
  expect(container.querySelector('.pinned-board.is-expanded')).toBeTruthy()
  fireEvent.keyDown(window, { key: 'Escape' })
  expect(container.querySelector('.pinned-board.is-expanded')).toBeNull()
  expect(screen.getByRole('button', { name: 'Expand whiteboard' })).toBeTruthy()

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Close whiteboard' }))
  })
  expect(onClose).toHaveBeenCalledTimes(1)
})
