import type { Style, Whiteboard } from '../api.ts'

const style: Style = { stroke: '#1f3a5f', fill: '#f4efe6', stroke_width: 2 }

export const formulaWhiteboard: Whiteboard = {
  version: 5,
  id: 'wb-formula',
  session_id: 'session-1',
  description: 'The area of a circle.',
  comments: [],
  steps: [
    {
      id: 'step-1',
      reply_part: '[[step:step-1]]',
      elements: [
        {
          id: 'formula-1',
          kind: 'math',
          author: 'agent',
          latex: 'A = \\pi r^{2}',
          position: { x: 10, y: 20 },
          size: { width: 80, height: 40 },
          style,
        },
        {
          id: 'snippet-1',
          kind: 'code',
          author: 'agent',
          language: 'python',
          code: 'def area(r):\n    return r * r',
          position: { x: 10, y: 80 },
          size: { width: 160, height: 64 },
          style,
        },
      ],
    },
  ],
}
