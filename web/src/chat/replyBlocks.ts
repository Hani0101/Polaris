/** Splits a tutor reply into the blocks ReplyText draws. A small Markdown subset only. */

export type CalloutTone = 'note' | 'tip' | 'warning'
export type CellAlign = 'left' | 'center' | 'right' | null

export type ReplyBlock =
  | { kind: 'heading'; text: string }
  | { kind: 'paragraph'; lines: string[] }
  | { kind: 'list'; ordered: boolean; start: number; items: string[] }
  | { kind: 'code'; language: string; code: string }
  | { kind: 'math'; tex: string }
  | { kind: 'quote'; blocks: ReplyBlock[] }
  | { kind: 'callout'; tone: CalloutTone; blocks: ReplyBlock[] }
  | { kind: 'table'; align: CellAlign[]; header: string[]; rows: string[][] }

const FENCE = /^\s*```\s*([\w+#.-]*)\s*$/
const HEADING = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/
const ORDERED = /^\s{0,3}(\d{1,9})[.)]\s+(.*)$/
const UNORDERED = /^\s{0,3}[-*+]\s+(.*)$/
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/
const QUOTE = /^\s{0,3}>\s?(.*)$/
const CALLOUT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$/i
const MATH_OPEN = /^\s*(\$\$|\\\[)\s*$/
const MATH_LINE = /^\s*(?:\$\$(.+)\$\$|\\\[(.+)\\\])\s*$/
const TABLE_DELIMITER = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/

const CALLOUT_TONES: Record<string, CalloutTone> = {
  NOTE: 'note',
  IMPORTANT: 'note',
  TIP: 'tip',
  WARNING: 'warning',
  CAUTION: 'warning',
}

/** The cells of one table row. A backslash keeps a pipe inside a cell. */
function tableCells(line: string): string[] {
  let row = line.trim()
  if (row.startsWith('|')) row = row.slice(1)
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1)
  return row.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'))
}

function isTableStart(line: string, next: string | undefined): boolean {
  if (next === undefined || !line.includes('|') || !next.includes('|')) return false
  return TABLE_DELIMITER.test(next) && tableCells(line).length === tableCells(next).length
}

function cellAlign(delimiter: string): CellAlign {
  const left = delimiter.startsWith(':')
  const right = delimiter.endsWith(':')
  if (left && right) return 'center'
  if (right) return 'right'
  if (left) return 'left'
  return null
}

function quoteBlock(lines: string[]): ReplyBlock {
  const callout = lines[0]?.trim().match(CALLOUT)
  if (!callout) return { kind: 'quote', blocks: parseReply(lines.join('\n')) }
  const rest = callout[2] ? [callout[2], ...lines.slice(1)] : lines.slice(1)
  return {
    kind: 'callout',
    tone: CALLOUT_TONES[callout[1].toUpperCase()],
    blocks: parseReply(rest.join('\n')),
  }
}

export function parseReply(text: string): ReplyBlock[] {
  const blocks: ReplyBlock[] = []
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  let paragraph: string[] | null = null
  let list: Extract<ReplyBlock, { kind: 'list' }> | null = null

  function close() {
    if (paragraph) blocks.push({ kind: 'paragraph', lines: paragraph })
    if (list) blocks.push(list)
    paragraph = null
    list = null
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const fence = line.match(FENCE)
    if (fence) {
      close()
      const code: string[] = []
      index += 1
      while (index < lines.length && !FENCE.test(lines[index])) {
        code.push(lines[index])
        index += 1
      }
      blocks.push({ kind: 'code', language: fence[1], code: code.join('\n') })
      continue
    }
    const mathLine = line.match(MATH_LINE)
    if (mathLine) {
      close()
      blocks.push({ kind: 'math', tex: (mathLine[1] ?? mathLine[2]).trim() })
      continue
    }
    const mathOpen = line.match(MATH_OPEN)
    if (mathOpen) {
      close()
      const closing = mathOpen[1] === '$$' ? '$$' : '\\]'
      const tex: string[] = []
      index += 1
      while (index < lines.length && lines[index].trim() !== closing) {
        tex.push(lines[index])
        index += 1
      }
      blocks.push({ kind: 'math', tex: tex.join('\n').trim() })
      continue
    }
    if (line.trim() === '') {
      close()
      continue
    }
    if (RULE.test(line)) {
      close()
      continue
    }
    if (QUOTE.test(line)) {
      close()
      const quoted: string[] = []
      while (index < lines.length) {
        const match = lines[index].match(QUOTE)
        if (!match) break
        quoted.push(match[1])
        index += 1
      }
      index -= 1
      blocks.push(quoteBlock(quoted))
      continue
    }
    if (isTableStart(line, lines[index + 1])) {
      close()
      const header = tableCells(line)
      const align = tableCells(lines[index + 1]).map(cellAlign)
      const rows: string[][] = []
      index += 2
      while (index < lines.length && lines[index].trim() !== '' && lines[index].includes('|')) {
        const cells = tableCells(lines[index])
        rows.push(header.map((_, column) => cells[column] ?? ''))
        index += 1
      }
      index -= 1
      blocks.push({ kind: 'table', align, header, rows })
      continue
    }
    const heading = line.match(HEADING)
    if (heading) {
      close()
      blocks.push({ kind: 'heading', text: heading[1] })
      continue
    }
    const ordered = line.match(ORDERED)
    const unordered = ordered ? null : line.match(UNORDERED)
    if (ordered || unordered) {
      const isOrdered = Boolean(ordered)
      const item = ordered ? ordered[2] : unordered![1]
      const current = list as Extract<ReplyBlock, { kind: 'list' }> | null
      if (!current || current.ordered !== isOrdered) {
        close()
        list = {
          kind: 'list',
          ordered: isOrdered,
          start: ordered ? Number(ordered[1]) : 1,
          items: [item],
        }
      } else {
        current.items.push(item)
      }
      continue
    }
    const content = line.trim()
    const currentList = list as Extract<ReplyBlock, { kind: 'list' }> | null
    if (currentList && /^\s/.test(line)) {
      const last = currentList.items.length - 1
      currentList.items[last] = `${currentList.items[last]} ${content}`
      continue
    }
    if (currentList) close()
    if (!paragraph) paragraph = []
    paragraph.push(content)
  }
  close()
  return blocks
}
