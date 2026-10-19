import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { LoaderCircle, Pencil, Trash2 } from 'lucide-react'
import { addFact, editFact, listFacts, MAX_FACT_LENGTH, removeFact } from './api.ts'
import type { FactKind, ProfileFact } from './api.ts'
import { useSignIn } from './auth.ts'
import { Modal } from './chat/Modal.tsx'
import { AlertBanner, AlertIcon, EmptyState, IconButton } from './chat/ui.tsx'
import './settings.css'
// The button spinner (DESIGN.md 7, Loading) is defined with the sign-in page.
import './signIn.css'

type ProfileDialogProps = {
  open: boolean
  onClose: () => void
  /** Closes the dialog and opens the sign-in page, which the profile needs (AU-12). */
  onSignIn: () => void
}

// The order the teaching agent reads facts in (FACT_KINDS in api/polaris/profile.py).
const GROUPS: { kind: FactKind; heading: string }[] = [
  { kind: 'goal', heading: 'What you want to learn' },
  { kind: 'taught', heading: 'How you like to be taught' },
  { kind: 'struggle', heading: 'Where you find it hard' },
  { kind: 'can_do', heading: 'What you can already do' },
  { kind: 'milestone', heading: 'What you have understood' },
  { kind: 'unsorted', heading: 'Other things' },
]

type Loaded =
  | { status: 'loading' }
  | { status: 'failed'; error: string }
  | { status: 'ready'; facts: ProfileFact[] }

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function BusyButton({
  busy,
  className,
  children,
}: {
  busy: boolean
  className?: string
  children: string
}) {
  return (
    <button
      type="submit"
      className={className ? `st-busy ${className}` : 'st-busy'}
      aria-disabled={busy || undefined}
      aria-busy={busy || undefined}
    >
      <span className={busy ? 'st-busy-label is-hidden' : 'st-busy-label'}>{children}</span>
      {busy ? (
        <span className="button-spinner" role="status">
          <LoaderCircle size={20} strokeWidth={2} aria-hidden="true" />
          <span className="visually-hidden">Saving</span>
        </span>
      ) : null}
    </button>
  )
}

function FieldError({ id, message }: { id: string; message: string }) {
  return (
    <p id={id} className="field-error">
      <AlertIcon />
      {message}
    </p>
  )
}

/**
 * PR-11: what Polaris knows about the learner, as bullet points they can
 * change. Signed-in only (AU-12). The next reply reads every change (PR-01).
 * The facts load each time the dialog opens, since the dialog mounts them then.
 */
export function ProfileDialog({ open, onClose, onSignIn }: ProfileDialogProps) {
  return (
    <Modal open={open} title="Profile" cancelLabel="Close" onCancel={onClose}>
      <ProfileFacts onSignIn={onSignIn} />
    </Modal>
  )
}

function ProfileFacts({ onSignIn }: { onSignIn: () => void }) {
  const account = useSignIn()
  const name = useId()
  const listRef = useRef<HTMLDivElement>(null)
  const addRef = useRef<HTMLInputElement>(null)
  // The fact whose Change button takes focus after the list renders again.
  const focusFact = useRef<string | null>(null)
  // After a remove, the add field takes focus once the confirm has let go of it.
  const focusAdd = useRef(false)
  const removeBusy = useRef(false)

  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [editing, setEditing] = useState<{ id: string; draft: string } | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState<ProfileFact | null>(null)
  const [removeError, setRemoveError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const [attempt, setAttempt] = useState(0)

  const signedIn = account.status === 'signed-in'

  useEffect(() => {
    if (!signedIn) return
    const controller = new AbortController()
    listFacts(controller.signal).then(
      (facts) => setLoaded({ status: 'ready', facts }),
      (caught: unknown) => {
        if (controller.signal.aborted) return
        setLoaded({
          status: 'failed',
          error: errorText(caught, "Couldn't load your profile."),
        })
      },
    )
    return () => controller.abort()
  }, [signedIn, attempt])

  useEffect(() => {
    if (focusAdd.current && removing === null) {
      focusAdd.current = false
      addRef.current?.focus()
      return
    }
    const id = focusFact.current
    if (id === null || loaded.status !== 'ready' || editing !== null) return
    focusFact.current = null
    listRef.current
      ?.querySelector<HTMLButtonElement>(`li[data-fact-id="${id}"] .st-fact-edit button`)
      ?.focus()
  }, [loaded, editing, removing])

  function startEdit(fact: ProfileFact) {
    setEditing({ id: fact.id, draft: fact.text })
    setEditError(null)
  }

  function cancelEdit() {
    if (editing) focusFact.current = editing.id
    setEditing(null)
    setEditError(null)
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editing || saving) return
    if (!editing.draft.trim()) {
      setEditError('Type something, or remove this instead.')
      return
    }
    setSaving(true)
    try {
      const written = await editFact(editing.id, editing.draft)
      focusFact.current = written.fact.id
      setLoaded({ status: 'ready', facts: written.facts })
      setEditing(null)
      setEditError(null)
      setAnnouncement('Saved. Polaris uses this from your next message.')
    } catch (caught) {
      setEditError(errorText(caught, "Couldn't save the change. Try again."))
    } finally {
      setSaving(false)
    }
  }

  function onEditKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Escape') return
    event.preventDefault()
    cancelEdit()
  }

  async function confirmRemove() {
    if (!removing || removeBusy.current) return
    removeBusy.current = true
    try {
      const body = await removeFact(removing.id)
      focusAdd.current = true
      setLoaded({ status: 'ready', facts: body.facts })
      setRemoving(null)
      setRemoveError(null)
      setAnnouncement('Removed. Polaris no longer uses it.')
    } catch (caught) {
      setRemoveError(errorText(caught, "Couldn't remove it. Try again."))
    } finally {
      removeBusy.current = false
    }
  }

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (adding) return
    if (!draft.trim()) {
      setAddError('Type something to add.')
      addRef.current?.focus()
      return
    }
    setAdding(true)
    try {
      const written = await addFact(draft)
      setLoaded({ status: 'ready', facts: written.facts })
      setDraft('')
      setAddError(null)
      setAnnouncement('Added. Polaris uses this from your next message.')
    } catch (caught) {
      setAddError(errorText(caught, "Couldn't add it. Try again."))
      addRef.current?.focus()
    } finally {
      setAdding(false)
    }
  }

  function renderFact(fact: ProfileFact) {
    if (editing?.id === fact.id) {
      const inputId = `${name}-edit`
      const errorId = `${name}-edit-error`
      return (
        <li key={fact.id} className="st-fact is-editing" data-fact-id={fact.id}>
          <form className="st-fact-form" onSubmit={(event) => void saveEdit(event)} noValidate>
            <div className="field">
              <label className="field-label" htmlFor={inputId}>
                Change this
              </label>
              <input
                id={inputId}
                type="text"
                className={editError ? 'text-input is-error' : 'text-input'}
                value={editing.draft}
                maxLength={MAX_FACT_LENGTH}
                autoComplete="off"
                autoFocus
                aria-invalid={editError ? true : undefined}
                aria-describedby={editError ? errorId : undefined}
                onChange={(event) => {
                  setEditing({ id: fact.id, draft: event.target.value })
                  setEditError(null)
                }}
                onKeyDown={onEditKeyDown}
              />
              {editError ? <FieldError id={errorId} message={editError} /> : null}
            </div>
            <div className="st-actions">
              <BusyButton busy={saving}>Save change</BusyButton>
              <button type="button" className="secondary" onClick={cancelEdit}>
                Cancel
              </button>
            </div>
          </form>
        </li>
      )
    }
    return (
      <li key={fact.id} className="st-fact" data-fact-id={fact.id}>
        <div className="st-fact-row">
          <span className="st-fact-text">{fact.text}</span>
          <span className="st-fact-edit">
            <IconButton label={`Change “${fact.text}”`} size="sm" onClick={() => startEdit(fact)}>
              <Pencil size={20} strokeWidth={2} aria-hidden="true" />
            </IconButton>
            <IconButton
              label={`Remove “${fact.text}”`}
              size="sm"
              onClick={() => {
                setRemoving(fact)
                setRemoveError(null)
              }}
            >
              <Trash2 size={20} strokeWidth={2} aria-hidden="true" />
            </IconButton>
          </span>
        </div>
      </li>
    )
  }

  function renderBody() {
    if (account.status === 'checking' || (signedIn && loaded.status === 'loading')) {
      return (
        <ul className="st-skeleton" aria-label="Loading" aria-busy="true">
          <li className="skeleton st-skeleton-line" />
          <li className="skeleton st-skeleton-line" />
          <li className="skeleton st-skeleton-line" />
        </ul>
      )
    }
    if (!signedIn) {
      return (
        <div className="st-signed-out">
          <p className="st-intro">
            Sign in to see what Polaris knows about you and change it. Polaris keeps a profile only
            while you are signed in.
          </p>
          <div>
            <button type="button" className="secondary" onClick={onSignIn}>
              Sign in
            </button>
          </div>
        </div>
      )
    }
    if (loaded.status === 'failed') {
      return (
        <AlertBanner
          action={
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setLoaded({ status: 'loading' })
                setAttempt((n) => n + 1)
              }}
            >
              Try again
            </button>
          }
        >
          {loaded.error} Check your connection and try again.
        </AlertBanner>
      )
    }
    if (loaded.status !== 'ready') return null
    const facts = loaded.facts
    const addId = `${name}-add`
    const addHelpId = `${name}-add-help`
    const addErrorId = `${name}-add-error`
    return (
      <>
        <p className="st-intro">
          This is what Polaris knows about you. It reads this before every reply, so a change here
          applies from your next message.
        </p>
        {facts.length === 0 ? (
          <EmptyState
            title="Nothing on your profile yet"
            body="Polaris adds what it learns about you when you leave a session. You can add something below."
          />
        ) : (
          <div ref={listRef} className="st-facts">
            {GROUPS.map((group) => {
              const items = facts.filter((fact) => fact.kind === group.kind)
              if (items.length === 0) return null
              const headingId = `${name}-${group.kind}`
              return (
                <section key={group.kind} className="st-fact-group" aria-labelledby={headingId}>
                  <h3 id={headingId} className="st-subheading">
                    {group.heading}
                  </h3>
                  <ul className="st-fact-list">{items.map(renderFact)}</ul>
                </section>
              )
            })}
          </div>
        )}
        <form className="st-add" onSubmit={(event) => void add(event)} noValidate>
          <div className="field">
            <label className="field-label" htmlFor={addId}>
              Add something Polaris should know
            </label>
            <input
              ref={addRef}
              id={addId}
              type="text"
              className={addError ? 'text-input is-error' : 'text-input'}
              value={draft}
              maxLength={MAX_FACT_LENGTH}
              autoComplete="off"
              aria-invalid={addError ? true : undefined}
              aria-describedby={addError ? addErrorId : addHelpId}
              onChange={(event) => {
                setDraft(event.target.value)
                setAddError(null)
              }}
            />
            {addError ? (
              <FieldError id={addErrorId} message={addError} />
            ) : (
              <p id={addHelpId} className="field-help">
                For example: I learn best from worked examples.
              </p>
            )}
          </div>
          <div className="st-actions">
            <BusyButton busy={adding} className="secondary">
              Add to profile
            </BusyButton>
          </div>
        </form>
      </>
    )
  }

  return (
    <div className="st-profile">
      {renderBody()}
      <p className="visually-hidden" role="status" aria-live="polite">
        {announcement}
      </p>
      <Modal
        open={removing !== null}
        title="Remove this from your profile?"
        variant="confirm"
        mainLabel="Remove from profile"
        onMain={() => void confirmRemove()}
        onCancel={() => {
          setRemoving(null)
          setRemoveError(null)
        }}
      >
        <p>
          “{removing?.text ?? ''}” will be taken off your profile, and Polaris stops using it from
          your next message. This can’t be undone.
        </p>
        {removeError ? (
          <div className="modal-alert">
            <AlertBanner>{removeError}</AlertBanner>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
