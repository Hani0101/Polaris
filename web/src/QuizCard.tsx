import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Check, LoaderCircle, X } from 'lucide-react'
import { gradeQuiz } from './api.ts'
import type { Quiz } from './api.ts'
import { AlertBanner } from './chat/ui.tsx'
import './quiz.css'

type QuizCardProps = {
  quiz: Quiz
  expanded?: boolean
  onGraded: (quiz: Quiz) => void
  onExpand?: (quizId: string) => void
}

type CheckButtonProps = {
  label: string
  pending: boolean
  disabled?: boolean
  variant?: 'primary' | 'secondary'
  onClick: () => void
}

/** Button with the loading state from DESIGN.md: width kept, clicks blocked, spinner, same name. */
function CheckButton({ label, pending, disabled, variant = 'primary', onClick }: CheckButtonProps) {
  const classes = [variant === 'secondary' ? 'secondary' : '', pending ? 'qz-loading' : '']
    .filter(Boolean)
    .join(' ')
  return (
    <button
      type="button"
      className={classes || undefined}
      disabled={disabled}
      aria-disabled={pending || undefined}
      aria-busy={pending || undefined}
      onClick={() => {
        if (!pending) onClick()
      }}
    >
      <span className="qz-button-label">{label}</span>
      {pending ? (
        <LoaderCircle className="qz-spinner" size={20} strokeWidth={2} aria-hidden="true" />
      ) : null}
    </button>
  )
}

type ResultFeedbackProps = {
  right: boolean
  explanation: string
  whyWrong?: string
}

/** QZ-06: why the correct choice is right; on a miss, first why the learner's pick is not. */
function ResultFeedback({ right, explanation, whyWrong }: ResultFeedbackProps) {
  let headline: ReactNode
  const body: string[] = []
  if (right) {
    headline = (
      <>
        <Check size={16} strokeWidth={2} aria-hidden="true" />
        Correct
      </>
    )
  } else {
    headline = (
      <>
        <X size={16} strokeWidth={2} aria-hidden="true" />
        Not quite, here's why
      </>
    )
    if (whyWrong) body.push(whyWrong)
  }
  if (explanation) body.push(explanation)
  return (
    <div className={right ? 'qz-feedback is-correct' : 'qz-feedback is-incorrect'}>
      <p className="qz-feedback-headline">{headline}</p>
      {body.map((text, line) => (
        <p key={line} className="qz-feedback-text">
          {text}
        </p>
      ))}
    </div>
  )
}

export function QuizCard({ quiz, expanded = false, onGraded, onExpand }: QuizCardProps) {
  // The graded quiz from the server, kept here too so review starts even before the parent
  // passes the graded quiz back down.
  const [result, setResult] = useState<Quiz | null>(null)
  const view = quiz.score === null && result?.id === quiz.id ? result : quiz
  const graded = view.score !== null

  const [draft, setDraft] = useState<Record<string, string>>({})
  const [index, setIndex] = useState(0)
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(false)
  const progressId = useId()
  const questionRef = useRef<HTMLHeadingElement>(null)
  const scoreRef = useRef<HTMLParagraphElement>(null)
  const focusNext = useRef<'question' | 'score' | null>(null)

  const feedback = useMemo(
    () => new Map((view.feedback ?? []).map((item) => [item.question_id, item])),
    [view.feedback],
  )

  useEffect(() => {
    const target = focusNext.current
    focusNext.current = null
    if (target === 'question') questionRef.current?.focus()
    if (target === 'score') scoreRef.current?.focus()
  }, [index, graded])

  const total = view.questions.length
  const position = Math.min(index, total - 1)
  const current = view.questions[position]
  if (!current) return null

  const picks = graded ? (view.submitted ?? draft) : draft
  const picked = picks[current.id]
  const isLast = position === total - 1
  const done = position + (picked ? 1 : 0)
  const review = graded ? feedback.get(current.id) : undefined
  const QuestionHeading = expanded ? 'h2' : 'h4'

  function go(to: number) {
    focusNext.current = 'question'
    setIndex(to)
  }

  async function check() {
    if (graded || pending) return
    const missing = view.questions.findIndex((question) => !draft[question.id])
    if (missing !== -1) {
      go(missing)
      return
    }
    setPending(true)
    try {
      // One call grades the whole quiz (QZ-04). The key comes back only with the graded result (QZ-03).
      const next = await gradeQuiz(view.id, draft)
      setFailed(false)
      focusNext.current = 'score'
      setResult(next)
      setIndex(0)
      onGraded(next)
    } catch {
      setFailed(true)
    } finally {
      setPending(false)
    }
  }

  return (
    <article className="qz-card">
      {!expanded ? <h3 className="qz-title">{view.title}</h3> : null}
      {graded && view.score ? (
        <p className="qz-score" ref={scoreRef} tabIndex={-1}>
          You got {view.score.earned} of {view.score.total} right.
        </p>
      ) : null}

      <div className="qz-progress">
        <p className="qz-progress-text" id={progressId}>
          Question {position + 1} of {total}
        </p>
        <div
          className="qz-progress-track"
          role="progressbar"
          aria-labelledby={progressId}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={done}
        >
          <div className="qz-progress-fill" style={{ width: `${(done / total) * 100}%` }} />
        </div>
      </div>

      <fieldset className="qz-question" key={current.id}>
        <legend className="qz-legend">
          <QuestionHeading className="qz-prompt" ref={questionRef} tabIndex={-1}>
            {current.prompt}
          </QuestionHeading>
        </legend>
        <div className="qz-options">
          {current.choices.map((choice) => {
            const chosen = picked === choice.id
            // QZ-03: the answer key arrives only with a graded quiz, inside its feedback, so
            // nothing is marked before grading. In review the correct choice is marked, and a
            // missed question also marks the learner's pick as their answer (QZ-06).
            const outcome =
              review === undefined
                ? null
                : choice.id === review.correct_choice_id
                  ? 'correct'
                  : chosen && !review.right
                    ? 'incorrect'
                    : null
            const classes = ['qz-option']
            if (graded) classes.push('is-locked')
            if (outcome === 'correct') classes.push('is-correct')
            if (outcome === 'incorrect') classes.push('is-incorrect')
            return (
              <label key={choice.id} className={classes.join(' ')}>
                <input
                  className="visually-hidden"
                  type="radio"
                  name={`${view.id}-${current.id}`}
                  value={choice.id}
                  checked={chosen}
                  disabled={graded || pending}
                  onChange={() =>
                    setDraft((previous) => ({ ...previous, [current.id]: choice.id }))
                  }
                />
                <span className="qz-radio" aria-hidden="true" />
                <span className="qz-option-body">
                  <span>{choice.text}</span>
                  {outcome === 'correct' ? (
                    <span className="qz-option-mark">
                      <Check size={16} strokeWidth={2} aria-hidden="true" />
                      Correct answer
                    </span>
                  ) : null}
                  {outcome === 'incorrect' ? (
                    <span className="qz-option-mark">
                      <X size={16} strokeWidth={2} aria-hidden="true" />
                      Your answer
                    </span>
                  ) : null}
                </span>
              </label>
            )
          })}
        </div>
      </fieldset>

      <div aria-live="polite">
        {review ? (
          <ResultFeedback
            key={current.id}
            right={review.right}
            explanation={review.explanation}
            whyWrong={review.why_wrong}
          />
        ) : null}
      </div>

      {failed ? (
        <AlertBanner
          action={
            <CheckButton
              label="Try again"
              variant="secondary"
              pending={pending}
              onClick={() => void check()}
            />
          }
        >
          Couldn't check your answers. Your picks are still here, so try again.
        </AlertBanner>
      ) : null}

      <div className="qz-actions">
        {position > 0 ? (
          <button type="button" className="secondary" onClick={() => go(position - 1)}>
            Previous question
          </button>
        ) : null}
        {!isLast ? (
          <button
            type="button"
            disabled={(!graded && !picked) || pending}
            onClick={() => go(position + 1)}
          >
            Next question
          </button>
        ) : null}
        {isLast && !graded ? (
          <CheckButton
            label="Check answers"
            pending={pending}
            disabled={!picked}
            onClick={() => void check()}
          />
        ) : null}
        {!expanded && onExpand ? (
          <button type="button" className="secondary" onClick={() => onExpand(view.id)}>
            Open on its own page
          </button>
        ) : null}
      </div>
    </article>
  )
}
