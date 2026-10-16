import { afterEach, expect, test, vi } from 'vitest'
import {
  _clearNoticeWatchers,
  _setNoticeWatchers,
  askNoticePermission,
  noticePermission,
  showReadyNotice,
  watchAnimationJob,
} from './animationNotices.ts'

afterEach(() => {
  _clearNoticeWatchers()
  _setNoticeWatchers(null)
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

test('permission is not asked by reading the current answer', () => {
  const requestPermission = vi.fn()
  vi.stubGlobal('Notification', {
    permission: 'default',
    requestPermission,
  })
  expect(noticePermission()).toBe('default')
  expect(requestPermission).not.toHaveBeenCalled()
})

test('a job start asks for permission when the OS has no answer', async () => {
  const askPermission = vi.fn().mockResolvedValue('granted')
  const pollJob = vi.fn().mockResolvedValue({
    id: 'job-1',
    kind: 'animation',
    session_id: 's-1',
    status: 'running',
  })
  const timers: Array<() => void> = []
  _setNoticeWatchers({
    askPermission,
    pollJob,
    showReady: vi.fn(),
    setTimer: (handler) => {
      timers.push(handler as () => void)
      return timers.length
    },
    clearTimer: vi.fn(),
  })

  watchAnimationJob('s-1', 'job-1')
  expect(askPermission).toHaveBeenCalledTimes(1)
})

test('a ready job sends a notice that opens the animation', async () => {
  vi.useFakeTimers()
  const showReady = vi.fn()
  const onStatus = vi.fn()
  const pollJob = vi
    .fn()
    .mockResolvedValueOnce({
      id: 'job-1',
      kind: 'animation',
      session_id: 's-1',
      status: 'running',
    })
    .mockResolvedValueOnce({
      id: 'job-1',
      kind: 'animation',
      session_id: 's-1',
      status: 'ready',
    })

  _setNoticeWatchers({
    askPermission: vi.fn().mockResolvedValue('granted'),
    pollJob,
    showReady,
  })

  watchAnimationJob('s-1', 'job-1', onStatus)
  await vi.advanceTimersByTimeAsync(10_000)
  expect(showReady).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(10_000)
  expect(showReady).toHaveBeenCalledWith('s-1', 'job-1', '/animation/s-1/job-1')
  expect(onStatus).toHaveBeenCalledWith('job-1', 'ready')
})

test('a failed job does not send a ready notice', async () => {
  vi.useFakeTimers()
  const showReady = vi.fn()
  const onStatus = vi.fn()
  _setNoticeWatchers({
    askPermission: vi.fn().mockResolvedValue('granted'),
    pollJob: vi.fn().mockResolvedValue({
      id: 'job-1',
      kind: 'animation',
      session_id: 's-1',
      status: 'failed',
    }),
    showReady,
  })

  watchAnimationJob('s-1', 'job-1', onStatus)
  await vi.advanceTimersByTimeAsync(10_000)
  expect(showReady).not.toHaveBeenCalled()
  expect(onStatus).toHaveBeenCalledWith('job-1', 'failed')
})

test('a refused permission still skips the notice', () => {
  const Notice = vi.fn()
  vi.stubGlobal('Notification', Object.assign(Notice, { permission: 'denied' }))
  showReadyNotice('s-1', 'job-1')
  expect(Notice).not.toHaveBeenCalled()
})

test('askNoticePermission requests only when permission is default', async () => {
  const requestPermission = vi.fn().mockResolvedValue('granted')
  vi.stubGlobal('Notification', {
    permission: 'default',
    requestPermission,
  })
  await expect(askNoticePermission()).resolves.toBe('granted')
  expect(requestPermission).toHaveBeenCalledTimes(1)

  vi.stubGlobal('Notification', {
    permission: 'denied',
    requestPermission,
  })
  await expect(askNoticePermission()).resolves.toBe('denied')
  expect(requestPermission).toHaveBeenCalledTimes(1)
})
