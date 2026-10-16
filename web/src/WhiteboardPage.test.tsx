import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { WhiteboardArtifact } from './api.ts'
import { readableDescription } from './whiteboard/description.ts'
import { sampleWhiteboard } from './whiteboard/sampleWhiteboard.ts'
import { WhiteboardPage } from './WhiteboardPage.tsx'

const whiteboard: WhiteboardArtifact = { ...sampleWhiteboard, kind: 'whiteboard' }

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function stubFetch(response: Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => response),
  )
}

test('a stored whiteboard opens on its own page', async () => {
  stubFetch(Response.json(whiteboard))
  render(
    <WhiteboardPage sessionId="session-1" whiteboardId={whiteboard.id} onBack={() => {}} />,
  )
  expect(await screen.findByRole('region', { name: readableDescription(whiteboard) })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Back to the conversation' })).toBeTruthy()
  expect(vi.mocked(fetch).mock.calls[0][0]).toBe(
    `/api/sessions/session-1/whiteboards/${whiteboard.id}`,
  )
})

test('a reopened whiteboard shows every step', async () => {
  const stored: WhiteboardArtifact = {
    ...whiteboard,
    comments: [
      { id: 'c-whole', author: 'learner', text: 'the whole', element_id: 'rect-1' },
      { id: 'c-part', author: 'learner', text: 'the part', element_id: 'rect-2' },
    ],
  }
  stubFetch(Response.json(stored))
  render(
    <WhiteboardPage sessionId="session-1" whiteboardId={whiteboard.id} onBack={() => {}} />,
  )
  expect(await screen.findByText('the whole')).toBeTruthy()
  expect(screen.getByText('the part')).toBeTruthy()
})

test('Simpler on the whiteboard page sends that whiteboard', async () => {
  stubFetch(Response.json(whiteboard))
  const onSimpler = vi.fn()
  render(
    <WhiteboardPage
      sessionId="session-1"
      whiteboardId={whiteboard.id}
      onBack={() => {}}
      onSimpler={onSimpler}
    />,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Simpler' }))
  expect(onSimpler).toHaveBeenCalledWith(whiteboard.id)
})

test('a simpler whiteboard page links to the original', async () => {
  const simpler: WhiteboardArtifact = {
    ...whiteboard,
    id: 'wb-simple',
    version: 4,
    description: 'One box stands for the whole.',
    simplifies: 'wb-1',
  }
  stubFetch(Response.json(simpler))
  render(
    <WhiteboardPage sessionId="session-1" whiteboardId={simpler.id} onBack={() => {}} />,
  )
  const link = await screen.findByRole('link', { name: 'Original whiteboard' })
  expect(link.getAttribute('href')).toBe('/whiteboard/session-1/wb-1')
})

test('a whiteboard from another session is not drawn', async () => {
  stubFetch(
    Response.json({ detail: 'No whiteboard with that id.' }, { status: 404 }),
  )
  render(
    <WhiteboardPage sessionId="other-session" whiteboardId={whiteboard.id} onBack={() => {}} />,
  )
  expect((await screen.findByRole('alert')).textContent).toContain(
    'No whiteboard with that id.',
  )
  expect(screen.queryByRole('region', { name: readableDescription(whiteboard) })).toBeNull()
})

test('the learner can draw and leave a comment that is saved', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'PUT') return Response.json({ ...JSON.parse(String(init.body)), kind: 'whiteboard' })
    return Response.json(whiteboard)
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <WhiteboardPage sessionId="session-1" whiteboardId={whiteboard.id} onBack={() => {}} />,
  )

  fireEvent.click(await screen.findByRole('button', { name: 'Draw' }))
  const region = await screen.findByRole('region', { name: readableDescription(whiteboard) })
  await waitFor(() => {
    expect(region.getAttribute('data-ready')).toBe('true')
    expect(region.getAttribute('data-mode')).toBe('draw')
  })
  fireEvent.change(screen.getByRole('textbox', { name: 'Comment' }), {
    target: { value: 'the left box is the whole' },
  })
  const leave = screen.getByRole('button', { name: 'Leave comment' })
  await waitFor(() => {
    expect(leave.hasAttribute('disabled')).toBe(false)
  })
  fireEvent.click(leave)

  await waitFor(() => {
    const put = fetchMock.mock.calls.find((call) => call[1]?.method === 'PUT')
    expect(put?.[0]).toBe(`/api/sessions/session-1/whiteboards/${whiteboard.id}`)
    const body = JSON.parse(String(put?.[1]?.body)) as {
      comments: Array<{ author: string; text: string }>
      steps: Array<{ elements: Array<{ id: string; author: string; position: { x: number } }> }>
    }
    expect(body.comments[0]).toMatchObject({
      author: 'learner',
      text: 'the left box is the whole',
    })
    expect(body.steps[0].elements[0]).toMatchObject({ id: 'rect-1', author: 'agent' })
    expect(body.steps[0].elements[0].position.x).toBe(10)
  })
})
