/** A Lottie video: Lottie scenes played one after another, each with a caption. */

export type LottieScene = {
  id: string
  caption: string
  lottie: Record<string, unknown> & { fr: number; ip: number; op: number }
}

export type LottieVideo = {
  format: 'lottie'
  version: number
  id: string
  title: string
  description: string
  background: string
  scenes: LottieScene[]
  /** lottie-web's drawing quality, chosen by the learner (AN-26). Older videos have none. */
  quality?: 'low' | 'medium' | 'high'
  /** The frame rate every scene uses, chosen by the learner (AN-26). */
  fps?: number | null
}

export function isLottieVideo(value: unknown): value is LottieVideo {
  if (typeof value !== 'object' || value === null) return false
  const data = value as Record<string, unknown>
  return (
    data.format === 'lottie' &&
    typeof data.title === 'string' &&
    Array.isArray(data.scenes) &&
    data.scenes.length > 0
  )
}

/** Text a screen reader reads for the whole video (AN-15). */
export function readableVideoDescription(video: LottieVideo): string {
  const title = video.title.trim()
  let description = video.description.trim()
  if (!/[.!?]$/.test(description)) description += '.'
  const count = video.scenes.length
  return `${title}. ${description} It has ${count} ${count === 1 ? 'step' : 'steps'}.`
}

export function sceneSeconds(scene: LottieScene): number {
  return (scene.lottie.op - scene.lottie.ip) / scene.lottie.fr
}
