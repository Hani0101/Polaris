/**
 * Step controls for the animation player (AN-12, AN-13). Pure, so the
 * component only wires buttons and frames to it.
 *
 * Playing runs through the steps and stops at the end of the last one.
 * Next plays the next step. Back shows the picture at the end of the step
 * before, paused. Replay plays the current step again from the picture at
 * the end of the step before it. Under reduced motion nothing plays: every
 * step shows its end picture, and only Back, Next, and the step buttons move.
 */

export type PlayerState = {
  step: number
  /** Milliseconds into the current step. */
  time: number
  playing: boolean
  /** Goes up each time a step starts or is shown, so narration knows when to speak. */
  starts: number
}

export type PlayerEvent =
  | { type: 'tick'; elapsed: number }
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'next' }
  | { type: 'back' }
  | { type: 'replay' }
  | { type: 'jump'; step: number }
  | { type: 'reduce' }

export function initialPlayer(durations: number[], reduced: boolean): PlayerState {
  return reduced
    ? { step: 0, time: durations[0] ?? 0, playing: false, starts: 1 }
    : { step: 0, time: 0, playing: true, starts: 1 }
}

function shown(state: PlayerState, step: number, durations: number[]): PlayerState {
  return { step, time: durations[step], playing: false, starts: state.starts + 1 }
}

function started(state: PlayerState, step: number): PlayerState {
  return { step, time: 0, playing: true, starts: state.starts + 1 }
}

export function nextPlayer(
  state: PlayerState,
  event: PlayerEvent,
  durations: number[],
  reduced: boolean,
): PlayerState {
  const last = durations.length - 1
  if (reduced) {
    switch (event.type) {
      case 'next':
        return state.step < last ? shown(state, state.step + 1, durations) : state
      case 'back':
        return state.step > 0 ? shown(state, state.step - 1, durations) : state
      case 'jump':
        return event.step >= 0 && event.step <= last ? shown(state, event.step, durations) : state
      case 'reduce':
        return { ...state, time: durations[state.step], playing: false }
      default:
        return state
    }
  }
  switch (event.type) {
    case 'tick': {
      if (!state.playing) return state
      const time = state.time + event.elapsed
      if (time < durations[state.step]) return { ...state, time }
      if (state.step >= last) return { ...state, time: durations[state.step], playing: false }
      return started(state, state.step + 1)
    }
    case 'play': {
      if (state.playing) return state
      const ended = state.time >= durations[state.step]
      if (ended && state.step >= last) return started(state, 0)
      if (ended) return started(state, state.step + 1)
      if (state.time === 0) return { ...state, playing: true, starts: state.starts + 1 }
      return { ...state, playing: true }
    }
    case 'pause':
      return { ...state, playing: false }
    case 'next':
      return state.step < last ? started(state, state.step + 1) : state
    case 'back':
      return state.step > 0 ? shown(state, state.step - 1, durations) : state
    case 'replay':
      return started(state, state.step)
    case 'jump':
      return event.step >= 0 && event.step <= last ? started(state, event.step) : state
    case 'reduce':
      return { ...state, time: durations[state.step], playing: false }
  }
}
