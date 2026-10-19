import { act, cleanup, renderHook } from '@testing-library/react'
import type { Editor } from 'tldraw'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { BoardPicture, Whiteboard, WhiteboardArtifact } from '../api.ts'
import { useBoardSaving } from './useBoardSaving.ts'

const saves = vi.hoisted(() => [] as Array<{ resolve: () => void; reject: (error: Error) => void }>)
const boardPicture = vi.hoisted(() => vi.fn())

vi.mock('../api.ts', () => ({
  saveWhiteboard: vi.fn(
    () =>
      new Promise((resolve, reject) => {
        saves.push({ resolve: () => resolve({ id: 'wb-1' }), reject })
      }),
  ),
}))

vi.mock('./picture.ts', () => ({ boardPicture }))

const picture: BoardPicture = { whiteboard_id: 'wb-1', media_type: 'image/png', data: 'png' }

function drawing(label: string): Whiteboard {
  return { label } as unknown as Whiteboard
}

function renderSaving() {
  const onPicture = vi.fn()
  const onSaved = vi.fn<(whiteboard: WhiteboardArtifact) => void>()
  const view = renderHook(() =>
    useBoardSaving({ sessionId: 's-1', whiteboardId: 'wb-1', onSaved, onPicture }),
  )
  act(() => view.result.current.onEditor({} as Editor))
  return { saving: () => view.result.current, onPicture }
}

async function settle() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  saves.length = 0
  boardPicture.mockReset()
  boardPicture.mockResolvedValue(picture)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

test('a pause in drawing saves the board and pictures it', async () => {
  const { saving, onPicture } = renderSaving()

  act(() => saving().onDrawingChange(drawing('a')))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300)
  })
  saves[0].resolve()
  await settle()

  expect(boardPicture).toHaveBeenCalledTimes(1)
  expect(onPicture).toHaveBeenCalledWith(picture)
})

test('a save the learner drew past makes no picture; the next save does', async () => {
  const { saving, onPicture } = renderSaving()

  act(() => saving().onDrawingChange(drawing('a')))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300)
  })
  act(() => saving().onDrawingChange(drawing('b')))
  saves[0].resolve()
  await settle()
  expect(boardPicture).not.toHaveBeenCalled()

  await act(async () => {
    await vi.advanceTimersByTimeAsync(300)
  })
  saves[1].resolve()
  await settle()

  expect(boardPicture).toHaveBeenCalledTimes(1)
  expect(onPicture).toHaveBeenCalledTimes(1)
})

test('flush pictures the last change when an earlier save was drawn past', async () => {
  const { saving, onPicture } = renderSaving()

  act(() => saving().onDrawingChange(drawing('a')))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300)
  })
  act(() => saving().onDrawingChange(drawing('b')))
  let flushed: Promise<void> = Promise.resolve()
  act(() => {
    flushed = saving().flush()
  })
  saves[0].resolve()
  saves[1].resolve()
  await act(async () => {
    await flushed
  })

  expect(boardPicture).toHaveBeenCalledTimes(1)
  expect(onPicture).toHaveBeenCalledTimes(1)
})

test('a failed save still takes the picture an earlier save left to it', async () => {
  const { saving, onPicture } = renderSaving()

  act(() => saving().onDrawingChange(drawing('a')))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300)
  })
  act(() => saving().onDrawingChange(drawing('b')))
  saves[0].resolve()
  await settle()
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300)
  })
  saves[1].reject(new Error('offline'))
  await settle()

  expect(saving().saveError).toBe('offline')
  expect(boardPicture).toHaveBeenCalledTimes(1)
  expect(onPicture).toHaveBeenCalledTimes(1)
})
