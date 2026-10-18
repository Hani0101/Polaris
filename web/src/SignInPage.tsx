import { useCallback, useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowLeft, Eye, EyeOff, LoaderCircle } from 'lucide-react'
import {
  SignInBlocked,
  choosePair,
  readSignInStatus,
  signIn,
  signOut,
  useSignIn,
} from './auth.ts'
import { ApiError } from './httpError.ts'
import { AlertBanner, AlertIcon, IconButton } from './chat/ui.tsx'
import './settings.css'
import './signIn.css'

const MIN_PASSWORD_LENGTH = 8

type SignInPageProps = {
  onBack: () => void
  /** The learner signed in. The page goes back to the conversation. */
  onSignedIn: () => void
}

type FieldErrors = Partial<Record<'username' | 'password' | 'passwordAgain', string>>

/** AU-13: say how long is left, in whole minutes, so a screen reader is not read every second. */
function blockedText(seconds: number): string {
  const minutes = Math.max(1, Math.ceil(seconds / 60))
  const left = minutes === 1 ? '1 minute' : `${minutes} minutes`
  return `Sign-in is paused after five tries that didn't match. Try again in ${left}.`
}

function failureText(caught: unknown, action: string): string {
  if (caught instanceof ApiError && caught.status === 401) {
    // AU-06: never says which part was wrong.
    return "That username and password don't match. Check them and try again."
  }
  if (caught instanceof ApiError && caught.status === 422) return caught.message
  return `Couldn't ${action}. Check that Polaris is running and try again.`
}

/** Seconds a block has left, counting down each second to 0 (AU-13). */
function useBlock(): [number, (seconds: number) => void] {
  const [until, setUntil] = useState<number | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)
  useEffect(() => {
    if (until === null) return
    const timer = window.setInterval(() => {
      const left = Math.max(0, (until - Date.now()) / 1000)
      setSecondsLeft(left)
      if (left === 0) setUntil(null)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [until])
  const block = useCallback((seconds: number) => {
    setSecondsLeft(Math.max(0, seconds))
    setUntil(seconds > 0 ? Date.now() + seconds * 1000 : null)
  }, [])
  return [secondsLeft, block]
}

type TextFieldProps = {
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete: string
  error?: string
  help?: string
  password?: boolean
}

function TextField({ label, value, onChange, autoComplete, error, help, password }: TextFieldProps) {
  const id = useId()
  const [shown, setShown] = useState(false)
  const note = error ?? help
  const input = (
    <input
      id={id}
      type={password && !shown ? 'password' : 'text'}
      className={error ? 'text-input is-error' : 'text-input'}
      value={value}
      autoComplete={autoComplete}
      autoCapitalize="none"
      spellCheck={false}
      aria-invalid={error ? true : undefined}
      aria-describedby={note ? `${id}-note` : undefined}
      onChange={(event) => onChange(event.target.value)}
    />
  )
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {password ? (
        <div className="password-input">
          {input}
          <IconButton
            label={shown ? 'Hide password' : 'Show password'}
            size="sm"
            onClick={() => setShown((current) => !current)}
          >
            {shown ? (
              <EyeOff size={20} strokeWidth={2} aria-hidden="true" />
            ) : (
              <Eye size={20} strokeWidth={2} aria-hidden="true" />
            )}
          </IconButton>
        </div>
      ) : (
        input
      )}
      {error ? (
        <p id={`${id}-note`} className="field-error">
          <AlertIcon />
          <span>{error}</span>
        </p>
      ) : help ? (
        <p id={`${id}-note`} className="field-help">
          {help}
        </p>
      ) : null}
    </div>
  )
}

function SubmitButton({ busy, disabled, children }: { busy: boolean; disabled: boolean; children: string }) {
  return (
    <button
      type="submit"
      className="si-submit"
      disabled={disabled}
      aria-disabled={busy || undefined}
      aria-busy={busy || undefined}
    >
      <span className={busy ? 'si-submit-label is-hidden-label' : 'si-submit-label'}>{children}</span>
      {busy ? (
        <span className="button-spinner" role="status">
          <LoaderCircle size={20} strokeWidth={2} aria-hidden="true" />
          <span className="visually-hidden">Loading</span>
        </span>
      ) : null}
    </button>
  )
}

export function SignInPage({ onBack, onSignedIn }: SignInPageProps) {
  const account = useSignIn()
  const headingId = useId()
  const [pairStored, setPairStored] = useState<boolean | null>(null)
  const [statusError, setStatusError] = useState(false)
  const [loadCount, setLoadCount] = useState(0)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [passwordAgain, setPasswordAgain] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [blockedSeconds, block] = useBlock()

  useEffect(() => {
    const controller = new AbortController()
    readSignInStatus(controller.signal)
      .then((status) => {
        setPairStored(status.pair_stored)
        block(status.blocked_seconds)
        setStatusError(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatusError(true)
      })
    return () => controller.abort()
  }, [loadCount, block])

  const blocked = blockedSeconds > 0
  const choosing = pairStored === false

  function checkChosen(): FieldErrors {
    const errors: FieldErrors = {}
    if (!username.trim()) errors.username = 'Enter a username.'
    if (password.length < MIN_PASSWORD_LENGTH) {
      errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`
    }
    if (passwordAgain !== password) errors.passwordAgain = "The two passwords don't match."
    return errors
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || blocked) return
    setError(null)
    const errors = choosing ? checkChosen() : {}
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return
    setBusy(true)
    try {
      if (choosing) await choosePair(username, password, passwordAgain)
      else await signIn(username, password)
      onSignedIn()
    } catch (caught) {
      if (caught instanceof SignInBlocked) {
        block(caught.seconds)
      } else if (caught instanceof ApiError && caught.status === 409) {
        // The pair was chosen in another tab, or a sign-in found none. Ask again.
        setLoadCount((count) => count + 1)
        setError(caught.message)
      } else {
        setError(failureText(caught, choosing ? 'save your username and password' : 'sign in'))
      }
      setPassword('')
      setPasswordAgain('')
    } finally {
      setBusy(false)
    }
  }

  async function onSignOut() {
    setError(null)
    setBusy(true)
    try {
      await signOut()
    } catch {
      setError("Couldn't sign out. Check that Polaris is running and try again.")
    } finally {
      setBusy(false)
    }
  }

  let body
  if (account.status === 'signed-in') {
    body = (
      <div className="si-form">
        <p>You're signed in as {account.username}. Polaris uses your profile in every session.</p>
        <div>
          <button type="button" className="secondary" onClick={() => void onSignOut()} disabled={busy}>
            Sign out
          </button>
        </div>
      </div>
    )
  } else if (statusError) {
    body = (
      <AlertBanner
        action={
          <button type="button" className="secondary" onClick={() => setLoadCount((count) => count + 1)}>
            Try again
          </button>
        }
      >
        Couldn't reach Polaris. Check that it is running and try again.
      </AlertBanner>
    )
  } else if (pairStored === null) {
    body = <div className="skeleton si-skeleton" aria-label="Loading" role="status" />
  } else {
    body = (
      <form className="si-form" onSubmit={(event) => void onSubmit(event)} noValidate>
        {choosing ? (
          <div className="si-intro">
            <h2 className="st-heading">Choose a username and password</h2>
            <p>
              This is the first sign-in on this machine, so the pair you choose now is the only one.
              Polaris can't reset it if you forget it, so keep it somewhere safe.
            </p>
          </div>
        ) : null}
        <TextField
          label="Username"
          value={username}
          onChange={setUsername}
          autoComplete="username"
          error={fieldErrors.username}
        />
        <TextField
          label="Password"
          value={password}
          onChange={setPassword}
          autoComplete={choosing ? 'new-password' : 'current-password'}
          error={fieldErrors.password}
          help={choosing ? `At least ${MIN_PASSWORD_LENGTH} characters.` : undefined}
          password
        />
        {choosing ? (
          <TextField
            label="Password again"
            value={passwordAgain}
            onChange={setPasswordAgain}
            autoComplete="new-password"
            error={fieldErrors.passwordAgain}
            password
          />
        ) : null}
        {blocked ? <AlertBanner>{blockedText(blockedSeconds)}</AlertBanner> : null}
        {error ? <AlertBanner>{error}</AlertBanner> : null}
        <div>
          <SubmitButton busy={busy} disabled={blocked}>
            {choosing ? 'Save and sign in' : 'Sign in'}
          </SubmitButton>
        </div>
        {choosing ? null : (
          <p className="field-help">Polaris can't reset a forgotten username or password.</p>
        )}
      </form>
    )
  }

  return (
    <div className="st-page">
      <header className="top-bar">
        <div className="top-bar-start">
          <button type="button" className="ghost" onClick={onBack}>
            <ArrowLeft size={20} strokeWidth={2} aria-hidden="true" />
            Back to the conversation
          </button>
          <p className="top-bar-mark">Polaris</p>
        </div>
        <p className="top-bar-title" />
        <div className="top-bar-end" />
      </header>
      <main className="st-main">
        <section className="si-column" aria-labelledby={headingId}>
          <h1 id={headingId} className="st-title">
            Sign in
          </h1>
          <p className="si-lead">
            Signing in lets Polaris keep your profile: how you like to be taught, what you can
            already do, and where you struggle. Chat, quizzes, whiteboards, and animations work
            without it. This sign-in stays on this machine and is not your Claude login.
          </p>
          {body}
        </section>
      </main>
    </div>
  )
}
