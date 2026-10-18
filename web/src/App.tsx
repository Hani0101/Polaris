import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  ApiError,
  createWhiteboard,
  getSession,
  leaveSession,
  listSessions,
  listWhiteboards,
  deleteSession,
  renameSession,
  sessionLabel,
  openSession,
  sendTurn,
  startSession,
  warmSession,
} from './api.ts'
import type {
  Artifact,
  BoardPicture,
  Quiz,
  Session,
  SessionSummary,
  Turn,
  WhiteboardArtifact,
} from './api.ts'
import { animationPagePath, pathAnimation } from './animationPath.ts'
import type { AskedStep } from './animation/askedStep.ts'
import type { AskAboutStep } from './animation/ScenePlayer.tsx'
import { AnimationPage } from './AnimationPage.tsx'
import { watchRunningAnimations } from './chat/animationNotices.ts'
import { ChatShell } from './chat/ChatShell.tsx'
import type { ViewTurn } from './chat/Conversation.tsx'
import { createDraft } from './chat/draft.ts'
import type { PinnedTurn } from './chat/PinnedWhiteboard.tsx'
import { pointingFromTurn, type PointedPart, type Pointing } from './whiteboard/pointing.ts'
import { prefetchWhiteboard } from './whiteboard/LazyWhiteboard.tsx'
import { SIMPLER_REQUEST, whiteboardPagePath } from './whiteboard/simpler.ts'
import { QuizPage } from './QuizPage.tsx'
import { SettingsPage } from './SettingsPage.tsx'
import { SETTINGS_PATH, isSettingsPath } from './settingsPath.ts'
import { restoreSignIn, signOut, useSignIn } from './auth.ts'
import { SignInPage } from './SignInPage.tsx'
import { SIGN_IN_PATH, isSignInPath } from './signInPath.ts'
import { useSteadyHandlers } from './useSteady.ts'
import { WhiteboardPage } from './WhiteboardPage.tsx'

const DevWhiteboardRoute = import.meta.env.DEV
  ? lazy(() =>
      import('./WhiteboardDevPage.tsx').then((module) => ({
        default: module.WhiteboardDevPage,
      })),
    )
  : null

const DevLottieRoute = import.meta.env.DEV
  ? lazy(() =>
      import('./LottieDevPage.tsx').then((module) => ({
        default: module.LottieDevPage,
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
  animationStep: AskedStep | null
}

type KeptTurn = {
  id: string
  after: number
  learner: string
  reply: string
  artifacts: Artifact[]
  pointing: Pointing | null
  animationStep: AskedStep | null
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

function withAnimationStatus(artifacts: Artifact[], jobId: string, status: string): Artifact[] {
  return artifacts.map((artifact) =>
    artifact.kind === 'animation' && artifact.id === jobId
      ? { ...artifact, status }
      : artifact,
  )
}

function boardsIn(turns: Turn[]): WhiteboardArtifact[] {
  return turns.flatMap((turn) =>
    turn.artifacts.filter((artifact): artifact is WhiteboardArtifact => artifact.kind === 'whiteboard'),
  )
}

function withQuiz(artifacts: Artifact[], quiz: Quiz): Artifact[] {
  return artifacts.map((artifact) =>
    artifact.kind === 'quiz' && artifact.id === quiz.id ? quiz : artifact,
  )
}

function stepKey(jobId: string, stepId: string): string {
  return `${jobId}/${stepId}`
}

/** A saved turn's asked step, with the number and caption when this visit knows them. */
function savedStep(turn: Turn, known: ReadonlyMap<string, AskedStep>): AskedStep | null {
  const asked = turn.animation_step
  if (!asked) return null
  return (
    known.get(stepKey(asked.job_id, asked.step_id)) ?? {
      jobId: asked.job_id,
      stepId: asked.step_id,
    }
  )
}

function savedView(
  turn: Turn,
  index: number,
  boards: WhiteboardArtifact[],
  known: ReadonlyMap<string, AskedStep>,
): ViewTurn {
  return {
    key: `saved-${index}`,
    learner: turn.learner_message,
    reply: turn.reply,
    artifacts: turn.artifacts,
    streaming: false,
    failed: false,
    pointing: pointingFromTurn(turn.pointing, boards),
    animationStep: savedStep(turn, known),
  }
}

function savedViews(saved: Turn[], known: ReadonlyMap<string, AskedStep>): ViewTurn[] {
  const boards = boardsIn(saved)
  return saved.map((turn, index) => savedView(turn, index, boards, known))
}

/** A turn the server has not saved, and the saved turn it came after. */
type PlacedTurn = { after: number; view: ViewTurn }

function keptViews(kept: KeptTurn[]): PlacedTurn[] {
  return kept.map((item) => ({
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
      animationStep: item.animationStep,
    },
  }))
}

function pendingView(pending: PendingTurn): PlacedTurn {
  return {
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
      animationStep: pending.animationStep,
    },
  }
}

function mergeTurns(saved: ViewTurn[], extras: PlacedTurn[]): ViewTurn[] {
  const placed = [...extras].sort((a, b) => a.after - b.after)
  const items: ViewTurn[] = []
  let index = 0
  for (const extra of placed) {
    while (index < extra.after && index < saved.length) {
      items.push(saved[index])
      index += 1
    }
    items.push(extra.view)
  }
  while (index < saved.length) {
    items.push(saved[index])
    index += 1
  }
  return items
}

function App() {
  const [path, setPath] = useState(window.location.pathname)
  const account = useSignIn()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [open, setOpen] = useState<Session | null>(null)
  // Kept outside React state, so a typed key draws the composer and not the app.
  const [draft] = useState(() => createDraft())
  const [pointing, setPointing] = useState<Pointing | null>(null)
  // The latest picture of a board the learner drew on, for their next message.
  const [picture, setPicture] = useState<BoardPicture | null>(null)
  // The board pinned above the conversation. Every turn is about it (WB-19).
  const [pinnedId, setPinnedId] = useState<string | null>(null)
  // Every whiteboard in the open session, for the Whiteboard tab (WB-18).
  const [boards, setBoards] = useState<WhiteboardArtifact[]>([])
  const [creatingBoard, setCreatingBoard] = useState(false)
  const [askedStep, setAskedStep] = useState<AskedStep | null>(null)
  // Steps asked about in this visit, so a saved turn's chip can name them.
  const [knownSteps, setKnownSteps] = useState<ReadonlyMap<string, AskedStep>>(() => new Map())
  const [pending, setPending] = useState<PendingTurn | null>(null)
  const [kept, setKept] = useState<KeptTurn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [sessionListOpen, setSessionListOpen] = useState(
    () => window.matchMedia(DESKTOP_QUERY).matches,
  )
  const [toolsOpen, setToolsOpen] = useState(() => window.matchMedia(DESKTOP_QUERY).matches)
  const [loading, setLoading] = useState(
    () => !(import.meta.env.DEV && window.location.pathname.startsWith('/dev/')),
  )
  const sendAbort = useRef<AbortController | null>(null)
  const sending = useRef(false)
  const switching = useRef(false)
  const toastTimer = useRef<number | null>(null)
  // The session whose agent was started in this visit, once the learner began typing.
  const warmedFor = useRef<string | null>(null)

  const sendablePicture = picture && picture.whiteboard_id === pinnedId ? picture : null

  // Saved and stopped turns keep their view objects while a reply streams, so
  // only the pending turn is drawn again on each chunk.
  const saved = useMemo(() => savedViews(open?.turns ?? [], knownSteps), [open, knownSteps])
  const stopped = useMemo(() => keptViews(kept), [kept])
  const turns = useMemo(
    () => mergeTurns(saved, pending ? [...stopped, pendingView(pending)] : stopped),
    [saved, stopped, pending],
  )

  // The artifacts of every turn not streaming. A streaming chunk leaves this list as it
  // was, so the tools panel is not drawn again on each one.
  const settled = pending && pending.status !== 'streaming' ? pending : null
  const artifacts = useMemo(
    () =>
      mergeTurns(saved, settled ? [...stopped, pendingView(settled)] : stopped).flatMap(
        (turn) => turn.artifacts,
      ),
    [saved, stopped, settled],
  )

  // The reply now running, and the pinned board as it last arrived in that reply.
  const pinnedTurn = useMemo((): PinnedTurn | null => {
    if (!pending || !pinnedId) return null
    const sent = pending.artifacts.filter(
      (artifact): artifact is WhiteboardArtifact =>
        artifact.kind === 'whiteboard' && artifact.id === pinnedId,
    )
    return {
      key: `${pending.after}:${pending.learner}`,
      reply: pending.reply,
      phase: pending.status === 'streaming' ? 'streaming' : pending.status === 'done' ? 'done' : 'stopped',
      board: sent.length > 0 ? sent[sent.length - 1] : null,
    }
  }, [pending, pinnedId])

  const animationStatusRef = useRef<(jobId: string, status: string) => void>(() => {})
  animationStatusRef.current = (jobId, status) => {
    setOpen((current) =>
      current
        ? {
            ...current,
            turns: current.turns.map((turn) => ({
              ...turn,
              artifacts: withAnimationStatus(turn.artifacts, jobId, status),
            })),
          }
        : current,
    )
    setPending((current) =>
      current
        ? { ...current, artifacts: withAnimationStatus(current.artifacts, jobId, status) }
        : current,
    )
    setKept((current) =>
      current.map((item) => ({
        ...item,
        artifacts: withAnimationStatus(item.artifacts, jobId, status),
      })),
    )
  }

  useEffect(() => {
    watchRunningAnimations(artifacts, (jobId, status) => {
      animationStatusRef.current(jobId, status)
    })
  }, [artifacts])

  // A refresh cookie from an earlier visit signs the learner back in quietly.
  // Without one the app opens anonymous (AU-01).
  useEffect(() => {
    void restoreSignIn()
  }, [])

  useEffect(() => {
    function onPop() {
      setPath(window.location.pathname)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  // The board code is left out of the first load. It loads once the app is idle,
  // so the first board shown does not wait for it.
  useEffect(() => {
    if (typeof window.requestIdleCallback === 'function') {
      const idle = window.requestIdleCallback(prefetchWhiteboard, { timeout: 5000 })
      return () => window.cancelIdleCallback(idle)
    }
    const timer = window.setTimeout(prefetchWhiteboard, 2000)
    return () => window.clearTimeout(timer)
  }, [])

  useEffect(() => {
    const media = window.matchMedia(DESKTOP_QUERY)
    function sync() {
      setSessionListOpen(media.matches)
      setToolsOpen(media.matches)
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

  async function onRename(sessionId: string, name: string) {
    const saved = await renameSession(sessionId, name)
    setSessions((current) =>
      current.map((session) =>
        session.id === sessionId ? { ...session, name: saved.name } : session,
      ),
    )
  }

  async function onDelete(sessionId: string) {
    const deleted = await deleteSession(sessionId)
    setSessions((current) => current.filter((session) => session.id !== sessionId))
    if (!deleted.facts_saved) {
      showToast("Deleted. Polaris couldn't save what it learned from that session.")
    }
    if (open?.id === sessionId) {
      setOpen(null)
      await onStart()
    }
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
    if (import.meta.env.DEV && window.location.pathname.startsWith('/dev/')) return
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

  async function loadBoards(sessionId: string) {
    try {
      setBoards(await listWhiteboards(sessionId))
    } catch {
      // The tab keeps the boards it had; the next turn or reopen loads them again.
    }
  }

  function resetConversation() {
    warmedFor.current = null
    sendAbort.current?.abort()
    setPending(null)
    setKept([])
    draft.set('')
    setPointing(null)
    setPicture(null)
    setPinnedId(null)
    setBoards([])
    setAskedStep(null)
    setSendError(null)
  }

  // Typing starts the agent, so the first reply does not wait for it. Opening a
  // session to read it does not. A failure only loses the head start.
  function warmOnTyping(value: string) {
    if (!open || open.ended || !value.trim() || warmedFor.current === open.id) return
    warmedFor.current = open.id
    warmSession(open.id).catch(() => {})
  }

  async function onStart() {
    setError(null)
    resetConversation()
    try {
      const session = await startSession()
      setOpen(session)
      void loadBoards(session.id)
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

  // One start or open at a time, so a second click does not start a second session.
  async function oneAtATime(change: () => Promise<void>) {
    if (switching.current) return
    switching.current = true
    try {
      await change()
    } finally {
      switching.current = false
    }
  }

  async function onOpen(sessionId: string) {
    setError(null)
    resetConversation()
    try {
      const session = await openSession(sessionId)
      setOpen(session)
      void loadBoards(session.id)
      await refresh()
      closeDrawerIfPhone()
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        showToast('That session no longer exists.')
        await onStart()
        return
      }
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

  async function onSignOut() {
    setError(null)
    try {
      await signOut()
    } catch {
      setError("Couldn't sign out. Check your connection and try again.")
    }
  }

  async function onCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      showToast('Copied')
    } catch {
      setSendError("Couldn't copy that reply. Select the text and copy it yourself.")
    }
  }

  function onQuizChecked(quiz: Quiz) {
    setOpen((current) =>
      current
        ? {
            ...current,
            turns: current.turns.map((turn) => ({
              ...turn,
              artifacts: withQuiz(turn.artifacts, quiz),
            })),
          }
        : current,
    )
    setKept((current) =>
      current.map((item) => ({ ...item, artifacts: withQuiz(item.artifacts, quiz) })),
    )
    setPending((current) =>
      current ? { ...current, artifacts: withQuiz(current.artifacts, quiz) } : current,
    )
  }

  function onStop() {
    sendAbort.current?.abort()
    sending.current = false
    setPending((current) =>
      current && current.status === 'streaming' ? { ...current, status: 'stopped' } : current,
    )
  }

  // Opening a board pins it in place of the one pinned before (WB-19).
  function pinBoard(whiteboardId: string) {
    setPinnedId(whiteboardId)
    setPicture((current) => (current && current.whiteboard_id !== whiteboardId ? null : current))
    setPointing((current) => (current && current.whiteboardId !== whiteboardId ? null : current))
  }

  // Closing unpins it, so later turns are no longer about it (WB-19).
  function unpinBoard() {
    setPinnedId(null)
    setPicture(null)
  }

  async function newBoard() {
    if (!open || creatingBoard) return
    setCreatingBoard(true)
    try {
      const board = await createWhiteboard(open.id)
      setBoards((current) => [...current, board])
      pinBoard(board.id)
    } catch (caught) {
      setSendError(
        errorText(caught, "Couldn't make a whiteboard. Check your connection and try again."),
      )
    } finally {
      setCreatingBoard(false)
    }
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

  function askAboutStep(ask: AskAboutStep) {
    const step: AskedStep = {
      jobId: ask.jobId,
      stepId: ask.stepId,
      stepNumber: ask.stepNumber,
      caption: ask.caption,
    }
    setAskedStep(step)
    setKnownSteps((current) => new Map(current).set(stepKey(step.jobId, step.stepId), step))
  }

  async function sendMessage(
    message: string,
    attached: Pointing | null = pointing,
    simplifies: string | null = null,
    step: AskedStep | null = askedStep,
  ) {
    if (!open || sending.current) return
    if (pending?.status === 'streaming') return
    sending.current = true
    // A simpler redraw is asked from the description alone, so the picture waits.
    // Only a picture of the pinned board is sent (WB-19).
    const sentPicture = simplifies ? null : sendablePicture
    const sentPinned = pinnedId
    setSendError(null)
    draft.set('')
    setPointing(null)
    if (sentPicture) setPicture(null)
    setAskedStep(null)
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
          animationStep: stopped.animationStep,
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
      animationStep: step,
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
        {
          signal: controller.signal,
          pointing: attached,
          simplifies,
          picture: sentPicture,
          animationStep: step,
          pinnedWhiteboardId: sentPinned,
        },
      )
      if (controller.signal.aborted) return
      setPending((current) =>
        current && current.status === 'streaming' ? { ...current, status: 'done' } : current,
      )
      // The boards and the session list load while the session does. A list that
      // fails to load keeps the sessions it had; the next refresh loads them again.
      void loadBoards(open.id)
      const listed = refresh().catch(() => {})
      const session = await getSession(open.id)
      if (controller.signal.aborted) return
      setOpen(session)
      setPending(null)
      await listed
    } catch (caught) {
      if (controller.signal.aborted) return
      const fallback = "Couldn't send that message. Check your connection and try again."
      if (sawText) {
        setPending((current) =>
          current ? { ...current, status: 'stopped', failed: true } : current,
        )
      } else {
        setPending(null)
        draft.set(message)
        setPointing(attached)
        if (sentPicture) setPicture(sentPicture)
        setAskedStep(step)
        setSendError(errorText(caught, fallback))
      }
    } finally {
      sending.current = false
    }
  }

  async function onSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = draft.get().trim()
    if (!message) return
    await sendMessage(message)
  }

  async function askSimpler(whiteboardId: string) {
    if (pathWhiteboard(window.location.pathname)) goTo('/')
    await sendMessage(SIMPLER_REQUEST, null, whiteboardId, null)
  }

  async function onTryAgain(
    learnerMessage: string,
    again?: Pointing | null,
    againStep?: AskedStep | null,
  ) {
    if (!open || sending.current) return
    await sendMessage(learnerMessage, again ?? null, null, againStep ?? null)
  }

  // The shell's handlers keep their identity, so the session list, top bar, tools
  // panel, and pinned board are not drawn again on every streamed chunk.
  const shell = useSteadyHandlers({
    onRetryLoad: () => void loadSessions(),
    onToggleSessions: () => setSessionListOpen((current) => !current),
    onCloseSessions: () => setSessionListOpen(false),
    onStart: () => void oneAtATime(onStart),
    onOpen: (sessionId: string) => void oneAtATime(() => onOpen(sessionId)),
    onRename,
    onDelete,
    onOpenSettings: () => {
      goTo(SETTINGS_PATH)
      if (!window.matchMedia(DESKTOP_QUERY).matches) setSessionListOpen(false)
    },
    onLeave: () => void onLeave(),
    onSignIn: () => goTo(SIGN_IN_PATH),
    onSignOut: () => void onSignOut(),
    onDraftChange: (value: string) => {
      if (sendError) setSendError(null)
      warmOnTyping(value)
    },
    onSend: (event: FormEvent<HTMLFormElement>) => void onSend(event),
    onStop,
    onCopy: (text: string) => void onCopy(text),
    onTryAgain: (message: string, again?: Pointing | null, againStep?: AskedStep | null) =>
      void onTryAgain(message, again, againStep),
    onOpenQuiz: (id: string) => goTo(quizPath(id)),
    onOpenWhiteboard: pinBoard,
    onOpenAnimation: (sessionId: string, jobId: string) => {
      goTo(animationPagePath(sessionId, jobId))
    },
    onSimpler: (id: string) => void askSimpler(id),
    onRemovePoint: removePoint,
    onRemovePicture: () => setPicture(null),
    onAsk: askAbout,
    onAskAboutStep: askAboutStep,
    onRemoveAnimationStep: () => setAskedStep(null),
    onCloseToast: () => setToast(null),
    onToggleTools: () => setToolsOpen((current) => !current),
    onCloseTools: () => setToolsOpen(false),
    onQuizChecked,
    onNewWhiteboard: () => void newBoard(),
    onClosePinned: unpinBoard,
    onPicture: (next: BoardPicture) => {
      if (next.whiteboard_id === pinnedId) setPicture(next)
    },
  })

  if (import.meta.env.DEV && DevWhiteboardRoute && path === '/dev/whiteboard') {
    return (
      <Suspense fallback={<p className="notice">Loading the dev whiteboard.</p>}>
        <DevWhiteboardRoute />
      </Suspense>
    )
  }

  if (import.meta.env.DEV && DevLottieRoute && path === '/dev/lottie') {
    return (
      <Suspense fallback={<p className="notice">Loading the dev Lottie player.</p>}>
        <DevLottieRoute />
      </Suspense>
    )
  }

  const quizId = pathQuizId(path)
  const whiteboardRoute = pathWhiteboard(path)
  const animationRoute = pathAnimation(path)
  const settingsRoute = isSettingsPath(path)
  const signInRoute = isSignInPath(path)
  const covering = Boolean(
    quizId || whiteboardRoute || animationRoute || settingsRoute || signInRoute,
  )

  async function onBackFromCover() {
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
    ? sessionLabel(sessions.find((session) => session.id === open.id))
    : null

  return (
    <>
      {settingsRoute ? <SettingsPage onBack={() => void onBackFromCover()} /> : null}
      {signInRoute ? (
        <SignInPage
          onBack={() => void onBackFromCover()}
          onSignedIn={() => void onBackFromCover()}
        />
      ) : null}
      {quizId ? <QuizPage quizId={quizId} onBack={() => void onBackFromCover()} /> : null}
      {whiteboardRoute ? (
        <WhiteboardPage
          key={`${whiteboardRoute.sessionId}/${whiteboardRoute.whiteboardId}`}
          sessionId={whiteboardRoute.sessionId}
          whiteboardId={whiteboardRoute.whiteboardId}
          onBack={() => void onBackFromCover()}
          onAsk={(parts) => {
            askAbout(whiteboardRoute.whiteboardId, parts)
            goTo('/')
          }}
          onSimpler={(id) => void askSimpler(id)}
          onPicture={(next) => {
            if (open?.id === whiteboardRoute.sessionId) setPicture(next)
          }}
          onOpenOriginal={(id) => goTo(whiteboardPath(whiteboardRoute.sessionId, id))}
          simplerBusy={pending?.status === 'streaming' || pending?.status === 'done'}
        />
      ) : null}
      {animationRoute ? (
        <AnimationPage
          key={`${animationRoute.sessionId}/${animationRoute.jobId}`}
          sessionId={animationRoute.sessionId}
          jobId={animationRoute.jobId}
          onBack={() => void onBackFromCover()}
          onAskAboutStep={
            open?.id === animationRoute.sessionId
              ? (ask) => {
                  askAboutStep(ask)
                  goTo('/')
                }
              : undefined
          }
        />
      ) : null}
      <div
        className={covering ? 'is-hidden' : undefined}
        hidden={covering}
        aria-hidden={covering ? true : undefined}
      >
        <ChatShell
          {...shell}
          sessions={sessions}
          openId={open?.id ?? null}
          sessionTitle={sessionTitle}
          loading={loading}
          error={error}
          sessionListOpen={sessionListOpen}
          account={account}
          turns={turns}
          draft={draft}
          sending={pending?.status === 'streaming' || pending?.status === 'done'}
          sendError={sendError}
          pointing={pointing}
          pictureAttached={sendablePicture !== null}
          animationStep={askedStep}
          toast={toast}
          artifacts={artifacts}
          toolsOpen={toolsOpen}
          whiteboards={boards}
          creatingWhiteboard={creatingBoard}
          pinnedWhiteboardId={pinnedId}
          pinnedTurn={pinnedTurn}
        />
      </div>
    </>
  )
}

export default App
