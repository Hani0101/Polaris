import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { MessageSquare } from 'lucide-react'
import { useValue, type Editor } from 'tldraw'
import type { Comment, Point } from '../api.ts'
import './toolbar.css'

type CommentPinsProps = {
  editor: Editor | null
  comments: Comment[]
}

type Spot = {
  comment: Comment
  number: number
  x: number
  y: number
}

type Layout = {
  spots: Spot[]
  width: number
  height: number
}

function commentAuthor(comment: Comment): string {
  return comment.author === 'agent' ? 'Polaris' : 'You'
}

/** Where a comment sits on the page: the top right corner of its element, or its own position. */
function pagePoint(editor: Editor, comment: Comment): Point | null {
  if (comment.element_id) {
    const shape = editor
      .getCurrentPageShapes()
      .find((item) => item.meta?.elementId === comment.element_id)
    const bounds = shape ? editor.getShapePageBounds(shape) : undefined
    if (bounds) return { x: bounds.maxX, y: bounds.minY }
  }
  return comment.position ?? null
}

export function CommentPins({ editor, comments }: CommentPinsProps) {
  const [openId, setOpenId] = useState<string | null>(null)
  const pins = useRef(new Map<string, HTMLButtonElement>())
  const card = useRef<HTMLDivElement>(null)
  const cardId = useId()

  // Recomputed when the camera, the shapes, or the board size change.
  const layout = useValue<Layout>(
    'comment pins',
    () => {
      if (!editor) return { spots: [], width: 0, height: 0 }
      const view = editor.getViewportScreenBounds()
      const sized = view.w > 0 && view.h > 0
      const spots: Spot[] = []
      comments.forEach((comment, index) => {
        const page = pagePoint(editor, comment)
        if (!page) return
        const at = editor.pageToViewport(page)
        if (sized && (at.x < 0 || at.y < 0 || at.x > view.w || at.y > view.h)) return
        spots.push({ comment, number: index + 1, x: at.x, y: at.y })
      })
      return { spots, width: view.w, height: view.h }
    },
    [editor, comments],
  )

  const open = layout.spots.find((spot) => spot.comment.id === openId) ?? null

  useEffect(() => {
    if (!openId) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setOpenId(null)
      pins.current.get(openId)?.focus()
    }
    const closeOutside = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (card.current?.contains(target) || pins.current.get(openId)?.contains(target)) return
      setOpenId(null)
    }
    document.addEventListener('keydown', closeOnEscape)
    document.addEventListener('pointerdown', closeOutside, true)
    return () => {
      document.removeEventListener('keydown', closeOnEscape)
      document.removeEventListener('pointerdown', closeOutside, true)
    }
  }, [openId])

  if (layout.spots.length === 0) return null

  function cardPlace(spot: Spot): CSSProperties {
    const right = layout.width > 0 && spot.x > layout.width / 2
    const below = layout.height <= 0 || spot.y <= layout.height / 2
    return {
      ...(right ? { right: layout.width - spot.x } : { left: spot.x }),
      ...(below ? { top: spot.y } : { bottom: layout.height - spot.y }),
    }
  }

  return (
    <div className="wb-pins">
      {layout.spots.map((spot) => {
        const author = commentAuthor(spot.comment)
        const isOpen = spot.comment.id === openId
        return (
          <button
            key={spot.comment.id}
            ref={(node) => {
              if (node) pins.current.set(spot.comment.id, node)
              else pins.current.delete(spot.comment.id)
            }}
            type="button"
            className="wb-pin"
            aria-label={`Comment ${spot.number} from ${author}`}
            aria-expanded={isOpen}
            aria-controls={isOpen ? cardId : undefined}
            style={{ left: spot.x, top: spot.y }}
            onClick={() => setOpenId(isOpen ? null : spot.comment.id)}
          >
            <span className="wb-pin-face">
              <MessageSquare aria-hidden="true" />
            </span>
          </button>
        )
      })}
      {open ? (
        <div
          ref={card}
          id={cardId}
          role="group"
          aria-label={`Comment ${open.number} from ${commentAuthor(open.comment)}`}
          className={
            open.y <= layout.height / 2 || layout.height <= 0
              ? 'wb-pin-card is-below'
              : 'wb-pin-card is-above'
          }
          style={cardPlace(open)}
        >
          <p className="wb-pin-author">{commentAuthor(open.comment)}</p>
          <p className="wb-pin-text">{open.comment.text}</p>
        </div>
      ) : null}
    </div>
  )
}
