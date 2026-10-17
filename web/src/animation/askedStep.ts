/** The animation step a turn asks about (AN-17), as the chat shows it. */

import type { AskAboutStep } from './ScenePlayer.tsx'

/** Number and caption are only for the chip; a saved turn may not know them. */
export type AskedStep = Pick<AskAboutStep, 'jobId' | 'stepId'> &
  Partial<Pick<AskAboutStep, 'stepNumber' | 'caption'>>

export function askedStepLabel(step: AskedStep): string {
  if (step.stepNumber === undefined) return 'Asking about a step of an animation'
  const caption = step.caption?.trim()
  return caption
    ? `Asking about step ${step.stepNumber}: ${caption}`
    : `Asking about step ${step.stepNumber}`
}
