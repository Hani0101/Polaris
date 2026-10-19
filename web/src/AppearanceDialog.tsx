import { useId } from 'react'
import { Modal } from './chat/Modal.tsx'
import { MODES, useAppearance } from './theme.ts'
import type { Mode } from './theme.ts'
import './settings.css'

type AppearanceDialogProps = {
  open: boolean
  onClose: () => void
}

const CHOICES: Record<Mode, { label: string; helper?: string }> = {
  system: { label: 'System', helper: 'Follows your device' },
  light: { label: 'Light' },
  dark: { label: 'Dark' },
}

/** ST-02 to ST-05: the mode applies as soon as it is chosen, so the dialog only closes. */
export function AppearanceDialog({ open, onClose }: AppearanceDialogProps) {
  const { mode, setMode } = useAppearance()
  const name = useId()

  return (
    <Modal open={open} title="Appearance" cancelLabel="Close" onCancel={onClose}>
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
    </Modal>
  )
}
