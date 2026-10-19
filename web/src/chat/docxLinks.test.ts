import { expect, test } from 'vitest'
import { keepWebLinks } from './docxLinks.ts'

test('a Word link opens a web address in a new tab and nothing else (RS-12)', () => {
  const root = document.createElement('div')
  root.innerHTML = `
    <a id="web" href="https://example.org/a">web</a>
    <a id="script" href="javascript:alert(1)">script</a>
    <a id="file" href="file:///C:/secret.txt">file</a>
    <a id="inside" href="#part-2">inside</a>
    <p id="part-2">Part 2</p>
  `

  keepWebLinks(root)

  const web = root.querySelector<HTMLAnchorElement>('#web')!
  expect(web.getAttribute('href')).toBe('https://example.org/a')
  expect(web.target).toBe('_blank')
  expect(web.rel).toBe('noreferrer noopener')
  expect(root.querySelector('#script')!.hasAttribute('href')).toBe(false)
  expect(root.querySelector('#file')!.hasAttribute('href')).toBe(false)
  expect(root.querySelector('#inside')!.getAttribute('href')).toBe('#part-2')
})
