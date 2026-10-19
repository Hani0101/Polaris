import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent, ReactNode, Ref, RefObject } from 'react'
import { Globe, Plus } from 'lucide-react'
import type { AnimationArtifact, Artifact, Deck, Quiz, WhiteboardArtifact } from '../api.ts'
import { askedStepLabel } from '../animation/askedStep.ts'
import type { AskedStep } from '../animation/askedStep.ts'
import { revealWhiteboard, visibleReply } from '../whiteboard/reveal.ts'
import type { RevealPhase } from '../whiteboard/reveal.ts'
import type { PointedPart, Pointing } from '../whiteboard/pointing.ts'
import { whiteboardPagePath } from '../whiteboard/simpler.ts'
import { Whiteboard, WhiteboardPlaceholder } from '../whiteboard/LazyWhiteboard.tsx'
import { useSteady } from '../useSteady.ts'
import { AnimationCard } from './AnimationCard.tsx'
import { useDraftText } from './draft.ts'
import type { Draft } from './draft.ts'
import { ReplyText } from './ReplyText.tsx'
import {
  AlertBanner,
  AlertIcon,
  CopyIcon,
  EmptyState,
  IconButton,
  PolarisStar,
  RetryIcon,
  SendIcon,
  StopIcon,
  ThinkingIndicator,
} from './ui.tsx'

export type ViewTurn = {
  key: string
  learner: string
  reply: string
  artifacts: Artifact[]
  streaming: boolean
  stopped?: boolean
  failed: boolean
  pointing?: Pointing | null
  animationStep?: AskedStep | null
}

type ConversationProps = {
  turns: ViewTurn[]
  /** The message being typed. Only the composer reads it, so a key draws the composer alone. */
  draft: Draft
  sending: boolean
  sendError: string | null
  sessionOpen: boolean
  onDraftChange: (value: string) => void
  onSend: (event: FormEvent<HTMLFormElement>) => void
  onStop: () => void
  onCopy: (text: string) => void
  onTryAgain: (
    learnerMessage: string,
    pointing?: Pointing | null,
    animationStep?: AskedStep | null,
  ) => void
  onOpenQuiz: (quizId: string) => void
  onOpenDeck?: (deckId: string) => void
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation?: (sessionId: string, jobId: string) => void
  onSimpler?: (whiteboardId: string) => void
  sessionId?: string | null
  onStart: () => void
  pointing?: Pointing | null
  onRemovePoint?: (elementId: string) => void
  // A picture of the learner's drawing goes with the next message.
  pictureAttached?: boolean
  onRemovePicture?: () => void
  /** Web mode: the next message lets Polaris search and read the web (CH-23). */
  webMode?: boolean
  onToggleWeb?: () => void
  /** The animation step the next turn asks about, shown as a chip (AN-17). */
  animationStep?: AskedStep | null
  onRemoveAnimationStep?: () => void
  onAsk?: (whiteboardId: string, parts: PointedPart[]) => void
  /** Phone only: opens the tools bottom sheet from the + button in the chat input. */
  onOpenTools?: () => void
  toolsButtonRef?: Ref<HTMLButtonElement>
  /** The whiteboard pinned above the turns, with the composer below (WB-19). */
  pinned?: ReactNode
  /** The pinned board shows above, so a turn does not draw it again. */
  pinnedWhiteboardId?: string | null
}

const PHONE_QUERY = '(max-width: 639px)'

// Where the browser sizes the message box to its text, no script measures it.
const BOX_SIZES_ITSELF =
  typeof CSS !== 'undefined' &&
  typeof CSS.supports === 'function' &&
  CSS.supports('field-sizing', 'content')

const noHandler = () => {}

// How close to the bottom the learner must be for the view to follow a reply.
const NEAR_BOTTOM_PX = 64

// The scrolling turns, so a board can tell how far it is from the screen.
const ScrollRoot = createContext<RefObject<HTMLElement | null> | null>(null)

/**
 * Whether the element is on screen or within a screen of it. Hidden behind another page, it
 * is not. Without IntersectionObserver it always is.
 */
function useNearScreen(target: RefObject<HTMLElement | null>): boolean {
  const root = useContext(ScrollRoot)
  const [near, setNear] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const node = target.current
    if (!node || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        const latest = entries.at(-1)
        if (latest) setNear(latest.isIntersecting)
      },
      { root: root?.current ?? null, rootMargin: '100% 0px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [target, root])
  return near
}

export function Conversation({
  turns,
  draft,
  sending,
  sendError,
  sessionOpen,
  onDraftChange,
  onSend,
  onStop,
  onCopy,
  onTryAgain,
  onOpenQuiz,
  onOpenDeck,
  onOpenWhiteboard,
  onOpenAnimation,
  onSimpler,
  sessionId = null,
  onStart,
  pointing = null,
  onRemovePoint,
  pictureAttached = false,
  onRemovePicture,
  webMode = false,
  onToggleWeb,
  animationStep = null,
  onRemoveAnimationStep,
  onAsk,
  onOpenTools,
  toolsButtonRef,
  pinned = null,
  pinnedWhiteboardId = null,
}: ConversationProps) {
  const scroller = useRef<HTMLDivElement>(null)
  const copy = useSteady(onCopy)
  const tryAgain = useSteady(onTryAgain)
  const openQuiz = useSteady(onOpenQuiz)
  const openDeck = useSteady(onOpenDeck ?? noHandler)
  const openWhiteboard = useSteady(onOpenWhiteboard)
  const openAnimation = useSteady(onOpenAnimation ?? noHandler)
  const simpler = useSteady(onSimpler ?? noHandler)
  const ask = useSteady(onAsk ?? noHandler)
  const draftChange = useSteady(onDraftChange)
  const send = useSteady(onSend)
  const stop = useSteady(onStop)
  const removePoint = useSteady(onRemovePoint ?? noHandler)
  const removePicture = useSteady(onRemovePicture ?? noHandler)
  const toggleWeb = useSteady(onToggleWeb ?? noHandler)
  const removeAnimationStep = useSteady(onRemoveAnimationStep ?? noHandler)
  const openTools = useSteady(onOpenTools ?? noHandler)

  // The view follows a reply only while the learner is at the bottom, so reading an
  // earlier turn is not pulled down. Sending or opening a session goes back down.
  const following = useRef(true)

  useEffect(() => {
    const node = scroller.current
    if (!node) return
    const onScroll = () => {
      following.current = node.scrollHeight - node.scrollTop - node.clientHeight <= NEAR_BOTTOM_PX
    }
    node.addEventListener('scroll', onScroll, { passive: true })
    return () => node.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    following.current = true
  }, [sessionId])

  useEffect(() => {
    if (sending) following.current = true
  }, [sending])

  useEffect(() => {
    const node = scroller.current
    if (!node || !following.current) return
    node.scrollTop = node.scrollHeight
  }, [turns, sending, sessionId])

  const empty = sessionOpen && turns.length === 0

  return (
    <section className="conversation" aria-label="Conversation">
      {pinned}
      <div className="conversation-scroll" ref={scroller} aria-busy={sending || undefined}>
        <div className="conversation-inner">
          {!sessionOpen ? (
            <div className="conversation-empty">
              <EmptyState
                title="No session open"
                body="Start a session or pick one from the list."
                action={
                  <button type="button" onClick={onStart}>
                    Start a session
                  </button>
                }
              />
            </div>
          ) : null}
          {empty ? (
            <p className="conversation-hint">Ask Polaris to start this session.</p>
          ) : null}
          <ScrollRoot.Provider value={scroller}>
            {turns.map((turn) => (
              <TurnBlock
                key={turn.key}
                turn={turn}
                onCopy={copy}
                onTryAgain={tryAgain}
                onOpenQuiz={openQuiz}
                onOpenDeck={openDeck}
                onOpenWhiteboard={openWhiteboard}
                onOpenAnimation={onOpenAnimation ? openAnimation : undefined}
                onSimpler={onSimpler ? simpler : undefined}
                sending={sending}
                sessionId={sessionId}
                onAsk={onAsk ? ask : undefined}
                pinnedWhiteboardId={pinnedWhiteboardId}
              />
            ))}
          </ScrollRoot.Provider>
        </div>
      </div>
      {sessionOpen ? (
        <Composer
          draft={draft}
          sending={sending}
          sendError={sendError}
          onDraftChange={draftChange}
          onSend={send}
          onStop={stop}
          pointing={pointing}
          onRemovePoint={onRemovePoint ? removePoint : undefined}
          pictureAttached={pictureAttached}
          onRemovePicture={onRemovePicture ? removePicture : undefined}
          webMode={webMode}
          onToggleWeb={onToggleWeb ? toggleWeb : undefined}
          animationStep={animationStep}
          onRemoveAnimationStep={onRemoveAnimationStep ? removeAnimationStep : undefined}
          onOpenTools={onOpenTools ? openTools : undefined}
          toolsButtonRef={toolsButtonRef}
        />
      ) : null}
    </section>
  )
}

/**
 * The message box and what goes with the next message. It alone reads the draft, so a
 * typed key draws it and nothing else.
 */
const Composer = memo(function Composer({
  draft,
  sending,
  sendError,
  onDraftChange,
  onSend,
  onStop,
  pointing,
  onRemovePoint,
  pictureAttached,
  onRemovePicture,
  webMode,
  onToggleWeb,
  animationStep,
  onRemoveAnimationStep,
  onOpenTools,
  toolsButtonRef,
}: {
  draft: Draft
  sending: boolean
  sendError: string | null
  onDraftChange: (value: string) => void
  onSend: (event: FormEvent<HTMLFormElement>) => void
  onStop: () => void
  pointing: Pointing | null
  onRemovePoint?: (elementId: string) => void
  pictureAttached: boolean
  onRemovePicture?: () => void
  webMode: boolean
  onToggleWeb?: () => void
  animationStep: AskedStep | null
  onRemoveAnimationStep?: () => void
  onOpenTools?: () => void
  toolsButtonRef?: Ref<HTMLButtonElement>
}) {
  const text = useDraftText(draft)
  const textarea = useRef<HTMLTextAreaElement>(null)

  // A browser without CSS field-sizing gets the box sized here. Reading scrollHeight
  // makes it lay out the page at once, so the CSS way is used where it exists.
  useEffect(() => {
    const node = textarea.current
    if (!node || BOX_SIZES_ITSELF) return
    node.style.height = 'auto'
    const max = 1.5 * 16 * 6
    node.style.height = `${Math.min(node.scrollHeight, max)}px`
  }, [text])

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) return
    if (window.matchMedia(PHONE_QUERY).matches) return
    event.preventDefault()
    event.currentTarget.form?.requestSubmit()
  }

  const canSend = text.trim() !== '' && !sending

  return (
    <form className="chat-input-bar" onSubmit={onSend}>
      {pointing && pointing.parts.length > 0 ? (
        <PointChips parts={pointing.parts} onRemove={onRemovePoint} />
      ) : null}
      {pictureAttached ? <PictureChip onRemove={onRemovePicture} /> : null}
      {webMode ? <WebChip onRemove={onToggleWeb} /> : null}
      {animationStep ? <StepChip step={animationStep} onRemove={onRemoveAnimationStep} /> : null}
      <div className={sendError ? 'chat-input is-error' : 'chat-input'}>
        {onOpenTools ? (
          <button
            ref={toolsButtonRef}
            type="button"
            className="icon-btn icon-btn--ghost icon-btn--md"
            aria-label="Open tools"
            aria-haspopup="dialog"
            onClick={onOpenTools}
          >
            <Plus size={20} strokeWidth={2} aria-hidden="true" />
          </button>
        ) : null}
        {onToggleWeb ? (
          <button
            type="button"
            className={
              webMode
                ? 'icon-btn icon-btn--ghost icon-btn--md web-toggle is-on'
                : 'icon-btn icon-btn--ghost icon-btn--md web-toggle'
            }
            aria-label="Web mode"
            aria-pressed={webMode}
            onClick={onToggleWeb}
          >
            <Globe size={20} strokeWidth={2} aria-hidden="true" />
          </button>
        ) : null}
        <label className="visually-hidden" htmlFor="learner-message">
          Message to Polaris
        </label>
        <textarea
          id="learner-message"
          ref={textarea}
          value={text}
          rows={1}
          placeholder="Ask about a topic"
          onChange={(event) => {
            draft.set(event.target.value)
            onDraftChange(event.target.value)
          }}
          onKeyDown={onKeyDown}
        />
        {sending ? (
          <IconButton label="Stop" variant="primary" onClick={onStop}>
            <StopIcon />
          </IconButton>
        ) : (
          <IconButton label="Send" variant="primary" type="submit" disabled={!canSend}>
            <SendIcon />
          </IconButton>
        )}
      </div>
      {sendError ? (
        <p className="chat-input-error">
          <AlertIcon />
          {sendError}
        </p>
      ) : null}
    </form>
  )
})

function revealPhase(turn: ViewTurn): RevealPhase {
  if (turn.streaming) return 'streaming'
  if (turn.stopped) return 'stopped'
  return 'done'
}

function PointChips({
  parts,
  onRemove,
}: {
  parts: PointedPart[]
  onRemove?: (elementId: string) => void
}) {
  return (
    <ul className="point-chips" aria-label="Pointed at">
      {parts.map((part) => (
        <li key={part.id} className="point-chip">
          <span>{part.label}</span>
          {onRemove ? (
            <button
              type="button"
              className="ghost"
              aria-label={`Remove ${part.label}`}
              onClick={() => onRemove(part.id)}
            >
              <span aria-hidden="true">×</span>
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

const PICTURE_LABEL = 'Picture of your drawing'

function PictureChip({ onRemove }: { onRemove?: () => void }) {
  return (
    <ul className="point-chips" aria-label="Sent with your message">
      <li className="point-chip">
        <span>{PICTURE_LABEL}</span>
        {onRemove ? (
          <button
            type="button"
            className="ghost"
            aria-label={`Remove ${PICTURE_LABEL.toLowerCase()}`}
            onClick={onRemove}
          >
            <span aria-hidden="true">×</span>
          </button>
        ) : null}
      </li>
    </ul>
  )
}

/** Says in text that web mode is on, since the toggle is an icon (CH-28). */
function WebChip({ onRemove }: { onRemove?: () => void }) {
  return (
    <ul className="point-chips" aria-label="Web mode">
      <li className="point-chip">
        <span>Web mode on: Polaris can search the web</span>
        {onRemove ? (
          <button type="button" className="ghost" aria-label="Turn off web mode" onClick={onRemove}>
            <span aria-hidden="true">×</span>
          </button>
        ) : null}
      </li>
    </ul>
  )
}

function StepChip({ step, onRemove }: { step: AskedStep; onRemove?: () => void }) {
  const label = askedStepLabel(step)
  return (
    <ul className="point-chips" aria-label="Animation step">
      <li className="point-chip step-chip">
        <span>{label}</span>
        {onRemove ? (
          <button
            type="button"
            className="ghost"
            aria-label={
              step.stepNumber === undefined ? 'Remove the step' : `Remove step ${step.stepNumber}`
            }
            onClick={onRemove}
          >
            <span aria-hidden="true">×</span>
          </button>
        ) : null}
      </li>
    </ul>
  )
}

const TurnBlock = memo(function TurnBlock({
  turn,
  onCopy,
  onTryAgain,
  onOpenQuiz,
  onOpenDeck,
  onOpenWhiteboard,
  onOpenAnimation,
  onSimpler,
  sending,
  sessionId,
  onAsk,
  pinnedWhiteboardId,
}: {
  turn: ViewTurn
  onCopy: (text: string) => void
  onTryAgain: (
    learnerMessage: string,
    pointing?: Pointing | null,
    animationStep?: AskedStep | null,
  ) => void
  onOpenQuiz: (quizId: string) => void
  onOpenDeck: (deckId: string) => void
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation?: (sessionId: string, jobId: string) => void
  onSimpler?: (whiteboardId: string) => void
  sending: boolean
  sessionId: string | null
  onAsk?: (whiteboardId: string, parts: PointedPart[]) => void
  pinnedWhiteboardId: string | null
}) {
  const quizzes = turn.artifacts.filter((artifact): artifact is Quiz => artifact.kind === 'quiz')
  const decks = turn.artifacts.filter((artifact): artifact is Deck => artifact.kind === 'deck')
  const animations = turn.artifacts.filter(
    (artifact): artifact is AnimationArtifact => artifact.kind === 'animation',
  )
  const phase = revealPhase(turn)
  const storedBoards = turn.artifacts.filter(
    (artifact): artifact is WhiteboardArtifact => artifact.kind === 'whiteboard',
  )
  const markers = storedBoards.flatMap((whiteboard) =>
    whiteboard.steps.map((step) => step.reply_part),
  )
  const reply = visibleReply(turn.reply, turn.streaming, markers)
  // The same board object while nothing changes, so the whiteboard is not redrawn.
  const whiteboards = useMemo(
    () =>
      turn.artifacts.flatMap((artifact) => {
        if (artifact.kind !== 'whiteboard' || artifact.id === pinnedWhiteboardId) return []
        const revealed = revealWhiteboard(artifact, turn.reply, phase)
        return revealed ? [revealed] : []
      }),
    [turn.artifacts, turn.reply, phase, pinnedWhiteboardId],
  )
  const thinking = turn.streaming && reply === '' && whiteboards.length === 0 && !turn.failed
  const finished = !turn.streaming && !turn.failed && turn.reply !== ''
  const visible =
    reply !== '' ||
    quizzes.length > 0 ||
    decks.length > 0 ||
    whiteboards.length > 0 ||
    animations.length > 0

  return (
    <article className="turn">
      <div className="chat-msg chat-msg--learner">
        {turn.pointing && turn.pointing.parts.length > 0 ? (
          <PointChips parts={turn.pointing.parts} />
        ) : null}
        {turn.animationStep ? <StepChip step={turn.animationStep} /> : null}
        <p>{turn.learner}</p>
      </div>
      {thinking ? <ThinkingIndicator status="Thinking" /> : null}
      {turn.failed ? (
        <div className="chat-msg chat-msg--tutor">
          <AlertBanner
            action={
              <button type="button" className="secondary" onClick={() => onTryAgain(turn.learner, turn.pointing, turn.animationStep)}>
                Try again
              </button>
            }
          >
            Couldn&apos;t finish that reply. Try again, or ask in a new way.
          </AlertBanner>
        </div>
      ) : null}
      {!thinking && !turn.failed && visible ? (
        <div className="chat-msg chat-msg--tutor">
          <div className="tutor-name">
            <PolarisStar />
            <p>Polaris</p>
          </div>
          {reply !== '' ? <ReplyText text={reply} live={turn.streaming} /> : null}
          {animations.map((job) => (
            <AnimationCard key={job.id} job={job} onOpen={onOpenAnimation} />
          ))}
          {quizzes.map((quiz) => (
            <div className="quiz-chip" key={quiz.id}>
              <div>
                <p className="quiz-chip-title">{quiz.title}</p>
                {quiz.score ? (
                  <p className="quiz-chip-score">
                    {quiz.score.earned} of {quiz.score.total} right
                  </p>
                ) : null}
              </div>
              <button type="button" className="secondary" onClick={() => onOpenQuiz(quiz.id)}>
                {quiz.score ? 'Review quiz' : 'Open quiz'}
              </button>
            </div>
          ))}
          {decks.map((deck) => (
            <div className="quiz-chip" key={deck.id}>
              <div>
                <p className="quiz-chip-title">{deck.title}</p>
                <p className="quiz-chip-score">
                  {deck.cards.length === 1 ? '1 flashcard' : `${deck.cards.length} flashcards`}
                </p>
              </div>
              <button type="button" className="secondary" onClick={() => onOpenDeck(deck.id)}>
                Open flashcards
              </button>
            </div>
          ))}
          {whiteboards.map((whiteboard) => (
            <TurnWhiteboard
              key={whiteboard.id}
              whiteboard={whiteboard}
              sending={sending}
              sessionId={sessionId}
              onOpenWhiteboard={onOpenWhiteboard}
              onSimpler={onSimpler}
              onAsk={onAsk}
            />
          ))}
          {finished ? (
            <div className="tutor-actions">
              <IconButton label="Copy" size="sm" onClick={() => onCopy(reply)}>
                <CopyIcon />
              </IconButton>
              <IconButton
                label="Try again"
                size="sm"
                onClick={() => onTryAgain(turn.learner, turn.pointing, turn.animationStep)}
              >
                <RetryIcon />
              </IconButton>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  )
})

/** A board in a turn, with its actions. It is drawn again only when the board changes. */
const TurnWhiteboard = memo(function TurnWhiteboard({
  whiteboard,
  sending,
  sessionId,
  onOpenWhiteboard,
  onSimpler,
  onAsk,
}: {
  whiteboard: WhiteboardArtifact
  sending: boolean
  sessionId: string | null
  onOpenWhiteboard: (whiteboardId: string) => void
  onSimpler?: (whiteboardId: string) => void
  onAsk?: (whiteboardId: string, parts: PointedPart[]) => void
}) {
  const ask = useCallback(
    (parts: PointedPart[]) => onAsk?.(whiteboard.id, parts),
    [onAsk, whiteboard.id],
  )
  // A tldraw editor draws every frame while mounted, so a board far off screen has none.
  const frame = useRef<HTMLDivElement>(null)
  const near = useNearScreen(frame)
  return (
    <div className="turn-whiteboard">
      <div className="turn-whiteboard-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => onOpenWhiteboard(whiteboard.id)}
        >
          Open whiteboard
        </button>
        <button
          type="button"
          className="secondary"
          disabled={sending || !onSimpler}
          onClick={() => onSimpler?.(whiteboard.id)}
        >
          Simpler
        </button>
        {sessionId && whiteboard.simplifies ? (
          <a
            className="whiteboard-original"
            href={whiteboardPagePath(sessionId, whiteboard.simplifies)}
            onClick={(event) => {
              const originalId = whiteboard.simplifies
              if (!originalId) return
              event.preventDefault()
              onOpenWhiteboard(originalId)
            }}
          >
            Original whiteboard
          </a>
        ) : null}
      </div>
      <div className="turn-whiteboard-board" ref={frame}>
        {near ? (
          <Whiteboard whiteboard={whiteboard} onAsk={onAsk ? ask : undefined} />
        ) : (
          <WhiteboardPlaceholder whiteboard={whiteboard} />
        )}
      </div>
    </div>
  )
})
