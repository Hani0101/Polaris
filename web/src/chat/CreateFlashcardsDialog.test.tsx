import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Resource } from '../api.ts'
import { CreateFlashcardsDialog } from './CreateFlashcardsDialog.tsx'
import { ResourcesProvider } from './resources.tsx'

const NOTE: Resource = { id: 'r2', kind: 'note', name: 'Week 2', media_type: 'text/plain', size: 20, pages: 1 }
const ADDED: Resource = {
  id: 'r3',
  kind: 'pdf',
  name: 'Cells.pdf',
  media_type: 'application/pdf',
  size: 2048,
  pages: 3,
}

let uploads: string[]

beforeEach(() => {
  uploads = []
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    if (url.endsWith('/resources') && init?.method === 'POST') {
      uploads.push(decodeURIComponent(String((init.headers as Record<string, string>)['X-Filename'])))
      return new Response(JSON.stringify(ADDED), { status: 201 })
    }
    return new Response(JSON.stringify({ resources: [NOTE] }), { status: 200 })
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderDialog() {
  const onSubmit = vi.fn()
  render(
    <ResourcesProvider sessionId="s1">
      <CreateFlashcardsDialog open onCancel={vi.fn()} onSubmit={onSubmit} />
    </ResourcesProvider>,
  )
  return onSubmit
}

function attach(files: File[]) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files } })
}

async function create() {
  const dialog = screen.getByRole('dialog')
  await act(async () => {
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create flashcards' }))
  })
}

test('the dialog needs something to go on (FC-03)', async () => {
  const onSubmit = renderDialog()

  await create()

  expect(onSubmit).not.toHaveBeenCalled()
  expect(screen.getByRole('alert').textContent).toContain(
    'Type what the flashcards should be about, attach a file, or pick a resource.',
  )
})

test('a mix of topic, file, and resource asks for a deck from all three (FC-01, FC-03)', async () => {
  const onSubmit = renderDialog()
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Week 2' }))
  fireEvent.change(screen.getByLabelText('What should the flashcards be about?'), {
    target: { value: 'cell energy' },
  })
  attach([new File(['%PDF-1.4'], 'Cells.pdf', { type: 'application/pdf' })])

  await create()

  // The attached file went through the Resources tab's add path (FC-03).
  expect(uploads).toEqual(['Cells.pdf'])
  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(
      'Make flashcards about cell energy. Use “Week 2” and “Cells.pdf”.',
    ),
  )
})

test('the dialog refuses what the Resources tab refuses (FC-03)', async () => {
  renderDialog()
  await screen.findByRole('checkbox', { name: 'Week 2' })
  const big = new File(['x'], 'Big.pdf', { type: 'application/pdf' })
  Object.defineProperty(big, 'size', { value: 11 * 1024 * 1024 })

  attach([big])

  expect(screen.getByRole('alert').textContent).toContain('Big.pdf is over the 10 MB limit.')
  expect(screen.queryByText('Big.pdf')).toBeNull()
})

test('a server refusal is shown and nothing is sent (FC-03)', async () => {
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      return new Response(
        JSON.stringify({ detail: 'That file is the wrong type. Add a PDF, Word (.docx), text or Markdown, PNG, or JPEG.' }),
        { status: 422 },
      )
    }
    return new Response(JSON.stringify({ resources: [] }), { status: 200 })
  })
  const onSubmit = renderDialog()
  attach([new File(['a,b'], 'sheet.pdf')])

  await create()

  expect(onSubmit).not.toHaveBeenCalled()
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('wrong type'))
})
