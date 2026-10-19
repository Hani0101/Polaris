import { lazy, Suspense, useEffect, useId, useRef, useState } from 'react'
import type { ChangeEvent, ComponentType, DragEvent, FormEvent, ReactNode } from 'react'
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  Globe,
  Image as ImageIcon,
  NotebookPen,
  Pencil,
  Trash2,
  Upload,
} from 'lucide-react'
import {
  RESOURCE_ACCEPT,
  RESOURCE_MAX_BYTES,
  RESOURCE_MAX_IMAGE_BYTES,
  RESOURCE_MAX_COUNT,
  RESOURCE_NAME_MAX,
  getResource,
  resourceFileUrl,
} from '../api.ts'
import type { Resource, ResourceKind, ResourceView } from '../api.ts'
import { Modal } from './Modal.tsx'
import { useResources } from './resources.tsx'
import { AlertBanner, AlertIcon, Badge, IconButton } from './ui.tsx'
import '../quiz.css'

const KIND_LABEL: Record<ResourceKind, string> = {
  pdf: 'PDF',
  docx: 'Word',
  text: 'Text',
  note: 'Note',
  image: 'Image',
  web: 'Web page',
}

function hostOf(url: string | null | undefined): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

/**
 * The PDF and Word viewers load on first use, as they carry pdf.js and docx-preview.
 * If their code cannot load, the preview shows the extracted text instead (RS-16).
 */
function lazyViewer<P extends { fallback: ReactNode }>(
  pick: (module: typeof import('./ResourcePages.tsx')) => ComponentType<P>,
) {
  const textOnly: ComponentType<P> = ({ fallback }) => <>{fallback}</>
  return lazy(() =>
    import('./ResourcePages.tsx').then(
      (module) => ({ default: pick(module) }),
      () => ({ default: textOnly }),
    ),
  )
}

const PdfPage = lazyViewer((module) => module.PdfPage)
const DocxPages = lazyViewer((module) => module.DocxPages)

const LIMIT_MB = RESOURCE_MAX_BYTES / (1024 * 1024)
const IMAGE_LIMIT_MB = RESOURCE_MAX_IMAGE_BYTES / (1024 * 1024)

function KindIcon({ kind }: { kind: ResourceKind }) {
  const props = { size: 16, strokeWidth: 2, 'aria-hidden': true } as const
  if (kind === 'image') return <ImageIcon {...props} />
  if (kind === 'note') return <NotebookPen {...props} />
  if (kind === 'web') return <Globe {...props} />
  return <FileText {...props} />
}

function describe(resource: Resource): string {
  if (resource.kind === 'web') return hostOf(resource.url)
  const from = resource.url ? ` from ${hostOf(resource.url)}` : ''
  if (resource.kind === 'pdf') {
    return (resource.pages === 1 ? '1 page' : `${resource.pages} pages`) + from
  }
  if (resource.kind === 'image') return `${Math.max(1, Math.round(resource.size / 1024))} KB${from}`
  return `${Math.max(1, Math.round(resource.size / 1024))} KB of text${from}`
}

/** Add a public web page by its link (RS-22). A refusal shows under the field (RS-19, RS-23). */
function WebPageForm({ disabled }: { disabled: boolean }) {
  const { addWeb } = useResources()
  const [url, setUrl] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const id = useId()

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const link = url.trim()
    if (!link) {
      setError('Paste the link of a web page.')
      return
    }
    setAdding(true)
    setError(null)
    try {
      await addWeb(link)
      setUrl('')
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : "Couldn't add that page. Try again.")
    } finally {
      setAdding(false)
    }
  }

  return (
    <form className="field resource-web" onSubmit={(event) => void onSubmit(event)} noValidate>
      <label className="field-label" htmlFor={id}>
        Add a web page
      </label>
      <div className="resource-web-row">
        <input
          id={id}
          type="url"
          inputMode="url"
          className={error ? 'text-input is-error' : 'text-input'}
          placeholder="https://example.org/article"
          value={url}
          autoComplete="off"
          spellCheck={false}
          disabled={disabled || adding}
          aria-invalid={error ? true : undefined}
          aria-describedby={`${id}-note`}
          onChange={(event) => {
            setUrl(event.target.value)
            if (error) setError(null)
          }}
        />
        <button type="submit" className="secondary" disabled={disabled || adding}>
          {adding ? 'Adding' : 'Add page'}
        </button>
      </div>
      {error ? (
        <p id={`${id}-note`} className="field-error" role="alert">
          <AlertIcon />
          <span>{error}</span>
        </p>
      ) : (
        <p id={`${id}-note`} className="field-help">
          Polaris reads the page once, from its public address.
        </p>
      )}
    </form>
  )
}

/**
 * The Resources tab: material the learner gives this session (RS-02, RS-13 to RS-16,
 * RS-19, RS-20). The agent reads it and never changes it.
 */
export function ResourcesTab() {
  const state = useResources()
  const { resources, focus } = state
  const [viewing, setViewing] = useState<{ id: string; page: number } | null>(null)
  const [seenNonce, setSeenNonce] = useState(0)
  const [naming, setNaming] = useState<Resource | null>(null)
  const [removing, setRemoving] = useState<Resource | null>(null)
  const [noteFor, setNoteFor] = useState<{ resource: Resource | null; text: string } | null>(null)
  const [dropping, setDropping] = useState(false)
  const picker = useRef<HTMLInputElement>(null)

  // A chosen citation shows its resource, at its page (RS-09).
  if (focus && focus.nonce !== seenNonce) {
    setSeenNonce(focus.nonce)
    setViewing({ id: focus.id, page: focus.page ?? 1 })
  }

  const current = viewing ? resources.find((item) => item.id === viewing.id) : undefined
  if (viewing && !current && state.loaded) setViewing(null)

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length > 0) void state.add(files)
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDropping(false)
    const files = Array.from(event.dataTransfer.files)
    if (files.length > 0) void state.add(files)
  }

  const full = resources.length >= RESOURCE_MAX_COUNT

  return (
    <div
      className={dropping ? 'resources is-dropping' : 'resources'}
      onDragOver={(event) => {
        if (!event.dataTransfer.types.includes('Files')) return
        event.preventDefault()
        setDropping(true)
      }}
      onDragLeave={() => setDropping(false)}
      onDrop={onDrop}
    >
      {state.error ? (
        <AlertBanner
          action={
            <button type="button" className="secondary" onClick={state.clearError}>
              Dismiss
            </button>
          }
        >
          {state.error}
        </AlertBanner>
      ) : null}
      {viewing && current ? (
        <ResourcePreview
          key={current.id}
          resource={current}
          page={viewing.page}
          onPage={(page) => setViewing({ id: current.id, page })}
          onBack={() => setViewing(null)}
          onRename={() => setNaming(current)}
          onRemove={() => setRemoving(current)}
          onEditNote={(text) => setNoteFor({ resource: current, text })}
        />
      ) : (
        <>
          <WebPageForm disabled={full} />
          <div className="tools-actions">
            <button
              type="button"
              className="secondary"
              onClick={() => picker.current?.click()}
              disabled={state.busy || full}
            >
              <Upload size={20} strokeWidth={2} aria-hidden="true" />
              {state.busy ? 'Adding' : 'Add files'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => setNoteFor({ resource: null, text: '' })}
              disabled={full}
            >
              <NotebookPen size={20} strokeWidth={2} aria-hidden="true" />
              Write a note
            </button>
            <input
              ref={picker}
              type="file"
              className="visually-hidden"
              accept={RESOURCE_ACCEPT}
              multiple
              tabIndex={-1}
              aria-label="Choose files to add"
              onChange={onPick}
            />
          </div>
          {full ? (
            <p className="field-help">
              A session holds at most {RESOURCE_MAX_COUNT} resources. Remove one to add another.
            </p>
          ) : (
            <div className="resource-drop">
              <Upload size={24} strokeWidth={2} aria-hidden="true" />
              <p className="resource-drop-title">Drop files here to add them</p>
              <p className="resource-drop-body">
                Polaris explains from a PDF, Word document, text or Markdown file, PNG or JPEG
                image, or your own note. A file can be up to {LIMIT_MB} MB and an image up to{' '}
                {IMAGE_LIMIT_MB} MB.
              </p>
            </div>
          )}
          {state.loaded ? <ResourceCount count={resources.length} /> : null}
          {resources.length > 0 ? (
            <ul className="tools-artifacts" aria-label="Resources in this session">
              {resources.map((resource) => (
                <li key={resource.id}>
                  <ResourceCard
                    resource={resource}
                    onOpen={() => setViewing({ id: resource.id, page: 1 })}
                    onRename={() => setNaming(resource)}
                    onRemove={() => setRemoving(resource)}
                  />
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
      <NameDialog
        resource={naming}
        onClose={() => setNaming(null)}
        onSave={async (name) => {
          if (!naming) return
          await state.rename(naming.id, name)
          setNaming(null)
        }}
      />
      <RemoveDialog
        resource={removing}
        onClose={() => setRemoving(null)}
        onRemove={async () => {
          if (!removing) return
          await state.remove(removing.id)
          if (viewing?.id === removing.id) setViewing(null)
          setRemoving(null)
        }}
      />
      <NoteDialog
        draft={noteFor}
        onClose={() => setNoteFor(null)}
        onSave={async (name, text) => {
          if (!noteFor) return
          if (noteFor.resource) await state.editNote(noteFor.resource.id, text)
          else {
            const added = await state.addNote(name, text)
            setViewing({ id: added.id, page: 1 })
          }
          setNoteFor(null)
        }}
      />
    </div>
  )
}

/** How many of the session's resources are used (RS-04). The text says the same as the bar. */
function ResourceCount({ count }: { count: number }) {
  return (
    <div className="qz-progress">
      <p className="qz-progress-text">
        {count} of {RESOURCE_MAX_COUNT} resources
      </p>
      <div className="qz-progress-track" aria-hidden="true">
        <div className="qz-progress-fill" style={{ width: `${(count / RESOURCE_MAX_COUNT) * 100}%` }} />
      </div>
    </div>
  )
}

function ResourceCard({
  resource,
  onOpen,
  onRename,
  onRemove,
}: {
  resource: Resource
  onOpen: () => void
  onRename: () => void
  onRemove: () => void
}) {
  return (
    <div className="resource-card">
      <button type="button" className="tools-card tools-card--clickable" onClick={onOpen}>
        <span className="tools-card-row">
          <KindIcon kind={resource.kind} />
          <span className="resource-name">{resource.name}</span>
        </span>
        <span className="tools-card-row">
          <Badge>{KIND_LABEL[resource.kind]}</Badge>
          <span className="tools-card-body">{describe(resource)}</span>
        </span>
      </button>
      <div className="resource-actions">
        <IconButton label={`Rename ${resource.name}`} size="sm" onClick={onRename}>
          <Pencil size={20} strokeWidth={2} aria-hidden="true" />
        </IconButton>
        <IconButton label={`Remove ${resource.name}`} size="sm" onClick={onRemove}>
          <Trash2 size={20} strokeWidth={2} aria-hidden="true" />
        </IconButton>
      </div>
    </div>
  )
}

/** Extracted text, shown when a PDF or Word document cannot be drawn (RS-16). */
function TextOnly({ note, text }: { note: string; text: string }) {
  return (
    <>
      <p className="field-help">{note}</p>
      <pre className="resource-text">{text}</pre>
    </>
  )
}

const loadingViewer = <div className="skeleton resource-skeleton" role="status" aria-label="Loading" />

/**
 * The preview (RS-12, RS-16): a PDF or Word document as its own pages, other text
 * as plain text, an image with alt text.
 */
function ResourcePreview({
  resource,
  page,
  onPage,
  onBack,
  onRename,
  onRemove,
  onEditNote,
}: {
  resource: Resource
  page: number
  onPage: (page: number) => void
  onBack: () => void
  onRename: () => void
  onRemove: () => void
  onEditNote: (text: string) => void
}) {
  const { sessionId } = useResources()
  const [view, setView] = useState<ResourceView | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const heading = useId()

  useEffect(() => {
    if (!sessionId || resource.kind === 'image') return
    const controller = new AbortController()
    getResource(sessionId, resource.id, controller.signal)
      .then(setView)
      .catch((caught) => {
        if (controller.signal.aborted) return
        setProblem(
          caught instanceof Error && caught.message
            ? caught.message
            : "Couldn't open this resource. Try again.",
        )
      })
    return () => controller.abort()
    // The text changes when a note is edited, which changes its size.
  }, [sessionId, resource.id, resource.kind, resource.size])

  const pages = view?.text_pages ?? []
  const isPdf = resource.kind === 'pdf'
  const last = Math.max(1, pages.length)
  const shown = Math.min(Math.max(1, page), last)

  let body: ReactNode
  if (resource.kind === 'image' && sessionId) {
    body = (
      <img
        className="resource-image"
        src={resourceFileUrl(sessionId, resource.id)}
        alt={resource.name}
      />
    )
  } else if (problem) {
    body = <AlertBanner>{problem}</AlertBanner>
  } else if (!view || !sessionId) {
    body = loadingViewer
  } else if (isPdf) {
    body = (
      <>
        <div className="resource-pager">
          <IconButton label="Previous page" size="sm" disabled={shown <= 1} onClick={() => onPage(shown - 1)}>
            <ChevronLeft size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
          <span className="resource-pager-label" aria-live="polite">
            Page {shown} of {last}
          </span>
          <IconButton label="Next page" size="sm" disabled={shown >= last} onClick={() => onPage(shown + 1)}>
            <ChevronRight size={20} strokeWidth={2} aria-hidden="true" />
          </IconButton>
        </div>
        <Suspense fallback={loadingViewer}>
          <PdfPage
            url={resourceFileUrl(sessionId, resource.id)}
            page={shown}
            fallback={
              <TextOnly
                note="This shows the text of the page only."
                text={pages[shown - 1] || 'No readable text on this page.'}
              />
            }
          />
        </Suspense>
      </>
    )
  } else if (resource.kind === 'docx') {
    body = (
      <Suspense fallback={loadingViewer}>
        <DocxPages
          url={resourceFileUrl(sessionId, resource.id)}
          name={resource.name}
          fallback={<TextOnly note="This shows the text of the document only." text={pages.join('\n\n')} />}
        />
      </Suspense>
    )
  } else {
    body = (
      <>
        {resource.kind === 'web' ? (
          <p className="field-help">This shows the text of the page as it was when you added it.</p>
        ) : null}
        <pre className="resource-text">{pages.join('\n\n')}</pre>
      </>
    )
  }

  return (
    <div className="resource-preview">
      <div className="resource-preview-head">
        <IconButton label="Back to resources" size="sm" onClick={onBack}>
          <ArrowLeft size={20} strokeWidth={2} aria-hidden="true" />
        </IconButton>
        <h3 className="resource-preview-title" id={heading}>
          {resource.name}
        </h3>
        <IconButton label={`Rename ${resource.name}`} size="sm" onClick={onRename}>
          <Pencil size={20} strokeWidth={2} aria-hidden="true" />
        </IconButton>
        <IconButton label={`Remove ${resource.name}`} size="sm" onClick={onRemove}>
          <Trash2 size={20} strokeWidth={2} aria-hidden="true" />
        </IconButton>
      </div>
      {resource.kind === 'note' && view ? (
        <div className="tools-actions">
          <button type="button" className="secondary" onClick={() => onEditNote(pages.join('\n\n'))}>
            Edit note
          </button>
        </div>
      ) : null}
      {resource.url ? (
        <p className="resource-source">
          <a href={resource.url} target="_blank" rel="noreferrer noopener">
            Open the page on {hostOf(resource.url)}
            <ExternalLink size={16} strokeWidth={2} aria-hidden="true" />
            <span className="visually-hidden"> (opens in a new tab)</span>
          </a>
        </p>
      ) : null}
      <div className="resource-preview-body" role="region" aria-labelledby={heading}>
        {body}
      </div>
    </div>
  )
}

function useSaving(onSave: () => Promise<void>) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function run() {
    setSaving(true)
    setError(null)
    try {
      await onSave()
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : "Couldn't save. Try again.")
    } finally {
      setSaving(false)
    }
  }
  return { saving, error, run, clear: () => setError(null) }
}

function NameDialog({
  resource,
  onClose,
  onSave,
}: {
  resource: Resource | null
  onClose: () => void
  onSave: (name: string) => Promise<void>
}) {
  const [value, setValue] = useState('')
  const [shownFor, setShownFor] = useState<string | null>(null)
  const inputId = useId()
  const saving = useSaving(() => onSave(value))
  if ((resource?.id ?? null) !== shownFor) {
    setShownFor(resource?.id ?? null)
    setValue(resource?.name ?? '')
    saving.clear()
  }
  return (
    <Modal
      open={resource !== null}
      title="Rename resource"
      mainLabel="Rename"
      onMain={() => void saving.run()}
      onCancel={onClose}
    >
      <div className="field">
        <label className="field-label" htmlFor={inputId}>
          Resource name
        </label>
        <input
          id={inputId}
          type="text"
          className="text-input"
          value={value}
          maxLength={RESOURCE_NAME_MAX}
          autoComplete="off"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            event.preventDefault()
            void saving.run()
          }}
        />
      </div>
      {saving.error ? (
        <div className="modal-alert">
          <AlertBanner>{saving.error}</AlertBanner>
        </div>
      ) : null}
    </Modal>
  )
}

function RemoveDialog({
  resource,
  onClose,
  onRemove,
}: {
  resource: Resource | null
  onClose: () => void
  onRemove: () => Promise<void>
}) {
  const saving = useSaving(onRemove)
  return (
    <Modal
      open={resource !== null}
      title="Remove this resource?"
      variant="confirm"
      mainLabel="Remove resource"
      onMain={() => void saving.run()}
      onCancel={onClose}
    >
      <p>
        “{resource?.name ?? ''}” will be removed from this session, and Polaris can no longer read
        it. Earlier replies stay as they are. This can’t be undone.
      </p>
      {saving.error ? (
        <div className="modal-alert">
          <AlertBanner>{saving.error}</AlertBanner>
        </div>
      ) : null}
    </Modal>
  )
}

function NoteDialog({
  draft,
  onClose,
  onSave,
}: {
  draft: { resource: Resource | null; text: string } | null
  onClose: () => void
  onSave: (name: string, text: string) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const [shown, setShown] = useState<typeof draft>(null)
  const nameId = useId()
  const textId = useId()
  const saving = useSaving(() => onSave(name, text))
  if (draft !== shown) {
    setShown(draft)
    setName(draft?.resource?.name ?? '')
    setText(draft?.text ?? '')
    saving.clear()
  }
  const editing = Boolean(draft?.resource)
  return (
    <Modal
      open={draft !== null}
      title={editing ? 'Edit note' : 'Write a note'}
      mainLabel="Save note"
      onMain={() => void saving.run()}
      onCancel={onClose}
    >
      {editing ? null : (
        <div className="field">
          <label className="field-label" htmlFor={nameId}>
            Note title
          </label>
          <input
            id={nameId}
            type="text"
            className="text-input"
            value={name}
            maxLength={RESOURCE_NAME_MAX}
            autoComplete="off"
            onChange={(event) => setName(event.target.value)}
          />
        </div>
      )}
      <div className="field">
        <label className="field-label" htmlFor={textId}>
          Note
        </label>
        <textarea
          id={textId}
          className="text-area"
          rows={8}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </div>
      {saving.error ? (
        <div className="modal-alert">
          <AlertBanner>{saving.error}</AlertBanner>
        </div>
      ) : null}
    </Modal>
  )
}
