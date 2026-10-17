import type { Style } from '../api.ts'

// Solid colors from tldraw's default light theme. Polaris stores a stroke
// as text (often hex). tldraw shapes use one of these names.
const SOLID_COLORS = [
  { name: 'black', red: 0x1d, green: 0x1d, blue: 0x1d },
  { name: 'grey', red: 0x9f, green: 0xa8, blue: 0xb2 },
  { name: 'light-violet', red: 0xe0, green: 0x85, blue: 0xf4 },
  { name: 'violet', red: 0xae, green: 0x3e, blue: 0xc9 },
  { name: 'blue', red: 0x44, green: 0x65, blue: 0xe9 },
  { name: 'light-blue', red: 0x4b, green: 0xa1, blue: 0xf1 },
  { name: 'yellow', red: 0xf1, green: 0xac, blue: 0x4b },
  { name: 'orange', red: 0xe1, green: 0x69, blue: 0x19 },
  { name: 'green', red: 0x09, green: 0x92, blue: 0x68 },
  { name: 'light-green', red: 0x4c, green: 0xb0, blue: 0x5e },
  { name: 'light-red', red: 0xf8, green: 0x77, blue: 0x77 },
  { name: 'red', red: 0xe0, green: 0x31, blue: 0x31 },
  { name: 'white', red: 0xff, green: 0xff, blue: 0xff },
] as const

// tldraw's default theme stroke width is 2, which is the small size.
// Wider Polaris strokes step up through the four tldraw sizes.
const STROKE_SIZES = [
  { size: 's', maxWidth: 2 },
  { size: 'm', maxWidth: 3.5 },
  { size: 'l', maxWidth: 5 },
] as const

// Wider than the last named step, so it maps back to tldraw's xl size.
const XL_STROKE_WIDTH = STROKE_SIZES[STROKE_SIZES.length - 1].maxWidth + 3

const STROKE_WIDTH_BY_SIZE: Record<string, number> = {
  s: STROKE_SIZES[0].maxWidth,
  m: STROKE_SIZES[1].maxWidth,
  l: STROKE_SIZES[2].maxWidth,
  xl: XL_STROKE_WIDTH,
}

export const learnerTextHeight = 32

export type PenSet = 'onLight' | 'onDark'

// The 6 pen boxes (DESIGN.md 2.3 and Color swatch picker). Box 1 is the
// tutor's pen, box 2 the learner's. The swatch shows the token color for the
// board's pen set; the stroke is drawn with a tldraw named color.
// DS-GAP: tldraw draws only its named palette, not the pen hex values, so each
// box maps to one named color by meaning (orange stays orange), used
// color.whiteboard.pen.* for the swatch only. tldraw's "black" turns light on
// a dark board, which matches the onDark tutor pen.
export const penColors = [
  { key: 'tutor', tldraw: 'black', name: { onLight: 'Black', onDark: 'White' } },
  { key: 'learner', tldraw: 'blue', name: { onLight: 'Blue', onDark: 'Blue' } },
  { key: 'red', tldraw: 'red', name: { onLight: 'Red', onDark: 'Red' } },
  { key: 'green', tldraw: 'green', name: { onLight: 'Green', onDark: 'Green' } },
  { key: 'orange', tldraw: 'orange', name: { onLight: 'Orange', onDark: 'Orange' } },
  { key: 'purple', tldraw: 'violet', name: { onLight: 'Purple', onDark: 'Purple' } },
] as const

export type PenColor = (typeof penColors)[number]['tldraw']

/** The learner pen, box 2. */
export const learnerPenColor: PenColor = 'blue'

export function penSwatchVar(set: PenSet, key: (typeof penColors)[number]['key']): string {
  const mode = set === 'onDark' ? 'on-dark' : 'on-light'
  return `var(--color-whiteboard-pen-${mode}-${key})`
}

export const whiteboardMarks = {
  dash: 'solid',
  font: 'sans',
  textAlign: 'start',
  textAutoSize: false,
  // A label inside a box is centered, as the backend layout check assumes.
  labelAlign: 'middle',
  labelVerticalAlign: 'middle',
  arrowKind: 'arc',
  arrowBend: 0,
  arrowheadStart: 'none',
  arrowheadEnd: 'arrow',
  lineSpline: 'line',
  scale: 1,
  fallbackColor: 'black',
  filled: 'semi',
  open: 'none',
  freehandComplete: true,
  freehandClosed: false,
  freehandPen: false,
} as const

// Agent marks use one color and a dashed stroke.
export const agentMarkLook = {
  color: 'red',
  dash: 'dashed',
  fill: whiteboardMarks.open,
} as const

// Parts the agent added beside the learner's drawing (WB-20): the tutor's pen,
// box 1, dashed. The learner only draws solid lines, so the dash tells them
// apart; red stays for marks.
export const agentAddedLook = {
  color: 'black',
  dash: 'dashed',
} as const

export type MappedStyle = {
  color: (typeof SOLID_COLORS)[number]['name']
  fill: typeof whiteboardMarks.filled | typeof whiteboardMarks.open
  dash: typeof whiteboardMarks.dash
  size: (typeof STROKE_SIZES)[number]['size'] | 'xl'
  font: typeof whiteboardMarks.font
}

type Rgb = { red: number; green: number; blue: number }

function parseHex(value: string): Rgb | null {
  const match = /^#([\da-f]{3}|[\da-f]{6})$/i.exec(value.trim())
  if (!match) return null
  const hex = match[1]
  if (hex.length === 3) {
    return {
      red: Number.parseInt(hex[0] + hex[0], 16),
      green: Number.parseInt(hex[1] + hex[1], 16),
      blue: Number.parseInt(hex[2] + hex[2], 16),
    }
  }
  return {
    red: Number.parseInt(hex.slice(0, 2), 16),
    green: Number.parseInt(hex.slice(2, 4), 16),
    blue: Number.parseInt(hex.slice(4, 6), 16),
  }
}

function distance(left: Rgb, right: Rgb): number {
  const red = left.red - right.red
  const green = left.green - right.green
  const blue = left.blue - right.blue
  return red * red + green * green + blue * blue
}

function nearestColor(stroke: string): MappedStyle['color'] {
  const rgb = parseHex(stroke)
  if (!rgb) return whiteboardMarks.fallbackColor
  let best: (typeof SOLID_COLORS)[number] = SOLID_COLORS[0]
  let bestDistance = distance(rgb, best)
  for (const color of SOLID_COLORS) {
    const next = distance(rgb, color)
    if (next < bestDistance) {
      best = color
      bestDistance = next
    }
  }
  return best.name
}

function strokeSize(width: number): MappedStyle['size'] {
  for (const step of STROKE_SIZES) {
    if (width <= step.maxWidth) return step.size
  }
  return 'xl'
}

function hex(color: { red: number; green: number; blue: number }): string {
  const part = (value: number) => value.toString(16).padStart(2, '0')
  return `#${part(color.red)}${part(color.green)}${part(color.blue)}`
}

export function styleFromShapeProps(props: {
  color?: unknown
  fill?: unknown
  size?: unknown
}): Style {
  const name = typeof props.color === 'string' ? props.color : whiteboardMarks.fallbackColor
  const color = SOLID_COLORS.find((entry) => entry.name === name) ?? SOLID_COLORS[0]
  const sizeName = typeof props.size === 'string' ? props.size : 's'
  const strokeWidth = STROKE_WIDTH_BY_SIZE[sizeName] ?? STROKE_WIDTH_BY_SIZE.s
  const filled = typeof props.fill === 'string' && props.fill !== whiteboardMarks.open
  return {
    stroke: hex(color),
    fill: filled ? hex(color) : null,
    stroke_width: strokeWidth,
  }
}

export function mapStyle(style: Style): MappedStyle {
  return {
    color: nearestColor(style.stroke),
    fill: style.fill ? whiteboardMarks.filled : whiteboardMarks.open,
    dash: whiteboardMarks.dash,
    size: strokeSize(style.stroke_width),
    font: whiteboardMarks.font,
  }
}
