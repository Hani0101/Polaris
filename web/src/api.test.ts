import { afterEach, expect, test, vi } from 'vitest'
import { sendTurn, turnBody, warmSession } from './api.ts'
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

test('a turn can carry a picture of a whiteboard', () => {
  const picture = { whiteboard_id: 'wb-1', media_type: 'image/png' as const, data: 'iVBORw0K' }

  expect(turnBody('Is this right?', null, null, picture)).toEqual({
    message: 'Is this right?',
    picture,
  })
  expect(turnBody('Is this right?', null, null, null)).toEqual({ message: 'Is this right?' })
})

test('a turn about an animation step names the job and the step (AN-17)', () => {
  expect(turnBody('Why?', null, null, null, { jobId: 'job-1', stepId: 'discard' })).toEqual({
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

test('a turn names the pinned whiteboard, and only while one is pinned (WB-19)', () => {
  expect(turnBody('Is this right?', null, null, null, null, 'wb-1')).toEqual({
    message: 'Is this right?',
    pinned_whiteboard_id: 'wb-1',
  })
  expect(turnBody('Is this right?', null, null, null, null, null)).toEqual({
    message: 'Is this right?',
  })
})

test('warmSession posts to the session warm route', async () => {
  const fetchMock = vi.fn(
    async (_input: RequestInfo, _init?: RequestInit) =>
      new Response(JSON.stringify({ id: 'session 1' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)

  await expect(warmSession('session 1')).resolves.toEqual({ id: 'session 1' })

  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/api/sessions/session%201/warm')
  expect(init?.method).toBe('POST')
})

test('only a web-mode turn asks for the web (CH-23)', () => {
  expect(turnBody('What is new?', null, null, null, null, null, true)).toEqual({
    message: 'What is new?',
    web: true,
  })
  expect(turnBody('What is new?', null, null, null, null, null, false)).toEqual({
    message: 'What is new?',
  })
})
