import type { Style, Whiteboard } from '../api.ts'

const style: Style = { stroke: '#1f3a5f', fill: '#f4efe6', stroke_width: 2 }

export const graphWhiteboard: Whiteboard = {
  version: 6,
  id: 'wb-graph',
  session_id: 'session-1',
  description: 'A straight line.',
  comments: [],
  steps: [
    {
      id: 'step-1',
      reply_part: '[[step:step-1]]',
      elements: [
        {
          id: 'graph-1',
          kind: 'graph',
          author: 'agent',
          x_label: 'x',
          y_label: 'y',
          x_min: 0,
          x_max: 2,
          y_min: -1,
          y_max: 6,
          position: { x: 10, y: 20 },
          size: { width: 200, height: 100 },
          style,
          series: [
            {
              expression: '2*x+1',
              sample_count: 3,
              plotted: [
                { x: 0, y: 1 },
                { x: 1, y: 3 },
                { x: 2, y: 5 },
              ],
            },
          ],
        },
      ],
    },
  ],
}
