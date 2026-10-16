import {
  BaseBoxShapeUtil,
  SVGContainer,
  T,
  type RecordProps,
  type TLShape,
} from 'tldraw'

export const GRAPH_SHAPE_TYPE = 'graph'

export type GraphPlot = { x: number; y: number }

export type GraphSeriesProps = { plotted: GraphPlot[] }

declare module '@tldraw/tlschema' {
  export interface TLGlobalShapePropsMap {
    [GRAPH_SHAPE_TYPE]: {
      w: number
      h: number
      xLabel: string
      yLabel: string
      xMin: number
      xMax: number
      yMin: number
      yMax: number
      stroke: string
      series: GraphSeriesProps[]
    }
  }
}

export type GraphShape = TLShape<typeof GRAPH_SHAPE_TYPE>

const plottedPoint = T.object({ x: T.number, y: T.number })
const seriesValidator = T.object({ plotted: T.arrayOf(plottedPoint) })

const graphProps: RecordProps<GraphShape> = {
  w: T.number,
  h: T.number,
  xLabel: T.string,
  yLabel: T.string,
  xMin: T.number,
  xMax: T.number,
  yMin: T.number,
  yMax: T.number,
  stroke: T.string,
  series: T.arrayOf(seriesValidator),
}

const SERIES_DASHES = ['', '6 4', '2 3', '8 3 2 3']

export type GraphFigureProps = {
  width: number
  height: number
  xLabel: string
  yLabel: string
  xMin: number
  xMax: number
  yMin: number
  yMax: number
  stroke: string
  series: Array<{ plotted?: GraphPlot[] }>
}

function coordinate(value: number): string {
  if (value === Math.trunc(value)) return String(Math.trunc(value))
  return String(Math.round(value * 1000) / 1000)
}

function finitePlots(series: { plotted?: GraphPlot[] }): GraphPlot[] | null {
  const plotted = series.plotted
  if (!plotted || plotted.length === 0) return null
  if (plotted.some((point) => !Number.isFinite(point.x) || !Number.isFinite(point.y))) return null
  return plotted
}

function toPixel(
  x: number,
  y: number,
  xMin: number,
  xMax: number,
  yMin: number,
  yMax: number,
  width: number,
  height: number,
): { x: number; y: number } {
  return {
    x: ((x - xMin) / (xMax - xMin)) * width,
    y: (1 - (y - yMin) / (yMax - yMin)) * height,
  }
}

function horizontalAxis(yMin: number, yMax: number, height: number): number {
  if (yMin <= 0 && yMax >= 0) return (1 - (0 - yMin) / (yMax - yMin)) * height
  if (yMax < 0) return 0
  return height
}

function verticalAxis(xMin: number, xMax: number, width: number): number {
  if (xMin <= 0 && xMax >= 0) return ((0 - xMin) / (xMax - xMin)) * width
  if (xMax < 0) return width
  return 0
}

export function GraphFigure({
  width,
  height,
  xLabel,
  yLabel,
  xMin,
  xMax,
  yMin,
  yMax,
  stroke,
  series,
}: GraphFigureProps) {
  if (!(xMax > xMin) || !(yMax > yMin) || !(width > 0) || !(height > 0)) {
    return <SVGContainer className="whiteboard-graph" />
  }
  const xAxis = horizontalAxis(yMin, yMax, height)
  const yAxis = verticalAxis(xMin, xMax, width)
  const labelY = Math.min(Math.max(xAxis - 6, 14), height - 4)
  const labelX = Math.min(yAxis + 6, width - 4)
  return (
    <SVGContainer className="whiteboard-graph" viewBox={`0 0 ${width} ${height}`} overflow="hidden">
      <line
        data-axis="x"
        x1={coordinate(0)}
        y1={coordinate(xAxis)}
        x2={coordinate(width)}
        y2={coordinate(xAxis)}
        stroke={stroke}
        strokeWidth={1}
      />
      <line
        data-axis="y"
        x1={coordinate(yAxis)}
        y1={coordinate(0)}
        x2={coordinate(yAxis)}
        y2={coordinate(height)}
        stroke={stroke}
        strokeWidth={1}
      />
      <text x={width - 4} y={labelY} textAnchor="end" fontSize={12} fill={stroke}>
        {xLabel}
      </text>
      <text x={labelX} y={14} fontSize={12} fill={stroke}>
        {yLabel}
      </text>
      {series.map((item, index) => {
        const plotted = finitePlots(item)
        if (!plotted) return null
        const points = plotted
          .map((point) => {
            const pixel = toPixel(point.x, point.y, xMin, xMax, yMin, yMax, width, height)
            return `${coordinate(pixel.x)},${coordinate(pixel.y)}`
          })
          .join(' ')
        const dash = SERIES_DASHES[index] ?? SERIES_DASHES[SERIES_DASHES.length - 1]
        return (
          <polyline
            key={index}
            data-series={index}
            points={points}
            fill="none"
            stroke={stroke}
            strokeWidth={2}
            strokeDasharray={dash || undefined}
          />
        )
      })}
    </SVGContainer>
  )
}

export class GraphShapeUtil extends BaseBoxShapeUtil<GraphShape> {
  static override type = GRAPH_SHAPE_TYPE
  static override props = graphProps

  override getDefaultProps(): GraphShape['props'] {
    return {
      w: 240,
      h: 180,
      xLabel: '',
      yLabel: '',
      xMin: -1,
      xMax: 1,
      yMin: -1,
      yMax: 1,
      stroke: '#1f3a5f',
      series: [],
    }
  }

  override component(shape: GraphShape) {
    return (
      <GraphFigure
        width={shape.props.w}
        height={shape.props.h}
        xLabel={shape.props.xLabel}
        yLabel={shape.props.yLabel}
        xMin={shape.props.xMin}
        xMax={shape.props.xMax}
        yMin={shape.props.yMin}
        yMax={shape.props.yMax}
        stroke={shape.props.stroke}
        series={shape.props.series}
      />
    )
  }

  override getIndicatorPath(shape: GraphShape) {
    const path = new Path2D()
    path.rect(0, 0, shape.props.w, shape.props.h)
    return path
  }
}

export const graphShapeUtils = [GraphShapeUtil]
