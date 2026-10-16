import { useEffect, useState } from 'react'
import { Clapperboard } from 'lucide-react'
import { getAnimationJob } from '../api.ts'
import type { AnimationArtifact } from '../api.ts'
import { AlertBanner, Badge } from './ui.tsx'
import './artifacts.css'

const RUNNING = 'running'
const READY = 'ready'
const FAILED = 'failed'
const POLL_MS = 10_000
// AN-09. Matches FAILURE_NOTICE in api/polaris/animation.py.
export const FAILURE_NOTICE = 'Polaris cannot create the animation right now. Try later.'

type AnimationCardProps = {
  job: AnimationArtifact
  onOpen?: (sessionId: string, jobId: string) => void
  onStatus?: (jobId: string, status: string) => void
}

/**
 * An animation job in the turn that started it (AN-01, AN-06). While the job
 * runs the card says so; the chat text carries the waiting notice (AN-02).
 * When ready, the learner can open the finished animation again.
 */
export function AnimationCard({ job, onOpen, onStatus }: AnimationCardProps) {
  const [polled, setPolled] = useState<string | null>(null)
  const status = job.status === RUNNING ? (polled ?? job.status) : job.status

  useEffect(() => {
    if (status !== RUNNING || !job.session_id) return
    const controller = new AbortController()
    const timer = window.setInterval(() => {
      getAnimationJob(job.session_id, job.id, controller.signal)
        .then((next) => {
          if (controller.signal.aborted) return
          setPolled(next.status)
          if (next.status !== RUNNING) onStatus?.(job.id, next.status)
        })
        .catch(() => {
          // A failed check changes nothing; the next one tries again.
        })
    }, POLL_MS)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [status, job.id, job.session_id, onStatus])

  const canOpen = status === READY && Boolean(onOpen)

  if (canOpen) {
    return (
      <button
        type="button"
        className="animation-card animation-card--clickable"
        onClick={() => onOpen?.(job.session_id, job.id)}
      >
        <Clapperboard size={20} strokeWidth={2} aria-hidden="true" />
        <p className="animation-card-title">Animation</p>
        <span className="animation-card-action">Open animation</span>
      </button>
    )
  }

  return (
    <div className="animation-card">
      <Clapperboard size={20} strokeWidth={2} aria-hidden="true" />
      <p className="animation-card-title">Animation</p>
      {status === RUNNING ? <Badge>In progress</Badge> : null}
      {status === FAILED ? (
        <AlertBanner>{FAILURE_NOTICE}</AlertBanner>
      ) : null}
    </div>
  )
}
