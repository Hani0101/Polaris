/** Splits a tutor reply into the blocks ReplyText draws. A small Markdown subset only. */

export type ReplyBlock =
  | { kind: 'heading'; text: string }
  | { kind: 'paragraph'; lines: string[] }
  | { kind: 'list'; ordered: boolean; start: number; items: string[] }
  | { kind: 'code'; language: string; code: string }

const FENCE = /^\s*```\s*([\w+#.-]*)\s*$/
const HEADING = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/
const ORDERED = /^\s{0,3}(\d{1,9})[.)]\s+(.*)$/
const UNORDERED = /^\s{0,3}[-*+]\s+(.*)$/
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/
const QUOTE = /^\s{0,3}>\s?(.*)$/

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
    if (line.trim() === '') {
      close()
      continue
    }
    if (RULE.test(line)) {
      close()
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
    const content = line.match(QUOTE)?.[1] ?? line.trim()
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

