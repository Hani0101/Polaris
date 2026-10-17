import type { ReactNode } from 'react'
import { common, createLowlight } from 'lowlight'

/**
 * Syntax colors for a code block in a tutor reply. lowlight returns a tree of
 * spans with highlight.js class names; reply.css maps those to color.code.*.
 * The tree is drawn as React elements, so no HTML string is ever inserted.
 */

type HighlightNode = { type: string; value?: string; properties?: { className?: unknown }; children?: HighlightNode[] }

const lowlight = createLowlight(common)

function toReact(nodes: HighlightNode[], key: string): ReactNode[] {
  return nodes.map((node, index) => {
    const id = `${key}-${index}`
    if (node.type === 'text') return node.value ?? ''
    if (node.type !== 'element') return null
    const className = node.properties?.className
    return (
      <span key={id} className={Array.isArray(className) ? className.join(' ') : undefined}>
        {toReact(node.children ?? [], id)}
      </span>
    )
  })
}

/** The code with syntax colors, or null when the language is unknown or unnamed. */
export function highlightCode(code: string, language: string): ReactNode[] | null {
  if (!language || !lowlight.registered(language)) return null
  try {
    return toReact(lowlight.highlight(language, code).children as HighlightNode[], 'h')
  } catch {
    return null
  }
}
