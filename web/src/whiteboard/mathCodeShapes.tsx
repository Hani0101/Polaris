import katex from 'katex'
import {
  BaseBoxShapeUtil,
  HTMLContainer,
  T,
  type RecordProps,
  type TLShape,
} from 'tldraw'

export const MATH_SHAPE_TYPE = 'math'
export const CODE_SHAPE_TYPE = 'code'

declare module '@tldraw/tlschema' {
  export interface TLGlobalShapePropsMap {
    [MATH_SHAPE_TYPE]: { w: number; h: number; latex: string }
    [CODE_SHAPE_TYPE]: { w: number; h: number; language: string; code: string }
  }
}

export type MathShape = TLShape<typeof MATH_SHAPE_TYPE>
export type CodeShape = TLShape<typeof CODE_SHAPE_TYPE>

const mathProps: RecordProps<MathShape> = {
  w: T.number,
  h: T.number,
  latex: T.string,
}

const codeProps: RecordProps<CodeShape> = {
  w: T.number,
  h: T.number,
  language: T.string,
  code: T.string,
}

const codeStyle = {
  fontFamily: 'var(--font-family-mono), ui-monospace, monospace',
  margin: 0,
  whiteSpace: 'pre' as const,
}

export function MathFormula({ latex }: { latex: string }) {
  let html: string | null = null
  try {
    html = katex.renderToString(latex, { throwOnError: true, displayMode: true })
  } catch {
    html = null
  }
  if (html === null) {
    return (
      <HTMLContainer className="whiteboard-math">
        <span className="whiteboard-math-source">{latex}</span>
      </HTMLContainer>
    )
  }
  return (
    <HTMLContainer className="whiteboard-math">
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </HTMLContainer>
  )
}

export function CodeBlock({ language, code }: { language: string; code: string }) {
  return (
    <HTMLContainer className="whiteboard-code-shape">
      <pre className="whiteboard-code" data-language={language} style={codeStyle}>
        <code>{code}</code>
      </pre>
    </HTMLContainer>
  )
}

export class MathShapeUtil extends BaseBoxShapeUtil<MathShape> {
  static override type = MATH_SHAPE_TYPE
  static override props = mathProps

  override getDefaultProps(): MathShape['props'] {
    return { w: 200, h: 80, latex: '' }
  }

  override component(shape: MathShape) {
    return <MathFormula latex={shape.props.latex} />
  }

  override getIndicatorPath(shape: MathShape) {
    const path = new Path2D()
    path.rect(0, 0, shape.props.w, shape.props.h)
    return path
  }
}

export class CodeShapeUtil extends BaseBoxShapeUtil<CodeShape> {
  static override type = CODE_SHAPE_TYPE
  static override props = codeProps

  override getDefaultProps(): CodeShape['props'] {
    return { w: 240, h: 120, language: '', code: '' }
  }

  override component(shape: CodeShape) {
    return <CodeBlock language={shape.props.language} code={shape.props.code} />
  }

  override getIndicatorPath(shape: CodeShape) {
    const path = new Path2D()
    path.rect(0, 0, shape.props.w, shape.props.h)
    return path
  }
}

export const mathCodeShapeUtils = [MathShapeUtil, CodeShapeUtil]
