import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Quiz } from './api.ts'
import { QuizCard } from './QuizCard.tsx'

const { gradeQuiz } = vi.hoisted(() => ({
  gradeQuiz: vi.fn<(quizId: string, choices: Record<string, string>) => Promise<Quiz>>(),
}))

vi.mock('./api.ts', () => ({ gradeQuiz }))

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

beforeEach(() => {
  gradeQuiz.mockReset()
})

afterEach(() => {
  cleanup()
})

test('shows one question at a time and Next question waits for a pick', () => {
  render(<QuizCard quiz={sampleQuiz()} onGraded={() => {}} />)

  expect(screen.getByText('Question 1 of 2')).toBeTruthy()
  expect(screen.getByText('How many sides does a triangle have?')).toBeTruthy()
  expect(screen.queryByText('What do the angles of a triangle add up to?')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Previous question' })).toBeNull()

  const next = screen.getByRole('button', { name: 'Next question' }) as HTMLButtonElement
  expect(next.disabled).toBe(true)
  fireEvent.click(screen.getByRole('radio', { name: 'Three' }))
  expect(next.disabled).toBe(false)

  fireEvent.click(next)
  expect(screen.getByText('Question 2 of 2')).toBeTruthy()
  expect(screen.getByText('What do the angles of a triangle add up to?')).toBeTruthy()
  expect(screen.queryByText('How many sides does a triangle have?')).toBeNull()
  expect(screen.getByRole('button', { name: 'Previous question' })).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Submit' })).toBeNull()
})

test('Check answers grades the whole quiz once, then review explains the mistake', async () => {
  const reads: string[] = []
  const quiz = watchKeyReads(sampleQuiz(), reads)
  const onGraded = vi.fn()
  gradeQuiz.mockResolvedValue({
    ...sampleQuiz(),
    score: { earned: 1, total: 2 },
    submitted: { q1: 'a', q2: 'a' },
    mistakes: [{ question_id: 'q2', explanation: 'The three angles always add up to 180 degrees.' }],
  })

  render(<QuizCard quiz={quiz} onGraded={onGraded} />)
  fireEvent.click(screen.getByRole('radio', { name: 'Three' }))
  fireEvent.click(screen.getByRole('button', { name: 'Next question' }))

  const check = screen.getByRole('button', { name: 'Check answers' }) as HTMLButtonElement
  expect(check.disabled).toBe(true)
  fireEvent.click(screen.getByRole('radio', { name: '90 degrees' }))
  expect(check.disabled).toBe(false)

  await act(async () => {
    fireEvent.click(check)
  })

  expect(gradeQuiz).toHaveBeenCalledTimes(1)
  expect(gradeQuiz).toHaveBeenCalledWith('quiz-1', { q1: 'a', q2: 'a' })
  expect(onGraded).toHaveBeenCalledTimes(1)

  // Review starts at the first question, which the learner got right.
  expect(screen.getByText('You got 1 of 2 right.')).toBeTruthy()
  expect(screen.getByText('Question 1 of 2')).toBeTruthy()
  expect(screen.getAllByText('Correct').length).toBeGreaterThan(0)
  expect(screen.queryByText("Not quite, here's why")).toBeNull()

  fireEvent.click(screen.getByRole('button', { name: 'Next question' }))
  expect(screen.getByText("Not quite, here's why")).toBeTruthy()
  expect(screen.getByText('The three angles always add up to 180 degrees.')).toBeTruthy()
  expect(screen.getByText('Your answer')).toBeTruthy()
  // QZ-03: the right choice of a missed question is never revealed.
  expect(screen.queryByText('Correct')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Check answers' })).toBeNull()

  expect(reads).toEqual([])
})

test('a quiz that arrives graded opens in review', () => {
  render(
    <QuizCard
      quiz={{
        ...sampleQuiz(),
        score: { earned: 2, total: 2 },
        submitted: { q1: 'a', q2: 'b' },
        mistakes: [],
      }}
      onGraded={() => {}}
    />,
  )
  expect(screen.getByText('You got 2 of 2 right.')).toBeTruthy()
  expect((screen.getByRole('radio', { name: /Three/ }) as HTMLInputElement).checked).toBe(true)
  expect(screen.queryByRole('button', { name: 'Check answers' })).toBeNull()
})

test('a grading problem shows an alert with Try again and keeps the picks', async () => {
  gradeQuiz.mockRejectedValueOnce(new Error('offline'))
  render(<QuizCard quiz={sampleQuiz()} onGraded={() => {}} />)
  fireEvent.click(screen.getByRole('radio', { name: 'Three' }))
  fireEvent.click(screen.getByRole('button', { name: 'Next question' }))
  fireEvent.click(screen.getByRole('radio', { name: '180 degrees' }))

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Check answers' }))
  })

  expect(screen.getByRole('alert').textContent).toContain("Couldn't check your answers.")
  expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  expect((screen.getByRole('radio', { name: '180 degrees' }) as HTMLInputElement).checked).toBe(true)
})

test('the inline card offers its own page', () => {
  const onExpand = vi.fn()
  render(<QuizCard quiz={sampleQuiz()} onGraded={() => {}} onExpand={onExpand} />)
  fireEvent.click(screen.getByRole('button', { name: 'Open on its own page' }))
  expect(onExpand).toHaveBeenCalledWith('quiz-1')
})
