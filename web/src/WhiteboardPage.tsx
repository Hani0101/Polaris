import { useCallback, useEffect, useRef, useState } from 'react'
import type { Editor } from 'tldraw'
import { getWhiteboard, saveWhiteboard } from './api.ts'
import type { BoardPicture, Whiteboard, WhiteboardArtifact } from './api.ts'
import { boardPicture } from './whiteboard/picture.ts'
import type { PointedPart } from './whiteboard/pointing.ts'
import { whiteboardPagePath } from './whiteboard/simpler.ts'
import { Whiteboard as WhiteboardBoard } from './whiteboard/Whiteboard.tsx'

const LEARNER_SAVE_DELAY_MS = 300

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
  const [saveError, setSaveError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'view' | 'draw'>('view')
  const pendingRef = useRef<Whiteboard | null>(null)
  const timerRef = useRef<number | null>(null)
  const editorRef = useRef<Editor | null>(null)
  const onEditor = useCallback((editor: Editor | null) => {
    editorRef.current = editor
  }, [])

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

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    }
  }, [])

  async function persist(drawing: Whiteboard) {
    const sent = JSON.stringify(drawing)
    try {
      const saved = await saveWhiteboard(sessionId, whiteboardId, drawing)
      const pending = pendingRef.current
      if (pending === null || JSON.stringify(pending) === sent) setWhiteboard(saved)
      setSaveError(null)
    } catch (caught) {
      setSaveError(errorText(caught))
      return
    }
    const editor = editorRef.current
    if (!editor || !onPicture) return
    const picture = await boardPicture(editor, whiteboardId)
    if (picture) onPicture(picture)
  }

  function onDrawingChange(next: Whiteboard) {
    pendingRef.current = next
    if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null
      const pending = pendingRef.current
      pendingRef.current = null
      if (pending) void persist(pending)
    }, LEARNER_SAVE_DELAY_MS)
  }

  async function goBack() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const pending = pendingRef.current
    pendingRef.current = null
    if (pending) await persist(pending)
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
