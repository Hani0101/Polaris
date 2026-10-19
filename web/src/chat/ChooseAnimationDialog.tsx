import { useEffect, useState } from 'react'
import { chooseAnimationSettings } from '../api.ts'
import type { AnimationArtifact, AnimationSettings } from '../api.ts'
import { setAnimationSettingsAsker, shareAnimationJob } from './animationJob.ts'
import { AnimationSettingsDialog } from './AnimationSettingsDialog.tsx'

/**
 * The one dialog that asks for a waiting job's settings (AN-21, AN-26). It opens
 * when the chat starts a job that needs them, and again from the job's card.
 * Not now leaves the job waiting.
 */
export function ChooseAnimationDialog() {
  const [job, setJob] = useState<AnimationArtifact | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(
    () =>
      setAnimationSettingsAsker((next) => {
        setJob(next)
        setOpen(true)
      }),
    [],
  )

  async function choose(settings: AnimationSettings) {
    if (!job) return
    const next = await chooseAnimationSettings(job.session_id, job.id, settings)
    shareAnimationJob(next)
    setOpen(false)
  }

  return (
    <AnimationSettingsDialog
      open={open}
      mode="choose"
      onCancel={() => setOpen(false)}
      onSubmit={choose}
    />
  )
}
