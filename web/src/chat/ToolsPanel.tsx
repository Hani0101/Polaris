import { useState } from 'react'
import type { ReactNode } from 'react'
import { Clapperboard, Layers, ListChecks, Presentation } from 'lucide-react'
import type { AnimationArtifact, Artifact, Quiz, WhiteboardArtifact } from '../api.ts'
import { AnimationPlayer } from '../AnimationPlayer.tsx'
import { QuizCard } from '../QuizCard.tsx'
import type { PointedPart } from '../whiteboard/pointing.ts'
import { Whiteboard } from '../whiteboard/Whiteboard.tsx'
import { Tabs } from './Tabs.tsx'
import type { TabItem } from './Tabs.tsx'
import { FAILURE_NOTICE } from './AnimationCard.tsx'
import { AlertBanner, Badge, CloseIcon, IconButton } from './ui.tsx'
import './tools.css'

export type ToolsTab = 'whiteboard' | 'quiz' | 'animation' | 'artifacts'

const TABS: TabItem<ToolsTab>[] = [
  { id: 'whiteboard', label: 'Whiteboard' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'animation', label: 'Animation' },
  { id: 'artifacts', label: 'Artifacts' },
]

type ToolsPanelProps = {
  artifacts: Artifact[]
  headingId: string
  onClose: () => void
  onOpenQuiz: (quizId: string) => void
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation: (sessionId: string, jobId: string) => void
  onQuizGraded: (quiz: Quiz) => void
  onAsk?: (whiteboardId: string, parts: PointedPart[]) => void
}

/** The tools content: header, then Whiteboard, Quiz, Animation, and Artifacts tabs. */
export function ToolsPanel({
  artifacts,
  headingId,
  onClose,
  onOpenQuiz,
  onOpenWhiteboard,
  onOpenAnimation,
  onQuizGraded,
  onAsk,
}: ToolsPanelProps) {
  const [tab, setTab] = useState<ToolsTab>('whiteboard')

  return (
    <div className="tools">
      <div className="tools-head">
        <h2 className="tools-title" id={headingId}>
          Tools
        </h2>
        <IconButton label="Close tools" size="sm" onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </div>
      <Tabs label="Tools" tabs={TABS} selected={tab} onSelect={setTab}>
        {tab === 'whiteboard' ? (
          <WhiteboardTab
            whiteboard={latest(artifacts, isWhiteboard)}
            onOpenWhiteboard={onOpenWhiteboard}
            onAsk={onAsk}
          />
        ) : null}
        {tab === 'quiz' ? (
          <QuizTab
            quiz={latest(artifacts, isQuiz)}
            onOpenQuiz={onOpenQuiz}
            onQuizGraded={onQuizGraded}
          />
        ) : null}
        {tab === 'animation' ? (
          <AnimationTab
            animation={latest(artifacts, isAnimation)}
            onOpenAnimation={onOpenAnimation}
          />
        ) : null}
        {tab === 'artifacts' ? (
          <ArtifactsTab
            artifacts={artifacts}
            onOpenQuiz={onOpenQuiz}
            onOpenWhiteboard={onOpenWhiteboard}
            onOpenAnimation={onOpenAnimation}
          />
        ) : null}
      </Tabs>
    </div>
  )
}

function isWhiteboard(artifact: Artifact): artifact is WhiteboardArtifact {
  return artifact.kind === 'whiteboard'
}

function isQuiz(artifact: Artifact): artifact is Quiz {
  return artifact.kind === 'quiz'
}

function isAnimation(artifact: Artifact): artifact is AnimationArtifact {
  return artifact.kind === 'animation'
}

function latest<T extends Artifact>(
  artifacts: Artifact[],
  match: (artifact: Artifact) => artifact is T,
): T | null {
  for (let index = artifacts.length - 1; index >= 0; index -= 1) {
    const artifact = artifacts[index]
    if (match(artifact)) return artifact
  }
  return null
}

function firstSentence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(/^[\s\S]*?[.?!](?=\s|$)/)
  return (match ? match[0] : trimmed).trim()
}

function ToolsEmpty({
  icon,
  title,
  body,
}: {
  icon: ReactNode
  title: string
  body: string
}) {
  return (
    <div className="empty-state tools-empty">
      {icon}
      <h3 className="empty-state-title">{title}</h3>
      <p className="empty-state-body">{body}</p>
    </div>
  )
}

function WhiteboardTab({
  whiteboard,
  onOpenWhiteboard,
  onAsk,
}: {
  whiteboard: WhiteboardArtifact | null
  onOpenWhiteboard: (whiteboardId: string) => void
  onAsk?: (whiteboardId: string, parts: PointedPart[]) => void
}) {
  if (!whiteboard) {
    return (
      <ToolsEmpty
        icon={<Presentation size={24} strokeWidth={2} aria-hidden="true" />}
        title="No whiteboard yet"
        body="Ask Polaris to draw an idea, and the whiteboard shows here."
      />
    )
  }
  return (
    <div className="tools-whiteboard">
      <div className="tools-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => onOpenWhiteboard(whiteboard.id)}
        >
          Open whiteboard
        </button>
      </div>
      <div className="tools-whiteboard-board">
        <Whiteboard
          key={whiteboard.id}
          whiteboard={whiteboard}
          onAsk={onAsk ? (parts) => onAsk(whiteboard.id, parts) : undefined}
        />
      </div>
    </div>
  )
}

function QuizTab({
  quiz,
  onOpenQuiz,
  onQuizGraded,
}: {
  quiz: Quiz | null
  onOpenQuiz: (quizId: string) => void
  onQuizGraded: (quiz: Quiz) => void
}) {
  if (!quiz) {
    return (
      <ToolsEmpty
        icon={<ListChecks size={24} strokeWidth={2} aria-hidden="true" />}
        title="No quiz yet"
        body="Ask Polaris for a quiz on what you learned, and it shows here."
      />
    )
  }
  return <QuizCard key={quiz.id} quiz={quiz} onGraded={onQuizGraded} onExpand={onOpenQuiz} />
}

function AnimationTab({
  animation,
  onOpenAnimation,
}: {
  animation: AnimationArtifact | null
  onOpenAnimation: (sessionId: string, jobId: string) => void
}) {
  if (!animation) {
    return (
      <ToolsEmpty
        icon={<Clapperboard size={24} strokeWidth={2} aria-hidden="true" />}
        title="No animation yet"
        body="Ask Polaris to animate an idea, and the animation shows here."
      />
    )
  }
  if (animation.status !== 'ready') {
    return <AnimationCard animation={animation} onOpen={onOpenAnimation} />
  }
  return (
    <div className="tools-animation">
      <div className="tools-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => onOpenAnimation(animation.session_id, animation.id)}
        >
          Open animation
        </button>
      </div>
      <AnimationPlayer
        key={animation.id}
        sessionId={animation.session_id}
        jobId={animation.id}
      />
    </div>
  )
}

function ArtifactsTab({
  artifacts,
  onOpenQuiz,
  onOpenWhiteboard,
  onOpenAnimation,
}: {
  artifacts: Artifact[]
  onOpenQuiz: (quizId: string) => void
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation: (sessionId: string, jobId: string) => void
}) {
  if (artifacts.length === 0) {
    return (
      <ToolsEmpty
        icon={<Layers size={24} strokeWidth={2} aria-hidden="true" />}
        title="No artifacts yet"
        body="Whiteboards, quizzes, and animations from this session show here."
      />
    )
  }
  const newestFirst = [...artifacts].reverse()
  return (
    <ul className="tools-artifacts" aria-label="Artifacts in this session">
      {newestFirst.map((artifact) => (
        <li key={`${artifact.kind}-${artifact.id}`}>
          {artifact.kind === 'quiz' ? (
            <ClickableCard title="Quiz" body={artifact.title} onOpen={() => onOpenQuiz(artifact.id)} />
          ) : null}
          {artifact.kind === 'whiteboard' ? (
            <ClickableCard
              title="Whiteboard"
              body={artifact.description ? firstSentence(artifact.description) : null}
              onOpen={() => onOpenWhiteboard(artifact.id)}
            />
          ) : null}
          {artifact.kind === 'animation' ? (
            <AnimationCard animation={artifact} onOpen={onOpenAnimation} />
          ) : null}
        </li>
      ))}
    </ul>
  )
}

function ClickableCard({
  title,
  body,
  onOpen,
}: {
  title: string
  body: string | null
  onOpen: () => void
}) {
  return (
    <button type="button" className="tools-card tools-card--clickable" onClick={onOpen}>
      <span className="tools-card-title">{title}</span>
      {body ? <span className="tools-card-body">{body}</span> : null}
    </button>
  )
}

function AnimationCard({
  animation,
  onOpen,
}: {
  animation: AnimationArtifact
  onOpen: (sessionId: string, jobId: string) => void
}) {
  if (animation.status === 'ready') {
    return (
      <ClickableCard
        title="Animation"
        body="Open the finished animation."
        onOpen={() => onOpen(animation.session_id, animation.id)}
      />
    )
  }
  return (
    <div className="tools-card">
      <span className="tools-card-row">
        <span className="tools-card-title">Animation</span>
        {animation.status === 'running' ? <Badge variant="neutral">In progress</Badge> : null}
      </span>
      {animation.status === 'running' ? (
        <span className="tools-card-body">Still working. You can keep talking.</span>
      ) : null}
      {animation.status === 'failed' ? <AlertBanner>{FAILURE_NOTICE}</AlertBanner> : null}
    </div>
  )
}
