import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Resource } from '../api.ts'
import { ReplyText } from './ReplyText.tsx'
import { ResourcesProvider, useResources } from './resources.tsx'
import { ResourcesTab } from './ResourcesTab.tsx'

const PDF: Resource = { id: 'r1', kind: 'pdf', name: 'Notes.pdf', media_type: 'application/pdf', size: 2048, pages: 5 }
const NOTE: Resource = { id: 'r2', kind: 'note', name: 'Week 2', media_type: 'text/plain', size: 20, pages: 1 }

type Handler = (url: string, init?: RequestInit) => unknown

let handler: Handler
let calls: { url: string; init?: RequestInit }[]

beforeEach(() => {
  calls = []
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    const result = handler(url, init)
    if (result instanceof Response) return result
    return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderTab(list: Resource[], onFocus?: () => void, withReply = false) {
  handler = (url, init) => {
    if (url.endsWith('/resources') && !init?.method) return { resources: list }
    if (url.endsWith('/resources/r1')) {
      return { ...PDF, text_pages: ['First page text', 'Second page text', '', '', ''] }
    }
    if (url.endsWith('/resources/r2')) return { ...NOTE, text_pages: ['Cells make energy.'] }
    return {}
  }
  return render(
    <ResourcesProvider sessionId="s1" onFocus={onFocus}>
      <ResourcesTab />
      {withReply ? (
        <ReplyText text="See [[cite:r1:2]] and [[cite:r2]] and [[cite:gone:1]]." />
      ) : null}
    </ResourcesProvider>,
  )
}

test('an empty session explains what can be added and the limits', async () => {
  renderTab([])
  expect(await screen.findByText('0 of 10 resources')).toBeTruthy()
  expect(screen.getByText('Drop files here to add them')).toBeTruthy()
  expect(screen.getByText(/10 MB and an image up to 5 MB/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Add files' })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Write a note' })).toBeTruthy()
})

test('resources are listed with their kind', async () => {
  renderTab([PDF, NOTE])
  expect(await screen.findByText('Notes.pdf')).toBeTruthy()
  expect(screen.getByText('PDF')).toBeTruthy()
  expect(screen.getByText('5 pages')).toBeTruthy()
  expect(screen.getByText('Note')).toBeTruthy()
  expect(screen.getByText('2 of 10 resources')).toBeTruthy()
})

test('a file over the limit is refused before it is sent', async () => {
  const { container } = renderTab([])
  await screen.findByText('0 of 10 resources')
  const input = container.querySelector('input[type="file"]') as HTMLInputElement
  const big = new File(['x'], 'big.pdf', { type: 'application/pdf' })
  Object.defineProperty(big, 'size', { value: 11 * 1024 * 1024 })

  fireEvent.change(input, { target: { files: [big] } })

  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(screen.getByRole('alert').textContent).toContain('10 MB')
  expect(calls.some((call) => call.init?.method === 'POST')).toBe(false)
})

test('a file is sent as the body with its name in a header', async () => {
  const { container } = renderTab([])
  await screen.findByText('0 of 10 resources')
  handler = (url, init) => {
    if (init?.method === 'POST') return { ...PDF, name: 'Week 2 slides.pdf' }
    return { resources: [] }
  }
  const input = container.querySelector('input[type="file"]') as HTMLInputElement

  fireEvent.change(input, {
    target: { files: [new File(['%PDF-'], 'Week 2 slides.pdf', { type: 'application/pdf' })] },
  })

  expect(await screen.findByText('Week 2 slides.pdf')).toBeTruthy()
  const post = calls.find((call) => call.init?.method === 'POST')
  expect((post?.init?.headers as Record<string, string>)['X-Filename']).toBe(
    encodeURIComponent('Week 2 slides.pdf'),
  )
})

test('a PDF opens page by page', async () => {
  renderTab([PDF])
  fireEvent.click(await screen.findByRole('button', { name: /^Notes.pdf/ }))

  expect(await screen.findByText('First page text')).toBeTruthy()
  expect(screen.getByText('Page 1 of 5')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
  expect(screen.getByText('Second page text')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Previous page' })).toBeTruthy()
})

test('a citation opens the resource at its page and asks the shell to show the tools', async () => {
  const onFocus = vi.fn()
  renderTab([PDF, NOTE], onFocus, true)

  const citation = await screen.findByRole('button', { name: 'Notes.pdf, p. 2' })
  fireEvent.click(citation)

  expect(onFocus).toHaveBeenCalled()
  expect(await screen.findByText('Second page text')).toBeTruthy()
  expect(screen.getByText('Page 2 of 5')).toBeTruthy()
})

test('a citation of a removed resource says so', async () => {
  renderTab([PDF, NOTE], undefined, true)
  expect(await screen.findByText('resource removed')).toBeTruthy()
})

test('a text citation names the resource', async () => {
  renderTab([PDF, NOTE], undefined, true)
  expect(await screen.findByRole('button', { name: 'Week 2' })).toBeTruthy()
})

test('removing asks first and names the resource', async () => {
  renderTab([PDF])
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Notes.pdf' }))

  const dialog = await screen.findByRole('alertdialog')
  expect(dialog.textContent).toContain('Notes.pdf')
  expect(dialog.textContent).toContain('can’t be undone')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
  expect(calls.some((call) => call.init?.method === 'DELETE')).toBe(false)
  expect(screen.getByText('Notes.pdf')).toBeTruthy()
})

test('removing a resource takes it off the list', async () => {
  renderTab([PDF])
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Notes.pdf' }))
  await screen.findByRole('alertdialog')
  fireEvent.click(screen.getByRole('button', { name: 'Remove resource' }))

  expect(await screen.findByText('0 of 10 resources')).toBeTruthy()
  expect(calls.some((call) => call.init?.method === 'DELETE')).toBe(true)
})

test('only a note has an edit control', async () => {
  renderTab([PDF, NOTE])
  fireEvent.click(await screen.findByRole('button', { name: /^Notes.pdf/ }))
  await screen.findByText('First page text')
  expect(screen.queryByRole('button', { name: 'Edit note' })).toBeNull()

  fireEvent.click(screen.getByRole('button', { name: 'Back to resources' }))
  fireEvent.click(await screen.findByRole('button', { name: /^Week 2/ }))
  expect(await screen.findByRole('button', { name: 'Edit note' })).toBeTruthy()
})

test('the tenth resource disables adding', async () => {
  const full = Array.from({ length: 10 }, (_, number) => ({ ...NOTE, id: `n${number}`, name: `Note ${number}` }))
  renderTab(full)
  expect(await screen.findByText(/at most 10 resources/)).toBeTruthy()
  expect((screen.getByRole('button', { name: 'Add files' }) as HTMLButtonElement).disabled).toBe(true)
})

test('without a provider a citation does not break the reply', () => {
  function Probe() {
    return <span>{useResources().resources.length}</span>
  }
  render(<Probe />)
  expect(screen.getByText('0')).toBeTruthy()
})

test('an image over the image limit is refused before it is sent', async () => {
  const { container } = renderTab([])
  await screen.findByText('0 of 10 resources')
  const input = container.querySelector('input[type="file"]') as HTMLInputElement
  const big = new File(['x'], 'photo.png', { type: 'image/png' })
  Object.defineProperty(big, 'size', { value: 6 * 1024 * 1024 })

  fireEvent.change(input, { target: { files: [big] } })

  expect((await screen.findByRole('alert')).textContent).toContain('5 MB')
  expect(calls.some((call) => call.init?.method === 'POST')).toBe(false)
})

test('a web page is added by its link and shows where it came from (RS-22)', async () => {
  renderTab([])
  await screen.findByText('0 of 10 resources')
  const page = { id: 'w1', kind: 'web', name: 'Photosynthesis basics', media_type: 'text/html', size: 900, pages: 1, url: 'https://www.example.org/plants' }
  handler = (url, init) => {
    if (url.endsWith('/resources/web') && init?.method === 'POST') return page
    if (url.endsWith('/resources/w1')) return { ...page, text_pages: ['Plants make sugar from light.'] }
    return { resources: [] }
  }

  fireEvent.change(screen.getByLabelText('Add a web page'), { target: { value: 'https://www.example.org/plants' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add page' }))

  expect(await screen.findByText('Photosynthesis basics')).toBeTruthy()
  expect(screen.getByText('Web page')).toBeTruthy()
  expect(screen.getByText('example.org')).toBeTruthy()
  const post = calls.find((call) => call.url.endsWith('/resources/web'))
  expect(JSON.parse(String(post?.init?.body))).toEqual({ url: 'https://www.example.org/plants' })

  fireEvent.click(screen.getByRole('button', { name: /^Photosynthesis basics/ }))
  expect(await screen.findByText('Plants make sugar from light.')).toBeTruthy()
  const source = screen.getByRole('link', { name: /Open the page on example.org/ })
  expect(source.getAttribute('href')).toBe('https://www.example.org/plants')
  expect(source.getAttribute('target')).toBe('_blank')
})

test('a refused link says why under the field (RS-23)', async () => {
  renderTab([])
  await screen.findByText('0 of 10 resources')
  handler = (url, init) => {
    if (url.endsWith('/resources/web') && init?.method === 'POST') {
      return new Response(
        JSON.stringify({ detail: 'Polaris only fetches public web pages, not addresses on this computer or its network.', code: 'not_public' }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      )
    }
    return { resources: [] }
  }

  const field = screen.getByLabelText('Add a web page')
  fireEvent.change(field, { target: { value: 'http://localhost:8000' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add page' }))

  expect((await screen.findByRole('alert')).textContent).toContain('only fetches public web pages')
  expect(field.getAttribute('aria-invalid')).toBe('true')
})
