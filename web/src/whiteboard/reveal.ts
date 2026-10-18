import type { Comment, Whiteboard, WhiteboardStep } from '../api.ts'

export type RevealPhase = 'streaming' | 'stopped' | 'done'

const COMPLETE_MARKER = /\[\[step:[^\]]*\]\]/g
const MARKER_OPENS = ['[[step:', '[[cite:']

export function revealWhiteboard<T extends Whiteboard>(
  whiteboard: T,
  rawReply: string,
  phase: RevealPhase,
): T | null {
  if (phase === 'done') return whiteboard
  const steps = stepsUnlockedBy(whiteboard.steps, rawReply)
  if (steps.length === 0) return null
  return {
    ...whiteboard,
    steps,
    comments: commentsWithSteps(whiteboard, steps),
  }
}

export function visibleReply(raw: string, streaming: boolean, markers: readonly string[] = []): string {
  let text = raw
  for (const marker of markers) {
    if (!marker) continue
    text = text.split(marker).join('')
  }
  text = text.replace(COMPLETE_MARKER, '')
  text = text.replace(/[ \t]{2,}/g, ' ')
  text = text.replace(/^[ \t]+/, '')
  if (!streaming) return text
  return hideIncompleteMarker(text)
}

/**
 * The pinned board while a reply adds to it (WB-20). The steps it had when the
 * turn began stay. A step added in this turn appears once its marker has
 * arrived in the reply text (WB-06).
 */
export function revealAddedSteps<T extends Whiteboard>(
  whiteboard: T,
  knownStepIds: ReadonlySet<string>,
  rawReply: string,
): T {
  const steps = whiteboard.steps.filter(
    (step) => knownStepIds.has(step.id) || (step.reply_part !== '' && rawReply.includes(step.reply_part)),
  )
  if (steps.length === whiteboard.steps.length) return whiteboard
  const shown = new Set(steps.flatMap((step) => step.elements.map((element) => element.id)))
  return {
    ...whiteboard,
    steps,
    comments: whiteboard.comments.filter(
      (comment) => !comment.element_id || shown.has(comment.element_id),
    ),
  }
}

function stepsUnlockedBy(steps: WhiteboardStep[], rawReply: string): WhiteboardStep[] {
  const unlocked: WhiteboardStep[] = []
  for (const step of steps) {
    if (!step.reply_part || !rawReply.includes(step.reply_part)) break
    unlocked.push(step)
  }
  return unlocked
}

function commentsWithSteps(whiteboard: Whiteboard, steps: WhiteboardStep[]): Comment[] {
  const shown = new Set(steps.flatMap((step) => step.elements.map((element) => element.id)))
  const firstShown = steps.some((step) => step.id === whiteboard.steps[0]?.id)
  return whiteboard.comments.filter((comment) => {
    if (comment.element_id) return shown.has(comment.element_id)
    return firstShown && comment.position != null
  })
}

function hideIncompleteMarker(text: string): string {
  const opened = text.lastIndexOf('[[')
  if (opened >= 0) {
    const tail = text.slice(opened)
    const unfinished =
      !tail.includes(']]') &&
      MARKER_OPENS.some((open) => tail.startsWith(open) || open.startsWith(tail))
    if (unfinished) return text.slice(0, opened).replace(/[ \t]+$/, '')
  }
  if (text.endsWith('[')) return text.slice(0, -1)
  return text
}
