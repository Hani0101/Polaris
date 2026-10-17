import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { Check, Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react'
import { animationManimUrl } from '../animationPath.ts'
import { IconButton } from '../chat/ui.tsx'
import { speak, stopSpeaking, useLocalVoice, useNarrationChoice } from './narration.ts'
import type { ManimManifest } from './manim.ts'
import type { AskAboutStep } from './ScenePlayer.tsx'
import './scene.css'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

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

type VideoStepPlayerProps = {
  manifest: ManimManifest
  sessionId: string
  jobId: string
  onAskAboutStep?: (ask: AskAboutStep) => void
}

function clipName(index: number): string {
  return String(index + 1).padStart(2, '0')
}

/**
 * Plays a Manim video one step at a time, with the same controls as the
 * Polaris player (AN-12). Under reduced motion each step shows its last
 * frame and only Back and Next move (AN-13). Captions are announced (AN-15).
 */
export function VideoStepPlayer({ manifest, sessionId, jobId, onAskAboutStep }: VideoStepPlayerProps) {
  const reduced = useReducedMotion()
  const [step, setStep] = useState(0)
  // "end" shows the step's last frame, as Back does in the Polaris player.
  const [mode, setMode] = useState<'play' | 'pause' | 'end'>(reduced ? 'end' : 'play')
  const [starts, setStarts] = useState(1)
  const video = useRef<HTMLVideoElement>(null)
  const voice = useLocalVoice()
  const [narrate, setNarrate] = useNarrationChoice()
  const narrating = narrate && voice !== null
  const total = manifest.steps.length
  const current = manifest.steps[step]
  const url = (name: string) => animationManimUrl(sessionId, jobId, name)
  const clip = url(`steps/step-${clipName(step)}.mp4`)
  const poster = url(`posters/step-${clipName(step)}.png`)
  const showPoster = reduced || mode === 'end'

  const [wasReduced, setWasReduced] = useState(reduced)
  if (reduced !== wasReduced) {
    setWasReduced(reduced)
    if (reduced) setMode('end')
  }

  useEffect(() => {
    const element = video.current
    if (!element || showPoster) return
    if (mode === 'play') {
      // play() can refuse, for example when the browser blocks autoplay.
      element.play()?.catch(() => setMode('pause'))
    } else {
      element.pause()
    }
  }, [mode, showPoster, clip, starts])

  useEffect(() => {
    if (narrating && voice) speak(current.caption, voice)
  }, [starts, narrating, voice, current.caption])

  useEffect(() => () => stopSpeaking(), [])

  function go(index: number, next: 'play' | 'end') {
    if (narrating) stopSpeaking()
    setStep(index)
    setMode(reduced ? 'end' : next)
    setStarts((count) => count + 1)
  }

  function ended() {
    if (step < total - 1) go(step + 1, 'play')
    else setMode('end')
  }

  function replay() {
    const element = video.current
    if (element) element.currentTime = 0
    setMode('play')
    setStarts((count) => count + 1)
  }

  const finished = step === total - 1 && mode === 'end'

  return (
    <div className="an-scene-player">
      <div className="an-scene-frame" role="img" aria-label={`${manifest.title}. ${manifest.description}`}>
        {showPoster ? (
          <img className="an-video" src={poster} alt="" />
        ) : (
          <video
            key={`${clip}-${starts}`}
            ref={video}
            className="an-video"
            src={clip}
            poster={step > 0 ? url(`posters/step-${clipName(step - 1)}.png`) : undefined}
            muted
            playsInline
            preload="auto"
            onEnded={ended}
            aria-hidden="true"
          />
        )}
      </div>
      <div className="an-caption" aria-live="polite" aria-atomic="true">
        <p className="an-caption-count">
          Step {step + 1} of {total}
        </p>
        <p className="an-caption-text">{current.caption}</p>
      </div>
      <div className="an-controls">
        <div className="an-transport">
          <IconButton label="Back" onClick={() => go(step - 1, 'end')} disabled={step === 0}>
            <SkipBack size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
          {reduced ? null : (
            <>
              {mode === 'play' ? (
                <IconButton label="Pause" onClick={() => setMode('pause')}>
                  <Pause size={20} strokeWidth={2} aria-hidden="true" />
                </IconButton>
              ) : (
                <IconButton
                  label={finished ? 'Play from the start' : 'Play'}
                  onClick={() => (finished ? go(0, 'play') : mode === 'end' ? replay() : setMode('play'))}
                >
                  <Play size={20} strokeWidth={2} aria-hidden="true" />
                </IconButton>
              )}
              <IconButton label="Replay step" onClick={replay}>
                <RotateCcw size={20} strokeWidth={2} aria-hidden="true" />
              </IconButton>
            </>
          )}
          <IconButton label="Next" onClick={() => go(step + 1, 'play')} disabled={step >= total - 1}>
            <SkipForward size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
        </div>
        <ol className="an-steps" aria-label="Steps">
          {manifest.steps.map((item, index) => {
            const isCurrent = index === step
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={isCurrent ? 'an-step is-current' : 'an-step'}
                  aria-label={`Step ${index + 1} of ${total}`}
                  aria-current={isCurrent ? 'step' : undefined}
                  onClick={() => go(index, 'play')}
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
                onChange={(event) => {
                  if (!event.target.checked) stopSpeaking()
                  setNarrate(event.target.checked)
                }}
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
                  stepId: current.id,
                  stepNumber: step + 1,
                  caption: current.caption,
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
