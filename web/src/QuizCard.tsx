import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { gradeQuiz } from './api.ts'
import type { Quiz } from './api.ts'

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'That quiz could not be graded. Pick a choice for each question, then try again.'
}

function CheckIcon() {
  return (
    <svg className="result-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M8.3 14.3 4.7 10.7l1.4-1.4 2.2 2.2 5.6-5.6 1.4 1.4z"
      />
    </svg>
  )
}

function CrossIcon() {
  return (
    <svg className="result-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M6.2 5.1 10 8.9l3.8-3.8 1.1 1.1L11.1 10l3.8 3.8-1.1 1.1L10 11.1l-3.8 3.8-1.1-1.1L8.9 10 5.1 6.2z"
      />
    </svg>
  )
}

type QuizCardProps = {
  quiz: Quiz
  expanded?: boolean
  onGraded: (quiz: Quiz) => void
  onExpand?: (quizId: string) => void
}

export function QuizCard({ quiz, expanded = false, onGraded, onExpand }: QuizCardProps) {
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const selected = quiz.submitted ?? draft
  const graded = quiz.score !== null
  const mistakes = useMemo(() => {
    return new Map(
      (quiz.mistakes ?? []).map((mistake) => [mistake.question_id, mistake.explanation]),
    )
  }, [quiz.mistakes])
  const answered = quiz.questions.every((question) => Boolean(selected[question.id]))

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (graded || pending) return
    if (!answered) {
      setError('Pick a choice for each question, then submit.')
      return
    }
    setPending(true)
    setError(null)
    try {
      onGraded(await gradeQuiz(quiz.id, selected))
    } catch (caught) {
      setError(errorText(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <article className={expanded ? 'quiz-card quiz-card-page' : 'quiz-card'}>
      <header className="quiz-head">
        <h3>{quiz.title}</h3>
        <p className="quiz-progress">
          {graded
            ? `You got ${quiz.score?.earned} of ${quiz.score?.total}.`
            : `${quiz.questions.length} questions`}
        </p>
      </header>
      {error ? (
        <p className="quiz-notice" role="alert">
          {error}
        </p>
      ) : null}
      <form onSubmit={(event) => void onSubmit(event)}>
        <ol className="quiz-questions">
          {quiz.questions.map((question, index) => {
            const explanation = mistakes.get(question.id)
            const wrong = graded && explanation !== undefined
            const right = graded && !wrong
            return (
              <li key={question.id}>
                <fieldset className={wrong ? 'quiz-question is-wrong' : right ? 'quiz-question is-right' : 'quiz-question'}>
                  <legend>
                    Question {index + 1} of {quiz.questions.length}
                  </legend>
                  <p className="quiz-prompt">{question.prompt}</p>
                  <div className="quiz-choices">
                    {question.choices.map((choice) => {
                      const choiceId = `${quiz.id}-${question.id}-${choice.id}`
                      return (
                        <label key={choice.id} className="quiz-choice" htmlFor={choiceId}>
                          <input
                            id={choiceId}
                            type="radio"
                            name={`${quiz.id}-${question.id}`}
                            value={choice.id}
                            checked={selected[question.id] === choice.id}
                            disabled={graded || pending}
                            onChange={() =>
                              setDraft((currentDraft) => ({
                                ...currentDraft,
                                [question.id]: choice.id,
                              }))
                            }
                          />
                          <span>{choice.text}</span>
                        </label>
                      )
                    })}
                  </div>
                  {right ? (
                    <p className="quiz-result is-success">
                      <CheckIcon />
                      Correct
                    </p>
                  ) : null}
                  {wrong ? (
                    <p className="quiz-result is-error">
                      <CrossIcon />
                      <span>
                        Not quite, here&apos;s why. {explanation}
                      </span>
                    </p>
                  ) : null}
                </fieldset>
              </li>
            )
          })}
        </ol>
        <div className="quiz-actions">
          {!graded ? (
            <button type="submit" disabled={pending}>
              {pending ? 'Checking…' : 'Submit'}
            </button>
          ) : (
            <p className="quiz-score" aria-live="polite">
              Score kept with this quiz: {quiz.score?.earned} of {quiz.score?.total}.
            </p>
          )}
          {!expanded && onExpand ? (
            <button type="button" className="secondary" onClick={() => onExpand(quiz.id)}>
              Open on its own page
            </button>
          ) : null}
        </div>
      </form>
    </article>
  )
}
