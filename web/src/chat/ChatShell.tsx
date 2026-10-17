import { useId, useRef, useState, useSyncExternalStore } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import type { Artifact, BoardPicture, Quiz, SessionSummary, WhiteboardArtifact } from '../api.ts'
import type { AskedStep } from '../animation/askedStep.ts'
import type { AskAboutStep } from '../animation/ScenePlayer.tsx'
import type { PointedPart, Pointing } from '../whiteboard/pointing.ts'
import { BottomSheet } from './BottomSheet.tsx'
import { Conversation } from './Conversation.tsx'
import type { ViewTurn } from './Conversation.tsx'
import { PinnedWhiteboard } from './PinnedWhiteboard.tsx'
import type { PinnedTurn } from './PinnedWhiteboard.tsx'
import { ResizeHandle, useSize } from './ResizeHandle.tsx'
import { SessionPanel } from './SessionPanel.tsx'
import { ToolsPanel } from './ToolsPanel.tsx'
import { TopBar } from './TopBar.tsx'
import { AlertBanner, Toast } from './ui.tsx'

const PHONE_QUERY = '(max-width: 639px)'
// Side panels the learner can drag on a laptop. DS-GAP: no token for the limits.
const PANEL_MIN = 200
const PANEL_MAX = 640

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
  onRename: (sessionId: string, name: string) => Promise<void>
  onOpenSettings: () => void
  onLeave: () => void
  turns: ViewTurn[]
  draft: string
  sending: boolean
  sendError: string | null
  onDraftChange: (value: string) => void
  onSend: (event: FormEvent<HTMLFormElement>) => void
  onStop: () => void
  onCopy: (text: string) => void
  onTryAgain: (
    learnerMessage: string,
    pointing?: Pointing | null,
    animationStep?: AskedStep | null,
  ) => void
  onOpenQuiz: (quizId: string) => void
  onOpenWhiteboard: (whiteboardId: string) => void
  onOpenAnimation: (sessionId: string, jobId: string) => void
  onSimpler: (whiteboardId: string) => void
  pointing: Pointing | null
  onRemovePoint: (elementId: string) => void
  pictureAttached?: boolean
  onRemovePicture?: () => void
  onAsk: (whiteboardId: string, parts: PointedPart[]) => void
  animationStep?: AskedStep | null
  onAskAboutStep?: (ask: AskAboutStep) => void
  onRemoveAnimationStep?: () => void
  toast: string | null
  onCloseToast: () => void
  artifacts?: Artifact[]
  toolsOpen?: boolean
  onToggleTools?: () => void
  onCloseTools?: () => void
  onQuizChecked?: (quiz: Quiz) => void
  /** Every whiteboard in the session, for the Whiteboard tab (WB-18). */
  whiteboards?: WhiteboardArtifact[]
  onNewWhiteboard?: () => void
  creatingWhiteboard?: boolean
  /** The board pinned above the conversation, and the reply adding to it (WB-19). */
  pinnedWhiteboardId?: string | null
  pinnedTurn?: PinnedTurn | null
  onClosePinned?: () => void
  onPicture?: (picture: BoardPicture) => void
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
  onRename,
  onOpenSettings,
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
  animationStep = null,
  onAskAboutStep,
  onRemoveAnimationStep,
  toast,
  onCloseToast,
  artifacts = [],
  toolsOpen = false,
  onToggleTools = noTools,
  onCloseTools = noTools,
  onQuizChecked = noTools,
  whiteboards = [],
  onNewWhiteboard,
  creatingWhiteboard = false,
  pinnedWhiteboardId = null,
  pinnedTurn = null,
  onClosePinned = noTools,
  onPicture,
}: ChatShellProps) {
  const phone = useMediaQuery(PHONE_QUERY)
  const [sheetOpen, setSheetOpen] = useState(false)
  const toolsButton = useRef<HTMLButtonElement>(null)
  const panelHeading = useId()
  const sheetHeading = useId()
  const sessionOpen = openId !== null
  const body = useRef<HTMLDivElement>(null)
  const [leftWidth, setLeftWidth] = useSize('polaris.panel.left', PANEL_MIN, PANEL_MAX)
  const [rightWidth, setRightWidth] = useSize('polaris.panel.right', PANEL_MIN, PANEL_MAX)
  const widthOf = (selector: string) => () =>
    body.current?.querySelector(selector)?.getBoundingClientRect().width ?? PANEL_MIN
  const panelWidths = {
    ...(leftWidth === null ? {} : { '--panel-left-width': `${leftWidth}px` }),
    ...(rightWidth === null ? {} : { '--panel-right-width': `${rightWidth}px` }),
  } as CSSProperties

  if (sheetOpen && (!phone || !sessionOpen)) setSheetOpen(false)

  // On a phone the sheet closes, so the board pinned above the chat is in view.
  function openBoard(whiteboardId: string) {
    setSheetOpen(false)
    onOpenWhiteboard(whiteboardId)
  }

  const toolsProps = {
    artifacts,
    whiteboards,
    pinnedWhiteboardId,
    creatingWhiteboard,
    onNewWhiteboard: onNewWhiteboard
      ? () => {
          setSheetOpen(false)
          onNewWhiteboard()
        }
      : undefined,
    onOpenQuiz,
    onOpenWhiteboard: openBoard,
    onOpenAnimation,
    onQuizChecked,
    onAsk,
    onAskAboutStep,
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
      <div className="app-body" ref={body} style={panelWidths}>
        <SessionPanel
          sessions={sessions}
          openId={openId}
          loading={loading}
          open={sessionListOpen}
          onClose={onCloseSessions}
          onStart={onStart}
          onOpen={onOpen}
          onRename={onRename}
          onOpenSettings={onOpenSettings}
        />
        {sessionListOpen ? (
          <ResizeHandle
            label="Resize sessions panel"
            orientation="vertical"
            grows={1}
            min={PANEL_MIN}
            max={PANEL_MAX}
            measure={widthOf('.session-panel')}
            onResize={setLeftWidth}
          />
        ) : null}
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
          animationStep={animationStep}
          onRemoveAnimationStep={onRemoveAnimationStep}
          onAsk={onAsk}
          onOpenTools={phone ? () => setSheetOpen(true) : undefined}
          toolsButtonRef={toolsButton}
          pinnedWhiteboardId={pinnedWhiteboardId}
          pinned={
            sessionOpen && openId && pinnedWhiteboardId ? (
              <PinnedWhiteboard
                key={pinnedWhiteboardId}
                sessionId={openId}
                whiteboardId={pinnedWhiteboardId}
                turn={pinnedTurn}
                onClose={onClosePinned}
                onAsk={(parts) => onAsk(pinnedWhiteboardId, parts)}
                onPicture={onPicture}
              />
            ) : null
          }
        />
        {sessionOpen && !phone && toolsOpen ? (
          <ResizeHandle
            label="Resize tools panel"
            orientation="vertical"
            grows={-1}
            min={PANEL_MIN}
            max={PANEL_MAX}
            measure={widthOf('.tools-panel')}
            onResize={setRightWidth}
          />
        ) : null}
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
