import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { getAnimationJob } from './api.ts'
import { AnimationPlayer } from './AnimationPlayer.tsx'
import { AlertBanner } from './chat/ui.tsx'
import './animation.css'

type AnimationPageProps = {
  sessionId: string
  jobId: string
  onBack: () => void
}

type LoadState = { kind: 'loading' } | { kind: 'ready' } | { kind: 'failed' }

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

export function AnimationPage({ sessionId, jobId, onBack }: AnimationPageProps) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    getAnimationJob(sessionId, jobId, controller.signal)
      .then((job) => {
        if (controller.signal.aborted) return
        setState({ kind: job.status === 'ready' ? 'ready' : 'failed' })
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: 'failed' })
      })
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
              <AnimationPlayer sessionId={sessionId} jobId={jobId} />
            </div>
          ) : null}
        </div>
      </main>
    </div>
  )
}
