import { render } from '@testing-library/react'
import { expect, test } from 'vitest'
import shapeSource from './graphShapes.tsx?raw'
import converterSource from './toTldraw.ts?raw'
import { GraphFigure } from './graphShapes.tsx'

test('a graph draws plotted points, both axes, and the labels', () => {
  const { container } = render(
    <GraphFigure
      width={100}
      height={100}
      xLabel="time"
      yLabel="height"
      xMin={0}
      xMax={2}
      yMin={0}
      yMax={2}
      stroke="#1f3a5f"
      series={[{ plotted: [{ x: 0, y: 0 }, { x: 2, y: 2 }] }]}
    />
  )

  expect(container.querySelector('polyline')?.getAttribute('points')).toBe('0,100 100,0')
  const xAxis = container.querySelector('[data-axis="x"]')
  const yAxis = container.querySelector('[data-axis="y"]')
  expect(xAxis?.getAttribute('y1')).toBe('100')
  expect(xAxis?.getAttribute('y2')).toBe('100')
  expect(yAxis?.getAttribute('x1')).toBe('0')
  expect(yAxis?.getAttribute('x2')).toBe('0')
  expect(container.textContent).toContain('time')
  expect(container.textContent).toContain('height')
})

test('a series without plotted points is not drawn', () => {
  const { container } = render(
    <GraphFigure
      width={100}
      height={100}
      xLabel="x"
      yLabel="y"
      xMin={0}
      xMax={2}
      yMin={0}
      yMax={2}
      stroke="#1f3a5f"
      series={[{ plotted: [] }]}
    />
  )

  expect(container.querySelector('polyline')).toBeNull()
  expect(container.querySelector('[data-axis="x"]')).toBeTruthy()
  expect(container.querySelector('[data-axis="y"]')).toBeTruthy()
})

test('the graph shape does not evaluate expressions', () => {
  for (const source of [shapeSource, converterSource]) {
    expect(source).not.toMatch(/\beval\s*\(/)
    expect(source).not.toMatch(/new Function\b/)
    expect(source).not.toMatch(/simpleeval/)
  }
})
