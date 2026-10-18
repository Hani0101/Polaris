/** A running animation job as the chat shows it: its status and stage (AN-19). */

import { useEffect, useState } from 'react'
import { getAnimationJob } from '../api.ts'
import type { AnimationArtifact, AnimationSettings, AnimationStage } from '../api.ts'

export const RUNNING = 'running'
// The job waits for the learner to pick the engine and its settings (AN-21, AN-26).
export const CHOOSING = 'choosing'
const POLL_MS = 10_000

const STAGE_TEXT: Record<AnimationStage, string> = {
  choosing: 'Waiting for you to choose the engine and quality',
  queued: 'Waiting for another animation to finish',
  writing: 'Writing the animation',
  checking: 'Checking the animation',
  fixing: 'Fixing the animation',
}

/** What the learner reads for a running job's stage (AN-19), or null. */
export function stageText(stage: AnimationStage | null | undefined): string | null {
  return stage ? (STAGE_TEXT[stage] ?? null) : null
}

export type JobListener = (job: AnimationArtifact) => void

type Polling = {
  pollJob: typeof getAnimationJob
  setTimer: typeof window.setInterval
  clearTimer: typeof window.clearInterval
}

const defaultPolling = (): Polling => ({
  pollJob: getAnimationJob,
  setTimer: (handler, ms) => window.setInterval(handler, ms),
  clearTimer: (id) => window.clearInterval(id),
})

type Poll = { timer: number; controller: AbortController; listeners: Set<JobListener> }

// One poll per job, shared by the app-level watcher and every card showing it.
const polls = new Map<string, Poll>()
let polling: Polling = defaultPolling()

function stopPoll(key: string, poll: Poll): void {
  if (polls.get(key) !== poll) return
  polling.clearTimer(poll.timer)
  poll.controller.abort()
  polls.delete(key)
}

function startPoll(key: string, sessionId: string, jobId: string): Poll {
  const poll: Poll = { timer: 0, controller: new AbortController(), listeners: new Set() }
  poll.timer = polling.setTimer(() => {
    polling
      .pollJob(sessionId, jobId, poll.controller.signal)
      .then((job) => {
        if (poll.controller.signal.aborted) return
        // A ready or failed job is not asked about again.
        if (job.status !== RUNNING && polls.get(key) === poll) {
          polling.clearTimer(poll.timer)
          polls.delete(key)
        }
        for (const listener of [...poll.listeners]) {
          if (poll.listeners.has(listener)) listener(job)
        }
      })
      .catch(() => {
        // A failed check changes nothing; the next one tries again.
      })
  }, POLL_MS)
  polls.set(key, poll)
  return poll
}

/**
 * Hears each check of a running job until it is ready or failed. The first
 * listener starts the job's one timer, and the last one to leave stops it.
 */
export function subscribeAnimationJob(
  sessionId: string,
  jobId: string,
  listener: JobListener,
): () => void {
  const key = `${sessionId}:${jobId}`
  const poll = polls.get(key) ?? startPoll(key, sessionId, jobId)
  poll.listeners.add(listener)
  return () => {
    poll.listeners.delete(listener)
    if (poll.listeners.size === 0) stopPoll(key, poll)
  }
}

/** Tell everyone hearing this job about news that did not come from a poll. */
export function shareAnimationJob(job: AnimationArtifact): void {
  const poll = polls.get(`${job.session_id}:${job.id}`)
  if (!poll) return
  for (const listener of [...poll.listeners]) listener(job)
}

type SettingsAsker = (job: AnimationArtifact) => void
let settingsAsker: SettingsAsker | null = null

/**
 * Opens the dialog that asks for a waiting job's engine, quality, and frame
 * rate (AN-21, AN-26). The app mounts the one dialog; cards and the chat call this.
 */
export function askForAnimationSettings(job: AnimationArtifact): void {
  settingsAsker?.(job)
}

/** The app's settings dialog registers here. Returns the unregister. */
export function setAnimationSettingsAsker(asker: SettingsAsker): () => void {
  settingsAsker = asker
  return () => {
    if (settingsAsker === asker) settingsAsker = null
  }
}

/** Test seam: replace the fetch and timers behind every poll. */
export function _setJobPolling(next: Partial<Polling> | null): void {
  polling = next ? { ...defaultPolling(), ...next } : defaultPolling()
}

/** Test seam: stop every poll. */
export function _stopJobPolling(): void {
  for (const [key, poll] of [...polls]) stopPoll(key, poll)
}

type JobView = {
  status: string
  stage: AnimationStage | null
  /** The engine, quality, and frame rate, once chosen (AN-26). */
  settings: AnimationSettings | null
}

/**
 * The job's latest status, stage, and settings. While it runs, it hears the
 * job's shared poll, which asks the backend again every few seconds; a failed
 * check changes nothing.
 */
export function useAnimationJob(
  job: AnimationArtifact,
  onStatus?: (jobId: string, status: string) => void,
): JobView {
  const [polled, setPolled] = useState<JobView | null>(null)
  const status = job.status === RUNNING ? (polled?.status ?? job.status) : job.status
  const stage = status === RUNNING ? (polled?.stage ?? job.stage ?? null) : null
  const settings = polled?.settings ?? job.settings ?? null

  useEffect(() => {
    if (status !== RUNNING || !job.session_id) return
    return subscribeAnimationJob(job.session_id, job.id, (next) => {
      setPolled({
        status: next.status,
        stage: next.stage ?? null,
        settings: next.settings ?? null,
      })
      if (next.status !== RUNNING) onStatus?.(job.id, next.status)
    })
  }, [status, job.id, job.session_id, onStatus])

  return { status, stage, settings }
}
