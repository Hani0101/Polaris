import { useId, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Check, Paperclip } from 'lucide-react'
import { RESOURCE_ACCEPT } from '../api.ts'
import { deckRequest } from '../deck.ts'
import { Modal } from './Modal.tsx'
import { fileProblem, useResources } from './resources.tsx'
import { AlertBanner, CloseIcon, IconButton } from './ui.tsx'
import '../deck.css'

type CreateFlashcardsDialogProps = {
  open: boolean
  onCancel: () => void
  /** Sends the learner turn that asks for the deck (FC-01). */
  onSubmit: (message: string) => void
}

/**
 * FC-03: what the flashcards should be about. Typed text, attached files, and
 * resources already in the session, in any mix, but at least one. An attached
 * file goes through the Resources tab's add path and becomes a resource.
 */
export function CreateFlashcardsDialog({ open, onCancel, onSubmit }: CreateFlashcardsDialogProps) {
  const { resources, addFile } = useResources()
  const [topic, setTopic] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [picked, setPicked] = useState<Set<string>>(() => new Set())
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [wasOpen, setWasOpen] = useState(open)
  const topicId = useId()
  const helpId = useId()
  const picker = useRef<HTMLInputElement>(null)

  // Each opening starts empty.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setTopic('')
      setFiles([])
      setPicked(new Set())
      setError(null)
    }
  }

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const chosen = Array.from(event.target.files ?? [])
    event.target.value = ''
    const next = [...files]
    for (const file of chosen) {
      // The Resources tab's early check, so a refusal names the same reason (RS-19).
      const problem = fileProblem(file, resources.length + next.length)
      if (problem) {
        setError(problem)
        break
      }
      next.push(file)
    }
    setFiles(next)
  }

  function toggle(resourceId: string) {
    setError(null)
    setPicked((current) => {
      const next = new Set(current)
      if (next.has(resourceId)) next.delete(resourceId)
      else next.add(resourceId)
      return next
    })
  }

  async function create() {
    if (busy) return
    if (!topic.trim() && files.length === 0 && picked.size === 0) {
      setError('Type what the flashcards should be about, attach a file, or pick a resource.')
      return
    }
    setBusy(true)
    setError(null)
    const names = resources.filter((item) => picked.has(item.id)).map((item) => item.name)
    let remaining = files
    try {
      for (const file of files) {
        const added = await addFile(file)
        names.push(added.name)
        remaining = remaining.slice(1)
        // An added file is now a resource; keep it picked if the next one is refused.
        setPicked((current) => new Set(current).add(added.id))
      }
    } catch (caught) {
      setFiles(remaining)
      setError(
        caught instanceof Error && caught.message
          ? caught.message
          : `Couldn't add ${remaining[0]?.name ?? 'that file'}. Try again.`,
      )
      setBusy(false)
      return
    }
    setBusy(false)
    onSubmit(deckRequest(topic, names))
  }

  return (
    <Modal
      open={open}
      title="Create flashcards"
      mainLabel={busy ? 'Adding files' : 'Create flashcards'}
      onMain={() => void create()}
      onCancel={onCancel}
    >
      <div className="fc-dialog">
        <div className="field">
          <label className="field-label" htmlFor={topicId}>
            What should the flashcards be about?
          </label>
          <textarea
            id={topicId}
            className="text-area"
            rows={3}
            value={topic}
            aria-describedby={helpId}
            onChange={(event) => {
              setTopic(event.target.value)
              setError(null)
            }}
          />
          <p className="field-help" id={helpId}>
            Type a topic, attach files, or pick resources. Polaris makes cards only from this
            session’s turns and resources.
          </p>
        </div>

        <div className="field">
          <div>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => picker.current?.click()}
            >
              <Paperclip size={20} strokeWidth={2} aria-hidden="true" />
              Attach files
            </button>
          </div>
          <input
            ref={picker}
            type="file"
            accept={RESOURCE_ACCEPT}
            multiple
            hidden
            onChange={onPick}
          />
          {files.length > 0 ? (
            <ul className="fc-files" aria-label="Files to add">
              {files.map((file, index) => (
                <li key={`${file.name}-${index}`} className="fc-file">
                  <span>{file.name}</span>
                  <IconButton
                    label={`Remove ${file.name}`}
                    size="sm"
                    disabled={busy}
                    onClick={() => setFiles(files.filter((_item, at) => at !== index))}
                  >
                    <CloseIcon />
                  </IconButton>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {resources.length > 0 ? (
          <fieldset className="fc-picks">
            <legend>Resources in this session</legend>
            {resources.map((resource) => (
              <label key={resource.id} className="fc-choice">
                <input
                  type="checkbox"
                  checked={picked.has(resource.id)}
                  disabled={busy}
                  onChange={() => toggle(resource.id)}
                />
                <span className="fc-check" aria-hidden="true">
                  <Check size={16} strokeWidth={2} />
                </span>
                <span className="fc-choice-name">{resource.name}</span>
              </label>
            ))}
          </fieldset>
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
