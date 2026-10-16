import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { getAnimationJob } from './api.ts'
import type { AnimationArtifact } from './api.ts'
import { animationMediaUrl } from './animationPath.ts'
import { AlertBanner } from './chat/ui.tsx'
import './animation.css'

type AnimationPageProps = {
  sessionId: string
  jobId: string
  onBack: () => void
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ready'; job: AnimationArtifact; mediaType: string }
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

function AnimationSkeleton() {
  return (
    <div className="an-page-column" role="status">
      <span className="visually-hidden">Loading the animation</span>
      <div className="an-stage" aria-hidden="true">
        <div className="skeleton an-skeleton-stage" />
      </div>
    </div>
  )
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

export function AnimationPage({ sessionId, jobId, onBack }: AnimationPageProps) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const job = await getAnimationJob(sessionId, jobId, controller.signal)
        if (controller.signal.aborted) return
        if (job.status !== 'ready') {
          setState({ kind: 'failed' })
          return
        }
        const mediaType = await probeMediaType(sessionId, jobId, controller.signal)
        if (controller.signal.aborted) return
        setState({ kind: 'ready', job, mediaType })
      } catch {
        if (controller.signal.aborted) return
        setState({ kind: 'failed' })
      }
    }
    void load()
    return () => controller.abort()
  }, [sessionId, jobId, attempt])

  function tryAgain() {
    setState({ kind: 'loading' })
    setAttempt((count) => count + 1)
  }

  return (
    <div className="an-page">
      <header className="top-bar">
        <div className="top-bar-start">
          <button type="button" className="ghost" onClick={onBack}>
            <ArrowLeft size={20} strokeWidth={2} aria-hidden="true" />
            Back to the conversation
          </button>
          <p className="top-bar-mark">Polaris</p>
        </div>
        <p className="top-bar-title">Animation</p>
        <div className="top-bar-end" />
      </header>
      <main className="an-page-main">
        <div className="an-page-grid">
          {state.kind === 'loading' ? <AnimationSkeleton /> : null}
          {state.kind === 'failed' ? (
            <div className="an-page-column">
              <AlertBanner
                action={
                  <button type="button" className="secondary" onClick={tryAgain}>
                    Try again
                  </button>
                }
              >
                Couldn&apos;t load this animation. Check your connection and try again.
              </AlertBanner>
            </div>
          ) : null}
          {state.kind === 'ready' ? (
            <div className="an-page-column">
              <div className="an-stage">
                <Playback
                  sessionId={sessionId}
                  jobId={jobId}
                  mediaType={state.mediaType}
                />
              </div>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  )
}
