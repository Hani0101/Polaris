import { useState } from 'react'
import type { ReactNode } from 'react'
import { Clapperboard, Layers, ListChecks, Presentation } from 'lucide-react'
import type { AnimationArtifact, Artifact, Quiz, WhiteboardArtifact } from '../api.ts'
import { AnimationPlayer } from '../AnimationPlayer.tsx'
import type { AskAboutStep } from '../animation/ScenePlayer.tsx'
import { QuizCard } from '../QuizCard.tsx'
import type { PointedPart } from '../whiteboard/pointing.ts'
import { Tabs } from './Tabs.tsx'
import type { TabItem } from './Tabs.tsx'
import { FAILURE_NOTICE } from './AnimationCard.tsx'
import { stageText, useAnimationJob } from './animationJob.ts'
import { ResourcesTab } from './ResourcesTab.tsx'
import { useResources } from './resources.tsx'
import { AlertBanner, Badge, CloseIcon, IconButton } from './ui.tsx'
import './tools.css'

export type ToolsTab = 'whiteboard' | 'quiz' | 'animation' | 'resources' | 'artifacts'

const TABS: TabItem<ToolsTab>[] = [
  { id: 'whiteboard', label: 'Whiteboard' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'animation', label: 'Animation' },
  { id: 'resources', label: 'Resources' },
  { id: 'artifacts', label: 'Artifacts' },
]

type ToolsPanelProps = {
  artifacts: Artifact[]
  headingId: string
  onClose: () => void
  onOpenQuiz: (quizId: string) => void
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation: (sessionId: string, jobId: string) => void
  onQuizChecked: (quiz: Quiz) => void
  onAsk?: (whiteboardId: string, parts: PointedPart[]) => void
  onAskAboutStep?: (ask: AskAboutStep) => void
  /** Every whiteboard in the session, including the learner's own (WB-18). */
  whiteboards?: WhiteboardArtifact[]
  pinnedWhiteboardId?: string | null
  onNewWhiteboard?: () => void
  creatingWhiteboard?: boolean
}

/** The tools content: header, then Whiteboard, Quiz, Animation, and Artifacts tabs. */
export function ToolsPanel({
  artifacts,
  headingId,
  onClose,
  onOpenQuiz,
  onOpenWhiteboard,
  onOpenAnimation,
  onQuizChecked,
  onAskAboutStep,
  whiteboards = [],
  pinnedWhiteboardId = null,
  onNewWhiteboard,
  creatingWhiteboard = false,
}: ToolsPanelProps) {
  const [tab, setTab] = useState<ToolsTab>('whiteboard')
  const { focus } = useResources()
  const [seenFocus, setSeenFocus] = useState(focus?.nonce ?? 0)

  // A chosen citation opens the Resources tab (RS-09).
  if (focus && focus.nonce !== seenFocus) {
    setSeenFocus(focus.nonce)
    setTab('resources')
  }

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
            whiteboards={whiteboards}
            pinnedWhiteboardId={pinnedWhiteboardId}
            onOpenWhiteboard={onOpenWhiteboard}
            onNewWhiteboard={onNewWhiteboard}
            creating={creatingWhiteboard}
          />
        ) : null}
        {tab === 'quiz' ? (
          <QuizTab
            quiz={latest(artifacts, isQuiz)}
            onOpenQuiz={onOpenQuiz}
            onQuizChecked={onQuizChecked}
          />
        ) : null}
        {tab === 'animation' ? (
          <AnimationTab
            animation={latest(artifacts, isAnimation)}
            onOpenAnimation={onOpenAnimation}
            onAskAboutStep={onAskAboutStep}
          />
        ) : null}
        {tab === 'resources' ? <ResourcesTab /> : null}
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

/** New whiteboard, then every board in the session. Opening one pins it (WB-18, WB-19). */
function WhiteboardTab({
  whiteboards,
  pinnedWhiteboardId,
  onOpenWhiteboard,
  onNewWhiteboard,
  creating,
}: {
  whiteboards: WhiteboardArtifact[]
  pinnedWhiteboardId: string | null
  onOpenWhiteboard: (whiteboardId: string) => void
  onNewWhiteboard?: () => void
  creating: boolean
}) {
  const newButton = onNewWhiteboard ? (
    <div className="tools-actions">
      <button type="button" onClick={onNewWhiteboard} disabled={creating}>
        New whiteboard
      </button>
    </div>
  ) : null
  if (whiteboards.length === 0) {
    return (
      <div className="tools-whiteboard">
        <ToolsEmpty
          icon={<Presentation size={24} strokeWidth={2} aria-hidden="true" />}
          title="No whiteboard yet"
          body="Make one to sketch an idea and ask Polaris about it, or ask Polaris to draw."
        />
        {newButton}
      </div>
    )
  }
  const newestFirst = [...whiteboards].reverse()
  return (
    <div className="tools-whiteboard">
      {newButton}
      <ul className="tools-artifacts" aria-label="Whiteboards in this session">
        {newestFirst.map((whiteboard) => {
          const pinned = whiteboard.id === pinnedWhiteboardId
          return (
            <li key={whiteboard.id}>
              <button
                type="button"
                className={
                  pinned
                    ? 'tools-card tools-card--clickable is-selected'
                    : 'tools-card tools-card--clickable'
                }
                aria-current={pinned ? 'true' : undefined}
                onClick={() => onOpenWhiteboard(whiteboard.id)}
              >
                <span className="tools-card-row">
                  <span className="tools-card-title">Whiteboard</span>
                  {pinned ? <Badge variant="accent">Pinned</Badge> : null}
                </span>
                {whiteboard.description ? (
                  <span className="tools-card-body">{firstSentence(whiteboard.description)}</span>
                ) : null}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function QuizTab({
  quiz,
  onOpenQuiz,
  onQuizChecked,
}: {
  quiz: Quiz | null
  onOpenQuiz: (quizId: string) => void
  onQuizChecked: (quiz: Quiz) => void
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
  return <QuizCard key={quiz.id} quiz={quiz} onChecked={onQuizChecked} onExpand={onOpenQuiz} />
}

function AnimationTab({
  animation,
  onOpenAnimation,
  onAskAboutStep,
}: {
  animation: AnimationArtifact | null
  onOpenAnimation: (sessionId: string, jobId: string) => void
  onAskAboutStep?: (ask: AskAboutStep) => void
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
        onAskAboutStep={onAskAboutStep}
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
  const { status, stage } = useAnimationJob(animation)
  if (status === 'ready') {
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
        {status === 'running' ? <Badge variant="neutral">In progress</Badge> : null}
      </span>
      {status === 'running' && stageText(stage) ? (
        <span className="tools-card-body" role="status">
          {stageText(stage)}
        </span>
      ) : null}
      {status === 'running' ? (
        <span className="tools-card-body">Still working. You can keep talking.</span>
      ) : null}
      {status === 'failed' ? <AlertBanner>{FAILURE_NOTICE}</AlertBanner> : null}
    </div>
  )
}
