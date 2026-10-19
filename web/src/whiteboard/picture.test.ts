import { expect, test } from 'vitest'
import { base64Bytes, boardPicture, PICTURE_MAX_SIDE, pictureScale } from './picture.ts'

test('a large board is scaled so its long side fits', () => {
  expect(pictureScale(800, 600)).toBe(1)
  expect(pictureScale(PICTURE_MAX_SIDE * 2, 100)).toBe(0.5)
  expect(pictureScale(0, 0)).toBe(1)
})

test('bytes become standard base64', () => {
  expect(base64Bytes(new Uint8Array([0x89, 0x50, 0x4e, 0x47]))).toBe('iVBORw==')
})

function fakeEditor(ids: string[], bytes: Uint8Array, fail = false) {
  const calls: unknown[] = []
  return {
    calls,
    editor: {
      getCurrentPageShapeIds: () => new Set(ids),
      getShapePageBounds: () => ({ minX: 0, minY: 0, maxX: 3136, maxY: 100 }),
      toImage: async (shapes: unknown, opts: unknown) => {
        calls.push({ shapes, opts })
        if (fail) throw new Error('no canvas')
        return { blob: new Blob([bytes as BlobPart]), width: 1, height: 1 }
      },
    },
  }
}

test('the picture is a light-mode PNG of every shape on the board', async () => {
  const { editor, calls } = fakeEditor(['shape:a', 'shape:b'], new Uint8Array([1, 2, 3]))

  // @ts-expect-error a partial editor is enough for the picture
  const picture = await boardPicture(editor, 'wb-1')

  expect(picture).toEqual({ whiteboard_id: 'wb-1', media_type: 'image/png', data: 'AQID' })
  expect(calls).toHaveLength(1)
  const { shapes, opts } = calls[0] as { shapes: string[]; opts: Record<string, unknown> }
  expect(shapes).toEqual(['shape:a', 'shape:b'])
  expect(opts).toMatchObject({ format: 'png', background: true, darkMode: false })
  expect(opts.scale).toBeCloseTo(PICTURE_MAX_SIDE / 3168)
})

test('an empty board or a failed export sends no picture', async () => {
  const empty = fakeEditor([], new Uint8Array([1]))
  const broken = fakeEditor(['shape:a'], new Uint8Array([1]), true)

  // @ts-expect-error a partial editor is enough for the picture
  expect(await boardPicture(empty.editor, 'wb-1')).toBeNull()
  expect(empty.calls).toHaveLength(0)
  // @ts-expect-error a partial editor is enough for the picture
  expect(await boardPicture(broken.editor, 'wb-1')).toBeNull()
})
