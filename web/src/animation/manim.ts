/** What a Manim job stores beside its video (feat/manim-experiment). */
export type ManimManifest = {
  engine: 'manim'
  id: string
  title: string
  description: string
  steps: { id: string; caption: string; start_s: number; duration_s: number }[]
}

export function isManimManifest(value: unknown): value is ManimManifest {
  if (typeof value !== 'object' || value === null) return false
  const data = value as Record<string, unknown>
  return data.engine === 'manim' && Array.isArray(data.steps) && data.steps.length > 0
}
