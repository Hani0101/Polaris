import type { Whiteboard, WhiteboardElement } from '../api.ts'

export type PointedPart = {
  id: string
  label: string
}

export type Pointing = {
  whiteboardId: string
  parts: PointedPart[]
}

export type SelectedShape = {
  id: string
  elementId?: string
}

export function elementLabel(element: WhiteboardElement): string {
  if (element.kind === 'text' && element.text.trim()) return element.text
  if (element.kind === 'math' && element.latex.trim()) return element.latex
  if (element.kind === 'code' && element.language.trim()) return element.language
  return element.kind
}

export function pointedParts(whiteboard: Whiteboard, selected: SelectedShape[]): PointedPart[] {
  const elements = new Map(
    whiteboard.steps.flatMap((step) => step.elements.map((element) => [element.id, element])),
  )
  const parts: PointedPart[] = []
  const seen = new Set<string>()
  for (const shape of selected) {
    const elementId = shape.elementId?.trim()
    if (!elementId || seen.has(elementId)) continue
    const element = elements.get(elementId)
    if (!element) continue
    seen.add(elementId)
    parts.push({ id: element.id, label: elementLabel(element) })
  }
  return parts
}

export function pointingFromTurn(
  pointing: { whiteboard_id: string; element_ids: string[] } | null | undefined,
  boards: Whiteboard[],
): Pointing | null {
  if (!pointing || pointing.element_ids.length === 0) return null
  const board = boards.find((item) => item.id === pointing.whiteboard_id)
  const elements = new Map(
    (board?.steps ?? []).flatMap((step) => step.elements.map((element) => [element.id, element])),
  )
  return {
    whiteboardId: pointing.whiteboard_id,
    parts: pointing.element_ids.map((id) => {
      const element = elements.get(id)
      return { id, label: element ? elementLabel(element) : id }
    }),
  }
}
