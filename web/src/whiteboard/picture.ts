import type { Editor } from 'tldraw'
import type { BoardPicture } from '../api.ts'

// The backend refuses a side over 2000 pixels. Claude reads images best at
// about 1568 pixels on the long side, so the picture is scaled to that.
export const PICTURE_MAX_SIDE = 1568

type PictureEditor = Pick<Editor, 'getCurrentPageShapeIds' | 'getShapePageBounds' | 'toImage'>

export function pictureScale(width: number, height: number): number {
  const longest = Math.max(width, height)
  if (!Number.isFinite(longest) || longest <= 0) return 1
  return Math.min(1, PICTURE_MAX_SIDE / longest)
}

export function base64Bytes(bytes: Uint8Array): string {
  let binary = ''
  const step = 0x8000
  for (let index = 0; index < bytes.length; index += step) {
    binary += String.fromCharCode(...bytes.subarray(index, index + step))
  }
  return btoa(binary)
}

function pageBounds(editor: PictureEditor, ids: ReturnType<Editor['getCurrentPageShapeIds']>) {
  let left = Infinity
  let top = Infinity
  let right = -Infinity
  let bottom = -Infinity
  for (const id of ids) {
    const bounds = editor.getShapePageBounds(id)
    if (!bounds) continue
    left = Math.min(left, bounds.minX)
    top = Math.min(top, bounds.minY)
    right = Math.max(right, bounds.maxX)
    bottom = Math.max(bottom, bounds.maxY)
  }
  return { width: right - left, height: bottom - top }
}

/**
 * A PNG of the whole board as the learner sees it, light mode, for the next
 * turn. Null when the board is empty or the export fails; the turn then goes
 * with the text description only.
 */
export async function boardPicture(
  editor: PictureEditor,
  whiteboardId: string,
): Promise<BoardPicture | null> {
  const ids = editor.getCurrentPageShapeIds()
  if (ids.size === 0) return null
  try {
    const { width, height } = pageBounds(editor, ids)
    const { blob } = await editor.toImage([...ids], {
      format: 'png',
      background: true,
      darkMode: false,
      padding: 16,
      pixelRatio: 1,
      scale: pictureScale(width + 32, height + 32),
    })
    const data = base64Bytes(new Uint8Array(await blob.arrayBuffer()))
    return { whiteboard_id: whiteboardId, media_type: 'image/png', data }
  } catch {
    return null
  }
}
