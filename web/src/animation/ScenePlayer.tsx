import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { Check, Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react'
import { IconButton } from '../chat/ui.tsx'
import { readableDescription } from './format.ts'
import type { Animation } from './format.ts'
import { speak, stopSpeaking, useLocalVoice, useNarrationChoice } from './narration.ts'
import { stateAt } from './playback.ts'
import { initialPlayer, nextPlayer } from './playerState.ts'
import type { PlayerEvent, PlayerState } from './playerState.ts'
import { Scene } from './Scene.tsx'
import './scene.css'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'
// A frame after a long pause (a hidden tab) counts as this much, so a step is not skipped.
const MAX_FRAME_MS = 250

export type AskAboutStep = {
  jobId: string
  stepId: string
  stepNumber: number
  caption: string
}

type ScenePlayerProps = {
  animation: Animation
  jobId: string
  onAskAboutStep?: (ask: AskAboutStep) => void
}

function useReducedMotion(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const media = window.matchMedia(REDUCED_MOTION_QUERY)
      media.addEventListener?.('change', notify)
      return () => media.removeEventListener?.('change', notify)
    },
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
  )
}

/**
 * Plays an animation in steps (AN-12). Each step's caption stays on screen
 * and a screen reader announces it (AN-15). Under reduced motion every step
 * shows its finished picture and only Back and Next move (AN-13).
 */
export function ScenePlayer({ animation, jobId, onAskAboutStep }: ScenePlayerProps) {
  const reduced = useReducedMotion()
  const durations = useMemo(() => animation.steps.map((step) => step.duration_ms), [animation])
  const [player, setPlayer] = useState<PlayerState>(() => initialPlayer(durations, reduced))
  const voice = useLocalVoice()
  const [narrate, setNarrate] = useNarrationChoice()
  const narrating = narrate && voice !== null

  const send = useCallback(
    (event: PlayerEvent) =>
      setPlayer((current) => nextPlayer(current, event, durations, reduced)),
    [durations, reduced],
  )

  // When the system starts asking for reduced motion, stop on the step's end picture.
  const [wasReduced, setWasReduced] = useState(reduced)
  if (reduced !== wasReduced) {
    setWasReduced(reduced)
    if (reduced) setPlayer((current) => nextPlayer(current, { type: 'reduce' }, durations, true))
  }

  useEffect(() => {
    if (!player.playing || reduced || typeof window.requestAnimationFrame !== 'function') return
    let frame = 0
    let last: number | null = null
    const loop = (now: number) => {
      if (last !== null) send({ type: 'tick', elapsed: Math.min(now - last, MAX_FRAME_MS) })
      last = now
      frame = window.requestAnimationFrame(loop)
    }
    frame = window.requestAnimationFrame(loop)
    return () => window.cancelAnimationFrame(frame)
  }, [player.playing, reduced, send])

  const step = animation.steps[player.step]
  const total = animation.steps.length

  // Narration reads the caption each time a step starts (AN-18).
  useEffect(() => {
    if (narrating && voice) speak(step.caption, voice)
  }, [player.starts, narrating, voice, step.caption])

  const narratingRef = useRef(narrating)
  useEffect(() => {
    narratingRef.current = narrating
  }, [narrating])
  useEffect(() => {
    return () => {
      if (narratingRef.current) stopSpeaking()
    }
  }, [])

  const scene = useMemo(
    () => stateAt(animation, player.step, player.time),
    [animation, player.step, player.time],
  )
  const label = useMemo(() => readableDescription(animation), [animation])
  const ended = player.step === total - 1 && player.time >= step.duration_ms

  function control(event: PlayerEvent) {
    if (narrating && event.type !== 'play') stopSpeaking()
    send(event)
  }

  function toggleNarration(on: boolean) {
    if (!on) stopSpeaking()
    setNarrate(on)
  }

  return (
    <div className="an-scene-player">
      <div className="an-scene-frame">
        <Scene animation={animation} scene={scene} label={label} />
      </div>
      <div className="an-caption" aria-live="polite" aria-atomic="true">
        <p className="an-caption-count">
          Step {player.step + 1} of {total}
        </p>
        <p className="an-caption-text">{step.caption}</p>
      </div>
      <div className="an-controls">
        <div className="an-transport">
          <IconButton
            label="Back"
            onClick={() => control({ type: 'back' })}
            disabled={player.step === 0}
          >
            <SkipBack size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
          {reduced ? null : (
            <>
              {player.playing ? (
                <IconButton label="Pause" onClick={() => control({ type: 'pause' })}>
                  <Pause size={20} strokeWidth={2} aria-hidden="true" />
                </IconButton>
              ) : (
                <IconButton
                  label={ended ? 'Play from the start' : 'Play'}
                  onClick={() => control({ type: 'play' })}
                >
                  <Play size={20} strokeWidth={2} aria-hidden="true" />
                </IconButton>
              )}
              <IconButton label="Replay step" onClick={() => control({ type: 'replay' })}>
                <RotateCcw size={20} strokeWidth={2} aria-hidden="true" />
              </IconButton>
            </>
          )}
          <IconButton
            label="Next"
            onClick={() => control({ type: 'next' })}
            disabled={player.step >= total - 1}
          >
            <SkipForward size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
        </div>
        <ol className="an-steps" aria-label="Steps">
          {animation.steps.map((item, index) => {
            const current = index === player.step
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={current ? 'an-step is-current' : 'an-step'}
                  aria-label={`Step ${index + 1} of ${total}`}
                  aria-current={current ? 'step' : undefined}
                  onClick={() => control({ type: 'jump', step: index })}
                >
                  {index + 1}
                </button>
              </li>
            )
          })}
        </ol>
      </div>
      {voice !== null || onAskAboutStep ? (
        <div className="an-extras">
          {voice !== null ? (
            <label className="an-narration">
              <input
                type="checkbox"
                className="visually-hidden"
                checked={narrate}
                onChange={(event) => toggleNarration(event.target.checked)}
              />
              <span className="an-checkbox" aria-hidden="true">
                {narrate ? <Check size={16} strokeWidth={2} /> : null}
              </span>
              Read captions aloud
            </label>
          ) : null}
          {onAskAboutStep ? (
            <button
              type="button"
              className="secondary"
              onClick={() =>
                onAskAboutStep({
                  jobId,
                  stepId: step.id,
                  stepNumber: player.step + 1,
                  caption: step.caption,
                })
              }
            >
              Ask about this step
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
