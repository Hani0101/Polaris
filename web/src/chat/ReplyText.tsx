import type { ReactNode } from 'react'
import { ExternalLink } from 'lucide-react'
import './reply.css'
import { parseReply } from './replyBlocks.ts'

/**
 * Renders a tutor reply as structured text: headings, numbered steps, lists,
 * short paragraphs, bold, code, and links. Only this small subset of Markdown
 * is read; anything else stays plain text. No raw HTML is ever rendered.
 */

const INLINE =
  /(`[^`\n]+`)|(\*\*(?=\S)[^\n]*?\S\*\*|__(?=\S)[^\n]*?\S__)|(\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\))|((?<![\w*])\*(?=[^\s*])[^*\n]*?[^\s*]\*(?![\w*]))/

function renderInline(text: string, key = 'i'): ReactNode[] {
  const nodes: ReactNode[] = []
  let rest = text
  let count = 0
  while (rest) {
    const match = rest.match(INLINE)
    if (!match || match.index === undefined) {
      nodes.push(rest)
      break
    }
    if (match.index > 0) nodes.push(rest.slice(0, match.index))
    const id = `${key}-${count}`
    const [whole, code, bold, link, label, href, plain] = match
    if (code) {
      nodes.push(<code key={id}>{code.slice(1, -1)}</code>)
    } else if (bold) {
      nodes.push(<strong key={id}>{renderInline(bold.slice(2, -2), id)}</strong>)
    } else if (link && label && href) {
      nodes.push(
        <a key={id} href={href} target="_blank" rel="noreferrer noopener">
          {renderInline(label, id)}
          {/* DS-GAP: icon size for an external link inside body text, used component.icon.size.sm */}
          <ExternalLink
            className="reply-external"
            size={16}
            strokeWidth={2}
            aria-hidden="true"
          />
          <span className="visually-hidden"> (opens in a new tab)</span>
        </a>,
      )
    } else if (plain) {
      // Italic is never used (DESIGN.md 3.4), so single-star emphasis reads as plain text.
      nodes.push(...renderInline(plain.slice(1, -1), id))
    } else {
      nodes.push(whole)
    }
    count += 1
    rest = rest.slice(match.index + whole.length)
  }
  return nodes
}

export function ReplyText({ text, live = false }: { text: string; live?: boolean }) {
  const blocks = parseReply(text)
  return (
    <div className="tutor-body reply" aria-live={live ? 'polite' : undefined}>
      {blocks.map((block, index) => {
        const key = `b${index}`
        if (block.kind === 'heading') {
          return <h3 key={key}>{renderInline(block.text, key)}</h3>
        }
        if (block.kind === 'code') {
          return (
            <pre key={key}>
              <code data-language={block.language || undefined}>{block.code}</code>
            </pre>
          )
        }
        if (block.kind === 'list') {
          const items = block.items.map((item, itemIndex) => (
            <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>
          ))
          return block.ordered ? (
            <ol key={key} start={block.start === 1 ? undefined : block.start}>
              {items}
            </ol>
          ) : (
            <ul key={key}>{items}</ul>
          )
        }
        return (
          <p key={key}>
            {block.lines.map((line, lineIndex) => (
              <span key={`${key}-${lineIndex}`}>
                {lineIndex > 0 ? <br /> : null}
                {renderInline(line, `${key}-${lineIndex}`)}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}
