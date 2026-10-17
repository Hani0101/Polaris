import { Modal } from './Modal.tsx'
import { AlertBanner } from './ui.tsx'

type DeleteDialogProps = {
  open: boolean
  /** What the session is called in the list. */
  label: string
  error: string | null
  onDelete: () => void
  onCancel: () => void
}

/** CH-11: one confirmation before a session is deleted. It says the profile keeps what it learned. */
export function DeleteDialog({ open, label, error, onDelete, onCancel }: DeleteDialogProps) {
  return (
    <Modal
      open={open}
      title="Delete this session?"
      variant="confirm"
      mainLabel="Delete session"
      onMain={onDelete}
      onCancel={onCancel}
    >
      <p>
        “{label}” will be deleted with its whiteboards, quizzes, and animations. This can’t be
        undone. What Polaris learned about you stays in your profile.
      </p>
      {error ? (
        <div className="modal-alert">
          <AlertBanner>{error}</AlertBanner>
        </div>
      ) : null}
    </Modal>
  )
}
