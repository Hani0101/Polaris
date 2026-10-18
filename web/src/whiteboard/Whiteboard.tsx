import {
  memo,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import { ChevronUp, PencilRuler } from 'lucide-react'
import { DefaultColorStyle, Tldraw, useValue, type Editor, type TLShape } from 'tldraw'
import 'katex/dist/katex.min.css'
import 'tldraw/tldraw.css'
import type { Comment, Whiteboard as WhiteboardData } from '../api.ts'
import { moveCamera } from './camera.ts'
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
import { boardTone } from './boardTone.ts'
import { whiteboardToShapes, type WhiteboardShapes } from './toTldraw.ts'

const TOOLS_KEY = 'polaris.whiteboard.tools'

const penTools = new Set<ToolId>(learnerDrawingTools.map((item) => item.id))

// One list for every board, so tldraw does not see new shape utils on each render.
const shapeUtils = [...mathCodeShapeUtils, ...graphShapeUtils]

export type WhiteboardProps = {
  whiteboard: WhiteboardData
  mode?: 'view' | 'draw'
  onChange?: (whiteboard: WhiteboardData) => void
  onAsk?: (parts: PointedPart[]) => void
  // The page uses the editor to take a picture of the board for the next turn.
  onEditor?: (editor: Editor | null) => void
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
    // Under the middle of the selection, in the board's own coordinates (the same ones the
    // comment pins use). The screen bounds count from the browser window, so they put the
    // button far from the selection. The CSS keeps it inside the board.
    const bounds = editor.getSelectionPageBounds()
    if (!bounds) return { parts, left: 12, top: 12 }
    const below = editor.pageToViewport({ x: bounds.x + bounds.w / 2, y: bounds.y + bounds.h })
    return { parts, left: below.x, top: below.y }
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

function drawShapes(editor: Editor, converted: WhiteboardShapes) {
  if (converted.shapes.length > 0) editor.createShapes(converted.shapes)
  if (converted.bindings.length > 0) editor.createBindings(converted.bindings)
}

/** Memoized, so a parent drawing again does not draw tldraw's providers and toolbar again. */
export const Whiteboard = memo(function Whiteboard({
  whiteboard,
  mode = 'view',
  onChange,
  onAsk,
  onEditor,
}: WhiteboardProps) {
  const converted = useMemo(() => whiteboardToShapes(whiteboard), [whiteboard])
  const region = useRef<HTMLElement>(null)
  // The board keeps the colors it first opened with, whatever the app mode becomes (WB-22).
  const tone = useMemo(() => boardTone(whiteboard.id), [whiteboard.id])
  const [editor, setEditor] = useState<Editor | null>(null)
  const [toolsShown, setToolsShown] = useState(() => {
    try {
      return window.localStorage.getItem(TOOLS_KEY) !== 'closed'
    } catch {
      return true
    }
  })
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
  // The steps last drawn in view mode, so a newly revealed step can be followed.
  const shownSteps = useRef<{ boardId: string; stepIds: string[] } | null>(null)
  const geoKind = useRef<'rectangle' | 'ellipse'>('rectangle')
  const commentFieldId = useId()
  const captionId = useId()
  const [drawn, setDrawn] = useState(whiteboard)
  const tldrawTool = useValue('tool', () => editor?.getCurrentToolId() ?? 'select', [editor])
  const active = toolFromTldraw(tldrawTool, geo, commenting)
  // Pens follow the board (DESIGN.md 2.3). A new board follows the app mode (WB-22).
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
    if (!onEditor) return
    onEditor(editor)
    return () => onEditor(null)
  }, [editor, onEditor])

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
      drawShapes(editor, converted)
      editor.setSelectedShapes([])
      const board = whiteboardRef.current
      const stepIds = board.steps.map((step) => step.id)
      const previous = shownSteps.current
      shownSteps.current = { boardId: board.id, stepIds }
      if (!previous || previous.boardId !== board.id || previous.stepIds.length === 0) {
        editor.zoomToFit({ animation: { duration: 0 } })
      } else {
        // A redraw with no new step leaves the camera where the learner put it.
        const added = stepIds.filter((stepId) => !previous.stepIds.includes(stepId))
        if (added.length > 0) moveCamera(editor, added)
      }
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
    // Read from the latest board, so a step the agent adds later is protected too (WB-20).
    const isAgentPart = (shape: TLShape) =>
      isCanonicalAgentShape(asLearnerShape(shape), agentIdsOf(whiteboardRef.current))
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
          drawShapes(editor, convertedRef.current)
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
        if (isAgentPart(prev)) return prev
        return next
      })
      const stopDelete = editor.sideEffects.registerBeforeDeleteHandler('shape', (shape) => {
        if (isAgentPart(shape)) return false
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

  // While the learner draws, a step the agent adds appears, and one taken back
  // goes, without touching their shapes (WB-20). Learner shapes are never redrawn here.
  useEffect(() => {
    if (!editor || mode !== 'draw') return
    const agentShapes = converted.shapes.filter((shape) => shape.meta?.author === 'agent')
    const wanted = new Set(agentShapes.map((shape) => shape.id))
    const gone = editor
      .getCurrentPageShapes()
      .filter((shape) => shape.meta?.author === 'agent' && !wanted.has(shape.id))
    if (gone.length > 0) {
      seeding.current = true
      try {
        editor.deleteShapes(gone.map((shape) => shape.id))
      } finally {
        seeding.current = false
      }
    }
    const missing = agentShapes.filter((shape) => !editor.getShape(shape.id))
    if (missing.length === 0) return
    const ids = new Set(missing.map((shape) => shape.id))
    seeding.current = true
    try {
      editor.createShapes(missing)
      const bindings = converted.bindings.filter(
        (binding) => ids.has(binding.fromId) || (binding.toId !== undefined && ids.has(binding.toId)),
      )
      if (bindings.length > 0) editor.createBindings(bindings)
    } finally {
      seeding.current = false
    }
    const stepIds = new Set(
      missing.flatMap((shape) => (typeof shape.meta?.stepId === 'string' ? [shape.meta.stepId] : [])),
    )
    moveCamera(editor, [...stepIds])
  }, [editor, mode, converted])

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

  // tldraw ignores the wheel until the board has focus, and the board does not
  // take focus on load. Focus it on the first wheel turn, unless the learner is typing.
  function focusForWheel() {
    if (!editor || editor.getInstanceState().isFocused) return
    if (document.activeElement?.closest('input, textarea')) return
    editor.focus()
  }

  function toggleTools() {
    const next = !toolsShown
    setToolsShown(next)
    try {
      window.localStorage.setItem(TOOLS_KEY, next ? 'open' : 'closed')
    } catch {
      // The choice just does not carry to the next visit.
    }
  }

  // Shift+1 brings the camera back to the content, as tldraw's own shortcut does.
  // The board has no tldraw UI, so the shortcut is handled here.
  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (!editor || !event.shiftKey || (event.key !== '!' && event.code !== 'Digit1')) return
    const target = event.target as HTMLElement
    if (target.closest('input, textarea, [contenteditable="true"]') || editor.getEditingShapeId()) {
      return
    }
    event.preventDefault()
    editor.zoomToFit({ animation: { duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 200 } })
  }

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

  // The wheel and a touchpad zoom the board; pinch zooms on a phone.
  // tldraw's saved input mode would override the wheel setting below.
  const onMount = useCallback((mounted: Editor) => {
    mounted.user.updateUserPreferences({ inputMode: null })
    mounted.setCameraOptions({ ...mounted.getCameraOptions(), wheelBehavior: 'zoom' })
    setEditor(mounted)
  }, [])

  const shown = mode === 'draw' ? comments : whiteboard.comments
  const caption = useMemo(
    () => readableDescription(mode === 'draw' ? { ...drawn, comments: shown } : whiteboard),
    [mode, drawn, shown, whiteboard],
  )

  return (
    <section
      ref={region}
      className="whiteboard"
      aria-labelledby={captionId}
      data-mode={mode}
      data-board={tone}
      onKeyDown={onKeyDown}
    >
      {converted.skipped.length > 0 ? (
        <p className="whiteboard-skipped" role="status">
          Some parts of this whiteboard were left out.
        </p>
      ) : null}
      <div className="whiteboard-surface" onWheelCapture={focusForWheel}>
        <Tldraw
          hideUi
          autoFocus={false}
          colorScheme={tone}
          onMount={onMount}
          shapeUtils={shapeUtils}
        />
        <CommentPins editor={editor} comments={shown} />
        {mode === 'draw' ? (
          <div className="wb-dock">
            <button
              type="button"
              className="icon-btn icon-btn--ghost wb-dock-toggle"
              aria-label={toolsShown ? 'Hide drawing tools' : 'Show drawing tools'}
              aria-expanded={toolsShown}
              onClick={toggleTools}
            >
              {toolsShown ? (
                <ChevronUp aria-hidden="true" size={20} strokeWidth={2} />
              ) : (
                <PencilRuler aria-hidden="true" size={20} strokeWidth={2} />
              )}
            </button>
            {toolsShown ? (
              <Toolbar editor={editor} active={active} onTool={chooseTool} onClear={clearBoard} />
            ) : null}
            {toolsShown && active && penTools.has(active) ? (
              <SwatchPicker set={penSet} value={penColor} onChange={choosePen} />
            ) : null}
          </div>
        ) : null}
        {ask && onAsk ? (
          <button
            type="button"
            className="whiteboard-ask"
            style={{ '--ask-left': `${ask.left}px`, '--ask-top': `${ask.top}px` } as CSSProperties}
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
})
