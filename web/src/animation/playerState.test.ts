import { expect, test } from 'vitest'
import { initialPlayer, nextPlayer } from './playerState.ts'
import type { PlayerEvent, PlayerState } from './playerState.ts'

const durations = [1000, 2000, 1500]

function run(state: PlayerState, events: PlayerEvent[], reduced = false): PlayerState {
  return events.reduce((current, event) => nextPlayer(current, event, durations, reduced), state)
}

test('playing runs through the steps and stops at the end of the last one', () => {
  const start = initialPlayer(durations, false)
  expect(start).toMatchObject({ step: 0, time: 0, playing: true })

  const second = run(start, [{ type: 'tick', elapsed: 1000 }])
  expect(second).toMatchObject({ step: 1, time: 0, playing: true })

  const end = run(second, [
    { type: 'tick', elapsed: 2000 },
    { type: 'tick', elapsed: 1000 },
    { type: 'tick', elapsed: 1000 },
  ])
  expect(end).toMatchObject({ step: 2, time: 1500, playing: false })
})

test('Next plays the next step, Back shows the end of the step before', () => {
  const paused = run(initialPlayer(durations, false), [
    { type: 'next' },
    { type: 'tick', elapsed: 300 },
    { type: 'pause' },
  ])
  expect(paused).toMatchObject({ step: 1, time: 300, playing: false })

  expect(run(paused, [{ type: 'next' }])).toMatchObject({ step: 2, time: 0, playing: true })
  expect(run(paused, [{ type: 'back' }])).toMatchObject({ step: 0, time: 1000, playing: false })
})

test('Replay starts the current step again', () => {
  const state = run(initialPlayer(durations, false), [
    { type: 'next' },
    { type: 'tick', elapsed: 1200 },
    { type: 'replay' },
  ])
  expect(state).toMatchObject({ step: 1, time: 0, playing: true })
})

test('Play after Back carries on with the next step; at the very end it starts over', () => {
  const back = run(initialPlayer(durations, false), [{ type: 'next' }, { type: 'back' }])
  expect(run(back, [{ type: 'play' }])).toMatchObject({ step: 1, time: 0, playing: true })

  const ended: PlayerState = { step: 2, time: 1500, playing: false, starts: 4 }
  expect(run(ended, [{ type: 'play' }])).toMatchObject({ step: 0, time: 0, playing: true })
})

test('under reduced motion nothing plays and each step shows its end', () => {
  const start = initialPlayer(durations, true)
  expect(start).toMatchObject({ step: 0, time: 1000, playing: false })

  expect(run(start, [{ type: 'play' }, { type: 'tick', elapsed: 500 }], true)).toEqual(start)
  expect(run(start, [{ type: 'next' }], true)).toMatchObject({ step: 1, time: 2000, playing: false })
  expect(run(start, [{ type: 'jump', step: 2 }], true)).toMatchObject({ step: 2, time: 1500 })
})

test('every step change counts as a start for narration', () => {
  const start = initialPlayer(durations, false)
  const moved = run(start, [{ type: 'next' }, { type: 'back' }, { type: 'replay' }])
  expect(moved.starts).toBe(start.starts + 3)
  const resumed = run(start, [{ type: 'tick', elapsed: 100 }, { type: 'pause' }, { type: 'play' }])
  expect(resumed.starts).toBe(start.starts)
})
