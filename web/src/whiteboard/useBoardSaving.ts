import { useCallback, useEffect, useRef, useState } from 'react'
import type { Editor } from 'tldraw'
import { saveWhiteboard } from '../api.ts'
import type { BoardPicture, Whiteboard, WhiteboardArtifact } from '../api.ts'
import { boardPicture } from './picture.ts'

const LEARNER_SAVE_DELAY_MS = 300

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'That whiteboard could not be saved.'
}

type BoardSavingOptions = {
  sessionId: string
  whiteboardId: string
  // The stored board after a save, unless the learner kept drawing meanwhile.
  onSaved: (whiteboard: WhiteboardArtifact) => void
  // A picture of the board after each saved learner change, for the next turn.
  onPicture?: (picture: BoardPicture) => void
}

/**
 * Saves the learner's drawing a short moment after they stop, and once more
 * on flush. The backend merges each save into the stored board (WB-21).
 */
export function useBoardSaving({ sessionId, whiteboardId, onSaved, onPicture }: BoardSavingOptions) {
  const [saveError, setSaveError] = useState<string | null>(null)
  const pendingRef = useRef<Whiteboard | null>(null)
  const timerRef = useRef<number | null>(null)
  const editorRef = useRef<Editor | null>(null)
  const callbacks = useRef({ onSaved, onPicture })
  const onEditor = useCallback((editor: Editor | null) => {
    editorRef.current = editor
  }, [])

  useEffect(() => {
    callbacks.current = { onSaved, onPicture }
  })

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
      if (pending === null || JSON.stringify(pending) === sent) callbacks.current.onSaved(saved)
      setSaveError(null)
    } catch (caught) {
      setSaveError(errorText(caught))
      return
    }
    const editor = editorRef.current
    const report = callbacks.current.onPicture
    if (!editor || !report) return
    const picture = await boardPicture(editor, whiteboardId)
    if (picture) report(picture)
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

  /** Saves a change still waiting for its delay, then resolves. */
  async function flush() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const pending = pendingRef.current
    pendingRef.current = null
    if (pending) await persist(pending)
  }

  return { saveError, onEditor, onDrawingChange, flush }
}
