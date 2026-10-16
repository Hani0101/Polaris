import { useEffect, useState } from 'react'
import { animationMediaUrl } from './animationPath.ts'
import { AlertBanner } from './chat/ui.tsx'
import './animation.css'

type AnimationPlayerProps = {
  sessionId: string
  jobId: string
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ready'; mediaType: string }
  | { kind: 'failed' }

async function probeMediaType(
  sessionId: string,
  jobId: string,
  signal: AbortSignal,
): Promise<string> {
  const response = await fetch(animationMediaUrl(sessionId, jobId), { signal })
  if (!response.ok) {
    throw new Error("Couldn't load the animation.")
  }
  // Body is discarded; the player loads the same URL again.
  await response.arrayBuffer()
  return response.headers.get('content-type') ?? ''
}

function Playback({
  sessionId,
  jobId,
  mediaType,
}: {
  sessionId: string
  jobId: string
  mediaType: string
}) {
  const src = animationMediaUrl(sessionId, jobId)
  if (mediaType.startsWith('video/')) {
    return (
      <video className="an-player" controls playsInline src={src}>
        Your browser cannot play this animation.
      </video>
    )
  }
  if (mediaType.startsWith('image/')) {
    return <img className="an-player" src={src} alt="Animation" />
  }
  if (mediaType.includes('html')) {
    return (
      <iframe
        className="an-player an-player--html"
        title="Animation"
        src={src}
        sandbox="allow-scripts"
      />
    )
  }
  return (
    <AlertBanner>This animation format cannot be shown in the browser.</AlertBanner>
  )
}

/** A finished animation in its stage (AN-06). Used by the page and the tools panel. */
export function AnimationPlayer({ sessionId, jobId }: AnimationPlayerProps) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    probeMediaType(sessionId, jobId, controller.signal)
      .then((mediaType) => {
        if (!controller.signal.aborted) setState({ kind: 'ready', mediaType })
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: 'failed' })
      })
    return () => controller.abort()
  }, [sessionId, jobId, attempt])

  if (state.kind === 'failed') {
    return (
      <AlertBanner
        action={
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setState({ kind: 'loading' })
              setAttempt((count) => count + 1)
            }}
          >
            Try again
          </button>
        }
      >
        Couldn&apos;t load this animation. Check your connection and try again.
      </AlertBanner>
    )
  }
  return (
    <div className="an-stage">
      {state.kind === 'loading' ? (
        <div role="status">
          <span className="visually-hidden">Loading the animation</span>
          <div className="skeleton an-skeleton-stage" aria-hidden="true" />
        </div>
      ) : (
        <Playback sessionId={sessionId} jobId={jobId} mediaType={state.mediaType} />
      )}
    </div>
  )
}
