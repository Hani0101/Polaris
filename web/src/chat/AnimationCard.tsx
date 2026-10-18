import { Clapperboard } from 'lucide-react'
import type { AnimationArtifact } from '../api.ts'
import { settingsText } from '../animation/settings.ts'
import {
  CHOOSING,
  RUNNING,
  askForAnimationSettings,
  stageText,
  useAnimationJob,
} from './animationJob.ts'
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
 * the waiting notice (AN-02). A job waiting for its engine and settings can
 * open the settings dialog again (AN-21). Once chosen, the settings show
 * while the job runs and after (AN-26). When ready, the learner can open the
 * finished animation again.
 */
export function AnimationCard({ job, onOpen, onStatus }: AnimationCardProps) {
  const { status, stage, settings } = useAnimationJob(job, onStatus)
  const choosing = status === RUNNING && stage === CHOOSING
  const stageLine = status === RUNNING && !choosing ? stageText(stage) : null
  const settingsLine = settings ? (
    <p className="animation-card-settings">{settingsText(settings)}</p>
  ) : null

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
        {settingsLine}
      </button>
    )
  }

  return (
    <div className="animation-card">
      <Clapperboard size={20} strokeWidth={2} aria-hidden="true" />
      <p className="animation-card-title">Animation</p>
      {choosing ? <Badge variant="accent">Waiting for you</Badge> : null}
      {status === RUNNING && !choosing ? <Badge>In progress</Badge> : null}
      {settingsLine}
      {stageLine ? (
        <p className="animation-card-stage" role="status">
          {stageLine}
        </p>
      ) : null}
      {choosing ? (
        <>
          <p className="animation-card-stage">
            Choose the engine, quality, and frame rate to start it.
          </p>
          <div className="animation-card-choose">
            <button
              type="button"
              className="secondary"
              onClick={() => askForAnimationSettings({ ...job, status, stage })}
            >
              Choose settings
            </button>
          </div>
        </>
      ) : null}
      {status === FAILED ? (
        <AlertBanner>{FAILURE_NOTICE}</AlertBanner>
      ) : null}
    </div>
  )
}
