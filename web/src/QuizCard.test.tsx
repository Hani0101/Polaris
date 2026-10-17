import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Quiz, QuizFeedback } from './api.ts'
import { QuizCard } from './QuizCard.tsx'

const { answerQuiz } = vi.hoisted(() => ({
  answerQuiz: vi.fn<(quizId: string, questionId: string, choiceId: string) => Promise<Quiz>>(),
}))

vi.mock('./api.ts', () => ({ answerQuiz }))

const KEY_FIELD = /answer|correct/i

/** Wraps the quiz so any read of an answer-key-like field is recorded (QZ-03). */
function watchKeyReads<T extends object>(value: T, reads: string[]): T {
  return new Proxy(value, {
    get(target, property, receiver) {
      if (typeof property === 'string' && KEY_FIELD.test(property)) reads.push(property)
      const inner = Reflect.get(target, property, receiver) as unknown
      return inner !== null && typeof inner === 'object' ? watchKeyReads(inner, reads) : inner
    },
  })
}

function sampleQuiz(): Quiz {
  return {
    id: 'quiz-1',
    kind: 'quiz',
    session_id: 'session-1',
    title: 'Triangles',
    score: null,
    questions: [
      {
        id: 'q1',
        prompt: 'How many sides does a triangle have?',
        choices: [
          { id: 'a', text: 'Three' },
          { id: 'b', text: 'Four' },
        ],
      },
      {
        id: 'q2',
        prompt: 'What do the angles of a triangle add up to?',
        choices: [
          { id: 'a', text: '90 degrees' },
          { id: 'b', text: '180 degrees' },
        ],
      },
    ],
  }
}

const RIGHT_Q1: QuizFeedback = {
  question_id: 'q1',
  right: true,
  correct_choice_id: 'a',
  explanation: 'A triangle is a shape with three straight sides.',
}

const WRONG_Q2: QuizFeedback = {
  question_id: 'q2',
  right: false,
  correct_choice_id: 'b',
  explanation: 'The three angles always add up to 180 degrees.',
  why_wrong: '90 degrees is one right angle, not the sum of all three.',
}

/** The quiz as the server sends it after q1 is checked (right). */
function afterFirst(): Quiz {
  return { ...sampleQuiz(), submitted: { q1: 'a' }, feedback: [RIGHT_Q1] }
}

/** The quiz as the server sends it once both are checked: q1 right, q2 missed. */
function finishedQuiz(feedback: QuizFeedback[] = [RIGHT_Q1, WRONG_Q2]): Quiz {
  return {
    ...sampleQuiz(),
    score: { earned: 1, total: 2 },
    submitted: { q1: 'a', q2: 'a' },
    feedback,
  }
}

/** The answer row a radio sits in, where the marks and feedback are. */
function optionRow(name: RegExp): HTMLElement {
  return screen.getByRole('radio', { name }).closest('label') as HTMLElement
}

beforeEach(() => {
  answerQuiz.mockReset()
})

afterEach(() => {
  cleanup()
})

test('shows one question at a time and Next question waits for a check', async () => {
  answerQuiz.mockResolvedValue(afterFirst())
  render(<QuizCard quiz={sampleQuiz()} onChecked={() => {}} />)

  expect(screen.getByText('Question 1 of 2')).toBeTruthy()
  expect(screen.getByText('How many sides does a triangle have?')).toBeTruthy()
  expect(screen.queryByText('What do the angles of a triangle add up to?')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Previous question' })).toBeNull()
  expect(screen.queryByRole('button', { name: /Check answer/ })).toBeNull()

  const next = screen.getByRole('button', { name: 'Next question' }) as HTMLButtonElement
  expect(next.disabled).toBe(true)
  await act(async () => {
    fireEvent.click(screen.getByRole('radio', { name: 'Three' }))
  })
  expect(next.disabled).toBe(false)

  fireEvent.click(next)
  expect(screen.getByText('Question 2 of 2')).toBeTruthy()
  expect(screen.getByText('What do the angles of a triangle add up to?')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Previous question' })).toBeTruthy()
  // The last question has no Next button and no results button (QZ-16).
  expect(screen.queryByRole('button', { name: 'Next question' })).toBeNull()
  expect(screen.queryByRole('button', { name: /results/i })).toBeNull()
})

test('picking checks that question at once and shows its feedback inside the options', async () => {
  const reads: string[] = []
  const onChecked = vi.fn()
  answerQuiz.mockResolvedValue(afterFirst())
  render(<QuizCard quiz={watchKeyReads(sampleQuiz(), reads)} onChecked={onChecked} />)

  // QZ-03: before the pick nothing is marked right or wrong.
  expect(screen.queryByText('Correct')).toBeNull()
  expect(screen.queryByText('Your answer')).toBeNull()

  await act(async () => {
    fireEvent.click(screen.getByRole('radio', { name: 'Three' }))
  })

  expect(answerQuiz).toHaveBeenCalledTimes(1)
  expect(answerQuiz).toHaveBeenCalledWith('quiz-1', 'q1', 'a')
  expect(onChecked).toHaveBeenCalledTimes(1)

  const pick = optionRow(/Three/)
  expect(pick.classList.contains('is-correct')).toBe(true)
  expect(within(pick).getByText('Correct')).toBeTruthy()
  expect(within(pick).getByText(RIGHT_Q1.explanation)).toBeTruthy()
  expect(screen.queryByText('Correct answer')).toBeNull()
  expect((screen.getByRole('radio', { name: /Four/ }) as HTMLInputElement).disabled).toBe(true)

  // QZ-03: the unchecked quiz never had an answer-key field to read.
  expect(reads).toEqual([])
})

test('a wrong pick marks it with the note and shows the correct choice with its explanation', () => {
  render(<QuizCard quiz={finishedQuiz()} onChecked={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Review answers' }))
  fireEvent.click(screen.getByRole('button', { name: 'Next question' }))

  const pick = optionRow(/90 degrees/)
  expect(pick.classList.contains('is-incorrect')).toBe(true)
  expect(within(pick).getByText('Your answer')).toBeTruthy()
  expect(within(pick).getByText(WRONG_Q2.why_wrong as string)).toBeTruthy()
  expect(within(pick).queryByText(WRONG_Q2.explanation)).toBeNull()
  expect((screen.getByRole('radio', { name: /90 degrees/ }) as HTMLInputElement).checked).toBe(true)

  // QZ-06: the explanation sits on the correct choice.
  const answer = optionRow(/180 degrees/)
  expect(answer.classList.contains('is-correct')).toBe(true)
  expect(within(answer).getByText('Correct answer')).toBeTruthy()
  expect(within(answer).getByText(WRONG_Q2.explanation)).toBeTruthy()
  expect((screen.getByRole('radio', { name: /180 degrees/ }) as HTMLInputElement).checked).toBe(false)
})

test('a wrong pick on an older quiz without a note still marks the correct choice', () => {
  const withoutNote: QuizFeedback = { ...WRONG_Q2 }
  delete withoutNote.why_wrong
  render(<QuizCard quiz={finishedQuiz([RIGHT_Q1, withoutNote])} onChecked={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Review answers' }))
  fireEvent.click(screen.getByRole('button', { name: 'Next question' }))

  expect(within(optionRow(/90 degrees/)).getByText('Your answer')).toBeTruthy()
  expect(within(optionRow(/180 degrees/)).getByText(WRONG_Q2.explanation)).toBeTruthy()
})

test('checking the last question keeps its feedback and shows the results under it', async () => {
  answerQuiz.mockResolvedValue(finishedQuiz())
  render(<QuizCard quiz={afterFirst()} onChecked={() => {}} />)

  // QZ-15: the quiz opens at the first question not yet checked.
  expect(screen.getByText('Question 2 of 2')).toBeTruthy()
  expect(screen.queryByText('You got 1 of 2 right.')).toBeNull()

  await act(async () => {
    fireEvent.click(screen.getByRole('radio', { name: '90 degrees' }))
  })

  expect(answerQuiz).toHaveBeenCalledWith('quiz-1', 'q2', 'a')
  expect(screen.getByText('Question 2 of 2')).toBeTruthy()
  expect(within(optionRow(/180 degrees/)).getByText(WRONG_Q2.explanation)).toBeTruthy()
  expect(screen.getByText('You got 1 of 2 right.')).toBeTruthy()
  const rows = screen.getAllByRole('button', { name: /^\d\. / })
  expect(rows.map((row) => row.textContent)).toEqual([
    '1. How many sides does a triangle have?Right',
    '2. What do the angles of a triangle add up to?Wrong',
  ])
})

test('a finished quiz opens on its results, and a row or Review answers opens a question', () => {
  render(<QuizCard quiz={finishedQuiz()} onChecked={() => {}} />)

  expect(screen.getByText('You got 1 of 2 right.')).toBeTruthy()
  expect(screen.queryByRole('radio')).toBeNull()

  fireEvent.click(screen.getByRole('button', { name: /^2\. / }))
  expect(screen.getByText('Question 2 of 2')).toBeTruthy()
  expect((screen.getByRole('radio', { name: /90 degrees/ }) as HTMLInputElement).checked).toBe(true)

  fireEvent.click(screen.getByRole('button', { name: 'Back to results' }))
  expect(screen.getByText('You got 1 of 2 right.')).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: 'Review answers' }))
  expect(screen.getByText('Question 1 of 2')).toBeTruthy()
  expect(within(optionRow(/Three/)).getByText(RIGHT_Q1.explanation)).toBeTruthy()
})

test('a half-finished quiz reopens with its checked question locked', () => {
  render(<QuizCard quiz={afterFirst()} onChecked={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Previous question' }))

  expect(screen.getByText('Question 1 of 2')).toBeTruthy()
  expect((screen.getByRole('radio', { name: /Three/ }) as HTMLInputElement).checked).toBe(true)
  expect((screen.getByRole('radio', { name: /Four/ }) as HTMLInputElement).disabled).toBe(true)
  expect(within(optionRow(/Three/)).getByText(RIGHT_Q1.explanation)).toBeTruthy()
})

test('a check that fails shows an alert and leaves the options unlocked', async () => {
  answerQuiz.mockRejectedValueOnce(new Error('offline'))
  const onChecked = vi.fn()
  render(<QuizCard quiz={sampleQuiz()} onChecked={onChecked} />)

  await act(async () => {
    fireEvent.click(screen.getByRole('radio', { name: 'Three' }))
  })

  expect(screen.getByRole('alert').textContent).toContain("Couldn't check that answer.")
  expect(onChecked).not.toHaveBeenCalled()
  expect(screen.queryByText('Correct')).toBeNull()
  const three = screen.getByRole('radio', { name: 'Three' }) as HTMLInputElement
  expect(three.checked).toBe(false)
  expect(three.disabled).toBe(false)
  expect((screen.getByRole('button', { name: 'Next question' }) as HTMLButtonElement).disabled).toBe(
    true,
  )
})

test('the inline card offers its own page', () => {
  const onExpand = vi.fn()
  render(<QuizCard quiz={sampleQuiz()} onChecked={() => {}} onExpand={onExpand} />)
  fireEvent.click(screen.getByRole('button', { name: 'Open on its own page' }))
  expect(onExpand).toHaveBeenCalledWith('quiz-1')
})
