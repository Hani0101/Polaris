import { memo, useEffect, useId, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'
import { getWhiteboard } from '../api.ts'
import type { BoardPicture, WhiteboardArtifact } from '../api.ts'
import type { PointedPart } from '../whiteboard/pointing.ts'
import { revealAddedSteps } from '../whiteboard/reveal.ts'
import type { RevealPhase } from '../whiteboard/reveal.ts'
import { useBoardSaving } from '../whiteboard/useBoardSaving.ts'
import { Whiteboard } from '../whiteboard/LazyWhiteboard.tsx'
import { ResizeHandle, useSize } from './ResizeHandle.tsx'
import { AlertIcon, CloseIcon, IconButton } from './ui.tsx'
import './pinned.css'

// DS-GAP: how tall the learner can drag the pinned board on a laptop, no token.
const PINNED_MIN = 200
const PINNED_MAX = 1200

/** The reply now running, and the pinned board as that reply last sent it. */
export type PinnedTurn = {
  key: string
  reply: string
  phase: RevealPhase
  board: WhiteboardArtifact | null
}

type PinnedWhiteboardProps = {
  sessionId: string
  whiteboardId: string
  turn: PinnedTurn | null
  onClose: () => void
  onAsk?: (parts: PointedPart[]) => void
  onPicture?: (picture: BoardPicture) => void
}

/**
 * The board pinned above the conversation (WB-19). The learner draws on it as
 * usual, and the agent's added steps appear on it as the reply reaches them.
 * Memoized, so the app drawing again does not draw tldraw's tree again.
 */
export const PinnedWhiteboard = memo(function PinnedWhiteboard({
  sessionId,
  whiteboardId,
  turn,
  onClose,
  onAsk,
  onPicture,
}: PinnedWhiteboardProps) {
  const [board, setBoard] = useState<WhiteboardArtifact | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  // The steps the board had when the running turn began.
  const [start, setStart] = useState<{ key: string; steps: ReadonlySet<string> } | null>(null)
  // The finished reply's board last placed on the pinned board.
  const [placed, setPlaced] = useState<WhiteboardArtifact | null>(null)
  const titleId = useId()
  const section = useRef<HTMLElement>(null)
  const [height, setHeight] = useSize('polaris.pinned.height', PINNED_MIN, PINNED_MAX)
  const { saveError, onEditor, onDrawingChange, flush } = useBoardSaving({
    sessionId,
    whiteboardId,
    onSaved: setBoard,
    onPicture,
  })

  useEffect(() => {
    const controller = new AbortController()
    getWhiteboard(sessionId, whiteboardId, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setBoard(next)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError("Couldn't open this whiteboard. Close it and open it again from the Whiteboard tab.")
        }
      })
    return () => controller.abort()
  }, [sessionId, whiteboardId])

  const turnKey = turn?.key ?? null
  if (turnKey !== null && board && start?.key !== turnKey) {
    setStart({ key: turnKey, steps: new Set(board.steps.map((step) => step.id)) })
  }

  // A finished reply leaves its steps on the board.
  const finished = turn?.phase === 'done' ? turn.board : null
  if (finished && finished !== placed) {
    setPlaced(finished)
    setBoard(finished)
  }

  useEffect(() => {
    if (!expanded) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setExpanded(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  const shown = useMemo(() => {
    if (!board) return null
    if (!turn?.board || turn.phase !== 'streaming') return board
    const known =
      start?.key === turn.key ? start.steps : new Set(board.steps.map((step) => step.id))
    return revealAddedSteps(turn.board, known, turn.reply)
  }, [board, turn, start])

  async function close() {
    await flush()
    onClose()
  }

  return (
    <section
      ref={section}
      className={expanded ? 'pinned-board is-expanded' : 'pinned-board'}
      aria-labelledby={titleId}
      style={height === null ? undefined : ({ '--pinned-height': `${height}px` } as CSSProperties)}
    >
      <div className="pinned-board-bar">
        <h2 className="pinned-board-title" id={titleId}>
          Whiteboard
        </h2>
        <IconButton
          label={expanded ? 'Collapse whiteboard' : 'Expand whiteboard'}
          size="sm"
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? (
            <Minimize2 size={20} strokeWidth={2} aria-hidden="true" />
          ) : (
            <Maximize2 size={20} strokeWidth={2} aria-hidden="true" />
          )}
        </IconButton>
        <IconButton label="Close whiteboard" size="sm" onClick={() => void close()}>
          <CloseIcon />
        </IconButton>
      </div>
      {error ? (
        <p className="pinned-board-error" role="alert">
          <AlertIcon />
          {error}
        </p>
      ) : null}
      {saveError ? (
        <p className="pinned-board-error" role="alert">
          <AlertIcon />
          {saveError} The drawing was not saved.
        </p>
      ) : null}
      {!board && !error ? <p className="pinned-board-loading">Loading the whiteboard.</p> : null}
      {shown ? (
        <div className="pinned-board-frame">
          <Whiteboard
            key={whiteboardId}
            whiteboard={shown}
            mode="draw"
            onChange={onDrawingChange}
            onAsk={onAsk}
            onEditor={onEditor}
          />
        </div>
      ) : null}
      {expanded ? null : (
        <ResizeHandle
          label="Resize whiteboard"
          orientation="horizontal"
          grows={1}
          min={PINNED_MIN}
          max={PINNED_MAX}
          measure={() => section.current?.getBoundingClientRect().height ?? PINNED_MIN}
          onResize={setHeight}
        />
      )}
    </section>
  )
})
