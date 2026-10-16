import { expect, test } from 'vitest'
import { turnBody } from './api.ts'
import { SIMPLER_REQUEST } from './whiteboard/simpler.ts'

test('a simpler turn sends the original whiteboard id', () => {
  expect(turnBody(SIMPLER_REQUEST, null, 'wb-1')).toEqual({
    message: 'Draw a simpler version of this whiteboard.',
    simplifies: 'wb-1',
  })
  expect(turnBody('Hello', null)).toEqual({ message: 'Hello' })
})
