import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  getSession,
  leaveSession,
  listSessions,
  openSession,
  sendTurn,
  startSession,
} from './api.ts'
import type { Artifact, Session, SessionSummary, Turn, WhiteboardArtifact } from './api.ts'
import { ChatShell } from './chat/ChatShell.tsx'
import type { ViewTurn } from './chat/Conversation.tsx'
import { pointingFromTurn, type PointedPart, type Pointing } from './whiteboard/pointing.ts'
import { SIMPLER_REQUEST, whiteboardPagePath } from './whiteboard/simpler.ts'
import { QuizPage } from './QuizPage.tsx'
import { WhiteboardPage } from './WhiteboardPage.tsx'

const DevWhiteboardRoute = import.meta.env.DEV
  ? lazy(() =>
      import('./WhiteboardDevPage.tsx').then((module) => ({
        default: module.WhiteboardDevPage,
      })),
    )
  : null

const DESKTOP_QUERY = '(min-width: 1024px)'
const TOAST_MS = 5000

type PendingTurn = {
  learner: string
  reply: string
  artifacts: Artifact[]
  status: 'streaming' | 'stopped' | 'done'
  after: number
  failed?: boolean
  pointing: Pointing | null
}

type KeptTurn = {
  id: string
  after: number
  learner: string
  reply: string
  artifacts: Artifact[]
  pointing: Pointing | null
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  return fallback
}

function quizPath(quizId: string): string {
  return `/quiz/${quizId}`
}

function pathQuizId(path: string): string | null {
  const match = path.match(/^\/quiz\/([^/]+)$/)
  return match ? decodeURIComponent(match[1]) : null
}

function whiteboardPath(sessionId: string, whiteboardId: string): string {
  return whiteboardPagePath(sessionId, whiteboardId)
}

function pathWhiteboard(path: string): { sessionId: string; whiteboardId: string } | null {
  const match = path.match(/^\/whiteboard\/([^/]+)\/([^/]+)$/)
  if (!match) return null
  return {
    sessionId: decodeURIComponent(match[1]),
    whiteboardId: decodeURIComponent(match[2]),
  }
}

function goTo(path: string) {
  history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function boardsIn(turns: Turn[]): WhiteboardArtifact[] {
  return turns.flatMap((turn) =>
    turn.artifacts.filter((artifact): artifact is WhiteboardArtifact => artifact.kind === 'whiteboard'),
  )
}

function savedView(turn: Turn, index: number, boards: WhiteboardArtifact[]): ViewTurn {
  return {
    key: `saved-${index}`,
    learner: turn.learner_message,
    reply: turn.reply,
    artifacts: turn.artifacts,
    streaming: false,
    failed: false,
    pointing: pointingFromTurn(turn.pointing, boards),
  }
}

function mergeTurns(saved: Turn[], kept: KeptTurn[], pending: PendingTurn | null): ViewTurn[] {
  const boards = boardsIn(saved)
  const extras: { id: string; after: number; view: ViewTurn }[] = kept.map((item) => ({
    id: item.id,
    after: item.after,
    view: {
      key: item.id,
      learner: item.learner,
      reply: item.reply,
      artifacts: item.artifacts,
      streaming: false,
      stopped: true,
      failed: false,
      pointing: item.pointing,
    },
  }))
  if (pending) {
    extras.push({
      id: 'pending',
      after: pending.after,
      view: {
        key: 'pending',
        learner: pending.learner,
        reply: pending.reply,
        artifacts: pending.artifacts,
        streaming: pending.status === 'streaming',
        stopped: pending.status === 'stopped',
        failed: Boolean(pending.failed),
        pointing: pending.pointing,
      },
    })
  }
  extras.sort((a, b) => a.after - b.after)
  const items: ViewTurn[] = []
  let index = 0
  for (const extra of extras) {
    while (index < extra.after && index < saved.length) {
      items.push(savedView(saved[index], index, boards))
      index += 1
    }
    items.push(extra.view)
  }
  while (index < saved.length) {
    items.push(savedView(saved[index], index, boards))
    index += 1
  }
  return items
}

function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [open, setOpen] = useState<Session | null>(null)
  const [draft, setDraft] = useState('')
  const [pointing, setPointing] = useState<Pointing | null>(null)
  const [pending, setPending] = useState<PendingTurn | null>(null)
  const [kept, setKept] = useState<KeptTurn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [sessionListOpen, setSessionListOpen] = useState(
    () => window.matchMedia(DESKTOP_QUERY).matches,
  )
  const [loading, setLoading] = useState(
    () => !(import.meta.env.DEV && window.location.pathname === '/dev/whiteboard'),
  )
  const sendAbort = useRef<AbortController | null>(null)
  const sending = useRef(false)
  const toastTimer = useRef<number | null>(null)

  const turns = useMemo(
    () => mergeTurns(open?.turns ?? [], kept, pending),
    [open, kept, pending],
  )

  useEffect(() => {
    function onPop() {
      setPath(window.location.pathname)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    const media = window.matchMedia(DESKTOP_QUERY)
    function sync() {
      setSessionListOpen(media.matches)
    }
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    return () => {
      if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    }
  }, [])

  async function refresh(signal?: AbortSignal) {
    const nextSessions = await listSessions(signal)
    if (signal?.aborted) return
    setSessions(nextSessions)
  }

  async function loadSessions() {
    setError(null)
    setLoading(true)
    try {
      await refresh()
    } catch (caught) {
      setError(
        errorText(
          caught,
          "Couldn't load your sessions. Check your connection and try again.",
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (import.meta.env.DEV && window.location.pathname === '/dev/whiteboard') return
    const controller = new AbortController()
    async function load() {
      try {
        await refresh(controller.signal)
      } catch (caught) {
        if (controller.signal.aborted) return
        setError(
          errorText(
            caught,
            "Couldn't load your sessions. Check your connection and try again.",
          ),
        )
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  function closeDrawerIfPhone() {
    if (!window.matchMedia(DESKTOP_QUERY).matches) setSessionListOpen(false)
  }

  function resetConversation() {
    sendAbort.current?.abort()
    setPending(null)
    setKept([])
    setDraft('')
    setPointing(null)
    setSendError(null)
  }

  async function onStart() {
    setError(null)
    resetConversation()
    try {
      const session = await startSession()
      setOpen(session)
      await refresh()
      closeDrawerIfPhone()
    } catch (caught) {
      setError(
        errorText(
          caught,
          "Couldn't start a session. Check your connection and try again.",
        ),
      )
    }
  }

  async function onOpen(sessionId: string) {
    setError(null)
    resetConversation()
    try {
      const session = await openSession(sessionId)
      setOpen(session)
      await refresh()
      closeDrawerIfPhone()
    } catch (caught) {
      setError(
        errorText(
          caught,
          "Couldn't open that session. Check your connection and try again.",
        ),
      )
    }
  }

  async function onLeave() {
    if (!open) return
    setError(null)
    resetConversation()
    try {
      await leaveSession(open.id)
      setOpen(null)
      await refresh()
    } catch (caught) {
      setError(
        errorText(
          caught,
          "Couldn't leave the session. Check your connection and try again.",
        ),
      )
    }
  }

  function showToast(message: string) {
    setToast(message)
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), TOAST_MS)
  }

  async function onCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      showToast('Copied')
    } catch {
      setSendError("Couldn't copy that reply. Select the text and copy it yourself.")
    }
  }

  function onStop() {
    sendAbort.current?.abort()
    sending.current = false
    setPending((current) =>
      current && current.status === 'streaming' ? { ...current, status: 'stopped' } : current,
    )
  }

  function askAbout(whiteboardId: string, parts: PointedPart[]) {
    if (parts.length === 0) return
    setPointing({ whiteboardId, parts })
  }

  function removePoint(elementId: string) {
    setPointing((current) => {
      if (!current) return null
      const parts = current.parts.filter((part) => part.id !== elementId)
      return parts.length === 0 ? null : { ...current, parts }
    })
  }

  async function sendMessage(
    message: string,
    attached: Pointing | null = pointing,
    simplifies: string | null = null,
  ) {
    if (!open || sending.current) return
    if (pending?.status === 'streaming') return
    sending.current = true
    setSendError(null)
    setDraft('')
    setPointing(null)
    const after =
      open.turns.length + kept.length + (pending?.status === 'stopped' ? 1 : 0)
    if (pending?.status === 'stopped') {
      const stopped = pending
      setKept((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          after: stopped.after,
          learner: stopped.learner,
          reply: stopped.reply,
          artifacts: stopped.artifacts,
          pointing: stopped.pointing,
        },
      ])
    }
    setPending({
      learner: message,
      reply: '',
      artifacts: [],
      status: 'streaming',
      after,
      pointing: attached,
    })
    const controller = new AbortController()
    sendAbort.current = controller
    let sawText = false
    try {
      await sendTurn(
        open.id,
        message,
        (chunk) => {
          sawText = true
          setPending((current) =>
            current ? { ...current, reply: current.reply + chunk } : current,
          )
        },
        (artifact) => {
          setPending((current) =>
            current
              ? { ...current, artifacts: [...current.artifacts, artifact] }
              : current,
          )
        },
        { signal: controller.signal, pointing: attached, simplifies },
      )
      if (controller.signal.aborted) return
      setPending((current) =>
        current && current.status === 'streaming' ? { ...current, status: 'done' } : current,
      )
      const session = await getSession(open.id)
      if (controller.signal.aborted) return
      setOpen(session)
      setPending(null)
      await refresh()
    } catch (caught) {
      if (controller.signal.aborted) return
      const fallback = "Couldn't send that message. Check your connection and try again."
      if (sawText) {
        setPending((current) =>
          current ? { ...current, status: 'stopped', failed: true } : current,
        )
      } else {
        setPending(null)
        setDraft(message)
        setPointing(attached)
        setSendError(errorText(caught, fallback))
      }
    } finally {
      sending.current = false
    }
  }

  async function onSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = draft.trim()
    if (!message) return
    await sendMessage(message)
  }

  async function askSimpler(whiteboardId: string) {
    if (pathWhiteboard(window.location.pathname)) goTo('/')
    await sendMessage(SIMPLER_REQUEST, null, whiteboardId)
  }

  async function onTryAgain(learnerMessage: string, again?: Pointing | null) {
    if (!open || sending.current) return
    await sendMessage(learnerMessage, again ?? null)
  }

  if (import.meta.env.DEV && DevWhiteboardRoute && path === '/dev/whiteboard') {
    return (
      <Suspense fallback={<p className="notice">Loading the dev whiteboard.</p>}>
        <DevWhiteboardRoute />
      </Suspense>
    )
  }

  const quizId = pathQuizId(path)
  const whiteboardRoute = pathWhiteboard(path)
  const covering = Boolean(quizId || whiteboardRoute)

  async function onBackFromQuiz() {
    goTo('/')
    if (!open) return
    try {
      const session = await getSession(open.id)
      setOpen(session)
      await refresh()
    } catch (caught) {
      setError(
        errorText(caught, "Couldn't refresh the session. Open it again from the list."),
      )
    }
  }

  const sessionTitle = open
    ? sessions.find((session) => session.id === open.id)?.preview || 'New session'
    : null

  return (
    <>
      {quizId ? <QuizPage quizId={quizId} onBack={() => void onBackFromQuiz()} /> : null}
      {whiteboardRoute ? (
        <WhiteboardPage
          key={`${whiteboardRoute.sessionId}/${whiteboardRoute.whiteboardId}`}
          sessionId={whiteboardRoute.sessionId}
          whiteboardId={whiteboardRoute.whiteboardId}
          onBack={() => void onBackFromQuiz()}
          onAsk={(parts) => {
            askAbout(whiteboardRoute.whiteboardId, parts)
            goTo('/')
          }}
          onSimpler={(id) => void askSimpler(id)}
          onOpenOriginal={(id) => goTo(whiteboardPath(whiteboardRoute.sessionId, id))}
          simplerBusy={pending?.status === 'streaming' || pending?.status === 'done'}
        />
      ) : null}
      <div
        className={covering ? 'is-hidden' : undefined}
        hidden={covering}
        aria-hidden={covering ? true : undefined}
      >
        <ChatShell
          sessions={sessions}
          openId={open?.id ?? null}
          sessionTitle={sessionTitle}
          loading={loading}
          error={error}
          onRetryLoad={() => void loadSessions()}
          sessionListOpen={sessionListOpen}
          onToggleSessions={() => setSessionListOpen((current) => !current)}
          onCloseSessions={() => setSessionListOpen(false)}
          onStart={() => void onStart()}
          onOpen={(sessionId) => void onOpen(sessionId)}
          onLeave={() => void onLeave()}
          turns={turns}
          draft={draft}
          sending={pending?.status === 'streaming' || pending?.status === 'done'}
          sendError={sendError}
          onDraftChange={(value) => {
            setDraft(value)
            if (sendError) setSendError(null)
          }}
          onSend={(event) => void onSend(event)}
          onStop={onStop}
          onCopy={(text) => void onCopy(text)}
          onTryAgain={(message, again) => void onTryAgain(message, again)}
          onOpenQuiz={(id) => goTo(quizPath(id))}
          onOpenWhiteboard={(id) => {
            if (!open) return
            goTo(whiteboardPath(open.id, id))
          }}
          onSimpler={(id) => void askSimpler(id)}
          pointing={pointing}
          onRemovePoint={removePoint}
          onAsk={askAbout}
          toast={toast}
          onCloseToast={() => setToast(null)}
        />
      </div>
    </>
  )
}

export default App
