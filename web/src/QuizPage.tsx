import { useEffect, useState } from 'react'
import { getQuiz } from './api.ts'
import type { Quiz } from './api.ts'
import { QuizCard } from './QuizCard.tsx'

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'That quiz could not be opened.'
}

type QuizPageProps = {
  quizId: string
  onBack: () => void
}

export function QuizPage({ quizId, onBack }: QuizPageProps) {
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const next = await getQuiz(quizId, controller.signal)
        if (controller.signal.aborted) return
        setQuiz(next)
      } catch (caught) {
        if (controller.signal.aborted) return
        setError(errorText(caught))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [quizId])

  return (
    <div className="app">
      <header className="top">
        <h1>Polaris</h1>
        <button type="button" className="secondary" onClick={onBack}>
          Back to the conversation
        </button>
      </header>
      {error ? (
        <p className="notice" role="alert">
          {error} Ask in the conversation if you need another way in.
        </p>
      ) : null}
      {loading ? <p>Loading the quiz.</p> : null}
      {quiz ? <QuizCard quiz={quiz} expanded onGraded={setQuiz} /> : null}
    </div>
  )
}
