import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { RefObject } from 'react'
import { Check, X } from 'lucide-react'
import { answerQuiz } from './api.ts'
import type { Quiz, QuizFeedback } from './api.ts'
import { AlertBanner } from './chat/ui.tsx'
import './quiz.css'

type QuizCardProps = {
  quiz: Quiz
  expanded?: boolean
  onChecked: (quiz: Quiz) => void
  onExpand?: (quizId: string) => void
}

/** What the card shows: a question, the results of a finished quiz, or a review of its questions. */
type Mode = 'questions' | 'results' | 'review'

function checkedCount(quiz: Quiz): number {
  return Object.keys(quiz.submitted ?? {}).length
}

type QuizResultsProps = {
  quiz: Quiz
  feedback: Map<string, QuizFeedback>
  scoreRef: RefObject<HTMLParagraphElement | null>
  onOpenQuestion: (index: number) => void
}

/** QZ-16: the score, and every question marked right or wrong. A row opens that question. */
function QuizResults({ quiz, feedback, scoreRef, onOpenQuestion }: QuizResultsProps) {
  return (
    <section className="qz-results" aria-label="Results">
      {quiz.score ? (
        <p className="qz-score" ref={scoreRef} tabIndex={-1}>
          You got {quiz.score.earned} of {quiz.score.total} right.
        </p>
      ) : null}
      <ul className="qz-result-list">
        {quiz.questions.map((question, index) => {
          const right = feedback.get(question.id)?.right === true
          return (
            <li key={question.id}>
              <button type="button" className="qz-result-row" onClick={() => onOpenQuestion(index)}>
                <span className="qz-result-prompt">
                  {index + 1}. {question.prompt}
                </span>
                <span className="qz-result-mark">
                  {right ? (
                    <Check size={16} strokeWidth={2} aria-hidden="true" />
                  ) : (
                    <X size={16} strokeWidth={2} aria-hidden="true" />
                  )}
                  {right ? 'Right' : 'Wrong'}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function QuizCard({ quiz, expanded = false, onChecked, onExpand }: QuizCardProps) {
  // The latest quiz from the server, kept here too so the feedback shows even before the
  // parent passes the updated quiz back down.
  const [result, setResult] = useState<Quiz | null>(null)
  const view = result?.id === quiz.id && checkedCount(result) > checkedCount(quiz) ? result : quiz
  const finished = view.score !== null

  const [mode, setMode] = useState<Mode>(finished ? 'results' : 'questions')
  // QZ-15: a quiz that is opened again continues at the first question not yet checked.
  const [index, setIndex] = useState(() => {
    const open = quiz.questions.findIndex((question) => !(question.id in (quiz.submitted ?? {})))
    return open === -1 ? 0 : open
  })
  const [pending, setPending] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const progressId = useId()
  const questionRef = useRef<HTMLHeadingElement>(null)
  const scoreRef = useRef<HTMLParagraphElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const focusNext = useRef<'question' | 'score' | 'next' | null>(null)

  const feedback = useMemo(
    () => new Map((view.feedback ?? []).map((item) => [item.question_id, item])),
    [view.feedback],
  )

  useEffect(() => {
    const target = focusNext.current
    focusNext.current = null
    if (target === 'question') questionRef.current?.focus()
    if (target === 'score') scoreRef.current?.focus()
    if (target === 'next') nextRef.current?.focus()
  }, [index, mode, view])

  const total = view.questions.length
  const position = Math.min(index, total - 1)
  const current = view.questions[position]
  if (!current) return null

  const submitted = view.submitted ?? {}
  const review = feedback.get(current.id)
  const picked = submitted[current.id] ?? pending ?? undefined
  const isLast = position === total - 1
  const done = checkedCount(view)
  const QuestionHeading = expanded ? 'h2' : 'h4'
  // QZ-16: the last question keeps its feedback on screen, with the results under it.
  const showResultsBelow = finished && mode === 'questions' && isLast

  function go(to: number) {
    focusNext.current = 'question'
    setIndex(to)
  }

  function openQuestion(to: number) {
    setMode('review')
    go(to)
  }

  async function pick(choiceId: string) {
    if (!current || review || pending) return
    setPending(choiceId)
    try {
      // QZ-14: picking checks the question. Only this question's key comes back (QZ-03).
      const next = await answerQuiz(view.id, current.id, choiceId)
      setFailed(false)
      focusNext.current = next.score ? 'score' : 'next'
      setResult(next)
      onChecked(next)
    } catch {
      setFailed(true)
    } finally {
      setPending(null)
    }
  }

  if (mode === 'results') {
    return (
      <article className="qz-card">
        {!expanded ? <h3 className="qz-title">{view.title}</h3> : null}
        <QuizResults
          quiz={view}
          feedback={feedback}
          scoreRef={scoreRef}
          onOpenQuestion={openQuestion}
        />
        <div className="qz-actions">
          <button type="button" onClick={() => openQuestion(0)}>
            Review answers
          </button>
          {!expanded && onExpand ? (
            <button type="button" className="secondary" onClick={() => onExpand(view.id)}>
              Open on its own page
            </button>
          ) : null}
        </div>
      </article>
    )
  }

  return (
    <article className="qz-card">
      {!expanded ? <h3 className="qz-title">{view.title}</h3> : null}

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
            // QZ-03: the key arrives only with a checked question, inside its feedback, so
            // nothing is marked before the pick. The correct choice is marked, and a miss
            // also marks the learner's pick as their answer (QZ-06).
            const outcome =
              review === undefined
                ? null
                : choice.id === review.correct_choice_id
                  ? 'correct'
                  : chosen && !review.right
                    ? 'incorrect'
                    : null
            const note =
              outcome === 'correct'
                ? review?.explanation
                : outcome === 'incorrect'
                  ? review?.why_wrong
                  : undefined
            const classes = ['qz-option']
            if (review) classes.push('is-locked')
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
                  disabled={review !== undefined || pending !== null}
                  onChange={() => void pick(choice.id)}
                />
                <span className="qz-radio" aria-hidden="true" />
                <span className="qz-option-body">
                  <span>{choice.text}</span>
                  {outcome === 'correct' ? (
                    <span className="qz-option-mark">
                      <Check size={16} strokeWidth={2} aria-hidden="true" />
                      {chosen ? 'Correct' : 'Correct answer'}
                    </span>
                  ) : null}
                  {outcome === 'incorrect' ? (
                    <span className="qz-option-mark">
                      <X size={16} strokeWidth={2} aria-hidden="true" />
                      Your answer
                    </span>
                  ) : null}
                  {note ? <span className="qz-option-note">{note}</span> : null}
                </span>
              </label>
            )
          })}
        </div>
      </fieldset>

      <div aria-live="polite" className="visually-hidden">
        {review ? (review.right ? 'Correct.' : 'Not quite.') : ''}
      </div>

      {failed ? <AlertBanner>Couldn't check that answer. Try again.</AlertBanner> : null}

      {showResultsBelow ? (
        <QuizResults
          quiz={view}
          feedback={feedback}
          scoreRef={scoreRef}
          onOpenQuestion={openQuestion}
        />
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
            ref={nextRef}
            disabled={!review || pending !== null}
            onClick={() => go(position + 1)}
          >
            Next question
          </button>
        ) : null}
        {mode === 'review' ? (
          <button type="button" className="secondary" onClick={() => setMode('results')}>
            Back to results
          </button>
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
