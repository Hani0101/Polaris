import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  RESOURCE_MAX_BYTES,
  RESOURCE_MAX_COUNT,
  RESOURCE_MAX_IMAGE_BYTES,
  addResourceNote,
  listResources,
  removeResource,
  updateResource,
  uploadResource,
} from '../api.ts'
import type { Resource } from '../api.ts'

/** A citation the learner chose: show this resource, at this page when it has pages (RS-09). */
export type ResourceFocus = { id: string; page: number | null; nonce: number }

export type ResourcesState = {
  sessionId: string | null
  resources: Resource[]
  /** False until the session's list has loaded, so a citation is not called removed too early. */
  loaded: boolean
  error: string | null
  busy: boolean
  focus: ResourceFocus | null
  add: (files: File[]) => Promise<void>
  addNote: (name: string, text: string) => Promise<Resource>
  rename: (resourceId: string, name: string) => Promise<void>
  editNote: (resourceId: string, text: string) => Promise<void>
  remove: (resourceId: string) => Promise<void>
  open: (resourceId: string, page?: number | null) => void
  clearError: () => void
}

const none = async () => {}

const EMPTY: ResourcesState = {
  sessionId: null,
  resources: [],
  loaded: false,
  error: null,
  busy: false,
  focus: null,
  add: none,
  addNote: async () => {
    throw new Error('Resources are not available here.')
  },
  rename: none,
  editNote: none,
  remove: none,
  open: () => {},
  clearError: () => {},
}

const ResourcesContext = createContext<ResourcesState>(EMPTY)

export function useResources(): ResourcesState {
  return useContext(ResourcesContext)
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

/** Why a file is refused before it is sent. The server checks the same limits (RS-04). */
export function fileProblem(file: File, count: number): string | null {
  if (count >= RESOURCE_MAX_COUNT) {
    return `A session holds at most ${RESOURCE_MAX_COUNT} resources. Remove one to add another.`
  }
  if (file.size > RESOURCE_MAX_BYTES) {
    return `${file.name} is over the ${RESOURCE_MAX_BYTES / (1024 * 1024)} MB limit.`
  }
  if (/\.(png|jpe?g)$/i.test(file.name) && file.size > RESOURCE_MAX_IMAGE_BYTES) {
    return `${file.name} is over the ${RESOURCE_MAX_IMAGE_BYTES / (1024 * 1024)} MB limit for an image.`
  }
  return null
}

/**
 * The open session's resources (RS-01). Adding, renaming, or removing one adds
 * no turn (RS-17). `onFocus` runs when a citation is chosen, so the shell can
 * open the tools.
 */
export function ResourcesProvider({
  sessionId,
  onFocus,
  children,
}: {
  sessionId: string | null
  onFocus?: () => void
  children: ReactNode
}) {
  const [loadedFor, setLoadedFor] = useState<string | null>(null)
  const [resources, setResources] = useState<Resource[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [focus, setFocus] = useState<ResourceFocus | null>(null)
  const [shownFor, setShownFor] = useState<string | null>(sessionId)

  // A different session starts with an empty list; its own list loads below.
  if (shownFor !== sessionId) {
    setShownFor(sessionId)
    setResources([])
    setLoadedFor(null)
    setError(null)
    setFocus(null)
  }

  useEffect(() => {
    if (!sessionId) return
    const controller = new AbortController()
    listResources(sessionId, controller.signal)
      .then((list) => {
        setResources(list)
        setLoadedFor(sessionId)
      })
      .catch((caught) => {
        if (controller.signal.aborted) return
        setError(errorText(caught, "Couldn't load your resources. Check your connection and try again."))
        setLoadedFor(sessionId)
      })
    return () => controller.abort()
  }, [sessionId])

  const add = useCallback(
    async (files: File[]) => {
      if (!sessionId) return
      setBusy(true)
      setError(null)
      let count = resources.length
      try {
        for (const file of files) {
          const problem = fileProblem(file, count)
          if (problem) {
            setError(problem)
            break
          }
          try {
            const added = await uploadResource(sessionId, file)
            setResources((current) => [...current, added])
            count += 1
          } catch (caught) {
            setError(errorText(caught, `Couldn't add ${file.name}. Try again.`))
            break
          }
        }
      } finally {
        setBusy(false)
      }
    },
    [resources.length, sessionId],
  )

  const addNote = useCallback(
    async (name: string, text: string) => {
      if (!sessionId) throw new Error('Open a session first.')
      const added = await addResourceNote(sessionId, name, text)
      setResources((current) => [...current, added])
      return added
    },
    [sessionId],
  )

  const rename = useCallback(
    async (resourceId: string, name: string) => {
      if (!sessionId) return
      const saved = await updateResource(sessionId, resourceId, { name })
      setResources((current) => current.map((item) => (item.id === resourceId ? saved : item)))
    },
    [sessionId],
  )

  const editNote = useCallback(
    async (resourceId: string, text: string) => {
      if (!sessionId) return
      const saved = await updateResource(sessionId, resourceId, { text })
      setResources((current) => current.map((item) => (item.id === resourceId ? saved : item)))
    },
    [sessionId],
  )

  const remove = useCallback(
    async (resourceId: string) => {
      if (!sessionId) return
      await removeResource(sessionId, resourceId)
      setResources((current) => current.filter((item) => item.id !== resourceId))
      setFocus((current) => (current?.id === resourceId ? null : current))
    },
    [sessionId],
  )

  const open = useCallback(
    (resourceId: string, page: number | null = null) => {
      setFocus((current) => ({ id: resourceId, page, nonce: (current?.nonce ?? 0) + 1 }))
      onFocus?.()
    },
    [onFocus],
  )

  const clearError = useCallback(() => setError(null), [])

  const value = useMemo<ResourcesState>(
    () => ({
      sessionId,
      resources,
      loaded: sessionId !== null && loadedFor === sessionId,
      error,
      busy,
      focus,
      add,
      addNote,
      rename,
      editNote,
      remove,
      open,
      clearError,
    }),
    [sessionId, resources, loadedFor, error, busy, focus, add, addNote, rename, editNote, remove, open, clearError],
  )

  return <ResourcesContext.Provider value={value}>{children}</ResourcesContext.Provider>
}
