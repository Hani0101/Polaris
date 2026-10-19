import { useId, type KeyboardEvent } from 'react'
import { Modal } from './Modal.tsx'
import { AlertBanner } from './ui.tsx'

export const MAX_NAME_LENGTH = 80

type RenameDialogProps = {
  open: boolean
  value: string
  error: string | null
  onChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
}

/** CH-06, CH-07: one text input in a modal. A blank name removes the name. */
export function RenameDialog({ open, value, error, onChange, onSave, onCancel }: RenameDialogProps) {
  const inputId = useId()
  const helpId = useId()

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return
    event.preventDefault()
    onSave()
  }

  return (
    <Modal
      open={open}
      title="Rename session"
      mainLabel="Rename"
      onMain={onSave}
      onCancel={onCancel}
    >
      <div className="field">
        <label className="field-label" htmlFor={inputId}>
          Session name
        </label>
        <input
          id={inputId}
          type="text"
          className="text-input"
          value={value}
          maxLength={MAX_NAME_LENGTH}
          autoComplete="off"
          aria-describedby={helpId}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <p id={helpId} className="field-help">
          Leave it blank to use your first message.
        </p>
      </div>
      {error ? (
        <div className="modal-alert">
          <AlertBanner>{error}</AlertBanner>
        </div>
      ) : null}
    </Modal>
  )
}
