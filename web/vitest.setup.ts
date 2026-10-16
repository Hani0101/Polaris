if (typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}

if (typeof globalThis.FontFace === 'undefined') {
  class TestFontFace {
    family: string
    style = 'normal'
    weight = 'normal'
    stretch = 'normal'
    unicodeRange = 'U+0-10FFFF'
    featureSettings = 'normal'
    ascentOverride = 'normal'
    descentOverride = 'normal'
    lineGapOverride = 'normal'
    display = 'auto'
    status = 'unloaded'

    constructor(family: string, _source: string, descriptors: Record<string, string> = {}) {
      this.family = family
      Object.assign(this, descriptors)
    }

    load() {
      this.status = 'loaded'
      return Promise.resolve(this)
    }
  }

  globalThis.FontFace = TestFontFace as unknown as typeof FontFace
}

if (typeof document !== 'undefined' && typeof document.fonts?.[Symbol.iterator] !== 'function') {
  const faces: FontFace[] = []
  Object.defineProperty(document, 'fonts', {
    configurable: true,
    value: {
      ready: Promise.resolve(),
      add(face: FontFace) {
        faces.push(face)
      },
      delete() {
        return false
      },
      check() {
        return true
      },
      load() {
        return Promise.resolve([])
      },
      forEach(callback: (face: FontFace) => void) {
        faces.forEach(callback)
      },
      [Symbol.iterator]() {
        return faces[Symbol.iterator]()
      },
    },
  })
}

if (typeof HTMLImageElement !== 'undefined' && typeof HTMLImageElement.prototype.decode !== 'function') {
  HTMLImageElement.prototype.decode = () => Promise.resolve()
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
