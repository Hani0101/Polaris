# Optimization

Speed and CPU findings for Polaris from a review on 18 Oct 2026, at commit `28c33b9`. Items are ranked by how much the learner would feel each one. Each item gives where the cost is, how it was measured, the fix, and its status.

Measurements used a copy of `api/data/polaris.db`, a temporary jsdom test run with React's development build, and a production build of `web/`. The jsdom times are inflated, so compare their ratios rather than their milliseconds.

No rule changes. Item 1 keeps PR-01, PR-05, and CH-16 as written.

Items 14 to 18 come from a second pass the same day, on the `later.md` note that typing in the chat spikes the CPU, and spikes it more with a board open. They were measured in headless Chromium driven by Playwright, with every `/api` call answered from copies of real sessions, so no session was opened or warmed on the server. The script typed 120 characters into the composer, 60 ms apart, at 1440 × 900, with 47 sessions in the list. It ran against the Vite dev server and against a production build, with a 5-turn and a 41-turn conversation, with and without a pinned board. A stand-in React DevTools hook counted the components that rendered on each key. Chrome's performance metrics, CPU profile, and trace gave the costs. Headless Chromium does not draw to a real screen, so GPU work is not covered.

What it found: a board left alone costs almost nothing. With a board pinned and nothing typed, the main thread was 2 to 4% busy, the same as without one. The cost is React drawing the app again on every key. The conversation's length makes no difference: 5 turns and 41 turns render the same 177 components per key, because each turn is memoized (item 2). The dev server's React costs about six times as much as the production build for the same renders, so the spike is far worse while developing.

| | Dev server | Production build |
|---|---|---|
| Main thread per key, no board | 44 to 52 ms | 7 to 10 ms (3 ms of it script) |
| Main thread per key, board pinned | 49 to 70 ms | 9 to 12 ms (4 ms of it script) |
| Components rendered per key | 177, or 257 with a board | the same |
| Time to type the 120 keys (7.2 s of key gaps) | 13 to 16 s, so keys queued up | 9.5 s |

## Status

| # | Item | Status |
|---|---|---|
| 1 | Starting, switching, or leaving a session waits for the profile pass | Done |
| 2 | Each streamed chunk re-renders the whole conversation | Done |
| 3 | The whiteboard in a streaming turn is rebuilt on every chunk | Done |
| 4 | Every whiteboard in the conversation is a live tldraw editor | Done |
| 5 | First load parses 2.5 MB of JavaScript | Done |
| 6 | Every database write waits on a slow disk | Done |
| 7 | The first message of a session waits for the Claude CLI to start | Done |
| 8 | Each reply checks every whiteboard three times | Done |
| 9 | Auto-scroll pulls the learner back down | Done |
| 10 | A PNG of the board is made after every pause in drawing | Done |
| 11 | A running animation job is polled two or three times | Done |
| 12 | Listing resources parses all their text | Done |
| 13 | Requests after a turn run one after another | Done |
| 14 | Each typed key draws the whole app again | Done |
| 15 | Each typed key draws the pinned board's tldraw tree again | Done |
| 16 | The shell around the conversation is not memoized | Done |
| 17 | Each typed key forces a layout to size the message box | Done |
| 18 | The phone check makes a new media query on every render | Done |

## 1. Starting, switching, or leaving a session waits for the profile pass

- **Where:** `close_ended` and `leave_session` in `api/polaris/app.py`.
- **Cost:** The response waits until the agent's client has closed and the profile pass has run. The pass starts the Claude CLI and makes a Haiku call. So "New session", opening another session, and Leave all freeze for that long. Closing the client alone can take up to 5 s, because the SDK waits for the CLI to exit. This is likely what `later.md` describes as slow switching that needs two clicks, and a second click creating a second session.
- **Fix:** End the session at once, and run the close and the pass after the response, one pass at a time. A reply waits for any pass still running before it reads the profile, and so does `GET /api/profile`. That keeps PR-01 and the "a later session teaches with those facts in hand" scenario. Deleting a session still waits for its pass (CH-16), and so does shutdown. A pass that sees an API key still stops the app (decision 0001). The browser also ignores a second start or open while one is running, so a double click no longer starts two sessions.
- **Done:** `Chat.end_in_background` and `Chat.wait_for_session_ends` in `api/polaris/chat.py`, and `oneAtATime` in `web/src/App.tsx`. New tests in `api/tests/test_chat.py` check that switching does not wait, that a reply waits for a pass still running, and that deleting an ended session waits for its pass. Tests that read a pass's result straight after the request now wait for it first.

## 2. Each streamed chunk re-renders the whole conversation

- **Where:** `mergeTurns` in `web/src/App.tsx`, `Maths` and code blocks in `web/src/chat/ReplyText.tsx`, and `ResourcesProvider` in `web/src/chat/resources.tsx`.
- **Cost:**
  - `mergeTurns` builds a new object for every saved turn on each chunk, so `memo(TurnBlock)` never skips a turn. With 15 saved turns, a chunk cost 10.9 ms, against 2.5 ms with stable objects. The cost grows with the length of the session.
  - The streaming reply runs KaTeX and syntax colors again for every formula and code block on each chunk. One 2,070-character reply streamed in 173 chunks made 2,001 `katex.renderToString` calls. The cost per chunk grows as the reply gets longer.
  - `ChatShell` passes a new `onFocus` on every render. That changes the resources context, so every citation in every past reply re-renders on each chunk.
- **Fix:** Build the views of saved and stopped turns only when they change, so only the pending turn is new on each chunk. Memoize `Maths` and a code-block component, so only the block still being written renders again. Keep `onFocus` in a ref.
- **Done:** The same 173-chunk reply now makes 19 KaTeX calls instead of 2,001, and a full re-render of it takes 0.9 ms instead of 9.6 ms. Saved turns keep their objects while a reply streams, which is the 2.5 ms case above.

## 3. The whiteboard in a streaming turn is rebuilt on every chunk

- **Where:** `revealWhiteboard` and `revealAddedSteps` in `web/src/whiteboard/reveal.ts`, and the view-mode effect in `web/src/whiteboard/Whiteboard.tsx`.
- **Cost:** `revealWhiteboard` returns a new object even when no new step has unlocked. The board is then converted again, and every tldraw shape is deleted and recreated: 20 times in 20 chunks in the test. The pinned board does the same while its added steps arrive.
- **Fix:** Return the same object for a board while it shows the same steps, and skip re-rendering a turn's board when nothing about it changed.
- **Done:** 20 chunks without a new step now convert the board 0 times, and the next step converts it once. The board in a turn is its own memoized component, `TurnWhiteboard` in `web/src/chat/Conversation.tsx`.

## 4. Every whiteboard in the conversation is a live tldraw editor

- **Where:** `<Tldraw>` in `web/src/whiteboard/Whiteboard.tsx`, mounted once per board by `web/src/chat/Conversation.tsx`.
- **Cost:** tldraw's `TickManager` runs every frame, up to 120 times a second, for as long as an editor is mounted. That includes boards scrolled out of view, and the chat hidden behind the quiz, whiteboard, animation, and settings pages. Opening a session mounts every board at once. The loop is confirmed in tldraw's source; its CPU use was not measured in a browser.
- **Fix:** Mount a turn's editor only while its board is near the screen. Otherwise show a placeholder of the same size that keeps the board's text description.
- **Done:** `TurnWhiteboard` in `web/src/chat/Conversation.tsx` mounts the editor only within one screen of the visible turns, using an `IntersectionObserver` on the conversation's scroll area. A board behind another page counts as off screen. Otherwise it shows `WhiteboardPlaceholder` from `web/src/whiteboard/LazyWhiteboard.tsx`: the board's surface in its colors, with its description. The pinned board and the whiteboard page keep their editors, since the learner draws there. A new test in `Conversation.test.tsx` mounts and unmounts a board as it nears and leaves the screen.

## 5. First load parses 2.5 MB of JavaScript

- **Where:** the production build of `web/`, which is one 2.52 MB chunk (758 KB gzipped).
- **Cost:** tldraw and the editor libraries it pulls in (prosemirror, tiptap, radix) are about 1.45 MB of that chunk. They load before the session list shows, though most screens never show a board. This matters most on phones, and the product is mobile first.
- **Fix:** Load `Whiteboard` with `React.lazy` in `Conversation`, `PinnedWhiteboard`, and `WhiteboardPage`, the only places the app reaches tldraw. Prefetch it once the app is idle.
- **Done:** All three now use `web/src/whiteboard/LazyWhiteboard.tsx`, and `App` prefetches it once the browser is idle. The main chunk is now 774 KB (237 KB gzipped), and tldraw has its own 1.74 MB chunk. A board first shown after the code has loaded draws at once, with no placeholder.

## 6. Every database write waits on a slow disk

- **Where:** `_open_db` in `api/polaris/chat.py`.
- **Cost:** `polaris.db` is on E:, a 5400 rpm hard disk. With SQLite's default `synchronous=FULL`, a commit there took 11 ms (median) and up to 89 ms. With `NORMAL` it took 0.05 ms. All access goes through one lock, so each commit also holds up every other request.
- **Fix:** `PRAGMA synchronous = NORMAL`, SQLite's recommended setting for WAL mode. It cannot corrupt the database, though a power cut can lose the last few commits.
- **Done:** in `_open_db`.

## 7. The first message of a session waits for the Claude CLI to start

- **Where:** `_ensure_client` in `api/polaris/teaching.py`.
- **Cost:** The client connects inside the first reply. Switching sessions disconnects it, so going back to a session pays again. The bundled CLI is a 271 MB `.exe` on the hard disk: its first launch took 4.8 s, and 0.1 s once cached.
- **Fix:** Connect in the background once the learner starts typing in a session. Connecting when a session opens would also start a CLI for every session the learner only opens to read. Separately, moving the repo or the venv to the NVMe drive speeds up every cold start: replies, profile passes, quiz key checks, and animation jobs.
- **Done:** `POST /api/sessions/{id}/warm` connects a session's client in the background (`Chat.warm_in_background` in `api/polaris/chat.py`, `ClaudeTeachingAgent.warm` in `api/polaris/teaching.py`). `warmOnTyping` in `web/src/App.tsx` calls it once per session open, when the draft first has text. The first reply waits for that same connect and sends exactly what a cold start would. It still reads the profile after any session-end work, and its stream is still checked for an API key. A session that ends during the connect waits for it, then closes the client. New tests in `api/tests/test_teaching.py` and `api/tests/test_chat.py` check this. Moving the repo or the venv to the NVMe drive is still to do, and is not a code change.

## 8. Each reply checks every whiteboard three times

- **Where:** `_turns`, `list_whiteboards`, and `whiteboards_for_reply` in `api/polaris/chat.py`.
- **Cost:** Each check re-plots graphs and re-parses LaTeX. The current boards cost about 3 ms in total. A heavy board that is still within the limits (4 graphs of 201 samples, 3 formulas, 30 pen strokes) costs 17 ms per check.
- **Fix:** Cache check results by the stored JSON text, since the check gives the same answer for the same text.
- **Done:** `_checked_board` in `api/polaris/chat.py` caches the check by the stored JSON text, for up to 128 boards. It keeps each board pickled, so every reader gets its own copy. `whiteboards_for_reply` no longer goes through `list_whiteboards`, and no check runs while the database lock is held. On the heavy board, a reply's three reads went from about 58 ms to about 10 ms. The first read after a board changes takes about 45 ms. `api/tests/test_board_check_cache.py` checks that each board is checked once, that every reader gets its own copy, and that a changed board is checked again.

## 9. Auto-scroll pulls the learner back down

- **Where:** the scroll effect in `web/src/chat/Conversation.tsx`.
- **Cost:** The conversation jumps to the bottom on every change, including each chunk, animation status updates, and quiz checks. It does so even while the learner has scrolled up to read.
- **Fix:** Follow the bottom only while the learner is near it. Sending a message or opening a session goes back to the bottom.
- **Done:** in `Conversation`. "Near" means within 64 px of the bottom. Sending includes Try again and Simpler. A new test in `Conversation.test.tsx` covers reading up, coming back down, and sending.

## 10. A PNG of the board is made after every pause in drawing

- **Where:** `persist` in `web/src/whiteboard/useBoardSaving.ts`.
- **Cost:** Every save, which comes 300 ms after the learner stops drawing, also renders the whole board to a PNG. When the learner has drawn again during the save, that PNG is already out of date, and the next save exports another.
- **Fix:** Skip the export when the board has changed since the save. The next save exports it, so the "A picture of the learner's drawing" rule in `docs/features/whiteboard.md` still holds. Exporting less often than each saved change would break that rule, so it needs a decision first.
- **Done:** in `persist`. A count of drawing changes tells a save whether the learner drew again while it ran. If so, it skips the PNG and the next save takes it, so each saved final change still gets one. If that next save fails, the earlier save takes the picture after all. `web/src/whiteboard/useBoardSaving.test.ts` checks a single pause, drawing during a save, flush, and the failed save.

## 11. A running animation job is polled two or three times

- **Where:** `watchAnimationJob` in `web/src/chat/animationNotices.ts`, and `useAnimationJob` in `web/src/chat/animationJob.ts`, used by both job cards.
- **Cost:** The app-level watcher and each mounted card poll the same job every 10 s.
- **Fix:** One poll per job, shared by every card.
- **Done:** `subscribeAnimationJob` in `web/src/chat/animationJob.ts` runs one 10 s poll per job for the app-level watcher and every card. It stops when the job finishes or the last subscriber leaves. With two cards and the watcher on one job, `web/src/chat/AnimationCard.test.tsx` sees one fetch per interval instead of three. A card that opens while its job is being polled gets the job's next poll, which can come sooner than 10 s.

## 12. Listing resources parses all their text

- **Where:** `_summary` in `api/polaris/resources.py`.
- **Cost:** Every turn, resource list, and upload loads each resource's full extracted text just to count its pages. With ten large PDFs that took 14 ms, against 2.4 ms when SQL counts them. Low priority: the current data has one small PDF.
- **Fix:** Count pages with `json_array_length(pages_json)` in the query.
- **Done:** `list_all` and `_row` in `api/polaris/resources.py` select the count, and the list no longer selects the text. `pages_json` is never null and always holds an array, so the counts are the same as before. New test: `test_the_list_counts_pages_without_the_text` in `api/tests/test_resources.py`.

## 13. Requests after a turn run one after another

- **Where:** `sendMessage` in `web/src/App.tsx`.
- **Cost:** After a turn, the session, the whiteboard list, and the session list are fetched partly one after another.
- **Fix:** Fetch them together.
- **Done:** A session list that fails to load after a turn now keeps the sessions it had, as the whiteboard list already did.

## 14. Each typed key draws the whole app again

- **Where:** the `draft` state in `App` in `web/src/App.tsx`, passed through `ChatShell` to the composer in `web/src/chat/Conversation.tsx`.
- **Cost:** Every key sets state at the root, so `App`, `ChatShell`, `SessionPanel` with every row, both session dialogs, `TopBar`, `ToolsPanel`, and `Conversation` render again. That is 177 components per key with 47 sessions, and 141 of them are the session rows' menus and their icons. On the dev server, 120 keys kept the main thread 44% busy and took 13 to 16 s to type instead of about 7 s, so the box lagged behind the keys. The production build spends 7 to 10 ms per key.
- **Fix:** Keep the draft in a composer component, not in `App`. `App` reads the text when it sends, clears it, and puts it back after a failed send, through a ref handle or a small store that only the composer reads. `warmOnTyping` and clearing `sendError` already act only once, so they can stay as callbacks from the composer. A key then renders the composer alone. This does most of the work for item 15 too.
- **Done:** The draft is a small store, `createDraft` in `web/src/chat/draft.ts`. `App` makes one, reads it on send, clears it, and puts the message back after a failed send. Only `Composer` in `web/src/chat/Conversation.tsx` reads it while the learner types. It is memoized, and `Conversation` passes it steady handlers. Measured again on 18 Oct with the same kind of run, against a production build with mocked `/api` answers (47 sessions, a 5-turn conversation, 120 keys 60 ms apart): a key now renders 5 components (the composer and its Send button) instead of 177, and the main thread spends about 4 ms per key. The mocked data is not the copies of real sessions the first run used, so compare the component counts, not the milliseconds. A new test in `Conversation.test.tsx` checks that typing fills the draft with no new props, and that the app can clear and restore it.

## 15. Each typed key draws the pinned board's tldraw tree again

- **Where:** `pinned` in `web/src/chat/ChatShell.tsx`, which builds `PinnedWhiteboard` with a new `onAsk` arrow on every render. Neither `PinnedWhiteboard` (`web/src/chat/PinnedWhiteboard.tsx`) nor `Whiteboard` (`web/src/whiteboard/Whiteboard.tsx`) is memoized. `Whiteboard` gives `<Tldraw>` a new `onMount` and a new `shapeUtils` array on every render, and works out `readableDescription` again each time.
- **Cost:** A pinned board adds about 80 components to every key: `PinnedWhiteboard`, both `Whiteboard` layers, about 35 of tldraw's providers (`TldrawEditor`, `TldrawUi`, and the tooltip, toast, dialog, and translation providers), the drawing `Toolbar` with its icons, and `CommentPins`. tldraw's canvas and shapes did not render again, so its own memoization holds. Dev server: up to 52% busy and 70 ms per key. Production build: 1 ms more script per key. Separately, Chrome's layer update (`PaintArtifactCompositor::Update`) took 129 ms over the 120 keys with the board and 73 ms without, because the board's layers are rebuilt on every repaint. Memoizing does not change that part.
- **Fix:** Memoize `PinnedWhiteboard` and the inner `Whiteboard`. Give them steady handlers: a `useCallback` for the pinned `onAsk` in `ChatShell`, and a steady `askAbout` from `App`, as `useSteady` does in `Conversation`. Move the `shapeUtils` array to the module, wrap `onMount` in `useCallback`, and memoize the caption. Item 14 stops this for typing, but a streamed reply still renders `App` on every chunk. While a reply streams onto the pinned board, `pinnedTurn` changes on every chunk, but the `shown` board changes only when a step appears, so a memoized `Whiteboard` would skip the rest.
- **Done:** `PinnedWhiteboard`, the lazy `Whiteboard` in `web/src/whiteboard/LazyWhiteboard.tsx`, and the inner `Whiteboard` are memoized. `ChatShell` gives the pinned board a steady `onAsk`, `App` gives it steady `onClose` and `onPicture`, and `pinnedTurn` is memoized on the pending turn. `onDrawingChange` from `useBoardSaving` keeps one identity. `Whiteboard` has a module-level `shapeUtils`, an `onMount` in `useCallback`, and a memoized caption. With a board pinned, a key also renders 5 components, instead of 257. The main thread spends about 7 ms per key, against about 4 ms without the board. That difference is Chrome's layer update, which memoizing does not change. The streaming case is read from the code, not measured.

## 16. The shell around the conversation is not memoized

- **Where:** `ChatShell`, `SessionPanel`, `TopBar`, and `ToolsPanel` in `web/src/chat/`. `App` passes about 25 new arrow functions to `ChatShell` on every render, and `ChatShell` builds `toolsProps` with new functions too.
- **Cost:** Any change to `App`'s state draws the whole shell again. For typing, that is the 177 components in item 14. While a reply streams, `App` changes on every chunk, so the session list, dialogs, and tools panel render again on every chunk too. Item 2 fixed this for the turns, not for the shell. The streaming case is read from the code, not measured.
- **Fix:** Memoize `SessionPanel` and its rows, `TopBar`, and `ToolsPanel`, and give them steady handlers. A memoized session row keeps its menu and icon from rendering again. Do it after item 14, which removes the biggest trigger.
- **Done:** `SessionPanel`, a new memoized `SessionRow`, `TopBar`, and `ToolsPanel` are memoized. `App` passes `ChatShell` its handlers through `useSteadyHandlers` in `web/src/useSteady.ts`, which keeps each one's identity and calls the latest. `useSteady` moved to the same file. `ChatShell` keeps its own handlers steady too, and its default lists are constants. The artifacts list passed to the tools panel now changes only when a turn that is not streaming changes, not on every chunk. Toggling the tools panel renders about 25 components, and none of them is a session row. A new test in `web/src/useSteady.test.ts` checks the handlers. The streaming case is read from the code, not measured.

## 17. Each typed key forces a layout to size the message box

- **Where:** the `draft` effect in `Conversation` in `web/src/chat/Conversation.tsx`. It sets the height to `auto`, then reads `scrollHeight`.
- **Cost:** Reading `scrollHeight` right after the change makes the browser lay out the page there and then. Each key caused 3 layouts (364 for 120 keys). The read was the largest single built-in call in the production profile, 0.33 ms per key. Small.
- **Fix:** Use CSS `field-sizing: content` with a `max-height` where the browser supports it, and keep the effect as a fallback only. Low priority.
- **Done:** `.chat-input textarea` in `web/src/index.css` has `field-sizing: content`, and keeps its six-line `max-height`. The effect in `Composer` runs only when `CSS.supports('field-sizing', 'content')` is false. Chromium now does 1 layout per key instead of 3.

## 18. The phone check makes a new media query on every render

- **Where:** `useMediaQuery` in `web/src/chat/ChatShell.tsx`. Its snapshot calls `window.matchMedia(query)` each time, and `useSyncExternalStore` reads the snapshot on every render.
- **Cost:** About 0.08 ms per render in the production build (9.5 ms over 121 renders). Small, and it goes with item 14.
- **Fix:** Make the `MediaQueryList` once per query and read `.matches` from it.
- **Done:** in `useMediaQuery`, once per query for each mounted shell, so a test that changes `matchMedia` still gets a new one on its next mount.
