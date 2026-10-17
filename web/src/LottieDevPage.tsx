import { useEffect, useState } from 'react'
import { LottiePlayer } from './animation/LottiePlayer.tsx'
import { isLottieVideo } from './animation/lottieVideo.ts'
import type { LottieVideo } from './animation/lottieVideo.ts'
import './animation.css'

/** Dev only: plays a Lottie video from ?src=<url> or a chosen animation.json. */
export function LottieDevPage() {
  const [video, setVideo] = useState<LottieVideo | null>(null)
  const [error, setError] = useState<string | null>(null)

  function accept(data: unknown) {
    if (isLottieVideo(data)) {
      setVideo(data)
      setError(null)
    } else {
      setError('That file is not a Lottie video.')
    }
  }

  useEffect(() => {
    const src = new URLSearchParams(window.location.search).get('src')
    if (!src) return
    fetch(src)
      .then((response) => response.json())
      .then(accept)
      .catch(() => setError(`Couldn't load ${src}.`))
  }, [])

  return (
    <main className="an-page-main" style={{ padding: 16 }}>
      <input
        type="file"
        accept="application/json"
        aria-label="Choose an animation.json"
        onChange={async (event) => {
          const file = event.target.files?.[0]
          if (file) accept(JSON.parse(await file.text()))
        }}
      />
      {error ? <p role="alert">{error}</p> : null}
      {video ? (
        <>
          <h1 style={{ fontSize: '1.25rem' }}>{video.title}</h1>
          <LottiePlayer key={video.title} video={video} jobId="dev" />
        </>
      ) : null}
    </main>
  )
}
