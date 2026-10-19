import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { MODE_KEY, getMode, readMode, resolvedTone, setMode } from './theme.ts'
import { boardTone } from './whiteboard/boardTone.ts'

function systemPrefers(dark: boolean) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: dark && query.includes('dark'),
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  )
}

beforeEach(() => {
  window.localStorage.clear()
  setMode('system')
  systemPrefers(false)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('a new browser starts on System with no attribute [ST-04]', () => {
  expect(readMode()).toBe('system')
  expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
})

test('a chosen mode applies at once and is kept in the browser [ST-05]', () => {
  setMode('dark')

  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(window.localStorage.getItem(MODE_KEY)).toBe('dark')
  expect(readMode()).toBe('dark')
})

test('choosing System clears the attribute and the stored choice [ST-03]', () => {
  setMode('light')
  setMode('system')

  expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  expect(window.localStorage.getItem(MODE_KEY)).toBeNull()
})

test('System follows the operating system, Light and Dark ignore it [ST-03]', () => {
  systemPrefers(true)

  expect(resolvedTone('system')).toBe('dark')
  expect(resolvedTone('light')).toBe('light')
  systemPrefers(false)
  expect(resolvedTone('system')).toBe('light')
  expect(resolvedTone('dark')).toBe('dark')
})

test('a browser that cannot keep the choice still changes the colors [ST-07]', () => {
  const blocked = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })

  expect(readMode()).toBe('system')
  setMode('dark')
  expect(getMode()).toBe('dark')
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')

  blocked.mockRestore()
  vi.restoreAllMocks()
})

test('a board keeps the colors it first opened with [WB-22, ST-09]', () => {
  setMode('light')
  expect(boardTone('board-1')).toBe('light')

  setMode('dark')
  expect(boardTone('board-1')).toBe('light')
  expect(boardTone('board-2')).toBe('dark')
})

test('the dark palette is written once per selector and stays the same [ST-08]', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const declarations = (selector: string) => {
    const open = css.indexOf(selector)
    expect(open).toBeGreaterThan(-1)
    let depth = 0
    let end = css.indexOf('{', open)
    for (let at = end; at < css.length; at += 1) {
      if (css[at] === '{') depth += 1
      if (css[at] === '}') depth -= 1
      if (depth === 0) {
        end = at
        break
      }
    }
    const body = css.slice(css.indexOf('{', open), end)
    return [...body.matchAll(/--color-[a-z0-9-]+:[^;]+;/g)].map((match) => match[0])
  }
  const bySystem = declarations(":root:not([data-theme='light']) {")
  const byChoice = declarations(":root[data-theme='dark'] {")

  expect(bySystem.length).toBeGreaterThan(30)
  expect(byChoice).toEqual(bySystem)
})
