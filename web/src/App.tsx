import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  getSession,
  leaveSession,
  listSessions,
  openSession,
  readProfile,
  sendTurn,
  startSession,
} from './api.ts'
import type { Session, SessionSummary } from './api.ts'

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}

function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [facts, setFacts] = useState<string[]>([])
  const [open, setOpen] = useState<Session | null>(null)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<{ learner: string; reply: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const sendAbort = useRef<AbortController | null>(null)
  const sending = useRef(false)

  async function refresh(signal?: AbortSignal) {
    const [nextSessions, nextFacts] = await Promise.all([
      listSessions(signal),
      readProfile(signal),
    ])
    if (signal?.aborted) return
    setSessions(nextSessions)
    setFacts(nextFacts)
  }

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        await refresh(controller.signal)
      } catch (caught) {
        if (controller.signal.aborted) return
        setError(errorText(caught))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  async function onStart() {
    setError(null)
    sendAbort.current?.abort()
    try {
      const session = await startSession()
      setOpen(session)
      setPending(null)
      setDraft('')
      await refresh()
    } catch (caught) {
      setError(errorText(caught))
    }
  }

  async function onOpen(sessionId: string) {
    setError(null)
    sendAbort.current?.abort()
    try {
      const session = await openSession(sessionId)
      setOpen(session)
      setPending(null)
      setDraft('')
      await refresh()
    } catch (caught) {
      setError(errorText(caught))
    }
  }

  async function onLeave() {
    if (!open) return
    setError(null)
    sendAbort.current?.abort()
    try {
      await leaveSession(open.id)
      setOpen(null)
      setPending(null)
      setDraft('')
      await refresh()
    } catch (caught) {
      setError(errorText(caught))
    }
  }

  async function onSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!open || sending.current) return
    const message = draft.trim()
    if (!message || pending) return
    sending.current = true
    setDraft('')
    setError(null)
    setPending({ learner: message, reply: '' })
    const controller = new AbortController()
    sendAbort.current = controller
    try {
      await sendTurn(
        open.id,
        message,
        (chunk) => {
          setPending((current) =>
            current ? { ...current, reply: current.reply + chunk } : current,
          )
        },
        controller.signal,
      )
      if (controller.signal.aborted) return
      const session = await getSession(open.id)
      if (controller.signal.aborted) return
      setOpen(session)
      setPending(null)
      await refresh()
    } catch (caught) {
      if (controller.signal.aborted) return
      setError(errorText(caught))
    } finally {
      sending.current = false
    }
  }

  return (
    <div className="app">
      <header className="top">
        <h1>Polaris</h1>
      </header>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="layout">
        <nav className="sessions" aria-label="Sessions">
          <div className="sessions-head">
            <h2>Sessions</h2>
            <button type="button" onClick={() => void onStart()}>
              New session
            </button>
          </div>
          {loading ? <p>Loading sessions.</p> : null}
          {!loading && sessions.length === 0 ? <p>No sessions yet.</p> : null}
          <ul>
            {sessions.map((session) => (
              <li key={session.id}>
                <button
                  type="button"
                  aria-current={open?.id === session.id ? 'page' : undefined}
                  onClick={() => void onOpen(session.id)}
                >
                  <span className="preview">{session.preview || 'New session'}</span>
                  {session.ended ? <span className="ended">Ended</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <main className="conversation">
          <section aria-label="Profile">
            <h2>Profile</h2>
            {facts.length === 0 ? (
              <p>Nothing stored yet.</p>
            ) : (
              <ul>
                {facts.map((fact, index) => (
                  <li key={`${fact}-${index}`}>{fact}</li>
                ))}
              </ul>
            )}
          </section>
          {open ? (
            <section aria-label="Conversation">
              <div className="conversation-head">
                <h2>Conversation</h2>
                <button type="button" onClick={() => void onLeave()}>
                  Leave session
                </button>
              </div>
              <div className="turns" aria-busy={pending !== null}>
                {open.turns.map((turn, index) => (
                  <article className="turn" key={`${turn.learner_message}-${index}`}>
                    <h3>You</h3>
                    <p className="learner">{turn.learner_message}</p>
                    <h3>Polaris</h3>
                    <p className="reply">{turn.reply}</p>
                  </article>
                ))}
                {pending ? (
                  <article className="turn">
                    <h3>You</h3>
                    <p className="learner">{pending.learner}</p>
                    <h3>Polaris</h3>
                    <p className="reply" aria-live="polite">
                      {pending.reply}
                    </p>
                  </article>
                ) : null}
              </div>
              <form onSubmit={(event) => void onSend(event)}>
                <label htmlFor="learner-message">Message</label>
                <textarea
                  id="learner-message"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  rows={3}
                />
                <button type="submit" disabled={draft.trim() === '' || pending !== null}>
                  Send
                </button>
              </form>
            </section>
          ) : (
            <p>Start a session or reopen one.</p>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
