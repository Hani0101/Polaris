import { useEffect, useRef } from 'react'
import type { FormEvent, KeyboardEvent, ReactNode, Ref } from 'react'
import { Plus } from 'lucide-react'
import type { AnimationArtifact, Artifact, Quiz, WhiteboardArtifact } from '../api.ts'
import { askedStepLabel } from '../animation/askedStep.ts'
import type { AskedStep } from '../animation/askedStep.ts'
import { revealWhiteboard, visibleReply } from '../whiteboard/reveal.ts'
import type { RevealPhase } from '../whiteboard/reveal.ts'
import type { PointedPart, Pointing } from '../whiteboard/pointing.ts'
import { whiteboardPagePath } from '../whiteboard/simpler.ts'
import { Whiteboard } from '../whiteboard/Whiteboard.tsx'
import { AnimationCard } from './AnimationCard.tsx'
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
  draft: string
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
  onOpenWhiteboard,
  onOpenAnimation,
  onSimpler,
  sessionId = null,
  onStart,
  pointing = null,
  onRemovePoint,
  pictureAttached = false,
  onRemovePicture,
  animationStep = null,
  onRemoveAnimationStep,
  onAsk,
  onOpenTools,
  toolsButtonRef,
  pinned = null,
  pinnedWhiteboardId = null,
}: ConversationProps) {
  const scroller = useRef<HTMLDivElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const node = scroller.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [turns])

  useEffect(() => {
    const node = textarea.current
    if (!node) return
    node.style.height = 'auto'
    const max = 1.5 * 16 * 6
    node.style.height = `${Math.min(node.scrollHeight, max)}px`
  }, [draft])

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) return
    if (window.matchMedia(PHONE_QUERY).matches) return
    event.preventDefault()
    event.currentTarget.form?.requestSubmit()
  }

  const empty = sessionOpen && turns.length === 0
  const canSend = draft.trim() !== '' && !sending

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
          {turns.map((turn) => (
            <TurnBlock
              key={turn.key}
              turn={turn}
              onCopy={onCopy}
              onTryAgain={onTryAgain}
              onOpenQuiz={onOpenQuiz}
              onOpenWhiteboard={onOpenWhiteboard}
              onOpenAnimation={onOpenAnimation}
              onSimpler={onSimpler}
              sending={sending}
              sessionId={sessionId}
              onAsk={onAsk}
              pinnedWhiteboardId={pinnedWhiteboardId}
            />
          ))}
        </div>
      </div>
      {sessionOpen ? (
        <form className="chat-input-bar" onSubmit={onSend}>
          {pointing && pointing.parts.length > 0 ? (
            <PointChips parts={pointing.parts} onRemove={onRemovePoint} />
          ) : null}
          {pictureAttached ? <PictureChip onRemove={onRemovePicture} /> : null}
          {animationStep ? (
            <StepChip step={animationStep} onRemove={onRemoveAnimationStep} />
          ) : null}
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
            <label className="visually-hidden" htmlFor="learner-message">
              Message to Polaris
            </label>
            <textarea
              id="learner-message"
              ref={textarea}
              value={draft}
              rows={1}
              placeholder="Ask about a topic"
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={onComposerKeyDown}
            />
            {sending ? (
              <IconButton label="Stop" variant="primary" onClick={onStop}>
                <StopIcon />
              </IconButton>
            ) : (
              <IconButton
                label="Send"
                variant="primary"
                type="submit"
                disabled={!canSend}
              >
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
      ) : null}
    </section>
  )
}

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

function TurnBlock({
  turn,
  onCopy,
  onTryAgain,
  onOpenQuiz,
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
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation?: (sessionId: string, jobId: string) => void
  onSimpler?: (whiteboardId: string) => void
  sending: boolean
  sessionId: string | null
  onAsk?: (whiteboardId: string, parts: PointedPart[]) => void
  pinnedWhiteboardId: string | null
}) {
  const quizzes = turn.artifacts.filter((artifact): artifact is Quiz => artifact.kind === 'quiz')
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
  const whiteboards = storedBoards.flatMap((whiteboard) => {
    if (whiteboard.id === pinnedWhiteboardId) return []
    const revealed = revealWhiteboard(whiteboard, turn.reply, phase)
    return revealed ? [{ ...revealed, kind: 'whiteboard' as const }] : []
  })
  const thinking = turn.streaming && reply === '' && whiteboards.length === 0 && !turn.failed
  const finished = !turn.streaming && !turn.failed && turn.reply !== ''
  const visible =
    reply !== '' || quizzes.length > 0 || whiteboards.length > 0 || animations.length > 0

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
          {whiteboards.map((whiteboard) => (
            <div className="turn-whiteboard" key={whiteboard.id}>
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
              <div className="turn-whiteboard-board">
                <Whiteboard
                  whiteboard={whiteboard}
                  onAsk={onAsk ? (parts) => onAsk(whiteboard.id, parts) : undefined}
                />
              </div>
            </div>
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
}
