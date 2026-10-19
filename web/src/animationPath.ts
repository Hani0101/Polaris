/** Route helpers for opening a finished animation (AN-06). */

export function animationPagePath(sessionId: string, jobId: string): string {
  return `/animation/${encodeURIComponent(sessionId)}/${encodeURIComponent(jobId)}`
}

export function pathAnimation(
  path: string,
): { sessionId: string; jobId: string } | null {
  const match = path.match(/^\/animation\/([^/]+)\/([^/]+)$/)
  if (!match) return null
  return {
    sessionId: decodeURIComponent(match[1]),
    jobId: decodeURIComponent(match[2]),
  }
}

export function animationMediaUrl(sessionId: string, jobId: string): string {
  return `/api/sessions/${encodeURIComponent(sessionId)}/jobs/${encodeURIComponent(jobId)}/media`
}

/** A file of a Manim job: its manifest, captions, step clips, or posters (experiment). */
export function animationManimUrl(sessionId: string, jobId: string, name: string): string {
  return `${animationMediaUrl(sessionId, jobId).replace(/\/media$/, '')}/manim/${name}`
}
