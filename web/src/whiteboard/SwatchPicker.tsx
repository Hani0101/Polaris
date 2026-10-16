import type { CSSProperties } from 'react'
import { penColors, penSwatchVar, type PenColor, type PenSet } from './style.ts'
import './toolbar.css'

type SwatchPickerProps = {
  /** The pen set that follows the board: onLight or onDark (DESIGN.md 2.3). */
  set: PenSet
  /** The tldraw color in use, or a color outside the 6 boxes. */
  value: string
  onChange: (color: PenColor) => void
}

export function SwatchPicker({ set, value, onChange }: SwatchPickerProps) {
  return (
    <div className="wb-swatches" role="group" aria-label="Pen color">
      {penColors.map((pen) => (
        <button
          key={pen.key}
          type="button"
          className="wb-swatch"
          aria-label={pen.name[set]}
          aria-pressed={value === pen.tldraw}
          style={{ '--wb-swatch-color': penSwatchVar(set, pen.key) } as CSSProperties}
          onClick={() => onChange(pen.tldraw)}
        />
      ))}
    </div>
  )
}
