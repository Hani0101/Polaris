import { useId } from 'react'
import type { ReactNode } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  CODE_LINE_HEIGHT,
  CODE_PADDING,
  DEFAULT_TEXT_SIZE,
  TEXT_LINE_HEIGHT,
  seriesRole,
} from './format.ts'
import type {
  Animation,
  AnimationElement,
  AnimationPoint,
  ArrowElement,
  CodeElement,
  ColorRole,
  GraphElement,
  MathElement,
  TextElement,
} from './format.ts'
import { baseBox } from './playback.ts'
import type { ElementState, SceneState } from './playback.ts'

// Every stroke is the same width, in canvas units.
const STROKE = 3
const AXIS_STROKE = 1.5
const ARROW_HEAD_LENGTH = 14
const ARROW_HEAD_HALF_WIDTH = 7
// Axis labels belong to the graph, not to the text the check measures.
const AXIS_LABEL_SIZE = 16
const FILL_OPACITY = 0.15

type SceneProps = {
  animation: Animation
  scene: SceneState
  label: string
}

/**
 * One picture of an animation on the 400 by 300 canvas. Colour roles become
 * classes that map to design-system tokens (AN-14), so the picture follows
 * the theme. The whole drawing is one image to a screen reader (AN-15).
 */
export function Scene({ animation, scene, label }: SceneProps) {
  const clipBase = useId()
  return (
    <svg
      className="an-scene"
      viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
      role="img"
      aria-label={label}
      preserveAspectRatio="xMidYMid meet"
    >
      {animation.elements.map((element, index) => {
        const state = scene[element.id]
        if (!state || !state.visible) return null
        return (
          <g
            key={element.id}
            className={`an-el an-role-${state.color}`}
            data-element={element.id}
            opacity={state.opacity < 1 ? round(state.opacity) : undefined}
            transform={transformFor(element, state)}
          >
            {drawElement(element, state, `${clipBase}-${index}`)}
          </g>
        )
      })}
    </svg>
  )
}

function round(value: number): number {
  return Math.round(value * 1000) / 1000
}

function transformFor(element: AnimationElement, state: ElementState): string | undefined {
  const moved = state.dx !== 0 || state.dy !== 0
  const scaled = state.scale !== 1
  if (!moved && !scaled) return undefined
  const parts: string[] = []
  if (moved) parts.push(`translate(${round(state.dx)} ${round(state.dy)})`)
  if (scaled) {
    // Scale around the centre of the element's box.
    const box = baseBox(element, state.text)
    const cx = round((box.left + box.right) / 2)
    const cy = round((box.top + box.bottom) / 2)
    parts.push(`translate(${cx} ${cy}) scale(${round(state.scale)}) translate(${-cx} ${-cy})`)
  }
  return parts.join(' ')
}

/** Dash props that draw ``amount`` (0 to 1) of a stroke from its start. */
function traced(amount: number) {
  if (amount >= 1) return {}
  return {
    pathLength: 1,
    strokeDasharray: '1 1',
    strokeDashoffset: round(1 - Math.max(0, amount)),
  }
}

function pointsPath(points: AnimationPoint[], closed = false): string {
  const [first, ...rest] = points
  const segments = [`M${round(first.x)} ${round(first.y)}`]
  for (const point of rest) segments.push(`L${round(point.x)} ${round(point.y)}`)
  if (closed) segments.push('Z')
  return segments.join(' ')
}

function drawElement(element: AnimationElement, state: ElementState, clipId: string): ReactNode {
  switch (element.kind) {
    case 'rectangle':
      return (
        <rect
          x={element.x}
          y={element.y}
          width={element.width}
          height={element.height}
          className={element.filled ? 'an-shape is-filled' : 'an-shape'}
          fillOpacity={element.filled ? FILL_OPACITY : undefined}
          strokeWidth={STROKE}
        />
      )
    case 'ellipse':
      return (
        <ellipse
          cx={element.x + element.width / 2}
          cy={element.y + element.height / 2}
          rx={element.width / 2}
          ry={element.height / 2}
          className={element.filled ? 'an-shape is-filled' : 'an-shape'}
          fillOpacity={element.filled ? FILL_OPACITY : undefined}
          strokeWidth={STROKE}
        />
      )
    case 'line':
      return (
        <line
          x1={element.start.x}
          y1={element.start.y}
          x2={element.end.x}
          y2={element.end.y}
          className="an-stroke"
          strokeWidth={STROKE}
          {...traced(state.drawn[0])}
        />
      )
    case 'arrow':
      return <Arrow element={element} drawn={state.drawn[0]} />
    case 'path':
      return (
        <path
          d={pointsPath(element.points, element.closed)}
          className="an-stroke"
          strokeWidth={STROKE}
          {...traced(state.drawn[0])}
        />
      )
    case 'text':
      return <TextLines element={element} text={state.text ?? element.text} />
    case 'code':
      return <CodeLines element={element} />
    case 'math':
      return <MathFormula element={element} />
    case 'graph':
      return <Graph element={element} drawn={state.drawn} role={state.color} clipId={clipId} />
  }
}

function Arrow({ element, drawn }: { element: ArrowElement; drawn: number }) {
  const { start, end } = element
  const length = Math.hypot(end.x - start.x, end.y - start.y)
  if (length === 0) return null
  const ux = (end.x - start.x) / length
  const uy = (end.y - start.y) / length
  const head = Math.min(ARROW_HEAD_LENGTH, length)
  // The shaft stops inside the head, so its round cap does not poke out.
  const shaftEnd = { x: end.x - ux * head * 0.5, y: end.y - uy * head * 0.5 }
  const base = { x: end.x - ux * head, y: end.y - uy * head }
  const left = { x: base.x - uy * ARROW_HEAD_HALF_WIDTH, y: base.y + ux * ARROW_HEAD_HALF_WIDTH }
  const right = { x: base.x + uy * ARROW_HEAD_HALF_WIDTH, y: base.y - ux * ARROW_HEAD_HALF_WIDTH }
  return (
    <>
      <line
        x1={start.x}
        y1={start.y}
        x2={round(shaftEnd.x)}
        y2={round(shaftEnd.y)}
        className="an-stroke"
        strokeWidth={STROKE}
        {...traced(drawn)}
      />
      {drawn >= 1 ? (
        <polygon
          className="an-arrow-head"
          points={[end, left, right].map((p) => `${round(p.x)},${round(p.y)}`).join(' ')}
        />
      ) : null}
    </>
  )
}

function TextLines({ element, text }: { element: TextElement; text: string }) {
  const size = element.size ?? DEFAULT_TEXT_SIZE
  const lineHeight = size * TEXT_LINE_HEIGHT
  return (
    <text
      className="an-text"
      x={element.x}
      fontSize={size}
      textAnchor={element.align ?? 'start'}
      xmlSpace="preserve"
    >
      {text.split('\n').map((line, index) => (
        <tspan
          key={index}
          x={element.x}
          y={round(element.y + (index + 0.5) * lineHeight)}
          dominantBaseline="central"
        >
          {line}
        </tspan>
      ))}
    </text>
  )
}

function CodeLines({ element }: { element: CodeElement }) {
  const size = element.size ?? DEFAULT_TEXT_SIZE
  const box = baseBox(element)
  const lineHeight = size * CODE_LINE_HEIGHT
  return (
    <>
      <rect
        className="an-code-box"
        x={box.left}
        y={box.top}
        width={box.right - box.left}
        height={box.bottom - box.top}
        rx={4}
      />
      <text
        className="an-code"
        x={element.x + CODE_PADDING}
        fontSize={size}
        xmlSpace="preserve"
        data-language={element.language}
      >
        {element.code.split('\n').map((line, index) => (
          <tspan
            key={index}
            x={element.x + CODE_PADDING}
            y={round(element.y + CODE_PADDING + (index + 0.5) * lineHeight)}
            dominantBaseline="central"
          >
            {line}
          </tspan>
        ))}
      </text>
    </>
  )
}

function MathFormula({ element }: { element: MathElement }) {
  let html: string | null = null
  try {
    html = katex.renderToString(element.latex, { throwOnError: true, displayMode: false })
  } catch {
    html = null
  }
  return (
    <foreignObject x={element.x} y={element.y} width={element.width} height={element.height}>
      <div className="an-math" style={{ fontSize: `${element.size ?? DEFAULT_TEXT_SIZE}px` }}>
        {html === null ? (
          <span className="an-math-source">{element.latex}</span>
        ) : (
          <span dangerouslySetInnerHTML={{ __html: html }} />
        )}
      </div>
    </foreignObject>
  )
}

function axisAt(min: number, max: number, extent: number, flip: boolean): number {
  // The axis sits at zero when zero is in range, else on the nearer edge.
  const zero = Math.min(Math.max(0, min), max)
  const share = (zero - min) / (max - min)
  return flip ? (1 - share) * extent : share * extent
}

function Graph({
  element,
  drawn,
  role,
  clipId,
}: {
  element: GraphElement
  drawn: number[]
  role: ColorRole
  clipId: string
}) {
  const { x, y, width, height, x_min: xMin, x_max: xMax, y_min: yMin, y_max: yMax } = element
  const toCanvas = (point: AnimationPoint): AnimationPoint => ({
    x: x + ((point.x - xMin) / (xMax - xMin)) * width,
    y: y + (1 - (point.y - yMin) / (yMax - yMin)) * height,
  })
  const xAxis = y + axisAt(yMin, yMax, height, true)
  const yAxis = x + axisAt(xMin, xMax, width, false)
  return (
    <>
      <clipPath id={clipId}>
        <rect x={x} y={y} width={width} height={height} />
      </clipPath>
      <line
        className="an-stroke"
        data-axis="x"
        x1={x}
        y1={round(xAxis)}
        x2={x + width}
        y2={round(xAxis)}
        strokeWidth={AXIS_STROKE}
      />
      <line
        className="an-stroke"
        data-axis="y"
        x1={round(yAxis)}
        y1={y}
        x2={round(yAxis)}
        y2={y + height}
        strokeWidth={AXIS_STROKE}
      />
      {element.x_label ? (
        <text
          className="an-text an-axis-label"
          x={x + width}
          y={round(Math.max(xAxis - AXIS_LABEL_SIZE * 0.75, y + AXIS_LABEL_SIZE * 0.5))}
          fontSize={AXIS_LABEL_SIZE}
          textAnchor="end"
          dominantBaseline="central"
        >
          {element.x_label}
        </text>
      ) : null}
      {element.y_label ? (
        <text
          className="an-text an-axis-label"
          x={round(Math.min(yAxis + 6, x + width))}
          y={y + AXIS_LABEL_SIZE * 0.5}
          fontSize={AXIS_LABEL_SIZE}
          dominantBaseline="central"
        >
          {element.y_label}
        </text>
      ) : null}
      <g clipPath={`url(#${clipId})`}>
        {element.series.map((series, index) => {
          const plotted = series.plotted ?? []
          const amount = drawn[index] ?? 1
          if (plotted.length === 0 || amount <= 0) return null
          const roleClass = `an-role-${seriesRole(role, index)}`
          if (plotted.length === 1) {
            const point = toCanvas(plotted[0])
            return (
              <circle
                key={index}
                className={`an-dot ${roleClass}`}
                data-series={index}
                cx={round(point.x)}
                cy={round(point.y)}
                r={STROKE}
              />
            )
          }
          return (
            <path
              key={index}
              className={`an-stroke ${roleClass}`}
              data-series={index}
              d={pointsPath(plotted.map(toCanvas))}
              strokeWidth={STROKE}
              {...traced(amount)}
            />
          )
        })}
      </g>
    </>
  )
}
