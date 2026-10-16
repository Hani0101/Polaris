import { Whiteboard } from './whiteboard/Whiteboard.tsx'
import { sampleWhiteboard } from './whiteboard/sampleWhiteboard.ts'

export function WhiteboardDevPage() {
  return (
    <div className="whiteboard-dev">
      <p className="notice" role="status">
        Dev only. This page shows a sample whiteboard and is not part of the product.
      </p>
      <div className="whiteboard-frame">
        <Whiteboard whiteboard={sampleWhiteboard} />
      </div>
    </div>
  )
}
