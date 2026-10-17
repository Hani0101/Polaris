import { Clapperboard } from 'lucide-react'
import type { AnimationArtifact } from '../api.ts'
import { RUNNING, stageText, useAnimationJob } from './animationJob.ts'
import { AlertBanner, Badge } from './ui.tsx'
import './artifacts.css'

const READY = 'ready'
const FAILED = 'failed'
// AN-09. Matches FAILURE_NOTICE in api/polaris/animation.py.
export const FAILURE_NOTICE = 'Polaris cannot create the animation right now. Try later.'

type AnimationCardProps = {
  job: AnimationArtifact
  onOpen?: (sessionId: string, jobId: string) => void
  onStatus?: (jobId: string, status: string) => void
}

/**
 * An animation job in the turn that started it (AN-01, AN-06). While the job
 * runs the card says so and names its stage (AN-19); the chat text carries
 * the waiting notice (AN-02). When ready, the learner can open the finished
 * animation again.
 */
export function AnimationCard({ job, onOpen, onStatus }: AnimationCardProps) {
  const { status, stage } = useAnimationJob(job, onStatus)
  const stageLine = status === RUNNING ? stageText(stage) : null

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
      {stageLine ? (
        <p className="animation-card-stage" role="status">
          {stageLine}
        </p>
      ) : null}
      {status === FAILED ? (
        <AlertBanner>{FAILURE_NOTICE}</AlertBanner>
      ) : null}
    </div>
  )
}
