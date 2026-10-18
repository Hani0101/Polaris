import { useId, useState } from 'react'
import { Atom, Shapes } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { chooseAnimationEngine } from '../api.ts'
import type { AnimationArtifact, AnimationEngine } from '../api.ts'
import { shareAnimationJob } from './animationJob.ts'
import { AlertBanner } from './ui.tsx'
import './artifacts.css'

type EngineOption = {
  engine: AnimationEngine
  label: string
  hint: string
  Icon: LucideIcon
}

const ENGINES: EngineOption[] = [
  {
    engine: 'manim',
    label: 'Animate with Manim',
    hint: 'Best for scientific topics: maths, physics, equations, and graphs.',
    Icon: Atom,
  },
  {
    engine: 'lottie',
    label: 'Animate with Lottie',
    hint: 'Best for other topics: how things work, processes, stories, and timelines.',
    Icon: Shapes,
  },
]

const CHOICE_ERROR = "Couldn't start the animation. Check your connection and try again."

/**
 * The learner picks the engine for a job that waits for a choice (AN-21).
 * Each engine is a full-width row like an answer option, with a line on what
 * it suits. Picking one starts the job; while that request runs, both rows
 * are locked so a second click cannot start a second writer.
 */
export function EnginePicker({ job }: { job: AnimationArtifact }) {
  const questionId = useId()
  const [picked, setPicked] = useState<AnimationEngine | null>(null)
  const [failed, setFailed] = useState(false)

  function choose(engine: AnimationEngine) {
    if (picked) return
    setPicked(engine)
    setFailed(false)
    chooseAnimationEngine(job.session_id, job.id, engine)
      .then((next) => shareAnimationJob(next))
      .catch(() => {
        setPicked(null)
        setFailed(true)
      })
  }

  return (
    <div className="engine-picker" role="group" aria-labelledby={questionId}>
      <p id={questionId} className="engine-picker-question">
        How should Polaris draw this animation?
      </p>
      {ENGINES.map(({ engine, label, hint, Icon }) => {
        const isPicked = picked === engine
        return (
          <button
            key={engine}
            type="button"
            className={isPicked ? 'engine-option is-picked' : 'engine-option'}
            aria-disabled={picked !== null}
            aria-busy={isPicked}
            onClick={() => choose(engine)}
          >
            <span className="engine-option-label">
              <Icon size={20} strokeWidth={2} aria-hidden="true" />
              {label}
            </span>
            <span className="engine-option-hint">
              {isPicked ? 'Starting the animation' : hint}
            </span>
          </button>
        )
      })}
      {failed ? <AlertBanner>{CHOICE_ERROR}</AlertBanner> : null}
    </div>
  )
}
