import { afterEach, beforeEach, expect, test, vi } from 'vitest'

type Route = (init?: RequestInit) => Response | Promise<Response>

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function granted(token: string) {
  return json({ access_token: token, expires_in: 3600, username: 'ada' })
}

/** Answers by "METHOD path" and records every call. */
function serve(routes: Record<string, Route>) {
  const calls: { key: string; init?: RequestInit }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    calls.push({ key, init })
    const route = routes[key]
    if (!route) throw new Error(`No route for ${key}`)
    return route(init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

function authorization(init?: RequestInit): string | undefined {
  return (init?.headers as Record<string, string> | undefined)?.Authorization
}

async function freshAuth() {
  vi.resetModules()
  return import('./auth.ts')
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
  vi.setSystemTime(new Date('2026-10-18T09:00:00Z'))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('with no refresh cookie the page opens anonymous [AU-01, AU-10]', async () => {
  serve({ 'POST /api/sign-in/refresh': () => json({ detail: 'Sign in again.' }, 401) })
  const auth = await freshAuth()

  expect(await auth.restoreSignIn()).toBe(false)

  expect(auth.signInState()).toEqual({ status: 'anonymous' })
  expect(await auth.accessHeader()).toEqual({})
})

test('signing in keeps the access token in memory only [AU-06, AU-08]', async () => {
  serve({ 'POST /api/sign-in': () => granted('token-1') })
  const auth = await freshAuth()

  await auth.signIn('ada', 'correct horse')

  expect(auth.signInState()).toEqual({ status: 'signed-in', username: 'ada' })
  expect(await auth.accessHeader()).toEqual({ Authorization: 'Bearer token-1' })
  expect(JSON.stringify({ ...window.localStorage })).not.toContain('token-1')
  expect(JSON.stringify({ ...window.sessionStorage })).not.toContain('token-1')
  expect(document.cookie).not.toContain('token-1')
})

test('an access token about to run out is refreshed before the request [AU-10]', async () => {
  const calls = serve({
    'POST /api/sign-in': () => granted('token-1'),
    'POST /api/sign-in/refresh': () => granted('token-2'),
  })
  const auth = await freshAuth()
  await auth.signIn('ada', 'correct horse')

  vi.setSystemTime(new Date('2026-10-18T09:59:45Z'))

  expect(await auth.accessHeader()).toEqual({ Authorization: 'Bearer token-2' })
  expect(calls.filter((call) => call.key === 'POST /api/sign-in/refresh')).toHaveLength(1)
})

test('the page refreshes on its own before the token runs out [AU-10]', async () => {
  const calls = serve({
    'POST /api/sign-in': () => granted('token-1'),
    'POST /api/sign-in/refresh': () => granted('token-2'),
  })
  const auth = await freshAuth()
  await auth.signIn('ada', 'correct horse')

  await vi.advanceTimersByTimeAsync(59 * 60 * 1000)

  expect(calls.map((call) => call.key)).toContain('POST /api/sign-in/refresh')
  expect(await auth.accessHeader()).toEqual({ Authorization: 'Bearer token-2' })
})

test('a dead refresh token makes the learner anonymous and turns go without a token [AU-10]', async () => {
  const calls = serve({
    'POST /api/sign-in': () => granted('token-1'),
    'POST /api/sign-in/refresh': () => json({ detail: 'Sign in again.' }, 401),
    'POST /api/sessions/s1/turns': () =>
      new Response('data: {"done": true}\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
  })
  const auth = await freshAuth()
  const api = await import('./api.ts')
  await auth.signIn('ada', 'correct horse')

  await vi.advanceTimersByTimeAsync(59 * 60 * 1000)
  await api.sendTurn('s1', 'Hi', () => {}, () => {})

  expect(auth.signInState()).toEqual({ status: 'anonymous' })
  const turn = calls.find((call) => call.key === 'POST /api/sessions/s1/turns')
  expect(authorization(turn?.init)).toBeUndefined()
})

test('two refreshes at once send one request [AU-09]', async () => {
  const calls = serve({ 'POST /api/sign-in/refresh': () => granted('token-2') })
  const auth = await freshAuth()

  await Promise.all([auth.refreshSignIn(), auth.refreshSignIn(), auth.restoreSignIn()])

  expect(calls).toHaveLength(1)
})

test('signing out revokes the refresh token and clears the access token [AU-11]', async () => {
  const calls = serve({
    'POST /api/sign-in': () => granted('token-1'),
    'DELETE /api/sign-in/refresh': () => json({}),
  })
  const auth = await freshAuth()
  await auth.signIn('ada', 'correct horse')

  await auth.signOut()

  expect(calls.map((call) => call.key)).toContain('DELETE /api/sign-in/refresh')
  expect(auth.signInState()).toEqual({ status: 'anonymous' })
  expect(await auth.accessHeader()).toEqual({})
})

test('a blocked sign-in says how long is left [AU-13]', async () => {
  serve({
    'POST /api/sign-in': () =>
      json({ detail: 'Sign-in is paused.', blocked_seconds: 540 }, 429),
  })
  const auth = await freshAuth()

  const caught = await auth.signIn('ada', 'correct horse').catch((error: unknown) => error)

  expect(caught).toBeInstanceOf(auth.SignInBlocked)
  expect((caught as InstanceType<typeof auth.SignInBlocked>).seconds).toBe(540)
  expect(auth.signInState()).toEqual({ status: 'checking' })
})

test('the profile is read with the token, refreshed once when refused [AU-12]', async () => {
  let profileCalls = 0
  const calls = serve({
    'POST /api/sign-in': () => granted('token-1'),
    'POST /api/sign-in/refresh': () => granted('token-2'),
    'GET /api/profile': (init) => {
      profileCalls += 1
      return authorization(init) === 'Bearer token-2'
        ? json({ facts: ['likes diagrams'] })
        : json({ detail: 'Sign in to see your profile.' }, 401)
    },
  })
  const auth = await freshAuth()
  const api = await import('./api.ts')
  await auth.signIn('ada', 'correct horse')

  expect(await api.readProfile()).toEqual(['likes diagrams'])
  expect(profileCalls).toBe(2)
  expect(calls.filter((call) => call.key === 'POST /api/sign-in/refresh')).toHaveLength(1)
})
