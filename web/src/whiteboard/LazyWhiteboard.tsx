import { lazy, memo, Suspense, useId, useMemo, useState } from 'react'
import type { Whiteboard as WhiteboardData } from '../api.ts'
import { boardTone } from './boardTone.ts'
import { readableDescription } from './description.ts'
import type { WhiteboardProps } from './Whiteboard.tsx'

type WhiteboardModule = typeof import('./Whiteboard.tsx')

// tldraw and the editor libraries it pulls in are most of the app's JavaScript, and most
// screens never show a board. So the board loads on first use, or once the app is idle.
let loading: Promise<WhiteboardModule> | null = null
let loaded: WhiteboardModule | null = null

function loadWhiteboard() {
  loading ??= import('./Whiteboard.tsx').then(
    (module) => {
      loaded = module
      return module
    },
    (error: unknown) => {
      // A failed load is tried again the next time a board is shown.
      loading = null
      throw error
    },
  )
  return loading
}

const LoadedWhiteboard = lazy(() =>
  loadWhiteboard().then((module) => ({ default: module.Whiteboard })),
)

/**
 * Starts loading the board code without showing a board. It resolves once the code has
 * loaded, or has failed to, and leaves a failure to the next board shown.
 */
export function prefetchWhiteboard(): Promise<void> {
  return loadWhiteboard().then(
    () => {},
    () => {},
  )
}

/** The board, with a placeholder of the same size while its code loads. */
export const Whiteboard = memo(function Whiteboard(props: WhiteboardProps) {
  // A board first shown after the code loaded is drawn at once. Each board keeps the
  // choice it started with, so its editor is never mounted twice.
  const [ready] = useState(() => loaded)
  if (ready) return <ready.Whiteboard {...props} />
  return (
    <Suspense fallback={<WhiteboardPlaceholder whiteboard={props.whiteboard} />}>
      <LoadedWhiteboard {...props} />
    </Suspense>
  )
})

/**
 * A board with no editor: its surface in the board's colors and its text description.
 * It stands in while the board loads, and for a board in a turn that is far off screen.
 */
export function WhiteboardPlaceholder({ whiteboard }: { whiteboard: WhiteboardData }) {
  const captionId = useId()
  const tone = useMemo(() => boardTone(whiteboard.id), [whiteboard.id])
  return (
    <section className="whiteboard" aria-labelledby={captionId} data-mode="view" data-board={tone}>
      <div className="whiteboard-surface whiteboard-surface--idle" />
      <p id={captionId} className="whiteboard-caption">
        {readableDescription(whiteboard)}
      </p>
    </section>
  )
}
