import { accessHeader, refreshSignIn } from './auth.ts'
import { ApiError, readDetail } from './httpError.ts'

export type Choice = {
  id: string
  text: string
}

export type QuizQuestion = {
  id: string
  prompt: string
  choices: Choice[]
}

export type QuizScore = {
  earned: number
  total: number
}

/** One per checked question (QZ-03): its key and note arrive when it is checked, never before. */
export type QuizFeedback = {
  question_id: string
  right: boolean
  correct_choice_id: string
  explanation: string
  // Only on a wrong answer, and absent on quizzes stored before notes existed.
  why_wrong?: string
}

export type Quiz = {
  id: string
  kind: 'quiz'
  session_id: string
  title: string
  questions: QuizQuestion[]
  /** Set when the last question is checked (QZ-08). */
  score: QuizScore | null
  /** The pick for each checked question. */
  submitted?: Record<string, string>
  /** The key of each checked question, in question order. */
  feedback?: QuizFeedback[]
}

export type Point = {
  x: number
  y: number
}

export type Size = {
  width: number
  height: number
}

export type Style = {
  stroke: string
  fill: string | null
  stroke_width: number
}

type WhiteboardElementBase = {
  id: string
  author: 'agent' | 'learner'
  position: Point
  size: Size
  style: Style
}

// label, start_element_id, and end_element_id exist on version 7 only.
export type RectangleElement = WhiteboardElementBase & {
  kind: 'rectangle'
  label?: string
}

export type EllipseElement = WhiteboardElementBase & {
  kind: 'ellipse'
  label?: string
}

export type ArrowElement = WhiteboardElementBase & {
  kind: 'arrow'
  start: Point
  end: Point
  label?: string
  start_element_id?: string
  end_element_id?: string
  bend?: number
}

export type LineElement = WhiteboardElementBase & {
  kind: 'line'
  start: Point
  end: Point
}

export type TextElement = WhiteboardElementBase & {
  kind: 'text'
  text: string
}

export type FreehandElement = WhiteboardElementBase & {
  kind: 'freehand'
  points: Point[]
}

export type MathElement = WhiteboardElementBase & {
  kind: 'math'
  latex: string
}

export type CodeElement = WhiteboardElementBase & {
  kind: 'code'
  language: string
  code: string
}

export type GraphPoint = {
  x: number
  y: number
}

export type FunctionSeries = {
  expression: string
  sample_count: number
  plotted?: GraphPoint[]
}

export type DataSeries = {
  points: GraphPoint[]
  plotted?: GraphPoint[]
}

export type GraphSeries = FunctionSeries | DataSeries

export type GraphElement = WhiteboardElementBase & {
  kind: 'graph'
  author: 'agent'
  x_label: string
  y_label: string
  x_min: number
  x_max: number
  y_min: number
  y_max: number
  series: GraphSeries[]
}

export type MarkElement = WhiteboardElementBase & {
  kind: 'mark'
  author: 'agent'
  mark: 'circle' | 'arrow' | 'note'
  target_element_id: string
  text?: string
  start?: Point
  end?: Point
}

export type WhiteboardElement =
  | RectangleElement
  | EllipseElement
  | ArrowElement
  | LineElement
  | TextElement
  | FreehandElement
  | MathElement
  | CodeElement
  | GraphElement
  | MarkElement

export type WhiteboardStep = {
  id: string
  reply_part: string
  elements: WhiteboardElement[]
  // A step the agent added beside the learner's drawing on a pinned board (WB-20).
  extension?: true
}

export type Comment = {
  id: string
  author: 'agent' | 'learner'
  text: string
  position?: Point | null
  element_id?: string | null
}

export type Whiteboard = {
  version: number
  id: string
  session_id: string
  description?: string
  simplifies?: string
  steps: WhiteboardStep[]
  comments: Comment[]
}

export type WhiteboardArtifact = Whiteboard & {
  kind: 'whiteboard'
}

/**
 * What a running job is doing (AN-19), or that it waits for the learner to
 * choose an engine (AN-21) or for a free place (AN-25). A ready or failed
 * job has no stage.
 */
export type AnimationStage = 'choosing' | 'queued' | 'writing' | 'checking' | 'fixing'

/** The two animation engines the learner chooses between (AN-21). */
export type AnimationEngine = 'manim' | 'lottie'

export type AnimationArtifact = {
  id: string
  kind: 'animation'
  session_id: string
  status: string
  stage?: AnimationStage | null
}

/** Where a flashcard comes from (FC-05). A removed resource keeps the card (FC-18). */
export type CardSource =
  | { kind: 'turn'; turn: number }
  | {
      kind: 'page'
      resource_id: string
      name: string
      page: number
      quote?: string
      removed?: boolean
    }
  | { kind: 'quote'; resource_id: string; name: string; quote: string; removed?: boolean }

export type CardRating = 'got_it' | 'again'

export type Flashcard = {
  id: string
  front: string
  back: string
  source: CardSource
  /** The latest rating, or null when unrated (FC-14). */
  rating: CardRating | null
}

export type Deck = {
  id: string
  kind: 'deck'
  session_id: string
  title: string
  cards: Flashcard[]
  counts: { got_it: number; again: number; unrated: number }
}

export type Artifact = Quiz | WhiteboardArtifact | AnimationArtifact | Deck

export type TurnPointing = {
  whiteboard_id: string
  element_ids: string[]
}

/** The animation step a turn asks about (AN-17). */
export type TurnAnimationStep = {
  job_id: string
  step_id: string
}

export type Turn = {
  learner_message: string
  reply: string
  artifacts: Artifact[]
  pointing?: TurnPointing
  animation_step?: TurnAnimationStep
}

export type TurnBody = {
  message: string
  pointing?: TurnPointing
  simplifies?: string
  picture?: BoardPicture
  animation_step?: TurnAnimationStep
  pinned_whiteboard_id?: string
  /** Web mode: the agent may search and read the web for this reply only (CH-23). */
  web?: boolean
}

/** A PNG of one whiteboard, sent with the next turn only. data is base64. */
export type BoardPicture = {
  whiteboard_id: string
  media_type: 'image/png'
  data: string
}

export function turnBody(
  message: string,
  pointing: { whiteboardId: string; parts: { id: string }[] } | null,
  simplifies?: string | null,
  picture?: BoardPicture | null,
  animationStep?: { jobId: string; stepId: string } | null,
  pinnedWhiteboardId?: string | null,
  web?: boolean,
): TurnBody {
  const body: TurnBody = { message }
  if (pointing && pointing.parts.length > 0) {
    body.pointing = {
      whiteboard_id: pointing.whiteboardId,
      element_ids: pointing.parts.map((part) => part.id),
    }
  }
  if (simplifies) body.simplifies = simplifies
  if (picture) body.picture = picture
  if (animationStep) {
    body.animation_step = { job_id: animationStep.jobId, step_id: animationStep.stepId }
  }
  if (pinnedWhiteboardId) body.pinned_whiteboard_id = pinnedWhiteboardId
  if (web) body.web = true
  return body
}

export type Session = {
  id: string
  ended: boolean
  turns: Turn[]
}

export type SessionSummary = {
  id: string
  ended: boolean
  /** The learner's name for the session, or an empty string. */
  name: string
  /** The title a model wrote from the first message (CH-20), or an empty string. */
  title: string
  preview: string
}

/** CH-06: the learner's name, else the generated title, else the first message, else a placeholder. */
export function sessionLabel(session: SessionSummary | undefined): string {
  return session?.name || session?.title || session?.preview || 'Untitled'
}

export { ApiError }

// A signed-in page sends its access token on every request (AU-08). Only the
// profile needs it (AU-12); everything else works without one.
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(await accessHeader()),
      ...init?.headers,
    },
  })
  if (!response.ok) throw new ApiError(response.status, await readDetail(response))
  return (await response.json()) as T
}

export function listSessions(signal?: AbortSignal): Promise<SessionSummary[]> {
  return request<{ sessions: SessionSummary[] }>('/api/sessions', { signal }).then(
    (body) => body.sessions,
  )
}

export function renameSession(sessionId: string, name: string): Promise<{ name: string }> {
  return request<{ name: string }>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function deleteSession(
  sessionId: string,
): Promise<{ id: string; facts_saved: boolean }> {
  return request<{ id: string; facts_saved: boolean }>(
    `/api/sessions/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
  )
}

/** The profile needs a valid access token (AU-12). A refused token is refreshed once. */
export async function readProfile(signal?: AbortSignal): Promise<string[]> {
  const read = () =>
    request<{ facts: string[] }>('/api/profile', { signal }).then((body) => body.facts)
  try {
    return await read()
  } catch (caught) {
    if (!(caught instanceof ApiError) || caught.status !== 401) throw caught
    if (!(await refreshSignIn())) throw caught
    return read()
  }
}

export function startSession(): Promise<Session> {
  return request<Session>('/api/sessions', { method: 'POST' })
}

export function openSession(sessionId: string): Promise<Session> {
  return request<Session>(`/api/sessions/${sessionId}/open`, { method: 'POST' })
}

export function leaveSession(sessionId: string): Promise<Session> {
  return request<Session>(`/api/sessions/${sessionId}/leave`, { method: 'POST' })
}

/** Ask the server to start the agent for an open session or a draft. Only a speed-up. */
export function warmSession(sessionId: string): Promise<{ id: string }> {
  return request<{ id: string }>(`/api/sessions/${encodeURIComponent(sessionId)}/warm`, {
    method: 'POST',
  })
}

export function getSession(sessionId: string, signal?: AbortSignal): Promise<Session> {
  return request<Session>(`/api/sessions/${sessionId}`, { signal })
}

export function getAnimationJob(
  sessionId: string,
  jobId: string,
  signal?: AbortSignal,
): Promise<AnimationArtifact> {
  return request<AnimationArtifact>(`/api/sessions/${sessionId}/jobs/${jobId}`, { signal })
}

/** Start a waiting animation job with the engine the learner chose (AN-21). */
export function chooseAnimationEngine(
  sessionId: string,
  jobId: string,
  engine: AnimationEngine,
): Promise<AnimationArtifact> {
  return request<AnimationArtifact>(`/api/sessions/${sessionId}/jobs/${jobId}/engine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engine }),
  })
}

export function getQuiz(quizId: string, signal?: AbortSignal): Promise<Quiz> {
  return request<Quiz>(`/api/quizzes/${quizId}`, { signal })
}

export function getWhiteboard(
  sessionId: string,
  whiteboardId: string,
  signal?: AbortSignal,
): Promise<WhiteboardArtifact> {
  return request<WhiteboardArtifact>(
    `/api/sessions/${sessionId}/whiteboards/${whiteboardId}`,
    { signal },
  )
}

export function listWhiteboards(
  sessionId: string,
  signal?: AbortSignal,
): Promise<WhiteboardArtifact[]> {
  return request<{ whiteboards: WhiteboardArtifact[] }>(
    `/api/sessions/${sessionId}/whiteboards`,
    { signal },
  ).then((body) => body.whiteboards)
}

/** An empty board the learner made from the Whiteboard tab (WB-18). */
export function createWhiteboard(sessionId: string): Promise<WhiteboardArtifact> {
  return request<WhiteboardArtifact>(`/api/sessions/${sessionId}/whiteboards`, {
    method: 'POST',
  })
}

export function saveWhiteboard(
  sessionId: string,
  whiteboardId: string,
  drawing: Whiteboard,
): Promise<WhiteboardArtifact> {
  return request<WhiteboardArtifact>(
    `/api/sessions/${sessionId}/whiteboards/${whiteboardId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(drawing),
    },
  )
}

/** Checks one pick against the stored key (QZ-14). The reply carries that question's key. */
export function answerQuiz(
  quizId: string,
  questionId: string,
  choiceId: string,
): Promise<Quiz> {
  return request<Quiz>(`/api/quizzes/${quizId}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id: questionId, choice_id: choiceId }),
  })
}

export function getDeck(deckId: string, signal?: AbortSignal): Promise<Deck> {
  return request<Deck>(`/api/decks/${encodeURIComponent(deckId)}`, { signal })
}

/** Keeps a card's latest rating (FC-14). */
export function rateCard(deckId: string, cardId: string, rating: CardRating): Promise<Deck> {
  return request<Deck>(`/api/decks/${encodeURIComponent(deckId)}/ratings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_id: cardId, rating }),
  })
}

/** Every card back to unrated (FC-14). */
export function resetRatings(deckId: string): Promise<Deck> {
  return request<Deck>(`/api/decks/${encodeURIComponent(deckId)}/ratings`, { method: 'DELETE' })
}

type StreamEvent = {
  text?: string
  artifact?: Artifact
  done?: boolean
  error?: string
}

function parseEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const events: StreamEvent[] = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  for (const part of parts) {
    for (const line of part.split('\n')) {
      if (line.startsWith('data: ')) {
        events.push(JSON.parse(line.slice('data: '.length)) as StreamEvent)
      }
    }
  }
  return { events, rest }
}

export async function sendTurn(
  sessionId: string,
  message: string,
  onText: (chunk: string) => void,
  onArtifact: (artifact: Artifact) => void,
  options?: {
    signal?: AbortSignal
    pointing?: { whiteboardId: string; parts: { id: string }[] } | null
    simplifies?: string | null
    picture?: BoardPicture | null
    animationStep?: { jobId: string; stepId: string } | null
    pinnedWhiteboardId?: string | null
    web?: boolean
  },
): Promise<void> {
  const response = await fetch(`/api/sessions/${sessionId}/turns`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(await accessHeader()),
    },
    body: JSON.stringify(
      turnBody(
        message,
        options?.pointing ?? null,
        options?.simplifies,
        options?.picture,
        options?.animationStep,
        options?.pinnedWhiteboardId,
        options?.web,
      ),
    ),
    signal: options?.signal,
  })
  if (!response.ok) throw new ApiError(response.status, await readDetail(response))
  if (!response.body) throw new Error('The reply could not be read.')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let sawDone = false
  while (!sawDone) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    const parsed = parseEvents(buffer)
    buffer = parsed.rest
    for (const event of parsed.events) {
      if (event.error) throw new Error(event.error)
      if (event.text) onText(event.text)
      if (event.artifact) onArtifact(event.artifact)
      if (event.done) sawDone = true
    }
    if (done) break
  }
  if (!sawDone) throw new Error('The reply ended early.')
}

export type ResourceKind = 'pdf' | 'docx' | 'text' | 'note' | 'image' | 'web'

export type Resource = {
  id: string
  kind: ResourceKind
  name: string
  media_type: string
  size: number
  /** PDF pages, or parts of other text. Zero for an image. */
  pages: number
  /** The page a resource added by its link came from (RS-22). Null for a file or a note. */
  url?: string | null
}

export type ResourceView = Resource & {
  /** The extracted text, one entry per page or part. Empty for an image. */
  text_pages: string[]
}

/** Limits the server enforces (RS-04). The client shows them early. */
export const RESOURCE_MAX_BYTES = 10 * 1024 * 1024
export const RESOURCE_MAX_IMAGE_BYTES = 5 * 1024 * 1024
export const RESOURCE_MAX_COUNT = 10
export const RESOURCE_NAME_MAX = 80
export const RESOURCE_ACCEPT = '.pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg'

function resourcesPath(sessionId: string): string {
  return `/api/sessions/${encodeURIComponent(sessionId)}/resources`
}

export function resourceFileUrl(sessionId: string, resourceId: string): string {
  return `${resourcesPath(sessionId)}/${encodeURIComponent(resourceId)}/file`
}

export function listResources(sessionId: string, signal?: AbortSignal): Promise<Resource[]> {
  return request<{ resources: Resource[] }>(resourcesPath(sessionId), { signal }).then(
    (body) => body.resources,
  )
}

/** The file is the request body and its name travels in X-Filename. */
export function uploadResource(sessionId: string, file: File): Promise<Resource> {
  return request<Resource>(resourcesPath(sessionId), {
    method: 'POST',
    headers: { 'X-Filename': encodeURIComponent(file.name) },
    body: file,
  })
}

export function addResourceNote(sessionId: string, name: string, text: string): Promise<Resource> {
  return request<Resource>(`${resourcesPath(sessionId)}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, text }),
  })
}

/** Polaris fetches the page once, from a public address only (RS-22, RS-23). */
export function addResourceWeb(sessionId: string, url: string): Promise<Resource> {
  return request<Resource>(`${resourcesPath(sessionId)}/web`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
}

export function getResource(
  sessionId: string,
  resourceId: string,
  signal?: AbortSignal,
): Promise<ResourceView> {
  return request<ResourceView>(`${resourcesPath(sessionId)}/${encodeURIComponent(resourceId)}`, {
    signal,
  })
}

export function updateResource(
  sessionId: string,
  resourceId: string,
  change: { name?: string; text?: string },
): Promise<Resource> {
  return request<Resource>(`${resourcesPath(sessionId)}/${encodeURIComponent(resourceId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(change),
  })
}

export function removeResource(sessionId: string, resourceId: string): Promise<{ id: string }> {
  return request<{ id: string }>(`${resourcesPath(sessionId)}/${encodeURIComponent(resourceId)}`, {
    method: 'DELETE',
  })
}
