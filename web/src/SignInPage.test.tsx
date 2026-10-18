import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

type Route = (init?: RequestInit) => Response

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function serve(routes: Record<string, Route>) {
  const calls: { key: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${String(input)}`
      calls.push({ key, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      const route = routes[key]
      if (!route) throw new Error(`No route for ${key}`)
      return route(init)
    }),
  )
  return calls
}

async function renderPage(onSignedIn = vi.fn()) {
  vi.resetModules()
  const { SignInPage } = await import('./SignInPage.tsx')
  render(<SignInPage onBack={() => {}} onSignedIn={onSignedIn} />)
  return onSignedIn
}

function type(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('the first visit chooses the pair, entering the password twice [AU-05]', async () => {
  const calls = serve({
    'GET /api/sign-in': () => json({ pair_stored: false, blocked_seconds: 0 }),
    'POST /api/sign-in/pair': () =>
      json({ access_token: 't', expires_in: 3600, username: 'ada' }),
  })
  const onSignedIn = await renderPage()

  await screen.findByRole('heading', { name: 'Choose a username and password' })
  type('Username', 'ada')
  type('Password', 'correct horse')
  type('Password again', 'correct horse')
  fireEvent.click(screen.getByRole('button', { name: 'Save and sign in' }))

  await waitFor(() => expect(onSignedIn).toHaveBeenCalled())
  expect(calls.find((call) => call.key === 'POST /api/sign-in/pair')?.body).toEqual({
    username: 'ada',
    password: 'correct horse',
    password_again: 'correct horse',
  })
})

test('a short password or an empty username is refused before sending [AU-05]', async () => {
  const calls = serve({
    'GET /api/sign-in': () => json({ pair_stored: false, blocked_seconds: 0 }),
  })
  await renderPage()

  await screen.findByLabelText('Password again')
  type('Password', 'short')
  type('Password again', 'shorter')
  fireEvent.click(screen.getByRole('button', { name: 'Save and sign in' }))

  expect(await screen.findByText('Enter a username.')).toBeTruthy()
  expect(screen.getByText('Use at least 8 characters.')).toBeTruthy()
  expect(screen.getByText("The two passwords don't match.")).toBeTruthy()
  expect(screen.getByLabelText('Username').getAttribute('aria-invalid')).toBe('true')
  expect(calls.map((call) => call.key)).toEqual(['GET /api/sign-in'])
})

test('the page asks for a username and a password [AU-04]', async () => {
  serve({ 'GET /api/sign-in': () => json({ pair_stored: true, blocked_seconds: 0 }) })
  await renderPage()

  expect(await screen.findByLabelText('Username')).toBeTruthy()
  expect((screen.getByLabelText('Password') as HTMLInputElement).type).toBe('password')
  expect(screen.queryByLabelText('Password again')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }))
  expect((screen.getByLabelText('Password') as HTMLInputElement).type).toBe('text')
})

test('a mismatch stays on the page and does not say which part was wrong [AU-06]', async () => {
  serve({
    'GET /api/sign-in': () => json({ pair_stored: true, blocked_seconds: 0 }),
    'POST /api/sign-in': () => json({ detail: "That username and password don't match." }, 401),
  })
  const onSignedIn = await renderPage()

  await screen.findByLabelText('Username')
  type('Username', 'ada')
  type('Password', 'not the password')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe("That username and password don't match. Check them and try again.")
  expect(onSignedIn).not.toHaveBeenCalled()
  expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('')
})

test('a forgotten pair cannot be replaced [AU-07]', async () => {
  serve({ 'GET /api/sign-in': () => json({ pair_stored: true, blocked_seconds: 0 }) })
  await renderPage()

  await screen.findByLabelText('Username')

  expect(screen.queryByRole('link')).toBeNull()
  expect(screen.queryByRole('button', { name: /forgot|reset|recover/i })).toBeNull()
  expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual([
    'Back to the conversation',
    '',
    'Sign in',
  ])
  expect(screen.getByText("Polaris can't reset a forgotten username or password.")).toBeTruthy()
})

test('a block says how long is left and refuses to send [AU-13]', async () => {
  const calls = serve({
    'GET /api/sign-in': () => json({ pair_stored: true, blocked_seconds: 540 }),
  })
  await renderPage()

  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe(
    "Sign-in is paused after five tries that didn't match. Try again in 9 minutes.",
  )
  const button = screen.getByRole('button', { name: 'Sign in' }) as HTMLButtonElement
  expect(button.disabled).toBe(true)
  fireEvent.submit(button.closest('form') as HTMLFormElement)
  expect(calls.map((call) => call.key)).toEqual(['GET /api/sign-in'])
})

test('the fifth wrong try shows the block [AU-13]', async () => {
  serve({
    'GET /api/sign-in': () => json({ pair_stored: true, blocked_seconds: 0 }),
    'POST /api/sign-in': () => json({ detail: 'Sign-in is paused.', blocked_seconds: 600 }, 429),
  })
  await renderPage()

  await screen.findByLabelText('Username')
  type('Username', 'ada')
  type('Password', 'not the password')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect((await screen.findByRole('alert')).textContent).toContain('Try again in 10 minutes.')
})
