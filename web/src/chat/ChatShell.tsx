import { useId, useRef, useState, useSyncExternalStore } from 'react'
import type { FormEvent } from 'react'
import type { Artifact, Quiz, SessionSummary } from '../api.ts'
import type { PointedPart, Pointing } from '../whiteboard/pointing.ts'
import { BottomSheet } from './BottomSheet.tsx'
import { Conversation } from './Conversation.tsx'
import type { ViewTurn } from './Conversation.tsx'
import { SessionPanel } from './SessionPanel.tsx'
import { ToolsPanel } from './ToolsPanel.tsx'
import { TopBar } from './TopBar.tsx'
import { AlertBanner, Toast } from './ui.tsx'

const PHONE_QUERY = '(max-width: 639px)'

function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const media = window.matchMedia(query)
      media.addEventListener('change', notify)
      return () => media.removeEventListener('change', notify)
    },
    () => window.matchMedia(query).matches,
  )
}

type ChatShellProps = {
  sessions: SessionSummary[]
  openId: string | null
  sessionTitle: string | null
  loading: boolean
  error: string | null
  onRetryLoad: () => void
  sessionListOpen: boolean
  onToggleSessions: () => void
  onCloseSessions: () => void
  onStart: () => void
  onOpen: (sessionId: string) => void
  onLeave: () => void
  turns: ViewTurn[]
  draft: string
  sending: boolean
  sendError: string | null
  onDraftChange: (value: string) => void
  onSend: (event: FormEvent<HTMLFormElement>) => void
  onStop: () => void
  onCopy: (text: string) => void
  onTryAgain: (learnerMessage: string, pointing?: Pointing | null) => void
  onOpenQuiz: (quizId: string) => void
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation: (sessionId: string, jobId: string) => void
  onSimpler: (whiteboardId: string) => void
  pointing: Pointing | null
  onRemovePoint: (elementId: string) => void
  pictureAttached?: boolean
  onRemovePicture?: () => void
  onAsk: (whiteboardId: string, parts: PointedPart[]) => void
  toast: string | null
  onCloseToast: () => void
  artifacts?: Artifact[]
  toolsOpen?: boolean
  onToggleTools?: () => void
  onCloseTools?: () => void
  onQuizGraded?: (quiz: Quiz) => void
}

const noTools = () => {}

export function ChatShell({
  sessions,
  openId,
  sessionTitle,
  loading,
  error,
  onRetryLoad,
  sessionListOpen,
  onToggleSessions,
  onCloseSessions,
  onStart,
  onOpen,
  onLeave,
  turns,
  draft,
  sending,
  sendError,
  onDraftChange,
  onSend,
  onStop,
  onCopy,
  onTryAgain,
  onOpenQuiz,
  onOpenWhiteboard,
  onOpenAnimation,
  onSimpler,
  pointing,
  onRemovePoint,
  pictureAttached,
  onRemovePicture,
  onAsk,
  toast,
  onCloseToast,
  artifacts = [],
  toolsOpen = false,
  onToggleTools = noTools,
  onCloseTools = noTools,
  onQuizGraded = noTools,
}: ChatShellProps) {
  const phone = useMediaQuery(PHONE_QUERY)
  const [sheetOpen, setSheetOpen] = useState(false)
  const toolsButton = useRef<HTMLButtonElement>(null)
  const panelHeading = useId()
  const sheetHeading = useId()
  const sessionOpen = openId !== null

  if (sheetOpen && (!phone || !sessionOpen)) setSheetOpen(false)

  const toolsProps = {
    artifacts,
    onOpenQuiz,
    onOpenWhiteboard,
    onOpenAnimation,
    onQuizGraded,
    onAsk,
  }

  return (
    <div className="app-shell">
      <TopBar
        sessionTitle={sessionTitle}
        sessionListOpen={sessionListOpen}
        onToggleSessions={onToggleSessions}
        onLeave={onLeave}
        canLeave={sessionOpen}
        showToolsToggle={sessionOpen && !phone}
        toolsOpen={toolsOpen}
        onToggleTools={onToggleTools}
      />
      {error ? (
        <div className="shell-alert">
          <AlertBanner
            action={
              <button type="button" className="secondary" onClick={onRetryLoad}>
                Try again
              </button>
            }
          >
            {error}
          </AlertBanner>
        </div>
      ) : null}
      <div className="app-body">
        <SessionPanel
          sessions={sessions}
          openId={openId}
          loading={loading}
          open={sessionListOpen}
          onClose={onCloseSessions}
          onStart={onStart}
          onOpen={onOpen}
        />
        {sessionListOpen ? (
          <button
            type="button"
            className="drawer-dismiss"
            aria-label="Close sessions"
            onClick={onCloseSessions}
          />
        ) : null}
        <Conversation
          turns={turns}
          draft={draft}
          sending={sending}
          sendError={sendError}
          sessionOpen={sessionOpen}
          onDraftChange={onDraftChange}
          onSend={onSend}
          onStop={onStop}
          onCopy={onCopy}
          onTryAgain={onTryAgain}
          onOpenQuiz={onOpenQuiz}
          onOpenWhiteboard={onOpenWhiteboard}
          onOpenAnimation={onOpenAnimation}
          onSimpler={onSimpler}
          sessionId={openId}
          onStart={onStart}
          pointing={pointing}
          onRemovePoint={onRemovePoint}
          pictureAttached={pictureAttached}
          onRemovePicture={onRemovePicture}
          onAsk={onAsk}
          onOpenTools={phone ? () => setSheetOpen(true) : undefined}
          toolsButtonRef={toolsButton}
        />
        {sessionOpen && !phone && toolsOpen ? (
          <aside className="tools-panel" aria-labelledby={panelHeading}>
            <ToolsPanel headingId={panelHeading} onClose={onCloseTools} {...toolsProps} />
          </aside>
        ) : null}
      </div>
      {sessionOpen && phone ? (
        <BottomSheet
          open={sheetOpen}
          labelledBy={sheetHeading}
          onClose={() => setSheetOpen(false)}
          returnFocus={toolsButton}
        >
          <ToolsPanel
            headingId={sheetHeading}
            onClose={() => setSheetOpen(false)}
            {...toolsProps}
          />
        </BottomSheet>
      ) : null}
      {toast ? <Toast message={toast} onClose={onCloseToast} /> : null}
    </div>
  )
}
