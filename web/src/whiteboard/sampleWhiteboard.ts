import type { Whiteboard } from '../api.ts'
import sample from './sample-whiteboard.json'

// Same whiteboard api/tests/test_whiteboard.py accepts. Copied here so the
// web tests do not edit that file.
export const sampleWhiteboard = sample as Whiteboard
