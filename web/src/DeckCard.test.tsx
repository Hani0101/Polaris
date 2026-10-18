import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { CardRating, Deck } from './api.ts'
import { DeckCard } from './DeckCard.tsx'
import { deckRequest, sourceText } from './deck.ts'

const { rateCard, resetRatings } = vi.hoisted(() => ({
  rateCard: vi.fn<(deckId: string, cardId: string, rating: CardRating) => Promise<Deck>>(),
  resetRatings: vi.fn<(deckId: string) => Promise<Deck>>(),
}))

vi.mock('./api.ts', () => ({ rateCard, resetRatings }))

function withCounts(deck: Deck): Deck {
  const marks = deck.cards.map((card) => card.rating)
  return {
    ...deck,
    counts: {
      got_it: marks.filter((mark) => mark === 'got_it').length,
      again: marks.filter((mark) => mark === 'again').length,
      unrated: marks.filter((mark) => mark === null).length,
    },
  }
}

function sampleDeck(): Deck {
  return withCounts({
    id: 'deck-1',
    kind: 'deck',
    session_id: 'session-1',
    title: 'Photosynthesis',
    counts: { got_it: 0, again: 0, unrated: 0 },
    cards: [
      {
        id: 'c1',
        front: 'What is chlorophyll?',
        back: 'The green pigment that absorbs light.',
        source: { kind: 'page', resource_id: 'r1', name: 'Notes.pdf', page: 4 },
        rating: null,
      },
      {
        id: 'c2',
        front: 'Where does respiration happen?',
        back: '<img src=x onerror=alert(1)>',
        source: { kind: 'quote', resource_id: 'r2', name: 'Week 2', quote: 'site of respiration' },
        rating: null,
      },
      {
        id: 'c3',
        front: 'What do plants make?',
        back: 'Glucose and oxygen.',
        source: { kind: 'turn', turn: 3 },
        rating: null,
      },
    ],
  })
}

let stored: Deck

beforeEach(() => {
  stored = sampleDeck()
  rateCard.mockImplementation(async (_deckId, cardId, rating) => {
    stored = withCounts({
      ...stored,
      cards: stored.cards.map((card) => (card.id === cardId ? { ...card, rating } : card)),
    })
    return stored
  })
  resetRatings.mockImplementation(async () => {
    stored = withCounts({ ...stored, cards: stored.cards.map((card) => ({ ...card, rating: null })) })
    return stored
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function press(name: string) {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name }))
  })
}

function front(): string {
  return screen.getByRole('region', { name: 'Flashcard' }).querySelector('.fc-front')?.textContent ?? ''
}

test('flip then rate: a card rated again comes back in the same sitting (FC-13)', async () => {
  render(<DeckCard deck={stored} onChanged={vi.fn()} />)

  await press('Study 3 cards')
  expect(front()).toBe('What is chlorophyll?')
  expect(screen.queryByText('The green pigment that absorbs light.')).toBeNull()

  await press('Show answer')
  expect(screen.getByText('The green pigment that absorbs light.')).toBeTruthy()
  await press('Again')
  expect(rateCard).toHaveBeenLastCalledWith('deck-1', 'c1', 'again')

  await press('Show answer')
  await press('Got it')
  await press('Show answer')
  await press('Got it')
  expect(front()).toBe('What is chlorophyll?')
})

test('the sitting ends when no card is rated again, with a count of each way (FC-13)', async () => {
  render(<DeckCard deck={stored} onChanged={vi.fn()} />)
  await press('Study 3 cards')

  await press('Show answer')
  await press('Again')
  for (let step = 0; step < 3; step += 1) {
    await press('Show answer')
    await press('Got it')
  }

  expect(screen.queryByRole('region', { name: 'Flashcard' })).toBeNull()
  expect(screen.getByText(/Sitting done\. 2 cards got it the first time, 1 card came back\./)).toBeTruthy()
})

test('a reopened deck shows its ratings and what is left to review (FC-14)', () => {
  const rated = withCounts({
    ...stored,
    cards: stored.cards.map((card, index) => ({
      ...card,
      rating: index === 0 ? 'got_it' : index === 1 ? 'again' : null,
    })),
  })
  render(<DeckCard deck={rated} onChanged={vi.fn()} />)

  expect(screen.getByText(/1 got it, 1 again, 1 not rated\. 2 cards still to review\./)).toBeTruthy()
  const rows = within(screen.getByRole('list', { name: 'Cards in this deck' })).getAllByRole('listitem')
  expect(rows.map((row) => row.querySelector('.badge')?.textContent)).toEqual([
    'Got it',
    'Again',
    'Not rated',
  ])
  expect(screen.getByRole('button', { name: 'Study 2 cards' })).toBeTruthy()
})

test('the learner can reset every rating after one confirmation (FC-14)', async () => {
  const onChanged = vi.fn()
  stored = withCounts({ ...stored, cards: stored.cards.map((card) => ({ ...card, rating: 'got_it' })) })
  render(<DeckCard deck={stored} onChanged={onChanged} />)

  await press('Reset ratings')
  const dialog = screen.getByRole('alertdialog')
  await act(async () => {
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reset ratings' }))
  })

  expect(resetRatings).toHaveBeenCalledWith('deck-1')
  expect(onChanged).toHaveBeenLastCalledWith(expect.objectContaining({ counts: { got_it: 0, again: 0, unrated: 3 } }))
  expect(screen.getByRole('button', { name: 'Study 3 cards' })).toBeTruthy()
})

test('each back shows its source (FC-05)', () => {
  const [pdf, note, turn] = stored.cards.map((card) => sourceText(card.source))

  expect(pdf).toBe('Notes.pdf, p. 4')
  expect(note).toBe('Week 2: “site of respiration”')
  expect(turn).toBe('Turn 3')
})

test('a removed resource leaves the card and says so (FC-18)', () => {
  expect(
    sourceText({ kind: 'page', resource_id: 'r1', name: 'Notes.pdf', page: 4, removed: true }),
  ).toBe('resource removed')
})

test('card text is shown as written, never as markup (FC-10)', async () => {
  const { container } = render(<DeckCard deck={stored} onChanged={vi.fn()} />)
  await press('Study 3 cards')
  await press('Show answer')
  await press('Got it')
  await press('Show answer')

  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeTruthy()
  expect(container.querySelector('img')).toBeNull()
})

test('a card has no edit control (FC-11)', async () => {
  render(<DeckCard deck={stored} onChanged={vi.fn()} />)
  expect(screen.queryByRole('button', { name: /edit/i })).toBeNull()
  await press('Study 3 cards')
  await press('Show answer')
  expect(screen.queryByRole('button', { name: /edit/i })).toBeNull()
  expect(screen.queryByRole('textbox')).toBeNull()
})

test('a rating that fails to save keeps the card and says so', async () => {
  rateCard.mockRejectedValueOnce(new Error('offline'))
  render(<DeckCard deck={stored} onChanged={vi.fn()} />)
  await press('Study 3 cards')
  await press('Show answer')
  await press('Got it')

  expect(screen.getByRole('alert').textContent).toContain("Couldn't save that rating. Try again.")
  expect(front()).toBe('What is chlorophyll?')
})

test('the expanded deck has no link to its own page (FC-02)', () => {
  render(<DeckCard deck={stored} expanded onChanged={vi.fn()} onExpand={vi.fn()} />)
  expect(screen.queryByRole('button', { name: 'Open on its own page' })).toBeNull()
})

test('the dialog request names the topic and every resource (FC-01, FC-03)', () => {
  expect(deckRequest('photosynthesis', ['Notes.pdf', 'Week 2'])).toBe(
    'Make flashcards about photosynthesis. Use “Notes.pdf” and “Week 2”.',
  )
  expect(deckRequest('  ', ['Notes.pdf'])).toBe('Make flashcards from “Notes.pdf”.')
  expect(deckRequest('cells', [])).toBe('Make flashcards about cells.')
})
