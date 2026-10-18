import { useId, useState } from 'react'
import type { AnimationEngine, AnimationSettings } from '../api.ts'
import { ENGINES, defaultSettings, engineChoice, isLegal } from '../animation/settings.ts'
import type { Choice } from '../animation/settings.ts'
import { Modal } from './Modal.tsx'
import { AlertBanner } from './ui.tsx'
import '../settings.css'
import './artifacts.css'

type AnimationSettingsDialogProps = {
  open: boolean
  /**
   * create: from the Tools panel, with a field for what the animation shows.
   * choose: for a job the chat already started, which waits for these settings.
   */
  mode: 'create' | 'choose'
  onCancel: () => void
  /** Resolves when the settings are taken; a rejection shows its message in the dialog. */
  onSubmit: (settings: AnimationSettings, topic: string) => Promise<void> | void
}

const NO_ENGINE = 'Choose Manim or Lottie.'
const NO_TOPIC = 'Type what the animation should show.'
const FALLBACK = "Couldn't start the animation. Check your connection and try again."

/**
 * AN-21, AN-26: the engine, then the quality and frame rate that engine offers.
 * Every choice is a radio, and switching engine resets the other two to that
 * engine's defaults, so only legal settings can be sent.
 */
export function AnimationSettingsDialog({
  open,
  mode,
  onCancel,
  onSubmit,
}: AnimationSettingsDialogProps) {
  const [topic, setTopic] = useState('')
  const [settings, setSettings] = useState<AnimationSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [wasOpen, setWasOpen] = useState(open)
  const name = useId()
  const topicId = useId()
  const topicHelpId = useId()

  // Each opening starts empty.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setTopic('')
      setSettings(null)
      setError(null)
      setBusy(false)
    }
  }

  function pickEngine(engine: AnimationEngine) {
    setError(null)
    setSettings((current) => (current?.engine === engine ? current : defaultSettings(engine)))
  }

  async function submit() {
    if (busy) return
    if (mode === 'create' && !topic.trim()) {
      setError(NO_TOPIC)
      return
    }
    if (!settings || !isLegal(settings)) {
      setError(NO_ENGINE)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(settings, topic.trim())
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : FALLBACK)
      setBusy(false)
    }
  }

  const choice = settings ? engineChoice(settings.engine) : null
  const create = mode === 'create'
  const mainLabel = busy ? 'Starting' : create ? 'Create animation' : 'Start animation'

  return (
    <Modal
      open={open}
      title={create ? 'Create animation' : 'Choose how to animate'}
      mainLabel={mainLabel}
      onMain={() => void submit()}
      onCancel={onCancel}
      cancelLabel={create ? 'Cancel' : 'Not now'}
    >
      <div className="as-dialog">
        {create ? (
          <div className="field">
            <label className="field-label" htmlFor={topicId}>
              What should the animation show?
            </label>
            <textarea
              id={topicId}
              className="text-area"
              rows={3}
              value={topic}
              disabled={busy}
              aria-describedby={topicHelpId}
              onChange={(event) => {
                setTopic(event.target.value)
                setError(null)
              }}
            />
            <p className="field-help" id={topicHelpId}>
              Polaris turns this into a step-by-step animation for this session.
            </p>
          </div>
        ) : (
          <p className="as-intro">
            Pick the engine, then how sharp and smooth the animation should be. Higher settings
            take longer to make.
          </p>
        )}

        <RadioGroup
          legend="Engine"
          name={`${name}-engine`}
          choices={ENGINES.map((item) => ({
            value: item.engine,
            label: item.label,
            helper: item.helper,
          }))}
          value={settings?.engine ?? null}
          disabled={busy}
          onChange={pickEngine}
        />

        {settings && choice ? (
          <>
            <RadioGroup
              legend="Quality"
              name={`${name}-quality`}
              choices={choice.qualities}
              value={settings.quality}
              disabled={busy}
              onChange={(quality) => setSettings({ ...settings, quality })}
            />
            <RadioGroup
              legend="Frame rate"
              name={`${name}-fps`}
              choices={choice.frameRates}
              value={settings.fps}
              disabled={busy}
              onChange={(fps) => setSettings({ ...settings, fps })}
            />
          </>
        ) : null}

        {error ? (
          <div className="modal-alert">
            <AlertBanner>{error}</AlertBanner>
          </div>
        ) : null}
      </div>
    </Modal>
  )
}

function RadioGroup<T extends string | number>({
  legend,
  name,
  choices,
  value,
  disabled,
  onChange,
}: {
  legend: string
  name: string
  choices: Choice<T>[]
  value: T | null
  disabled: boolean
  onChange: (value: T) => void
}) {
  return (
    <fieldset className="st-group">
      <legend className="st-legend">{legend}</legend>
      {choices.map((item) => (
        <label key={String(item.value)} className="st-choice">
          <input
            type="radio"
            name={name}
            value={String(item.value)}
            checked={value === item.value}
            disabled={disabled}
            onChange={() => onChange(item.value)}
          />
          <span className="st-radio" aria-hidden="true" />
          <span className="st-choice-body">
            <span>{item.label}</span>
            {item.helper ? <span className="st-helper">{item.helper}</span> : null}
          </span>
        </label>
      ))}
    </fieldset>
  )
}
