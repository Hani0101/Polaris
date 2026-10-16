import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Whiteboard as WhiteboardData } from '../api.ts'
import { learnerDrawingTools } from './drawingTools.ts'
import { agentMarkLook } from './style.ts'
import { readableDescription } from './description.ts'
import { formulaWhiteboard } from './formulaWhiteboard.ts'
import { graphWhiteboard } from './graphWhiteboard.ts'
import { CodeBlock, MathFormula } from './mathCodeShapes.tsx'
import { selectElements, Whiteboard, whiteboardEditor } from './Whiteboard.tsx'
import { sampleWhiteboard } from './sampleWhiteboard.ts'

afterEach(() => {
  cleanup()
})

test('a stored whiteboard renders', async () => {
  render(<Whiteboard whiteboard={sampleWhiteboard} />)
  const region = await screen.findByRole('region', { name: readableDescription(sampleWhiteboard) })
  await waitFor(() => {
    expect(region.getAttribute('data-ready')).toBe('true')
  })
  expect(screen.queryByRole('button', { name: 'Freehand' })).toBeNull()
})

test('a comment on the drawing is shown', async () => {
  render(
    <Whiteboard
      whiteboard={{
        ...sampleWhiteboard,
        comments: [
          {
            id: 'comment-1',
            author: 'learner',
            text: 'why this box',
            element_id: 'rect-1',
          },
        ],
      }}
    />,
  )

  expect(await screen.findByText('why this box')).toBeTruthy()
  expect(screen.getByText('About rect-1')).toBeTruthy()
})

test('draw mode offers the learner tools and saves a comment', async () => {
  const onChange = vi.fn()
  render(<Whiteboard whiteboard={sampleWhiteboard} mode="draw" onChange={onChange} />)
  const region = await screen.findByRole('region', { name: readableDescription(sampleWhiteboard) })
  await waitFor(() => {
    expect(region.getAttribute('data-ready')).toBe('true')
  })

  for (const item of learnerDrawingTools) {
    expect(screen.getByRole('button', { name: item.label })).toBeTruthy()
  }
  const leave = screen.getByRole('button', { name: 'Leave comment' })
  expect(leave.hasAttribute('disabled')).toBe(true)

  fireEvent.change(screen.getByRole('textbox', { name: 'Comment' }), {
    target: { value: 'the left box is the whole' },
  })
  expect(leave.hasAttribute('disabled')).toBe(false)
  fireEvent.click(leave)

  expect(screen.getByText('the left box is the whole')).toBeTruthy()
  expect(onChange).toHaveBeenCalled()
  const saved = onChange.mock.calls.at(-1)?.[0]
  expect(saved.comments[0].author).toBe('learner')
  expect(saved.comments[0].text).toBe('the left box is the whole')
  expect(saved.steps[0].elements[0]).toEqual(sampleWhiteboard.steps[0].elements[0])
})

test('selecting parts offers ask about this with polaris ids', async () => {
  const onAsk = vi.fn()
  render(<Whiteboard whiteboard={sampleWhiteboard} onAsk={onAsk} />)
  const region = await screen.findByRole('region', { name: readableDescription(sampleWhiteboard) })
  await waitFor(() => {
    expect(region.getAttribute('data-ready')).toBe('true')
  })
  expect(screen.queryByRole('button', { name: 'Ask about this' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Freehand' })).toBeNull()

  selectElements(region, ['rect-1', 'text-1'])

  fireEvent.click(await screen.findByRole('button', { name: 'Ask about this' }))
  expect(onAsk).toHaveBeenCalledWith([
    { id: 'rect-1', label: 'rectangle' },
    { id: 'text-1', label: 'half' },
  ])
  expect(region.getAttribute('data-mode')).toBe('view')
})

test('an agent mark is dashed and cannot be dragged', async () => {
  const learner = sampleWhiteboard.steps[0].elements[1]
  const marked: WhiteboardData = {
    version: 3,
    id: 'wb-1',
    session_id: 'session-1',
    comments: [],
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [learner],
      },
      {
        id: 'step-mark',
        reply_part: '[[step:step-mark]]',
        elements: [
          {
            id: 'mark-1',
            kind: 'mark',
            mark: 'circle',
            author: 'agent',
            target_element_id: learner.id,
            position: { x: 30, y: 40 },
            size: { width: 100, height: 80 },
            style: learner.style,
          },
        ],
      },
    ],
  }
  render(<Whiteboard whiteboard={marked} mode="draw" />)
  const region = await screen.findByRole('region', { name: readableDescription(marked) })
  await waitFor(() => {
    expect(region.getAttribute('data-ready')).toBe('true')
  })

  const editor = whiteboardEditor(region)
  const shape = editor.getCurrentPageShapes().find((item) => item.meta.elementId === 'mark-1')
  if (!shape) throw new Error('The mark was not drawn.')
  expect(shape.props).toMatchObject({
    color: agentMarkLook.color,
    dash: agentMarkLook.dash,
  })
  const origin = { x: shape.x, y: shape.y }

  editor.updateShape({ id: shape.id, type: shape.type, x: origin.x + 80, y: origin.y + 40 })
  editor.deleteShapes([shape.id])

  const locked = editor.getShape(shape.id)
  expect(locked?.x).toBe(origin.x)
  expect(locked?.y).toBe(origin.y)
})

const agentBox = sampleWhiteboard.steps[0].elements[0]

function describedBoard(): WhiteboardData {
  return {
    version: 4,
    id: 'wb-read',
    session_id: 'session-1',
    description: 'Two boxes show one half of a whole.',
    comments: [],
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [agentBox],
      },
    ],
  }
}

test('a graph shows axes and a polyline from plotted points', async () => {
  render(<Whiteboard whiteboard={graphWhiteboard} mode="draw" />)
  const caption = 'A straight line.\ngraph of y = 2*x+1 from 0 to 2'
  const region = await screen.findByRole('region', { name: caption })
  await waitFor(() => {
    expect(region.getAttribute('data-ready')).toBe('true')
  })
  expect(screen.queryByRole('button', { name: 'Graph' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Freehand' })).toBeTruthy()
  expect(learnerDrawingTools.some((item) => item.label === 'Graph')).toBe(false)

  const editor = whiteboardEditor(region)
  const graph = editor.getCurrentPageShapes().find((shape) => shape.meta.elementId === 'graph-1')
  if (!graph) throw new Error('The graph was not drawn.')
  expect(graph.type).toBe('graph')

  const drawn = render(<>{editor.getShapeUtil(graph).component(graph)}</>)
  expect(drawn.container.querySelector('polyline')).toBeTruthy()
  expect(drawn.container.querySelector('[data-axis="x"]')).toBeTruthy()
  expect(drawn.container.querySelector('[data-axis="y"]')).toBeTruthy()
  expect(drawn.container.textContent).toContain('x')
  expect(drawn.container.textContent).toContain('y')
  expect(drawn.container.textContent).not.toContain('2*x+1')
})

test('math and code are real text', async () => {
  render(<Whiteboard whiteboard={formulaWhiteboard} />)
  const caption =
    'The area of a circle.\nmath formula: A = \\pi r^{2}\ncode block in python, 2 lines'
  const region = await screen.findByRole('region', { name: caption })
  await waitFor(() => {
    expect(region.getAttribute('data-ready')).toBe('true')
  })
  expect(screen.queryByRole('button', { name: 'Math' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Code' })).toBeNull()

  const editor = whiteboardEditor(region)
  const math = editor.getCurrentPageShapes().find((shape) => shape.meta.elementId === 'formula-1')
  const code = editor.getCurrentPageShapes().find((shape) => shape.meta.elementId === 'snippet-1')
  if (!math || !code) throw new Error('The formula or code was not drawn.')
  expect(math.type).toBe('math')
  expect(code.type).toBe('code')

  const mathNode = editor.getShapeUtil(math).component(math)
  const codeNode = editor.getShapeUtil(code).component(code)
  const drawn = render(
    <>
      {mathNode}
      {codeNode}
    </>,
  )
  expect(drawn.container.querySelector('.katex')).toBeTruthy()
  const block = drawn.container.querySelector('pre.whiteboard-code')
  expect(block?.textContent).toBe('def area(r):\n    return r * r')
  expect(block?.getAttribute('style')).toMatch(/monospace/i)
  expect(block?.getAttribute('data-language')).toBe('python')
})

test('a formula that KaTeX cannot render shows the LaTeX source', () => {
  render(<MathFormula latex={'\\frac{'} />)
  expect(screen.getByText('\\frac{')).toBeTruthy()
  expect(document.querySelector('.katex')).toBeNull()
})

test('a code block is a monospace pre', () => {
  const code = 'def area(r):\n    return r * r'
  const { container } = render(<CodeBlock language="python" code={code} />)
  const block = container.querySelector('pre.whiteboard-code')
  expect(block?.textContent).toBe(code)
  expect(block?.getAttribute('style')).toMatch(/monospace/i)
  expect(block?.style.whiteSpace).toBe('pre')
})

test('the whiteboard exposes its description by role and name', async () => {
  const whiteboard = describedBoard()
  render(<Whiteboard whiteboard={whiteboard} />)
  const region = await screen.findByRole('region', { name: whiteboard.description })
  const caption = screen.getByText(whiteboard.description ?? '')
  expect(region.getAttribute('aria-labelledby')).toBe(caption.id)
  expect(caption.classList.contains('visually-hidden')).toBe(false)
})

test('learner changes update the description', async () => {
  const whiteboard = describedBoard()
  const { rerender } = render(<Whiteboard whiteboard={whiteboard} />)
  expect(await screen.findByRole('region', { name: whiteboard.description })).toBeTruthy()

  const next: WhiteboardData = {
    ...whiteboard,
    steps: [
      {
        ...whiteboard.steps[0],
        elements: [agentBox, { ...agentBox, id: 'box-2', author: 'learner' }],
      },
    ],
    comments: [
      { id: 'comment-1', author: 'learner', text: 'my answer', element_id: 'box-2' },
    ],
  }
  rerender(<Whiteboard whiteboard={next} />)
  const expected =
    'Two boxes show one half of a whole. Learner added 1 shape and 1 comment: a rectangle, "my answer".'
  const region = await screen.findByRole('region', { name: expected })
  expect(region).toBeTruthy()
  expect(screen.getByText(expected)).toBeTruthy()
})
