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

export type QuizMistake = {
  question_id: string
  explanation: string
}

export type Quiz = {
  id: string
  kind: 'quiz'
  session_id: string
  title: string
  questions: QuizQuestion[]
  score: QuizScore | null
  submitted?: Record<string, string>
  mistakes?: QuizMistake[]
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

export type RectangleElement = WhiteboardElementBase & {
  kind: 'rectangle'
}

export type EllipseElement = WhiteboardElementBase & {
  kind: 'ellipse'
}

export type ArrowElement = WhiteboardElementBase & {
  kind: 'arrow'
  start: Point
  end: Point
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

export type AnimationArtifact = {
  id: string
  kind: 'animation'
  session_id: string
  status: string
}

export type Artifact = Quiz | WhiteboardArtifact | AnimationArtifact

export type TurnPointing = {
  whiteboard_id: string
  element_ids: string[]
}

export type Turn = {
  learner_message: string
  reply: string
  artifacts: Artifact[]
  pointing?: TurnPointing
}

export function turnBody(
  message: string,
  pointing: { whiteboardId: string; parts: { id: string }[] } | null,
  simplifies?: string | null,
): { message: string; pointing?: TurnPointing; simplifies?: string } {
  const body: { message: string; pointing?: TurnPointing; simplifies?: string } = { message }
  if (pointing && pointing.parts.length > 0) {
    body.pointing = {
      whiteboard_id: pointing.whiteboardId,
      element_ids: pointing.parts.map((part) => part.id),
    }
  }
  if (simplifies) body.simplifies = simplifies
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
  preview: string
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

export function gradeQuiz(
  quizId: string,
  choices: Record<string, string>,
): Promise<Quiz> {
  return request<Quiz>(`/api/quizzes/${quizId}/grade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ choices }),
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
  },
): Promise<void> {
  const response = await fetch(`/api/sessions/${sessionId}/turns`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(turnBody(message, options?.pointing ?? null, options?.simplifies)),
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
