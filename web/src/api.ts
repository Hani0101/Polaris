export type Turn = {
  learner_message: string
  reply: string
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

type StreamEvent = {
  text?: string
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
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/sessions/${sessionId}/turns`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ message }),
    signal,
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
      if (event.done) sawDone = true
    }
    if (done) break
  }
  if (!sawDone) throw new Error('The reply ended early.')
}
