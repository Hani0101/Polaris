import type { Whiteboard } from '../api.ts'

/** A version 7 board: two labeled boxes and an arrow attached to both. */
export const linkedWhiteboard: Whiteboard = {
  version: 7,
  id: 'wb-linked',
  session_id: 'session-1',
  description: 'Heat melts ice.',
  steps: [
    {
      id: 'step-1',
      reply_part: '[[step:step-1]]',
      elements: [
        {
          id: 'heat',
          kind: 'rectangle',
          author: 'agent',
          position: { x: 40, y: 40 },
          size: { width: 160, height: 60 },
          style: { stroke: '#1d1d1d', fill: null, stroke_width: 2 },
          label: 'Heat',
        },
        {
          id: 'ice',
          kind: 'ellipse',
          author: 'agent',
          position: { x: 40, y: 200 },
          size: { width: 160, height: 60 },
          style: { stroke: '#1d1d1d', fill: null, stroke_width: 2 },
          label: 'Ice melts',
        },
        {
          id: 'heat-to-ice',
          kind: 'arrow',
          author: 'agent',
          position: { x: 120, y: 100 },
          size: { width: 0, height: 100 },
          style: { stroke: '#1d1d1d', fill: null, stroke_width: 2 },
          start: { x: 120, y: 100 },
          end: { x: 120, y: 200 },
          label: 'causes',
          start_element_id: 'heat',
          end_element_id: 'ice',
        },
      ],
    },
  ],
  comments: [],
}
