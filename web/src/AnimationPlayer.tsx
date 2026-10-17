import { useEffect, useState } from 'react'
import { animationManimUrl, animationMediaUrl } from './animationPath.ts'
import { isAnimation } from './animation/format.ts'
import type { Animation } from './animation/format.ts'
import { ScenePlayer } from './animation/ScenePlayer.tsx'
import type { AskAboutStep } from './animation/ScenePlayer.tsx'
import { isManimManifest } from './animation/manim.ts'
import type { ManimManifest } from './animation/manim.ts'
import { VideoStepPlayer } from './animation/VideoStepPlayer.tsx'
import { AlertBanner } from './chat/ui.tsx'
import './animation.css'

type AnimationPlayerProps = {
  sessionId: string
  jobId: string
  onAskAboutStep?: (ask: AskAboutStep) => void
}

type Media = { mediaType: string; animation: Animation | null; manim?: ManimManifest | null }

type LoadState = { kind: 'loading' } | ({ kind: 'ready' } & Media) | { kind: 'failed' }

async function probeMedia(sessionId: string, jobId: string, signal: AbortSignal): Promise<Media> {
  const response = await fetch(animationMediaUrl(sessionId, jobId), { signal })
  if (!response.ok) {
    throw new Error("Couldn't load the animation.")
  }
  const mediaType = response.headers.get('content-type') ?? ''
  if (mediaType.includes('json')) {
    // A new animation is data that Polaris plays (AN-04).
    const data: unknown = await response.json()
    return { mediaType, animation: isAnimation(data) ? data : null }
  }
  // Older jobs: the body is discarded and the player loads the same URL again (AN-06).
  await response.arrayBuffer()
  if (mediaType.startsWith('video/')) {
    // A Manim job keeps a manifest of its steps beside the video (experiment).
    try {
      const manifest = await fetch(animationManimUrl(sessionId, jobId, 'manim.json'), { signal })
      if (manifest.ok) {
        const data: unknown = await manifest.json()
        if (isManimManifest(data)) return { mediaType, animation: null, manim: data }
      }
    } catch {
      // No manifest: an older video plays in the browser's player.
    }
  }
  return { mediaType, animation: null }
}

function Playback({
  sessionId,
  jobId,
  mediaType,
  animation,
  manim,
  onAskAboutStep,
}: {
  sessionId: string
  jobId: string
  onAskAboutStep?: (ask: AskAboutStep) => void
} & Media) {
  if (manim) {
    return (
      <VideoStepPlayer
        manifest={manim}
        sessionId={sessionId}
        jobId={jobId}
        onAskAboutStep={onAskAboutStep}
      />
    )
  }
  if (animation) {
    return <ScenePlayer animation={animation} jobId={jobId} onAskAboutStep={onAskAboutStep} />
  }
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
export function AnimationPlayer({ sessionId, jobId, onAskAboutStep }: AnimationPlayerProps) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    probeMedia(sessionId, jobId, controller.signal)
      .then((media) => {
        if (!controller.signal.aborted) setState({ kind: 'ready', ...media })
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
        <Playback
          sessionId={sessionId}
          jobId={jobId}
          mediaType={state.mediaType}
          animation={state.animation}
          manim={state.manim}
          onAskAboutStep={onAskAboutStep}
        />
      )}
    </div>
  )
}
