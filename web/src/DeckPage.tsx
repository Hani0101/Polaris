import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { getDeck } from './api.ts'
import type { Deck } from './api.ts'
import { AlertBanner } from './chat/ui.tsx'
import { DeckCard } from './DeckCard.tsx'
import './quiz.css'
import './deck.css'

type DeckPageProps = {
  deckId: string
  onBack: () => void
}

/** FC-02: the same deck as in the chat, on its own page. */
export function DeckPage({ deckId, onBack }: DeckPageProps) {
  const [deck, setDeck] = useState<Deck | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    getDeck(deckId, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setDeck(next)
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => controller.abort()
  }, [deckId, attempt])

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
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      setFailed(false)
                      setAttempt((count) => count + 1)
                    }}
                  >
                    Try again
                  </button>
                }
              >
                Couldn't open these flashcards. Try again, or go back to the conversation.
              </AlertBanner>
            </div>
          ) : deck ? (
            <>
              <h1 className="qz-page-title">{deck.title}</h1>
              <div className="qz-page-column">
                <DeckCard deck={deck} expanded onChanged={setDeck} />
              </div>
            </>
          ) : (
            <div className="qz-page-column" role="status">
              <span className="visually-hidden">Loading the flashcards</span>
              <div className="skeleton qz-skeleton-title" aria-hidden="true" />
              <div className="qz-card" aria-hidden="true">
                <div className="skeleton qz-skeleton-small" />
                <div className="skeleton qz-skeleton-question" />
                <div className="skeleton qz-skeleton-option" />
                <div className="skeleton qz-skeleton-button" />
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
