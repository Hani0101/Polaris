import type { CardSource } from './api.ts'

export function deckPath(deckId: string): string {
  return `/deck/${encodeURIComponent(deckId)}`
}

export function pathDeckId(path: string): string | null {
  const match = path.match(/^\/deck\/([^/]+)$/)
  return match ? decodeURIComponent(match[1]) : null
}

/** FC-05: "Notes.pdf, p. 4", a resource name and its quoted phrase, or "Turn 3".
 * A removed resource says so (FC-18). */
export function sourceText(source: CardSource): string {
  if (source.kind === 'turn') return `Turn ${source.turn}`
  if (source.removed) return 'resource removed'
  if (source.kind === 'page') return `${source.name}, p. ${source.page}`
  return `${source.name}: “${source.quote}”`
}

function listNames(names: string[]): string {
  const quoted = names.map((name) => `“${name}”`)
  if (quoted.length <= 1) return quoted.join('')
  return `${quoted.slice(0, -1).join(', ')} and ${quoted[quoted.length - 1]}`
}

/** The visible learner turn the Create flashcards dialog sends (FC-01): the topic,
 * and every resource to use (FC-03). */
export function deckRequest(topic: string, names: string[]): string {
  const about = topic.trim()
  if (about && names.length > 0) {
    return `Make flashcards about ${about}. Use ${listNames(names)}.`
  }
  if (about) return `Make flashcards about ${about}.`
  return `Make flashcards from ${listNames(names)}.`
}
