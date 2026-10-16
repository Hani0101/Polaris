export const SIMPLER_REQUEST = 'Draw a simpler version of this whiteboard.'

export function whiteboardPagePath(sessionId: string, whiteboardId: string): string {
  return `/whiteboard/${encodeURIComponent(sessionId)}/${encodeURIComponent(whiteboardId)}`
}
