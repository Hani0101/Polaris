import { useCallback, useId, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import type { Artifact, BoardPicture, Deck, Quiz, SessionSummary, WhiteboardArtifact } from '../api.ts'
import type { AskedStep } from '../animation/askedStep.ts'
import type { SignInState } from '../auth.ts'
import type { AskAboutStep } from '../animation/ScenePlayer.tsx'
import type { PointedPart, Pointing } from '../whiteboard/pointing.ts'
import { useSteady } from '../useSteady.ts'
import { BottomSheet } from './BottomSheet.tsx'
import { Conversation } from './Conversation.tsx'
import type { ViewTurn } from './Conversation.tsx'
import type { Draft } from './draft.ts'
import { PinnedWhiteboard } from './PinnedWhiteboard.tsx'
import type { PinnedTurn } from './PinnedWhiteboard.tsx'
import { ResizeHandle, useSize } from './ResizeHandle.tsx'
import { ResourcesProvider } from './resources.tsx'
import { SessionPanel } from './SessionPanel.tsx'
import { ToolsPanel } from './ToolsPanel.tsx'
import { TopBar } from './TopBar.tsx'
import { AlertBanner, Toast } from './ui.tsx'

const PHONE_QUERY = '(max-width: 639px)'
// Side panels the learner can drag on a laptop. DS-GAP: no token for the limits.
const PANEL_MIN = 200
const PANEL_MAX = 640

function useMediaQuery(query: string): boolean {
  // One query list per query, read on every render, not a new one each time.
  const media = useMemo(() => window.matchMedia(query), [query])
  const subscribe = useCallback(
    (notify: () => void) => {
      media.addEventListener('change', notify)
      return () => media.removeEventListener('change', notify)
    },
    [media],
  )
  return useSyncExternalStore(subscribe, () => media.matches)
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
  onDelete: (sessionId: string) => Promise<void>
  onOpenSettings: () => void
  onLeave: () => void
  /** Sign-in state for the top bar (AU-01, AU-02). */
  account?: SignInState
  onSignIn?: () => void
  onSignOut?: () => void
  turns: ViewTurn[]
  draft: Draft
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
  onOpenDeck?: (deckId: string) => void
  onDeckChanged?: (deck: Deck) => void
  /** Sends the learner turn that asks for a deck, from the Create flashcards dialog (FC-01). */
  onAskForDeck?: (message: string) => void
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
// Defaults with one identity, so a memoized panel does not see a new list each render.
const noArtifacts: Artifact[] = []
const noWhiteboards: WhiteboardArtifact[] = []

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
  onDelete,
  onOpenSettings,
  onLeave,
  account,
  onSignIn,
  onSignOut,
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
  artifacts = noArtifacts,
  toolsOpen = false,
  onToggleTools = noTools,
  onCloseTools = noTools,
  onQuizChecked = noTools,
  onOpenDeck = noTools,
  onDeckChanged = noTools,
  onAskForDeck,
  whiteboards = noWhiteboards,
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
  const openBoard = useSteady((whiteboardId: string) => {
    setSheetOpen(false)
    onOpenWhiteboard(whiteboardId)
  })
  const newBoard = useSteady(() => {
    setSheetOpen(false)
    onNewWhiteboard?.()
  })
  // On a phone the sheet closes, so the learner sees the turn that asks for the deck.
  const askForDeck = useSteady((message: string) => {
    setSheetOpen(false)
    onAskForDeck?.(message)
  })
  const closeSheet = useCallback(() => setSheetOpen(false), [])
  const openSheet = useCallback(() => setSheetOpen(true), [])
  const askPinned = useSteady((parts: PointedPart[]) => {
    if (pinnedWhiteboardId) onAsk(pinnedWhiteboardId, parts)
  })

  const toolsProps = {
    artifacts,
    whiteboards,
    pinnedWhiteboardId,
    creatingWhiteboard,
    onNewWhiteboard: onNewWhiteboard ? newBoard : undefined,
    onOpenQuiz,
    onOpenWhiteboard: openBoard,
    onOpenAnimation,
    onQuizChecked,
    onAsk,
    onAskAboutStep,
    onOpenDeck,
    onDeckChanged,
    onCreateFlashcards: onAskForDeck ? askForDeck : undefined,
    sending,
  }

  // A chosen citation opens the tools where the Resources tab shows it (RS-09).
  function showResources() {
    if (phone) setSheetOpen(true)
    else if (!toolsOpen) onToggleTools()
  }

  return (
    <ResourcesProvider sessionId={openId} onFocus={showResources}>
      <div className="app-shell">
        <TopBar
          sessionTitle={sessionTitle}
          sessionListOpen={sessionListOpen}
          onToggleSessions={onToggleSessions}
          onLeave={onLeave}
          canLeave={sessionOpen}
          account={account}
          onSignIn={onSignIn}
          onSignOut={onSignOut}
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
            onDelete={onDelete}
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
            onOpenDeck={onOpenDeck}
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
            onOpenTools={phone ? openSheet : undefined}
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
                  onAsk={askPinned}
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
            onClose={closeSheet}
            returnFocus={toolsButton}
          >
            <ToolsPanel
              headingId={sheetHeading}
              onClose={closeSheet}
              {...toolsProps}
            />
          </BottomSheet>
        ) : null}
        {toast ? <Toast message={toast} onClose={onCloseToast} /> : null}
      </div>
    </ResourcesProvider>
  )
}
