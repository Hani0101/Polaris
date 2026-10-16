// The learner's whiteboard tools, in toolbar order (DESIGN.md, Whiteboard toolbar).
// Each drawing tool maps to a tldraw tool whose shapes fromTldraw can save.

export type ShapeToolId = 'line' | 'arrow' | 'rectangle' | 'ellipse'

export type ToolId = 'select' | 'draw' | 'eraser' | ShapeToolId | 'text' | 'comment' | 'hand'

/** The tldraw tool behind each Polaris tool. Comment has none: it uses select. */
export const tldrawToolFor: Record<ToolId, string> = {
  select: 'select',
  draw: 'draw',
  eraser: 'eraser',
  line: 'line',
  arrow: 'arrow',
  rectangle: 'geo',
  ellipse: 'geo',
  text: 'text',
  comment: 'select',
  hand: 'hand',
}

/** tldraw tools the learner may use. Anything else falls back to select. */
export const allowedTldrawTools = new Set(Object.values(tldrawToolFor))

/** The shapes behind the one Shapes button. */
export const shapeTools: ReadonlyArray<{ id: ShapeToolId; label: string }> = [
  { id: 'line', label: 'Line' },
  { id: 'arrow', label: 'Arrow' },
  { id: 'rectangle', label: 'Rectangle' },
  { id: 'ellipse', label: 'Circle' },
]

export const toolLabels: Record<ToolId, string> = {
  select: 'Select and move',
  draw: 'Pen',
  eraser: 'Eraser',
  line: 'Line',
  arrow: 'Arrow',
  rectangle: 'Rectangle',
  ellipse: 'Circle',
  text: 'Text',
  comment: 'Comment',
  hand: 'Pan and zoom',
}

/** Tools that draw something new, and so use the pen color. */
export const learnerDrawingTools: ReadonlyArray<{ id: ToolId; label: string }> = [
  { id: 'draw', label: toolLabels.draw },
  ...shapeTools,
  { id: 'text', label: toolLabels.text },
]

/** The Polaris tool for the current tldraw tool, or null when it has no button. */
export function toolFromTldraw(
  tldrawTool: string,
  geo: 'rectangle' | 'ellipse',
  commenting: boolean,
): ToolId | null {
  if (tldrawTool === 'select') return commenting ? 'comment' : 'select'
  if (tldrawTool === 'geo') return geo
  if (tldrawTool === 'draw') return 'draw'
  if (tldrawTool === 'eraser') return 'eraser'
  if (tldrawTool === 'line') return 'line'
  if (tldrawTool === 'arrow') return 'arrow'
  if (tldrawTool === 'text') return 'text'
  if (tldrawTool === 'hand') return 'hand'
  return null
}
