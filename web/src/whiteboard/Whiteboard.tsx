import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from 'react'
import { DefaultColorStyle, Tldraw, useValue, type Editor, type TLShape } from 'tldraw'
import 'katex/dist/katex.min.css'
import 'tldraw/tldraw.css'
import type { Comment, Whiteboard as WhiteboardData } from '../api.ts'
import { CommentPins } from './CommentPins.tsx'
import { readableDescription } from './description.ts'
import {
  allowedTldrawTools,
  learnerDrawingTools,
  tldrawToolFor,
  toolFromTldraw,
  type ToolId,
} from './drawingTools.ts'
import { pointedParts, type PointedPart } from './pointing.ts'
import { learnerPenColor, type PenColor } from './style.ts'
import { SwatchPicker } from './SwatchPicker.tsx'
import { Toolbar } from './Toolbar.tsx'
import {
  applyLearnerShapes,
  isCanonicalAgentShape,
  type LearnerShape,
} from './fromTldraw.ts'
import { graphShapeUtils } from './graphShapes.tsx'
import { mathCodeShapeUtils } from './mathCodeShapes.tsx'
import { whiteboardToShapes } from './toTldraw.ts'

const penTools = new Set<ToolId>(learnerDrawingTools.map((item) => item.id))

type WhiteboardProps = {
  whiteboard: WhiteboardData
  mode?: 'view' | 'draw'
  onChange?: (whiteboard: WhiteboardData) => void
  onAsk?: (parts: PointedPart[]) => void
}

type AskAt = {
  parts: PointedPart[]
  left: number
  top: number
}

const editors = new WeakMap<HTMLElement, Editor>()

export function whiteboardEditor(region: HTMLElement) {
  const editor = editors.get(region)
  if (!editor) throw new Error('The whiteboard is not ready.')
  return editor
}

export function selectElements(region: HTMLElement, elementIds: string[]) {
  const editor = whiteboardEditor(region)
  const wanted = new Set(elementIds)
  const pageShapes = editor.getCurrentPageShapes()
  const shapes = pageShapes.filter((shape) => {
    const elementId = shape.meta?.elementId
    return typeof elementId === 'string' && wanted.has(elementId)
  })
  if (shapes.length !== elementIds.length) {
    throw new Error(`Could not select ${elementIds.join(', ')}.`)
  }
  const ordered = elementIds.map((elementId) => {
    const shape = shapes.find((item) => item.meta?.elementId === elementId)
    if (!shape) throw new Error(`Could not select ${elementId}.`)
    return shape
  })
  editor.setSelectedShapes(ordered)
}

function askAt(editor: Editor, whiteboard: WhiteboardData): AskAt | null {
  const parts = pointedParts(
    whiteboard,
    editor.getSelectedShapes().map((shape) => ({
      id: shape.id,
      elementId: typeof shape.meta?.elementId === 'string' ? shape.meta.elementId : undefined,
    })),
  )
  if (parts.length === 0) return null
  try {
    const bounds = editor.getSelectionScreenBounds()
    const container = editor.getContainer()
    const maxLeft = Math.max(container.clientWidth - 12, 12)
    const maxTop = Math.max(container.clientHeight - 12, 12)
    if (!bounds) return { parts, left: 12, top: 12 }
    return {
      parts,
      left: Math.min(Math.max(bounds.x + bounds.w / 2, 12), maxLeft),
      top: Math.min(Math.max(bounds.y, 12), maxTop),
    }
  } catch {
    return { parts, left: 12, top: 12 }
  }
}

function sameAsk(left: AskAt | null, right: AskAt | null): boolean {
  if (left === right) return true
  if (!left || !right) return false
  if (left.left !== right.left || left.top !== right.top || left.parts.length !== right.parts.length) {
    return false
  }
  return left.parts.every(
    (part, index) => part.id === right.parts[index].id && part.label === right.parts[index].label,
  )
}

function asLearnerShape(shape: TLShape): LearnerShape {
  return {
    id: shape.id,
    type: shape.type,
    x: shape.x,
    y: shape.y,
    meta: shape.meta as LearnerShape['meta'],
    props: shape.props,
  }
}

function agentIdsOf(whiteboard: WhiteboardData): Set<string> {
  return new Set(
    whiteboard.steps.flatMap((step) =>
      step.elements.filter((element) => element.author === 'agent').map((element) => element.id),
    ),
  )
}

function commentTarget(editor: Editor): Pick<Comment, 'position' | 'element_id'> {
  const selected = editor.getSelectedShapes()
  if (selected.length === 1) {
    const elementId = selected[0].meta?.elementId
    if (typeof elementId === 'string' && elementId.trim()) return { element_id: elementId }
  }
  const center = editor.getViewportPageBounds().center
  return { position: { x: center.x, y: center.y } }
}

function nextCommentId(comments: Comment[]): string {
  const id = `learner-comment-${crypto.randomUUID()}`
  if (comments.some((comment) => comment.id === id)) return nextCommentId(comments)
  return id
}

export function Whiteboard({ whiteboard, mode = 'view', onChange, onAsk }: WhiteboardProps) {
  const converted = useMemo(() => whiteboardToShapes(whiteboard), [whiteboard])
  const region = useRef<HTMLElement>(null)
  const [editor, setEditor] = useState<Editor | null>(null)
  const [commenting, setCommenting] = useState(false)
  const [geo, setGeo] = useState<'rectangle' | 'ellipse'>('rectangle')
  const commentField = useRef<HTMLInputElement>(null)
  const [ask, setAsk] = useState<AskAt | null>(null)
  const [draft, setDraft] = useState('')
  const [comments, setComments] = useState(whiteboard.comments)
  const whiteboardRef = useRef(whiteboard)
  const commentsRef = useRef(whiteboard.comments)
  const onChangeRef = useRef(onChange)
  const onAskRef = useRef(onAsk)
  const convertedRef = useRef(converted)
  const seeding = useRef(false)
  const geoKind = useRef<'rectangle' | 'ellipse'>('rectangle')
  const commentFieldId = useId()
  const captionId = useId()
  const [drawn, setDrawn] = useState(whiteboard)
  const tldrawTool = useValue('tool', () => editor?.getCurrentToolId() ?? 'select', [editor])
  const active = toolFromTldraw(tldrawTool, geo, commenting)
  // Pens follow the board (DESIGN.md 2.3). The board follows the app mode.
  const penSet = useValue(
    'pen set',
    () => (editor?.getColorMode() === 'dark' ? 'onDark' : 'onLight'),
    [editor],
  )
  const penColor = useValue(
    'pen color',
    (): string => (editor ? editor.getStyleForNextShape(DefaultColorStyle) : learnerPenColor),
    [editor],
  )

  useEffect(() => {
    setDrawn(whiteboard)
  }, [whiteboard])

  useEffect(() => {
    whiteboardRef.current = whiteboard
    commentsRef.current = comments
    onChangeRef.current = onChange
    onAskRef.current = onAsk
    convertedRef.current = converted
  })

  useEffect(() => {
    if (mode !== 'draw') return
    commentsRef.current = whiteboardRef.current.comments
    setComments(whiteboardRef.current.comments)
  }, [mode, whiteboard.id])

  useEffect(() => {
    if (!editor || !region.current || mode !== 'view') return
    const node = region.current
    try {
      // createShapes does nothing while the editor is readonly, so unlock,
      // replace the shapes, then lock again. Selection still works when locked.
      editor.updateInstanceState({ isReadonly: false })
      const existing = [...editor.getCurrentPageShapeIds()]
      if (existing.length > 0) editor.deleteShapes(existing)
      if (converted.shapes.length > 0) editor.createShapes(converted.shapes)
      editor.setSelectedShapes([])
      editor.zoomToFit({ animation: { duration: 0 } })
      node.dataset.ready = 'true'
    } catch {
      node.dataset.ready = 'false'
    } finally {
      editor.updateInstanceState({ isReadonly: true })
    }
  }, [editor, mode, converted])

  useEffect(() => {
    if (!editor || !region.current || mode !== 'draw') return
    const node = region.current
    const agentIds = agentIdsOf(whiteboardRef.current)
    const publish = () => {
      const report = onChangeRef.current
      if (!report || seeding.current) return
      const next = {
        ...applyLearnerShapes(
          whiteboardRef.current,
          editor.getCurrentPageShapes().map(asLearnerShape),
        ),
        comments: commentsRef.current,
      }
      setDrawn(next)
      report(next)
    }
    try {
      editor.updateInstanceState({ isReadonly: false })
      if (editor.getCurrentPageShapeIds().size === 0) {
        seeding.current = true
        try {
          const shapes = convertedRef.current.shapes
          if (shapes.length > 0) editor.createShapes(shapes)
          editor.zoomToFit({ animation: { duration: 0 } })
        } finally {
          seeding.current = false
        }
      }
      // The learner draws with pen box 2 (DESIGN.md 2.3).
      editor.setStyleForNextShapes(DefaultColorStyle, learnerPenColor, { history: 'ignore' })
      // Undo starts empty, so it never takes back the stored drawing.
      editor.clearHistory()
      const stopCreate = editor.sideEffects.registerBeforeCreateHandler('shape', (shape) => {
        if (shape.meta?.author === 'agent' || shape.meta?.author === 'learner') return shape
        const existing =
          typeof shape.meta?.elementId === 'string' ? shape.meta.elementId.trim() : ''
        const raw = shape.id.startsWith('shape:') ? shape.id.slice('shape:'.length) : shape.id
        const elementId = existing || (raw ? `learner-${raw}` : raw)
        const meta = { ...shape.meta, author: 'learner' as const, elementId }
        if (shape.type === 'geo') {
          return { ...shape, meta, props: { ...shape.props, geo: geoKind.current } }
        }
        return { ...shape, meta }
      })
      const stopChange = editor.sideEffects.registerBeforeChangeHandler('shape', (prev, next) => {
        if (isCanonicalAgentShape(asLearnerShape(prev), agentIds)) return prev
        return next
      })
      const stopDelete = editor.sideEffects.registerBeforeDeleteHandler('shape', (shape) => {
        if (isCanonicalAgentShape(asLearnerShape(shape), agentIds)) return false
      })
      const stopTools = editor.store.listen(
        () => {
          if (!allowedTldrawTools.has(editor.getCurrentToolId())) editor.setCurrentTool('select')
        },
        { source: 'user', scope: 'session' },
      )
      const stopShapes = editor.store.listen(
        () => {
          publish()
        },
        { source: 'user', scope: 'document' },
      )
      node.dataset.ready = 'true'
      return () => {
        stopCreate()
        stopChange()
        stopDelete()
        stopTools()
        stopShapes()
      }
    } catch {
      node.dataset.ready = 'false'
    }
  }, [editor, mode, whiteboard.id])

  useEffect(() => {
    const node = region.current
    if (!editor || !node) return
    editors.set(node, editor)
    const sync = () => {
      const next = onAskRef.current ? askAt(editor, whiteboardRef.current) : null
      setAsk((current) => (sameAsk(current, next) ? current : next))
    }
    sync()
    const stop = editor.store.listen(sync)
    return () => {
      stop()
      editors.delete(node)
    }
  }, [editor, whiteboard])

  function chooseTool(next: ToolId) {
    if (!editor) return
    if (next === 'rectangle' || next === 'ellipse') {
      geoKind.current = next
      setGeo(next)
    }
    setCommenting(next === 'comment')
    editor.setCurrentTool(tldrawToolFor[next])
    // Comment uses the select tool: pick a part, then write in the comment field.
    if (next === 'comment') commentField.current?.focus()
  }

  function choosePen(color: PenColor) {
    editor?.setStyleForNextShapes(DefaultColorStyle, color)
  }

  // Removes only the learner's shapes. The agent's drawing and marks stay,
  // and the comments stay. It is not undoable, as the confirm dialog says.
  function clearBoard() {
    if (!editor) return
    const learner = editor
      .getCurrentPageShapes()
      .filter((shape) => shape.meta?.author === 'learner')
      .map((shape) => shape.id)
    if (learner.length > 0) editor.deleteShapes(learner)
    editor.clearHistory()
  }

  function leaveComment(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || !editor) return
    const comment: Comment = {
      id: nextCommentId(commentsRef.current),
      author: 'learner',
      text,
      ...commentTarget(editor),
    }
    const nextComments = [...commentsRef.current, comment]
    commentsRef.current = nextComments
    setComments(nextComments)
    setDraft('')
    setCommenting(false)
    const next = {
      ...applyLearnerShapes(
        whiteboardRef.current,
        editor.getCurrentPageShapes().map(asLearnerShape),
      ),
      comments: nextComments,
    }
    setDrawn(next)
    onChange?.(next)
  }

  const shown = mode === 'draw' ? comments : whiteboard.comments
  const described = mode === 'draw' ? { ...drawn, comments: shown } : whiteboard
  const caption = readableDescription(described)

  return (
    <section ref={region} className="whiteboard" aria-labelledby={captionId} data-mode={mode}>
      {converted.skipped.length > 0 ? (
        <p className="whiteboard-skipped" role="status">
          Some parts of this whiteboard were left out.
        </p>
      ) : null}
      <div className="whiteboard-surface">
        <Tldraw
          hideUi
          autoFocus={false}
          colorScheme="system"
          onMount={setEditor}
          shapeUtils={[...mathCodeShapeUtils, ...graphShapeUtils]}
        />
        <CommentPins editor={editor} comments={shown} />
        {mode === 'draw' ? (
          <div className="wb-dock">
            <Toolbar editor={editor} active={active} onTool={chooseTool} onClear={clearBoard} />
            {active && penTools.has(active) ? (
              <SwatchPicker set={penSet} value={penColor} onChange={choosePen} />
            ) : null}
          </div>
        ) : null}
        {ask && onAsk ? (
          <button
            type="button"
            className="whiteboard-ask"
            style={{ left: ask.left, top: ask.top }}
            onClick={() => onAsk(ask.parts)}
          >
            Ask about this
          </button>
        ) : null}
      </div>
      <p id={captionId} className="whiteboard-caption">
        {caption}
      </p>
      {shown.length > 0 ? (
        <ul className="visually-hidden" aria-label="Comments">
          {shown.map((comment) => (
            <li key={comment.id}>
              <span>{comment.text}</span>
              {comment.element_id ? (
                <span className="whiteboard-comment-where">About {comment.element_id}</span>
              ) : comment.position ? (
                <span className="whiteboard-comment-where">
                  At ({comment.position.x}, {comment.position.y})
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {mode === 'draw' ? (
        <form className="wb-comment-form" onSubmit={leaveComment}>
          <label htmlFor={commentFieldId} className="wb-comment-label">
            Comment
          </label>
          <div className="wb-comment-row">
            <input
              ref={commentField}
              id={commentFieldId}
              className="wb-comment-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="submit" className="secondary" disabled={!editor || !draft.trim()}>
              Leave comment
            </button>
          </div>
        </form>
      ) : null}
    </section>
  )
}
