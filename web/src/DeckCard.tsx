import { useEffect, useId, useRef, useState } from 'react'
import { rateCard, resetRatings } from './api.ts'
import type { CardRating, Deck, Flashcard } from './api.ts'
import { Modal } from './chat/Modal.tsx'
import { sourceText } from './deck.ts'
import { AlertBanner, Badge } from './chat/ui.tsx'
import './quiz.css'
import './deck.css'

type DeckCardProps = {
  deck: Deck
  expanded?: boolean
  onChanged: (deck: Deck) => void
  onExpand?: (deckId: string) => void
}

/** One sitting (FC-13): the cards still to show, and those rated "again" in it. */
type Sitting = {
  queue: string[]
  size: number
  cameBack: Set<string>
  flipped: boolean
}

type Summary = { firstTime: number; cameBack: number }

function toReview(deck: Deck): Flashcard[] {
  return deck.cards.filter((card) => card.rating !== 'got_it')
}

function cardCount(count: number): string {
  return count === 1 ? '1 card' : `${count} cards`
}

const RATING_LABEL: Record<CardRating, string> = { got_it: 'Got it', again: 'Again' }

export function DeckCard({ deck, expanded = false, onChanged, onExpand }: DeckCardProps) {
  // The latest deck from the server, so a rating shows before the parent passes it back.
  const [latest, setLatest] = useState<Deck | null>(null)
  const view = latest?.id === deck.id ? latest : deck
  const [sitting, setSitting] = useState<Sitting | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState<string | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)
  const progressId = useId()
  const frontRef = useRef<HTMLHeadingElement>(null)
  const backRef = useRef<HTMLDivElement>(null)
  const summaryRef = useRef<HTMLParagraphElement>(null)
  const focusNext = useRef<'front' | 'back' | 'summary' | null>(null)

  useEffect(() => {
    const target = focusNext.current
    focusNext.current = null
    if (target === 'front') frontRef.current?.focus()
    if (target === 'back') backRef.current?.focus()
    if (target === 'summary') summaryRef.current?.focus()
  }, [sitting, summary])

  function keep(next: Deck) {
    setLatest(next)
    onChanged(next)
  }

  function startSitting() {
    const pending = toReview(view)
    const cards = pending.length > 0 ? pending : view.cards
    setFailed(null)
    setSummary(null)
    focusNext.current = 'front'
    setSitting({
      queue: cards.map((card) => card.id),
      size: cards.length,
      cameBack: new Set(),
      flipped: false,
    })
  }

  function flip() {
    if (!sitting) return
    focusNext.current = 'back'
    setSitting({ ...sitting, flipped: true })
  }

  async function rate(rating: CardRating) {
    if (!sitting || busy) return
    const [cardId, ...rest] = sitting.queue
    setBusy(true)
    try {
      keep(await rateCard(view.id, cardId, rating))
      setFailed(null)
    } catch {
      setFailed("Couldn't save that rating. Try again.")
      return
    } finally {
      setBusy(false)
    }
    // FC-13: a card rated "again" comes back later in the same sitting.
    const cameBack = new Set(sitting.cameBack)
    if (rating === 'again') cameBack.add(cardId)
    const queue = rating === 'again' ? [...rest, cardId] : rest
    if (queue.length === 0) {
      focusNext.current = 'summary'
      setSitting(null)
      setSummary({ firstTime: sitting.size - cameBack.size, cameBack: cameBack.size })
      return
    }
    focusNext.current = 'front'
    setSitting({ ...sitting, queue, cameBack, flipped: false })
  }

  async function reset() {
    setBusy(true)
    try {
      keep(await resetRatings(view.id))
      setFailed(null)
      setSummary(null)
      setConfirmReset(false)
    } catch {
      setFailed("Couldn't reset the ratings. Try again.")
      setConfirmReset(false)
    } finally {
      setBusy(false)
    }
  }

  const title = !expanded ? <h3 className="qz-title">{view.title}</h3> : null
  const expand =
    !expanded && onExpand ? (
      <button type="button" className="secondary" onClick={() => onExpand(view.id)}>
        Open on its own page
      </button>
    ) : null

  if (sitting) {
    const card = view.cards.find((item) => item.id === sitting.queue[0])
    if (!card) return null
    const done = sitting.size - new Set(sitting.queue).size
    const FrontHeading = expanded ? 'h2' : 'h4'
    return (
      <article className="qz-card">
        {title}
        <div className="qz-progress">
          <p className="qz-progress-text" id={progressId}>
            {done} of {cardCount(sitting.size)} done
          </p>
          <div
            className="qz-progress-track"
            role="progressbar"
            aria-labelledby={progressId}
            aria-valuemin={0}
            aria-valuemax={sitting.size}
            aria-valuenow={done}
          >
            <div className="qz-progress-fill" style={{ width: `${(done / sitting.size) * 100}%` }} />
          </div>
        </div>
        <section className="fc-face" aria-label="Flashcard">
          <FrontHeading className="fc-front" ref={frontRef} tabIndex={-1}>
            {card.front}
          </FrontHeading>
          {sitting.flipped ? (
            <div className="fc-back" ref={backRef} tabIndex={-1}>
              <p>{card.back}</p>
              <p className="fc-source">Source: {sourceText(card.source)}</p>
            </div>
          ) : null}
        </section>
        {failed ? <AlertBanner>{failed}</AlertBanner> : null}
        <div className="qz-actions">
          {sitting.flipped ? (
            <>
              <button type="button" disabled={busy} onClick={() => void rate('got_it')}>
                Got it
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => void rate('again')}
              >
                Again
              </button>
            </>
          ) : (
            <button type="button" onClick={flip}>
              Show answer
            </button>
          )}
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setFailed(null)
              setSitting(null)
            }}
          >
            Stop studying
          </button>
        </div>
      </article>
    )
  }

  const pending = toReview(view)
  return (
    <article className="qz-card">
      {title}
      {summary ? (
        <p className="qz-score" ref={summaryRef} tabIndex={-1}>
          Sitting done. {cardCount(summary.firstTime)} got it the first time
          {summary.cameBack > 0 ? `, ${cardCount(summary.cameBack)} came back.` : '.'}
        </p>
      ) : null}
      <p className="fc-tally">
        {cardCount(view.cards.length)}. {view.counts.got_it} got it, {view.counts.again} again,{' '}
        {view.counts.unrated} not rated.{' '}
        {pending.length > 0
          ? `${cardCount(pending.length)} still to review.`
          : 'Nothing left to review.'}
      </p>
      <ol className="fc-list" aria-label="Cards in this deck">
        {view.cards.map((card) => (
          <li key={card.id} className="fc-list-row">
            <span className="fc-list-front">{card.front}</span>
            {card.rating ? (
              <Badge variant={card.rating === 'got_it' ? 'accent' : 'neutral'}>
                {RATING_LABEL[card.rating]}
              </Badge>
            ) : (
              <Badge>Not rated</Badge>
            )}
          </li>
        ))}
      </ol>
      {failed ? <AlertBanner>{failed}</AlertBanner> : null}
      <div className="qz-actions">
        <button type="button" onClick={startSitting}>
          {pending.length > 0 ? `Study ${cardCount(pending.length)}` : 'Study all cards'}
        </button>
        {view.counts.unrated < view.cards.length ? (
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => setConfirmReset(true)}
          >
            Reset ratings
          </button>
        ) : null}
        {expand}
      </div>
      <Modal
        open={confirmReset}
        title="Reset the ratings of this deck?"
        variant="confirm"
        mainLabel="Reset ratings"
        onMain={() => void reset()}
        onCancel={() => setConfirmReset(false)}
      >
        <p>Every card in “{view.title}” goes back to not rated. The cards stay as they are.</p>
      </Modal>
    </article>
  )
}
