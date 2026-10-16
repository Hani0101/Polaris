/**
 * Operating-system notices for animation jobs (AN-03, AN-07, AN-08, AN-09).
 *
 * Permission is asked when a long-running job starts, not when the app opens.
 * A ready notice opens the animation. Failed jobs never get a ready notice.
 */

import { getAnimationJob } from '../api.ts'
import { animationPagePath } from '../animationPath.ts'

const POLL_MS = 10_000
const NOTICE_TITLE = 'Polaris'
const READY_BODY = 'Your animation is ready.'

export type NoticePermission = NotificationPermission | 'unsupported'

type WatchKey = string

type Watchers = {
  askPermission: () => Promise<NoticePermission>
  showReady: (sessionId: string, jobId: string, openPath: string) => void
  pollJob: typeof getAnimationJob
  setTimer: typeof window.setInterval
  clearTimer: typeof window.clearInterval
}

const defaultWatchers = (): Watchers => ({
  askPermission: askNoticePermission,
  showReady: showReadyNotice,
  pollJob: getAnimationJob,
  setTimer: (handler, ms) => window.setInterval(handler, ms),
  clearTimer: (id) => window.clearInterval(id),
})

const watching = new Map<WatchKey, number>()
let watchers: Watchers = defaultWatchers()

function keyOf(sessionId: string, jobId: string): WatchKey {
  return `${sessionId}:${jobId}`
}

export function noticesSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window
}

/** Current permission. Does not prompt (AN-07: prompt only when a job starts). */
export function noticePermission(): NoticePermission {
  if (!noticesSupported()) return 'unsupported'
  return Notification.permission
}

/** Ask once when a long-running job starts, if the OS has no answer yet (AN-07). */
export async function askNoticePermission(): Promise<NoticePermission> {
  if (!noticesSupported()) return 'unsupported'
  if (Notification.permission !== 'default') return Notification.permission
  return Notification.requestPermission()
}

/**
 * Show a ready notice when permission was granted (AN-03).
 * No-op when permission was refused (AN-08) or notices are unsupported.
 */
export function showReadyNotice(
  sessionId: string,
  jobId: string,
  openPath: string = animationPagePath(sessionId, jobId),
): void {
  if (!noticesSupported()) return
  if (Notification.permission !== 'granted') return
  const notice = new Notification(NOTICE_TITLE, {
    body: READY_BODY,
    tag: `animation-ready-${jobId}`,
  })
  notice.onclick = () => {
    window.focus()
    history.pushState({}, '', openPath)
    window.dispatchEvent(new PopStateEvent('popstate'))
    notice.close()
  }
}

/** Test seam: replace timers and Notification helpers. */
export function _setNoticeWatchers(next: Partial<Watchers> | null): void {
  watchers = next ? { ...defaultWatchers(), ...next } : defaultWatchers()
}

/** Test seam: stop every watcher. */
export function _clearNoticeWatchers(): void {
  for (const timer of watching.values()) watchers.clearTimer(timer)
  watching.clear()
}

export type AnimationStatusHandler = (jobId: string, status: string) => void

/**
 * When a job is running, ask for permission (once) and poll until ready or failed.
 * On ready, send an OS notice if allowed. Failed jobs get no ready notice (AN-09).
 */
export function watchAnimationJob(
  sessionId: string,
  jobId: string,
  onStatus?: AnimationStatusHandler,
): void {
  const key = keyOf(sessionId, jobId)
  if (watching.has(key)) return

  void watchers.askPermission()

  const timer = watchers.setTimer(() => {
    void watchers
      .pollJob(sessionId, jobId)
      .then((job) => {
        if (job.status === 'running') return
        stopWatching(key)
        onStatus?.(jobId, job.status)
        if (job.status === 'ready') {
          watchers.showReady(sessionId, jobId, animationPagePath(sessionId, jobId))
        }
      })
      .catch(() => {
        // Keep polling; a single failed check is not the end of the job.
      })
  }, POLL_MS)

  watching.set(key, timer)
}

function stopWatching(key: WatchKey): void {
  const timer = watching.get(key)
  if (timer === undefined) return
  watchers.clearTimer(timer)
  watching.delete(key)
}

/** Register every running animation in a list of artifacts. */
export function watchRunningAnimations(
  artifacts: { id: string; kind: string; session_id: string; status: string }[],
  onStatus?: AnimationStatusHandler,
): void {
  for (const artifact of artifacts) {
    if (artifact.kind !== 'animation' || artifact.status !== 'running') continue
    watchAnimationJob(artifact.session_id, artifact.id, onStatus)
  }
}
