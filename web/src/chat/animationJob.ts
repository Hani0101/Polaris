/** A running animation job as the chat shows it: its status and stage (AN-19). */

import { useEffect, useState } from 'react'
import { getAnimationJob } from '../api.ts'
import type { AnimationArtifact, AnimationStage } from '../api.ts'

export const RUNNING = 'running'
const POLL_MS = 10_000

const STAGE_TEXT: Record<AnimationStage, string> = {
  writing: 'Writing the animation',
  checking: 'Checking the animation',
  fixing: 'Fixing the animation',
}

/** What the learner reads for a running job's stage (AN-19), or null. */
export function stageText(stage: AnimationStage | null | undefined): string | null {
  return stage ? (STAGE_TEXT[stage] ?? null) : null
}

type JobView = { status: string; stage: AnimationStage | null }

/**
 * The job's latest status and stage. While it runs, it asks the backend
 * again every few seconds; a failed check changes nothing.
 */
export function useAnimationJob(
  job: AnimationArtifact,
  onStatus?: (jobId: string, status: string) => void,
): JobView {
  const [polled, setPolled] = useState<JobView | null>(null)
  const status = job.status === RUNNING ? (polled?.status ?? job.status) : job.status
  const stage = status === RUNNING ? (polled?.stage ?? job.stage ?? null) : null

  useEffect(() => {
    if (status !== RUNNING || !job.session_id) return
    const controller = new AbortController()
    const timer = window.setInterval(() => {
      getAnimationJob(job.session_id, job.id, controller.signal)
        .then((next) => {
          if (controller.signal.aborted) return
          setPolled({ status: next.status, stage: next.stage ?? null })
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

  return { status, stage }
}
