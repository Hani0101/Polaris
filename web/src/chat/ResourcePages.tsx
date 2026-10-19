import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { GlobalWorkerOptions, RenderingCancelledException, TextLayer, getDocument } from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { renderAsync } from 'docx-preview'
import { keepWebLinks } from './docxLinks.ts'

/**
 * A PDF or Word resource drawn as it is in the file (RS-12, RS-16). This module
 * holds pdf.js and docx-preview, so it loads only when such a resource is opened.
 */

GlobalWorkerOptions.workerSrc = workerUrl

type Status = 'loading' | 'ready' | 'failed'

/** The width of an element, kept current as the panel resizes. */
function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    setWidth(element.clientWidth)
    const observer = new ResizeObserver(() => setWidth(element.clientWidth))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return { ref, width }
}

function Loading() {
  return <div className="skeleton resource-skeleton" role="status" aria-label="Loading" />
}

/**
 * One page of a PDF, drawn by pdf.js at the panel's width, with its text laid
 * over it so it can be selected and read aloud. `fallback` shows when the file
 * cannot be drawn.
 */
export function PdfPage({ url, page, fallback }: { url: string; page: number; fallback: ReactNode }) {
  const { ref: frame, width } = useWidth<HTMLDivElement>()
  const canvas = useRef<HTMLCanvasElement>(null)
  const text = useRef<HTMLDivElement>(null)
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null)
  const [status, setStatus] = useState<Status>('loading')

  useEffect(() => {
    const task = getDocument({ url })
    let active = true
    // A load stopped by the cleanup below rejects too, and is not a failure.
    task.promise.then(
      (loaded) => active && setDoc(loaded),
      () => active && setStatus('failed'),
    )
    return () => {
      active = false
      setDoc(null)
      void task.destroy()
    }
  }, [url])

  useEffect(() => {
    if (!doc || width === 0 || !canvas.current || !text.current) return
    const target = canvas.current
    const layer = text.current
    let cancelled = false
    let cancel = () => {}

    void (async () => {
      try {
        const pdfPage = await doc.getPage(Math.min(Math.max(1, page), doc.numPages))
        if (cancelled) return
        const scale = width / pdfPage.getViewport({ scale: 1 }).width
        const viewport = pdfPage.getViewport({ scale })
        const ratio = window.devicePixelRatio || 1
        target.width = Math.floor(viewport.width * ratio)
        target.height = Math.floor(viewport.height * ratio)
        const drawing = pdfPage.render({
          canvas: target,
          viewport,
          transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
        })
        cancel = () => drawing.cancel()
        await drawing.promise
        if (cancelled) return
        frame.current?.style.setProperty('--total-scale-factor', String(scale))
        layer.replaceChildren()
        const words = new TextLayer({
          textContentSource: pdfPage.streamTextContent(),
          container: layer,
          viewport,
        })
        cancel = () => words.cancel()
        await words.render()
        if (!cancelled) setStatus('ready')
      } catch (caught) {
        if (cancelled || caught instanceof RenderingCancelledException) return
        setStatus('failed')
      }
    })()

    return () => {
      cancelled = true
      cancel()
    }
  }, [doc, page, width, frame])

  if (status === 'failed') return <>{fallback}</>
  // The page stays laid out while it loads, unseen, so its width can be measured.
  return (
    <div className="resource-page-slot">
      {status === 'loading' ? <Loading /> : null}
      <div ref={frame} className={status === 'ready' ? 'resource-page' : 'resource-page is-loading'}>
        <canvas ref={canvas} aria-hidden="true" />
        <div ref={text} className="textLayer" />
      </div>
    </div>
  )
}

// Styles inside the document's own shadow root, so the document's styles and
// Polaris's never mix. Design tokens still reach it, as custom properties do.
const DOCX_STYLE = `
:host { display: block; }
.pages { display: flex; flex-direction: column; gap: var(--space-sm); }
.page {
  overflow: hidden;
  border: var(--border-width-default) solid var(--color-border-default);
  border-radius: var(--radius-md);
}
/* The page keeps the document's own paper in both modes, like a printed page. */
section.docx { background: white; }
`

/**
 * A Word document drawn by docx-preview as its own pages, each scaled to the
 * panel's width. `fallback` shows when the file cannot be drawn.
 */
export function DocxPages({ url, name, fallback }: { url: string; name: string; fallback: ReactNode }) {
  const { ref: host, width } = useWidth<HTMLDivElement>()
  const [status, setStatus] = useState<Status>('loading')

  useEffect(() => {
    const element = host.current
    if (!element) return
    const controller = new AbortController()
    const root = element.shadowRoot ?? element.attachShadow({ mode: 'open' })
    const style = document.createElement('style')
    style.textContent = DOCX_STYLE
    const documentStyles = document.createElement('div')
    const pages = document.createElement('div')
    pages.className = 'pages'
    root.replaceChildren(style, documentStyles, pages)

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Status ${response.status}`)
        return response.blob()
      })
      .then((blob) =>
        renderAsync(blob, pages, documentStyles, {
          className: 'docx',
          inWrapper: false,
          // HTML embedded in the document is never shown (RS-12).
          renderAltChunks: false,
          renderComments: false,
          renderChanges: false,
        }),
      )
      .then(() => {
        if (controller.signal.aborted) return
        keepWebLinks(pages)
        for (const section of pages.querySelectorAll<HTMLElement>(':scope > section.docx')) {
          const frame = document.createElement('div')
          frame.className = 'page'
          section.replaceWith(frame)
          frame.append(section)
        }
        setStatus('ready')
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('failed')
      })

    return () => {
      controller.abort()
      root.replaceChildren()
    }
  }, [url, host])

  // Each page is shrunk to fit the panel, never grown, so nothing scrolls sideways (6.5).
  useEffect(() => {
    const root = host.current?.shadowRoot
    if (status !== 'ready' || !root || width === 0) return
    for (const section of root.querySelectorAll<HTMLElement>('section.docx')) {
      section.style.zoom = ''
      const room = section.parentElement?.clientWidth ?? width
      const pageWidth = section.offsetWidth
      if (pageWidth > room) section.style.zoom = String(room / pageWidth)
    }
  }, [status, width, host])

  if (status === 'failed') return <>{fallback}</>
  return (
    <div className="resource-docx">
      {status === 'loading' ? <Loading /> : null}
      <div ref={host} role="document" aria-label={name} hidden={status !== 'ready'} />
    </div>
  )
}
