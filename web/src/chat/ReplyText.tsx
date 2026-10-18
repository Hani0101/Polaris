import { useMemo } from 'react'
import type { ReactNode } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { BookOpen, ExternalLink, Info, Lightbulb, TriangleAlert } from 'lucide-react'
import './reply.css'
import { highlightCode } from './highlightCode.tsx'
import { useResources } from './resources.tsx'
import { parseReply, type CalloutTone, type ReplyBlock } from './replyBlocks.ts'

/**
 * Renders a tutor reply as structured text: headings, numbered steps, lists,
 * short paragraphs, quotes, callouts, tables, maths, bold, key terms, struck
 * text, code with syntax colors, and links. Only this subset of Markdown is
 * read; anything else stays plain text. No raw HTML from the reply is ever
 * rendered. The only HTML inserted is KaTeX's own output for maths.
 */

const INLINE =
  /(?<cite>\[\[cite:(?<citeId>[\w-]+)(?::(?<citePage>\d+))?\]\])|(?<code>`[^`\n]+`)|(?<bold>\*\*(?=\S)[^\n]*?\S\*\*|__(?=\S)[^\n]*?\S__)|(?<key>==(?=\S)[^\n]*?\S==)|(?<strike>~~(?=\S)[^\n]*?\S~~)|(?<link>\[(?<label>[^\]\n]+)\]\((?<href>https?:\/\/[^\s)]+)\))|(?<math>(?<![\\\w])\$(?=[^\s$])(?:[^$\n]*?[^\s$\\])?\$(?!\d)|\\\((?<parenMath>[^\n]+?)\\\))|(?<plain>(?<![\w*])\*(?=[^\s*])[^*\n]*?[^\s*]\*(?![\w*]))/

const CALLOUT: Record<CalloutTone, { label: string; Icon: typeof Info }> = {
  note: { label: 'Note', Icon: Info },
  tip: { label: 'Tip', Icon: Lightbulb },
  warning: { label: 'Warning', Icon: TriangleAlert },
}

const NUMBER_CELL = /^[-+−]?[\d.,\s]*\d[\d.,\s]*%?$/

/** A backslash before a dollar sign keeps it a dollar sign, not maths. */
function text(value: string): string {
  return value.replace(/\\\$/g, '$')
}

function Maths({ tex, display, source }: { tex: string; display: boolean; source: string }) {
  let html: string
  try {
    // Display maths is set in inline mode with \displaystyle so a long line can
    // wrap at its operators on a phone (DESIGN.md 6.5: nothing scrolls sideways).
    html = katex.renderToString(display ? `\\displaystyle ${tex}` : tex, { throwOnError: true })
  } catch {
    return display ? <pre className="reply-math-source"><code>{source}</code></pre> : <code>{source}</code>
  }
  const Tag = display ? 'div' : 'span'
  return <Tag className={display ? 'reply-math-block' : 'reply-math'} dangerouslySetInnerHTML={{ __html: html }} />
}

/**
 * A citation of a learner's resource, written by the agent as [[cite:id:page]].
 * It names the resource and page, and opens them in the Resources tab. A
 * resource that has been removed says so instead (RS-15).
 */
function Citation({ id, page }: { id: string; page: number | null }) {
  const { resources, loaded, open } = useResources()
  const resource = resources.find((item) => item.id === id)
  if (!resource) {
    return <span className="reply-cite is-removed">{loaded ? 'resource removed' : 'a resource'}</span>
  }
  const label = page !== null && resource.kind === 'pdf' ? `${resource.name}, p. ${page}` : resource.name
  return (
    <button
      type="button"
      className="reply-cite"
      onClick={() => open(id, resource.kind === 'pdf' ? page : null)}
    >
      <BookOpen size={16} strokeWidth={2} aria-hidden="true" />
      {label}
    </button>
  )
}

function renderInline(value: string, key = 'i'): ReactNode[] {
  const nodes: ReactNode[] = []
  let rest = value
  let count = 0
  while (rest) {
    const match = rest.match(INLINE)
    if (!match || match.index === undefined || !match.groups) {
      nodes.push(text(rest))
      break
    }
    if (match.index > 0) nodes.push(text(rest.slice(0, match.index)))
    const id = `${key}-${count}`
    const whole = match[0]
    const { cite, citeId, citePage, code, bold, key: term, strike, link, label, href, math, parenMath, plain } = match.groups
    if (cite && citeId) {
      nodes.push(<Citation key={id} id={citeId} page={citePage ? Number(citePage) : null} />)
    } else if (code) {
      nodes.push(<code key={id}>{code.slice(1, -1)}</code>)
    } else if (bold) {
      nodes.push(<strong key={id}>{renderInline(bold.slice(2, -2), id)}</strong>)
    } else if (term) {
      nodes.push(
        <strong key={id} className="reply-key">
          {renderInline(term.slice(2, -2), id)}
        </strong>,
      )
    } else if (strike) {
      nodes.push(<s key={id}>{renderInline(strike.slice(2, -2), id)}</s>)
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
    } else if (math) {
      nodes.push(<Maths key={id} tex={parenMath ?? math.slice(1, -1)} display={false} source={math} />)
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

function renderBlock(block: ReplyBlock, key: string): ReactNode {
  if (block.kind === 'heading') {
    return <h3 key={key}>{renderInline(block.text, key)}</h3>
  }
  if (block.kind === 'code') {
    return (
      <pre key={key}>
        <code data-language={block.language || undefined}>
          {highlightCode(block.code, block.language) ?? block.code}
        </code>
      </pre>
    )
  }
  if (block.kind === 'math') {
    return <Maths key={key} tex={block.tex} display source={block.tex} />
  }
  if (block.kind === 'quote') {
    return <blockquote key={key}>{renderBlocks(block.blocks, key)}</blockquote>
  }
  if (block.kind === 'callout') {
    const { label, Icon } = CALLOUT[block.tone]
    return (
      <div key={key} className={`reply-callout reply-callout--${block.tone}`}>
        <p className="reply-callout-label">
          <Icon size={16} strokeWidth={2} aria-hidden="true" />
          {label}
        </p>
        {renderBlocks(block.blocks, key)}
      </div>
    )
  }
  if (block.kind === 'table') {
    const cellClass = (cell: string) => (NUMBER_CELL.test(cell) ? 'reply-number' : undefined)
    return (
      <table key={key}>
        <thead>
          <tr>
            {block.header.map((cell, column) => (
              <th key={column} scope="col" style={{ textAlign: block.align[column] ?? undefined }}>
                {renderInline(cell, `${key}-h${column}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, column) => (
                <td
                  key={column}
                  className={cellClass(cell)}
                  style={{ textAlign: block.align[column] ?? undefined }}
                >
                  {renderInline(cell, `${key}-${rowIndex}-${column}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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
}

function renderBlocks(blocks: ReplyBlock[], key: string): ReactNode[] {
  return blocks.map((block, index) => renderBlock(block, `${key}-b${index}`))
}

export function ReplyText({ text: reply, live = false }: { text: string; live?: boolean }) {
  // Parsing, maths, and code colors run again only when the reply text changes.
  const blocks = useMemo(() => renderBlocks(parseReply(reply), 'r'), [reply])
  return (
    <div className="tutor-body reply" aria-live={live ? 'polite' : undefined}>
      {blocks}
    </div>
  )
}
