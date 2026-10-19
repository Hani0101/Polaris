import { useEffect, useState } from 'react'
import { getWhiteboard } from './api.ts'
import type { BoardPicture, WhiteboardArtifact } from './api.ts'
import type { PointedPart } from './whiteboard/pointing.ts'
import { whiteboardPagePath } from './whiteboard/simpler.ts'
import { useBoardSaving } from './whiteboard/useBoardSaving.ts'
import { Whiteboard as WhiteboardBoard } from './whiteboard/LazyWhiteboard.tsx'

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'That whiteboard could not be opened.'
}

type WhiteboardPageProps = {
  sessionId: string
  whiteboardId: string
  onBack: () => void
  onAsk?: (parts: PointedPart[]) => void
  onSimpler?: (whiteboardId: string) => void
  onOpenOriginal?: (whiteboardId: string) => void
  // A picture of the board after each saved learner change, for the next turn.
  onPicture?: (picture: BoardPicture) => void
  simplerBusy?: boolean
}

export function WhiteboardPage({
  sessionId,
  whiteboardId,
  onBack,
  onAsk,
  onSimpler,
  onOpenOriginal,
  onPicture,
  simplerBusy = false,
}: WhiteboardPageProps) {
  const [whiteboard, setWhiteboard] = useState<WhiteboardArtifact | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'view' | 'draw'>('view')
  const { saveError, onEditor, onDrawingChange, flush } = useBoardSaving({
    sessionId,
    whiteboardId,
    onSaved: setWhiteboard,
    onPicture,
  })

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const next = await getWhiteboard(sessionId, whiteboardId, controller.signal)
        if (controller.signal.aborted) return
        setWhiteboard(next)
      } catch (caught) {
        if (controller.signal.aborted) return
        setError(errorText(caught))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [sessionId, whiteboardId])

  async function goBack() {
    await flush()
    onBack()
  }

  return (
    <div className="whiteboard-page">
      <header className="top">
        <h1>Polaris</h1>
        <button type="button" className="secondary" onClick={() => void goBack()}>
          Back to the conversation
        </button>
        {whiteboard && mode === 'view' ? (
          <button type="button" onClick={() => setMode('draw')}>
            Draw
          </button>
        ) : null}
        {whiteboard ? (
          <button
            type="button"
            className="secondary"
            disabled={simplerBusy || !onSimpler}
            onClick={() => onSimpler?.(whiteboard.id)}
          >
            Simpler
          </button>
        ) : null}
        {whiteboard?.simplifies ? (
          <a
            className="whiteboard-original"
            href={whiteboardPagePath(sessionId, whiteboard.simplifies)}
            onClick={(event) => {
              const originalId = whiteboard.simplifies
              if (!originalId || !onOpenOriginal) return
              event.preventDefault()
              onOpenOriginal(originalId)
            }}
          >
            Original whiteboard
          </a>
        ) : null}
      </header>
      {error ? (
        <p className="notice" role="alert">
          {error} Ask in the conversation if you need another way in.
        </p>
      ) : null}
      {saveError ? (
        <p className="notice" role="alert">
          {saveError} The drawing was not saved.
        </p>
      ) : null}
      {loading ? <p>Loading the whiteboard.</p> : null}
      {whiteboard ? (
        <div className="whiteboard-frame">
          <WhiteboardBoard
            whiteboard={whiteboard}
            mode={mode}
            onChange={onDrawingChange}
            onAsk={onAsk}
            onEditor={onEditor}
          />
        </div>
      ) : null}
    </div>
  )
}
