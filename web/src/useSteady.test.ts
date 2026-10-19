import { renderHook } from '@testing-library/react'
import { expect, test } from 'vitest'
import { useSteadyHandlers } from './useSteady.ts'

test('steady handlers keep their identity and call the latest handler', () => {
  const { result, rerender } = renderHook(
    ({ name }) => useSteadyHandlers({ greet: () => `hello ${name}` }),
    { initialProps: { name: 'first' } },
  )
  const first = result.current
  expect(first.greet()).toBe('hello first')

  rerender({ name: 'second' })
  expect(result.current).toBe(first)
  expect(result.current.greet).toBe(first.greet)
  expect(first.greet()).toBe('hello second')
})
