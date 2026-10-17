// Renders Lottie scenes in headless Chromium with lottie-web, the same
// renderer the web player uses. The animation writer calls this to look at
// its own frames, and the backend check calls it to catch scenes that crash
// or draw nothing.
//
// Input (stdin, JSON):
//   { background: "#rrggbb", width: 960, out: "<dir>",
//     scenes: [{ id, lottie, frames: [int, ...] }] }
// Output (stdout, JSON):
//   { scenes: [{ id, errors: [str], frames: [{ frame, ink }], sheet: "<png path>" }] }
// `ink` is the share of sampled pixels that differ from the background.

import { readFileSync, mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const lottiePath = join(root, 'web/node_modules/lottie-web/build/player/lottie_light.min.js')
const fontDir = join(root, 'web/node_modules/@fontsource')

function fontFace(family, file, weight) {
  const data = readFileSync(join(fontDir, file)).toString('base64')
  return `@font-face{font-family:'${family}';font-weight:${weight};src:url(data:font/woff2;base64,${data}) format('woff2');}`
}

const FONTS = [
  fontFace(
    'Atkinson Hyperlegible Next',
    'atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-400-normal.woff2',
    400,
  ),
  fontFace(
    'Atkinson Hyperlegible Next',
    'atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-700-normal.woff2',
    700,
  ),
  fontFace(
    'Atkinson Hyperlegible Mono',
    'atkinson-hyperlegible-mono/files/atkinson-hyperlegible-mono-latin-400-normal.woff2',
    400,
  ),
].join('\n')

async function readStdin() {
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  return JSON.parse(Buffer.concat(chunks).toString('utf8'))
}

// Runs in the page: draws every requested frame of one scene in a grid,
// labels each cell, and measures how much of each frame is not background.
async function drawSheet({ lottie, frames, background, cellWidth }) {
  const errors = []
  window.onerror = (message) => errors.push(String(message))
  const ratio = lottie.h / lottie.w
  const cellHeight = Math.round(cellWidth * ratio)
  const columns = Math.min(frames.length, 3)
  const sheet = document.getElementById('sheet')
  sheet.style.gridTemplateColumns = `repeat(${columns}, ${cellWidth}px)`
  await document.fonts.load("40px 'Atkinson Hyperlegible Next'")
  await document.fonts.load("bold 40px 'Atkinson Hyperlegible Next'")
  await document.fonts.load("40px 'Atkinson Hyperlegible Mono'")

  async function measureInk(box, background, width, height) {
    const svg = box.querySelector('svg')
    if (!svg) return 0
    const clone = svg.cloneNode(true)
    clone.setAttribute('width', width)
    clone.setAttribute('height', height)
    const text = new XMLSerializer().serializeToString(clone)
    const image = new Image()
    image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text)
    await image.decode().catch(() => {})
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(width / 4)
    canvas.height = Math.round(height / 4)
    const context = canvas.getContext('2d')
    context.fillStyle = background
    context.fillRect(0, 0, canvas.width, canvas.height)
    const base = context.getImageData(0, 0, 1, 1).data
    try {
      context.drawImage(image, 0, 0, canvas.width, canvas.height)
    } catch {
      return 1
    }
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data
    let inked = 0
    for (let index = 0; index < pixels.length; index += 4) {
      const diff =
        Math.abs(pixels[index] - base[0]) +
        Math.abs(pixels[index + 1] - base[1]) +
        Math.abs(pixels[index + 2] - base[2])
      if (diff > 24) inked += 1
    }
    return inked / (pixels.length / 4)
  }

  const results = []
  for (const frame of frames) {
    const cell = document.createElement('figure')
    const box = document.createElement('div')
    box.className = 'box'
    box.style.width = `${cellWidth}px`
    box.style.height = `${cellHeight}px`
    box.style.background = background
    const label = document.createElement('figcaption')
    label.textContent = `frame ${frame}`
    cell.append(box, label)
    sheet.append(cell)
    let ink = 0
    try {
      const anim = window.lottie.loadAnimation({
        container: box,
        renderer: 'svg',
        loop: false,
        autoplay: false,
        animationData: structuredClone(lottie),
        rendererSettings: { preserveAspectRatio: 'xMidYMid meet' },
      })
      await new Promise((done) => {
        if (anim.isLoaded) done()
        else anim.addEventListener('DOMLoaded', done)
        setTimeout(done, 3000)
      })
      anim.goToAndStop(frame, true)
      ink = await measureInk(box, background, cellWidth, cellHeight)
    } catch (error) {
      errors.push(`frame ${frame}: ${error && error.message ? error.message : error}`)
    }
    results.push({ frame, ink })
  }
  return { errors, frames: results }
}

// Playwright's own Chromium when it is installed, else the system's Edge or Chrome.
async function launchBrowser() {
  let last
  for (const options of [{}, { channel: 'msedge' }, { channel: 'chrome' }]) {
    try {
      return await chromium.launch(options)
    } catch (error) {
      last = error
    }
  }
  throw last
}

async function main() {
  const input = await readStdin()
  const out = resolve(input.out)
  mkdirSync(out, { recursive: true })
  const browser = await launchBrowser()
  const results = []
  try {
    for (const scene of input.scenes) {
      const page = await browser.newPage({ deviceScaleFactor: 1 })
      const pageErrors = []
      page.on('pageerror', (error) => pageErrors.push(error.message))
      await page.setContent(
        `<!doctype html><html><head><style>${FONTS}
        body{margin:0;padding:12px;background:#777;font:14px 'Atkinson Hyperlegible Next',sans-serif}
        #sheet{display:grid;gap:12px}
        figure{margin:0}
        .box{overflow:hidden}
        figcaption{color:#fff;padding-top:4px}
        </style></head><body><div id="sheet"></div></body></html>`,
      )
      await page.addScriptTag({ path: lottiePath })
      let drawn
      try {
        drawn = await page.evaluate(drawSheet, {
          lottie: scene.lottie,
          frames: scene.frames,
          background: input.background ?? '#ffffff',
          cellWidth: input.width ?? 480,
        })
      } catch (error) {
        drawn = { errors: [String(error.message ?? error)], frames: [] }
      }
      const sheet = join(out, `${scene.id}.png`)
      await page.locator('#sheet').screenshot({ path: sheet }).catch(() => {})
      results.push({
        id: scene.id,
        errors: [...drawn.errors, ...pageErrors],
        frames: drawn.frames,
        sheet,
      })
      await page.close()
    }
  } finally {
    await browser.close()
  }
  process.stdout.write(JSON.stringify({ scenes: results }))
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error))
  process.exit(1)
})
