/**
 * The local sign-in (AU-02 to AU-13, decision 0008).
 *
 * The access token lives only in this module's memory, never in storage
 * (AU-08). The refresh token is an httpOnly cookie the page cannot read
 * (AU-09). The page refreshes before the access token runs out, and a refused
 * refresh makes the learner anonymous without blocking chat (AU-10).
 */

import { useSyncExternalStore } from 'react'
import { ApiError, readDetail } from './httpError.ts'

export type SignInState =
  | { status: 'checking' }
  | { status: 'anonymous' }
  | { status: 'signed-in'; username: string }

export type SignInStatus = {
  pair_stored: boolean
  blocked_seconds: number
}

/** AU-13: sign-in is paused. `seconds` is how long is left. */
export class SignInBlocked extends ApiError {
  seconds: number

  constructor(message: string, seconds: number) {
    super(429, message)
    this.seconds = seconds
  }
}

const REFRESH_PATH = '/api/sign-in/refresh'
// Refresh this long before the access token runs out.
const REFRESH_EARLY_MS = 60_000
// A refresh that could not reach the server is tried again after this.
const RETRY_MS = 30_000

type Access = { token: string; expiresAt: number }

let state: SignInState = { status: 'checking' }
let access: Access | null = null
let refreshTimer: ReturnType<typeof setTimeout> | null = null
let refreshing: Promise<boolean> | null = null
const listeners = new Set<() => void>()

function setState(next: SignInState) {
  state = next
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function signInState(): SignInState {
  return state
}

export function useSignIn(): SignInState {
  return useSyncExternalStore(subscribe, signInState)
}

function schedule(delay: number) {
  if (refreshTimer !== null) clearTimeout(refreshTimer)
  refreshTimer = setTimeout(() => {
    refreshTimer = null
    void refreshSignIn()
  }, Math.max(0, delay))
}

function forget() {
  access = null
  if (refreshTimer !== null) clearTimeout(refreshTimer)
  refreshTimer = null
}

type Granted = { access_token: string; expires_in: number; username: string }

function accept(granted: Granted) {
  const lifetime = granted.expires_in * 1000
  access = { token: granted.access_token, expiresAt: Date.now() + lifetime }
  schedule(lifetime - REFRESH_EARLY_MS)
  setState({ status: 'signed-in', username: granted.username })
}

function becomeAnonymous() {
  forget()
  setState({ status: 'anonymous' })
}

/** One refresh at a time, across tabs too: a second use of a replaced token ends the sign-in (AU-09). */
function oneRefreshAtATime(run: () => Promise<boolean>): Promise<boolean> {
  const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined
  if (!locks) return run()
  return locks.request('polaris-sign-in-refresh', run)
}

async function postRefresh(): Promise<boolean> {
  let response: Response
  try {
    response = await fetch(REFRESH_PATH, { method: 'POST', headers: { Accept: 'application/json' } })
  } catch {
    // The server could not be reached. Keep what we have and try again soon.
    schedule(RETRY_MS)
    if (state.status === 'checking') setState({ status: 'anonymous' })
    return access !== null && access.expiresAt > Date.now()
  }
  if (!response.ok) {
    // Expired, replaced, or revoked: the learner is anonymous now (AU-10).
    becomeAnonymous()
    return false
  }
  accept((await response.json()) as Granted)
  return true
}

/**
 * Get a new access token with the refresh cookie. Resolves whether the
 * learner is still signed in. Never throws.
 */
export function refreshSignIn(): Promise<boolean> {
  if (!refreshing) {
    refreshing = oneRefreshAtATime(postRefresh).finally(() => {
      refreshing = null
    })
  }
  return refreshing
}

/**
 * The Authorization header for the next request, refreshed first when the
 * token is about to run out (AU-10). Empty while anonymous.
 */
export async function accessHeader(): Promise<Record<string, string>> {
  if (state.status === 'checking' && refreshing) await refreshing
  if (access && access.expiresAt - Date.now() < REFRESH_EARLY_MS / 2) await refreshSignIn()
  return access ? { Authorization: `Bearer ${access.token}` } : {}
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init.headers },
  })
  if (response.status === 429) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string
      blocked_seconds?: number
    }
    throw new SignInBlocked(body.detail ?? 'Sign-in is paused.', body.blocked_seconds ?? 0)
  }
  if (!response.ok) throw new ApiError(response.status, await readDetail(response))
  return (await response.json()) as T
}

/** Whether a pair is stored yet (AU-05), and how long a block has left (AU-13). */
export function readSignInStatus(signal?: AbortSignal): Promise<SignInStatus> {
  return send<SignInStatus>('/api/sign-in', { method: 'GET', signal })
}

/** AU-05: the first visit chooses the pair, which also signs the learner in. */
export async function choosePair(
  username: string,
  password: string,
  passwordAgain: string,
): Promise<void> {
  accept(
    await send<Granted>('/api/sign-in/pair', {
      method: 'POST',
      body: JSON.stringify({ username, password, password_again: passwordAgain }),
    }),
  )
}

/** AU-06: a matching pair signs the learner in. */
export async function signIn(username: string, password: string): Promise<void> {
  accept(
    await send<Granted>('/api/sign-in', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  )
}

/** AU-11: revoke the refresh token and drop the access token. The profile stays. */
export async function signOut(): Promise<void> {
  const response = await fetch(REFRESH_PATH, { method: 'DELETE' })
  if (!response.ok) throw new ApiError(response.status, await readDetail(response))
  becomeAnonymous()
}

/** On load, a refresh cookie from an earlier visit signs the learner back in quietly. */
export function restoreSignIn(): Promise<boolean> {
  return refreshSignIn()
}
