import { useState, type KeyboardEvent, type ReactNode } from 'react'
import {
  ArrowUpRight,
  Circle,
  Ellipsis,
  Eraser,
  Hand,
  MessageSquare,
  Minus,
  MousePointer2,
  Pen,
  Redo2,
  Shapes,
  Square,
  Trash2,
  Type,
  Undo2,
} from 'lucide-react'
import { useValue, type Editor } from 'tldraw'
import { DropdownMenu } from '../chat/Menu.tsx'
import { Modal } from '../chat/Modal.tsx'
import { shapeTools, toolLabels, type ShapeToolId, type ToolId } from './drawingTools.ts'
import './toolbar.css'

type ToolbarProps = {
  editor: Editor | null
  /** The tool in use, or null when tldraw is in a tool with no button. */
  active: ToolId | null
  onTool: (tool: ToolId) => void
  /** Removes the learner's drawing. Called only after the learner confirms. */
  onClear: () => void
}

const shapeIcons: Record<ShapeToolId, ReactNode> = {
  line: <Minus aria-hidden="true" />,
  arrow: <ArrowUpRight aria-hidden="true" />,
  rectangle: <Square aria-hidden="true" />,
  ellipse: <Circle aria-hidden="true" />,
}

function isShapeTool(tool: ToolId | null): tool is ShapeToolId {
  return shapeTools.some((item) => item.id === tool)
}

const TOOL_CLASS = 'icon-btn icon-btn--ghost wb-tool'

export function Toolbar({ editor, active, onTool, onClear }: ToolbarProps) {
  const [confirming, setConfirming] = useState(false)
  const canUndo = useValue('can undo', () => editor?.canUndo() ?? false, [editor])
  const canRedo = useValue('can redo', () => editor?.canRedo() ?? false, [editor])
  const ready = editor !== null

  function tool(id: ToolId, icon: ReactNode) {
    return (
      <button
        type="button"
        className={TOOL_CLASS}
        aria-label={toolLabels[id]}
        aria-pressed={active === id}
        disabled={!ready}
        onClick={() => onTool(id)}
      >
        {icon}
      </button>
    )
  }

  // Arrow keys move between the tools; Tab still reaches each one.
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    const buttons = [
      ...event.currentTarget.querySelectorAll<HTMLButtonElement>(':scope > button:not(:disabled)'),
    ]
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement)
    if (at < 0) return
    event.preventDefault()
    const step = event.key === 'ArrowRight' ? 1 : -1
    buttons[(at + step + buttons.length) % buttons.length]?.focus()
  }

  return (
    <>
      <div className="wb-toolbar" role="toolbar" aria-label="Drawing tools" onKeyDown={onKeyDown}>
        {tool('select', <MousePointer2 aria-hidden="true" />)}
        {tool('draw', <Pen aria-hidden="true" />)}
        {tool('eraser', <Eraser aria-hidden="true" />)}
        <DropdownMenu
          label="Shapes"
          triggerClassName={TOOL_CLASS}
          pressed={isShapeTool(active)}
          disabled={!ready}
          items={shapeTools.map((item) => ({
            id: item.id,
            label: item.label,
            icon: shapeIcons[item.id],
            onSelect: () => onTool(item.id),
          }))}
        >
          {isShapeTool(active) ? shapeIcons[active] : <Shapes aria-hidden="true" />}
        </DropdownMenu>
        {tool('text', <Type aria-hidden="true" />)}
        {tool('comment', <MessageSquare aria-hidden="true" />)}
        <button
          type="button"
          className={TOOL_CLASS}
          aria-label="Undo"
          disabled={!ready || !canUndo}
          onClick={() => editor?.undo()}
        >
          <Undo2 aria-hidden="true" />
        </button>
        <button
          type="button"
          className={TOOL_CLASS}
          aria-label="Redo"
          disabled={!ready || !canRedo}
          onClick={() => editor?.redo()}
        >
          <Redo2 aria-hidden="true" />
        </button>
        {tool('hand', <Hand aria-hidden="true" />)}
        <DropdownMenu
          label="More"
          triggerClassName={TOOL_CLASS}
          disabled={!ready}
          items={[
            {
              id: 'clear',
              label: 'Clear board',
              icon: <Trash2 aria-hidden="true" />,
              destructive: true,
              onSelect: () => setConfirming(true),
            },
          ]}
        >
          <Ellipsis aria-hidden="true" />
        </DropdownMenu>
      </div>
      <Modal
        open={confirming}
        variant="confirm"
        title="Clear this board?"
        mainLabel="Clear board"
        onMain={() => {
          setConfirming(false)
          onClear()
        }}
        onCancel={() => setConfirming(false)}
      >
        <p>This removes your drawing. Polaris's drawing stays. This can't be undone.</p>
      </Modal>
    </>
  )
}
