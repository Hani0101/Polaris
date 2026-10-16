import type { FormEvent } from 'react'
import type { SessionSummary } from '../api.ts'
import type { PointedPart, Pointing } from '../whiteboard/pointing.ts'
import { Conversation } from './Conversation.tsx'
import type { ViewTurn } from './Conversation.tsx'
import { SessionPanel } from './SessionPanel.tsx'
import { TopBar } from './TopBar.tsx'
import { AlertBanner, Toast } from './ui.tsx'

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
  onSimpler: (whiteboardId: string) => void
  pointing: Pointing | null
  onRemovePoint: (elementId: string) => void
  onAsk: (whiteboardId: string, parts: PointedPart[]) => void
  toast: string | null
  onCloseToast: () => void
}

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
  onSimpler,
  pointing,
  onRemovePoint,
  onAsk,
  toast,
  onCloseToast,
}: ChatShellProps) {
  return (
    <div className="app-shell">
      <TopBar
        sessionTitle={sessionTitle}
        sessionListOpen={sessionListOpen}
        onToggleSessions={onToggleSessions}
        onLeave={onLeave}
        canLeave={openId !== null}
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
          sessionOpen={openId !== null}
          onDraftChange={onDraftChange}
          onSend={onSend}
          onStop={onStop}
          onCopy={onCopy}
          onTryAgain={onTryAgain}
          onOpenQuiz={onOpenQuiz}
          onOpenWhiteboard={onOpenWhiteboard}
          onSimpler={onSimpler}
          sessionId={openId}
          onStart={onStart}
          pointing={pointing}
          onRemovePoint={onRemovePoint}
          onAsk={onAsk}
        />
      </div>
      {toast ? <Toast message={toast} onClose={onCloseToast} /> : null}
    </div>
  )
}
