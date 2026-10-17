import { useId } from 'react'
import { ArrowLeft } from 'lucide-react'
import { MODES, useAppearance } from './theme.ts'
import type { Mode } from './theme.ts'
import './settings.css'

type SettingsPageProps = {
  onBack: () => void
}

const CHOICES: Record<Mode, { label: string; helper?: string }> = {
  system: { label: 'System', helper: 'Follows your device' },
  light: { label: 'Light' },
  dark: { label: 'Dark' },
}

export function SettingsPage({ onBack }: SettingsPageProps) {
  const { mode, setMode } = useAppearance()
  const name = useId()

  return (
    <div className="st-page">
      <header className="top-bar">
        <div className="top-bar-start">
          <button type="button" className="ghost" onClick={onBack}>
            <ArrowLeft size={20} strokeWidth={2} aria-hidden="true" />
            Back to the conversation
          </button>
          <p className="top-bar-mark">Polaris</p>
        </div>
        <p className="top-bar-title" />
        <div className="top-bar-end" />
      </header>
      <main className="st-main">
        <div className="st-column">
          <h1 className="st-title">Settings</h1>
          <section className="st-section" aria-labelledby={`${name}-appearance`}>
            <h2 id={`${name}-appearance`} className="st-heading">
              Appearance
            </h2>
            <fieldset className="st-group">
              <legend className="st-legend">Colors</legend>
              {MODES.map((choice) => (
                <label key={choice} className="st-choice">
                  <input
                    type="radio"
                    name={name}
                    value={choice}
                    checked={mode === choice}
                    onChange={() => setMode(choice)}
                  />
                  <span className="st-radio" aria-hidden="true" />
                  <span className="st-choice-body">
                    <span>{CHOICES[choice].label}</span>
                    {CHOICES[choice].helper ? (
                      <span className="st-helper">{CHOICES[choice].helper}</span>
                    ) : null}
                  </span>
                </label>
              ))}
            </fieldset>
          </section>
        </div>
      </main>
    </div>
  )
}
