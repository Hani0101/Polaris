import { afterEach, expect, test, vi } from 'vitest'
import { sendTurn, turnBody } from './api.ts'
import { SIMPLER_REQUEST } from './whiteboard/simpler.ts'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('a simpler turn sends the original whiteboard id', () => {
  expect(turnBody(SIMPLER_REQUEST, null, 'wb-1')).toEqual({
    message: 'Draw a simpler version of this whiteboard.',
    simplifies: 'wb-1',
  })
  expect(turnBody('Hello', null)).toEqual({ message: 'Hello' })
})

test('a turn about an animation step names the job and the step (AN-17)', () => {
  expect(turnBody('Why?', null, null, { jobId: 'job-1', stepId: 'discard' })).toEqual({
    message: 'Why?',
    animation_step: { job_id: 'job-1', step_id: 'discard' },
  })
})

test('sendTurn posts the animation step with the message', async () => {
  const fetchMock = vi.fn(
    async (_input: RequestInfo, _init?: RequestInit) =>
      new Response('data: {"done": true}\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)

  await sendTurn('session-1', 'Why does it go left?', () => {}, () => {}, {
    animationStep: { jobId: 'job-1', stepId: 'discard' },
  })

  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/api/sessions/session-1/turns')
  expect(JSON.parse(String(init?.body))).toEqual({
    message: 'Why does it go left?',
    animation_step: { job_id: 'job-1', step_id: 'discard' },
  })
})
