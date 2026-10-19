/**
 * Links in a drawn Word document (RS-12). A web address opens in a new tab, a
 * link to a place in the document scrolls there, and anything else, such as a
 * javascript: or file: address, is left as plain text.
 */
export function keepWebLinks(root: ParentNode): void {
  for (const link of root.querySelectorAll<HTMLAnchorElement>('a[href]')) {
    const href = link.getAttribute('href') ?? ''
    if (href.startsWith('#') && href.length > 1) {
      const target = href.slice(1)
      link.addEventListener('click', (event) => {
        event.preventDefault()
        root.querySelector(`[id="${CSS.escape(target)}"], [name="${CSS.escape(target)}"]`)?.scrollIntoView()
      })
      continue
    }
    let url: URL | null = null
    try {
      url = new URL(href)
    } catch {
      url = null
    }
    if (url && (url.protocol === 'https:' || url.protocol === 'http:')) {
      link.target = '_blank'
      link.rel = 'noreferrer noopener'
    } else {
      link.removeAttribute('href')
    }
  }
}
