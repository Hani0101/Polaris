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

/** What a running job is doing (AN-19). A ready or failed job has no stage. */
export type AnimationStage = 'writing' | 'checking' | 'fixing'

export type AnimationArtifact = {
  id: string
  kind: 'animation'
  session_id: string
  status: string
  stage?: AnimationStage | null
}

export type Artifact = Quiz | WhiteboardArtifact | AnimationArtifact

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
  preview: string
}

/** CH-06: the learner's name, else the first message, else a placeholder. */
export function sessionLabel(session: SessionSummary | undefined): string {
  return session?.name || session?.preview || 'New session'
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // The body was not JSON.
  }
  return response.statusText || 'The request failed.'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
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

export function readProfile(signal?: AbortSignal): Promise<string[]> {
  return request<{ facts: string[] }>('/api/profile', { signal }).then((body) => body.facts)
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
  },
): Promise<void> {
  const response = await fetch(`/api/sessions/${sessionId}/turns`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(
      turnBody(
        message,
        options?.pointing ?? null,
        options?.simplifies,
        options?.picture,
        options?.animationStep,
        options?.pinnedWhiteboardId,
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
