import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { Check, Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react'
import type { AnimationItem } from 'lottie-web'
import { IconButton } from '../chat/ui.tsx'
import { readableVideoDescription } from './lottieVideo.ts'
import type { LottieVideo } from './lottieVideo.ts'
import { speak, stopSpeaking, useLocalVoice, useNarrationChoice } from './narration.ts'
import type { AskAboutStep } from './ScenePlayer.tsx'
import './scene.css'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'
const FONT_LOADS = [
  "400 40px 'Atkinson Hyperlegible Next'",
  "700 40px 'Atkinson Hyperlegible Next'",
  "400 40px 'Atkinson Hyperlegible Mono'",
]

type LottieModule = typeof import('lottie-web')['default']
let lottieModule: Promise<LottieModule> | null = null

/** lottie-web's SVG build without expression support, loaded on first use. */
function loadLottie(): Promise<LottieModule> {
  lottieModule ??= import('lottie-web/build/player/lottie_light').then(
    (module) => module.default as unknown as LottieModule,
  )
  return lottieModule
}

async function loadFonts(): Promise<void> {
  if (typeof document === 'undefined' || !document.fonts) return
  await Promise.all(FONT_LOADS.map((font) => document.fonts.load(font).catch(() => [])))
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

type LottiePlayerProps = {
  video: LottieVideo
  jobId: string
  onAskAboutStep?: (ask: AskAboutStep) => void
}

/**
 * Plays a Lottie video scene by scene. Scenes run on into each other like
 * one video; the learner can pause, go back, skip, replay a scene, or jump
 * with the step dots. Under reduced motion each scene shows its last frame.
 */
export function LottiePlayer({ video, jobId, onAskAboutStep }: LottiePlayerProps) {
  const reduced = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(!reduced)
  const [ended, setEnded] = useState(false)
  // Bumped to restart the current scene from frame 0.
  const [starts, setStarts] = useState(0)
  const [progress, setProgress] = useState(0)
  const [failed, setFailed] = useState(false)
  const container = useRef<HTMLDivElement>(null)
  const anim = useRef<AnimationItem | null>(null)
  const playingRef = useRef(playing)
  const voice = useLocalVoice()
  const [narrate, setNarrate] = useNarrationChoice()
  const narrating = narrate && voice !== null

  useEffect(() => {
    playingRef.current = playing
  }, [playing])

  const total = video.scenes.length
  const scene = video.scenes[index]
  const label = useMemo(() => readableVideoDescription(video), [video])

  // Mount the current scene. A new scene or a restart builds a fresh player.
  useEffect(() => {
    const box = container.current
    if (!box) return
    let cancelled = false
    let item: AnimationItem | null = null
    setProgress(0)
    Promise.all([loadLottie(), loadFonts()])
      .then(([lottie]) => {
        if (cancelled) return
        item = lottie.loadAnimation({
          container: box,
          renderer: 'svg',
          loop: false,
          autoplay: false,
          animationData: structuredClone(scene.lottie),
          rendererSettings: { preserveAspectRatio: 'xMidYMid meet' },
        })
        anim.current = item
        const frames = Math.max(1, item.totalFrames - 1)
        item.addEventListener('enterFrame', () => {
          if (item) setProgress(Math.min(1, item.currentFrame / frames))
        })
        item.addEventListener('complete', () => {
          setProgress(1)
          if (!playingRef.current) return
          if (index < total - 1) {
            setIndex(index + 1)
          } else {
            setPlaying(false)
            setEnded(true)
          }
        })
        item.addEventListener('DOMLoaded', () => {
          if (!item) return
          if (reduced) {
            item.goToAndStop(item.totalFrames - 1, true)
            setProgress(1)
          } else if (playingRef.current) {
            item.play()
          } else {
            item.goToAndStop(0, true)
          }
        })
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
      item?.destroy()
      if (anim.current === item) anim.current = null
    }
    // `playing` is read through a ref so pausing does not rebuild the scene.
  }, [scene, index, total, reduced, starts])

  // Narration reads the caption each time a scene starts (AN-18).
  useEffect(() => {
    if (narrating && voice && !reduced) speak(scene.caption, voice)
  }, [index, starts, narrating, voice, scene.caption, reduced])

  useEffect(() => () => stopSpeaking(), [])

  function go(next: number) {
    if (narrating) stopSpeaking()
    setEnded(false)
    if (next === index) {
      setStarts((count) => count + 1)
    } else {
      setIndex(next)
    }
    if (!reduced) setPlaying(true)
  }

  function play() {
    if (ended) {
      setEnded(false)
      setPlaying(true)
      if (index === 0) setStarts((count) => count + 1)
      else setIndex(0)
      return
    }
    setPlaying(true)
    const item = anim.current
    if (!item) return
    if (item.currentFrame >= item.totalFrames - 1) {
      item.goToAndPlay(0, true)
    } else {
      item.play()
    }
  }

  function pause() {
    if (narrating) stopSpeaking()
    setPlaying(false)
    anim.current?.pause()
  }

  function toggleNarration(on: boolean) {
    if (!on) stopSpeaking()
    setNarrate(on)
  }

  return (
    <div className="an-scene-player">
      <div
        className="an-scene-frame an-lottie-frame"
        style={{ background: video.background }}
        role="img"
        aria-label={label}
      >
        <div ref={container} className="an-lottie" />
        {failed ? (
          <p className="an-lottie-error">This animation could not be drawn.</p>
        ) : null}
      </div>
      <div className="an-lottie-progress" aria-hidden="true">
        {video.scenes.map((item, position) => (
          <span key={item.id} className="an-lottie-track">
            <span
              className="an-lottie-fill"
              style={{
                transform: `scaleX(${position < index ? 1 : position === index ? progress : 0})`,
              }}
            />
          </span>
        ))}
      </div>
      <div className="an-caption" aria-live="polite" aria-atomic="true">
        <p className="an-caption-count">
          Step {index + 1} of {total}
        </p>
        <p className="an-caption-text">{scene.caption}</p>
      </div>
      <div className="an-controls">
        <div className="an-transport">
          <IconButton label="Back" onClick={() => go(index - 1)} disabled={index === 0}>
            <SkipBack size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
          {reduced ? null : (
            <>
              {playing ? (
                <IconButton label="Pause" onClick={pause}>
                  <Pause size={20} strokeWidth={2} aria-hidden="true" />
                </IconButton>
              ) : (
                <IconButton label={ended ? 'Play from the start' : 'Play'} onClick={play}>
                  <Play size={20} strokeWidth={2} aria-hidden="true" />
                </IconButton>
              )}
              <IconButton label="Replay step" onClick={() => go(index)}>
                <RotateCcw size={20} strokeWidth={2} aria-hidden="true" />
              </IconButton>
            </>
          )}
          <IconButton label="Next" onClick={() => go(index + 1)} disabled={index >= total - 1}>
            <SkipForward size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
        </div>
        <ol className="an-steps" aria-label="Steps">
          {video.scenes.map((item, position) => {
            const current = position === index
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={current ? 'an-step is-current' : 'an-step'}
                  aria-label={`Step ${position + 1} of ${total}`}
                  aria-current={current ? 'step' : undefined}
                  onClick={() => go(position)}
                >
                  {position + 1}
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
                  stepId: scene.id,
                  stepNumber: index + 1,
                  caption: scene.caption,
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
