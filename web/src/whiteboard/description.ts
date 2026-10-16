import type { Comment, GraphElement, GraphSeries, Whiteboard, WhiteboardElement } from '../api.ts'

export function readableDescription(whiteboard: Whiteboard): string {
  const learner = learnerSentence(whiteboard)
  const stored = whiteboard.description?.trim() ?? ''
  const base = stored || drawingSummary(whiteboard)
  const extras = mathCodeLines(whiteboard)
  if (extras.length > 0) {
    const text = [base, ...extras].join('\n')
    return learner ? `${text}\n${learner}` : text
  }
  if (!learner) return base
  if (base.endsWith('.') || base.endsWith('!') || base.endsWith('?')) return `${base} ${learner}`
  return `${base}. ${learner}`
}

function mathCodeLines(whiteboard: Whiteboard): string[] {
  const lines: string[] = []
  for (const element of elementsOf(whiteboard)) {
    if (element.kind === 'math') lines.push(`math formula: ${element.latex}`)
    else if (element.kind === 'code') {
      lines.push(`code block in ${element.language}, ${lineCount(element.code)} lines`)
    } else if (element.kind === 'graph') lines.push(graphLine(element))
  }
  return lines
}

function graphLine(element: GraphElement): string {
  const start = formatAxis(element.x_min)
  const end = formatAxis(element.x_max)
  const only = element.series.length === 1 ? element.series[0] : undefined
  if (only && isFunctionSeries(only)) {
    return `graph of y = ${only.expression} from ${start} to ${end}`
  }
  return `graph with ${element.series.length} series from ${start} to ${end}`
}

function isFunctionSeries(series: GraphSeries): series is GraphSeries & { expression: string } {
  return 'expression' in series && !('points' in series)
}

function formatAxis(value: number): string {
  if (Number.isFinite(value) && value === Math.trunc(value)) return String(Math.trunc(value))
  return value.toFixed(6).replace(/0+$/, '').replace(/\.$/, '')
}

function lineCount(code: string): number {
  // Match Python str.splitlines so the caption agrees with the API.
  if (!code) return 1
  const lines = code.split(/\r\n|\n|\r/)
  if (lines.length > 1 && lines[lines.length - 1] === '') lines.pop()
  return lines.length || 1
}

function elementsOf(whiteboard: Whiteboard): WhiteboardElement[] {
  return whiteboard.steps.flatMap((step) => step.elements)
}

function learnerSentence(whiteboard: Whiteboard): string {
  const elements = elementsOf(whiteboard).filter((element) => {
    if (element.author !== 'learner') return false
    return element.kind !== 'math' && element.kind !== 'code'
  })
  const comments = whiteboard.comments.filter((comment) => comment.author === 'learner')
  if (elements.length === 0 && comments.length === 0) return ''
  const counts: string[] = []
  if (elements.length > 0) {
    counts.push(`${elements.length} ${elements.length === 1 ? 'shape' : 'shapes'}`)
  }
  if (comments.length > 0) {
    counts.push(`${comments.length} ${comments.length === 1 ? 'comment' : 'comments'}`)
  }
  const details = [
    ...elements.map(screenPhrase),
    ...comments.map((comment) => `"${comment.text}"`),
  ]
  return `Learner added ${counts.join(' and ')}: ${details.join(', ')}.`
}

function drawingSummary(whiteboard: Whiteboard): string {
  const phrases = [
    ...elementsOf(whiteboard)
      .filter((element) => element.kind !== 'math' && element.kind !== 'code' && element.kind !== 'graph')
      .map(screenPhrase),
    ...whiteboard.comments.map((comment) => commentPhrase(comment)),
  ]
  if (phrases.length === 0) return 'An empty whiteboard.'
  return `${capitalize(joinPhrases(phrases))}.`
}

function commentPhrase(comment: Comment): string {
  return `a comment "${comment.text}"`
}

function screenPhrase(element: WhiteboardElement): string {
  if (element.kind === 'mark') {
    if (element.mark === 'note' && element.text?.trim()) return `a note "${element.text}"`
    return an(`${element.mark} mark`)
  }
  if (element.kind === 'text') {
    if (element.text.trim()) return `text reading "${element.text}"`
    return 'text'
  }
  if (element.kind === 'freehand') return 'a freehand line'
  return an(element.kind)
}

function an(name: string): string {
  const article = 'aeiou'.includes(name[0]?.toLowerCase() ?? '') ? 'an' : 'a'
  return `${article} ${name}`
}

function joinPhrases(phrases: string[]): string {
  if (phrases.length === 1) return phrases[0]
  if (phrases.length === 2) return `${phrases[0]} and ${phrases[1]}`
  return `${phrases.slice(0, -1).join(', ')}, and ${phrases[phrases.length - 1]}`
}

function capitalize(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text
}
