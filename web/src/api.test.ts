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

test('a turn can carry a picture of a whiteboard', () => {
  const picture = { whiteboard_id: 'wb-1', media_type: 'image/png' as const, data: 'iVBORw0K' }

  expect(turnBody('Is this right?', null, null, picture)).toEqual({
    message: 'Is this right?',
    picture,
  })
  expect(turnBody('Is this right?', null, null, null)).toEqual({ message: 'Is this right?' })
})
