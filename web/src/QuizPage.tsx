import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { getQuiz } from './api.ts'
import type { Quiz } from './api.ts'
import { AlertBanner } from './chat/ui.tsx'
import { QuizCard } from './QuizCard.tsx'
import './quiz.css'

type QuizPageProps = {
  quizId: string
  onBack: () => void
}

/** Loading skeleton: the shape of the page title and the quiz card (DESIGN.md: Loading skeleton). */
function QuizSkeleton() {
  return (
    <div className="qz-page-column" role="status">
      <span className="visually-hidden">Loading the quiz</span>
      <div className="qz-card" aria-hidden="true">
        <div className="skeleton qz-skeleton-small" />
        <div className="skeleton qz-skeleton-bar" />
        <div className="skeleton qz-skeleton-question" />
        <div className="skeleton qz-skeleton-option" />
        <div className="skeleton qz-skeleton-option" />
        <div className="skeleton qz-skeleton-option" />
        <div className="skeleton qz-skeleton-button" />
      </div>
    </div>
  )
}

export function QuizPage({ quizId, onBack }: QuizPageProps) {
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const next = await getQuiz(quizId, controller.signal)
        if (controller.signal.aborted) return
        setQuiz(next)
      } catch {
        if (controller.signal.aborted) return
        setFailed(true)
      }
    }
    void load()
    return () => controller.abort()
  }, [quizId, attempt])

  function tryAgain() {
    setFailed(false)
    setAttempt((count) => count + 1)
  }

  return (
    <div className="qz-page">
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
      <main className="qz-page-main">
        <div className="qz-page-grid">
          {failed ? (
            <div className="qz-page-column">
              <AlertBanner
                action={
                  <button type="button" className="secondary" onClick={tryAgain}>
                    Try again
                  </button>
                }
              >
                Couldn't open this quiz. Try again, or go back to the conversation.
              </AlertBanner>
            </div>
          ) : quiz ? (
            <>
              <h1 className="qz-page-title">{quiz.title}</h1>
              <div className="qz-page-column">
                <QuizCard quiz={quiz} expanded onGraded={setQuiz} />
              </div>
            </>
          ) : (
            <>
              <div className="skeleton qz-skeleton-title" aria-hidden="true" />
              <QuizSkeleton />
            </>
          )}
        </div>
      </main>
    </div>
  )
}
