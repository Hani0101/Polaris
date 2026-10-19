import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, expect, test, vi } from 'vitest'
import type { WhiteboardArtifact } from '../api.ts'
import { readableDescription } from '../whiteboard/description.ts'
import { prefetchWhiteboard } from '../whiteboard/LazyWhiteboard.tsx'
import { revealWhiteboard } from '../whiteboard/reveal.ts'
import { sampleWhiteboard } from '../whiteboard/sampleWhiteboard.ts'
import { Conversation } from './Conversation.tsx'
import { createDraft } from './draft.ts'

// The board code loads on first use. Loading it first keeps each test's wait short.
beforeAll(() => prefetchWhiteboard(), 60_000)

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const noop = () => {}

test('the composer is named and Send stays off while empty', () => {
  render(
    <Conversation
      turns={[]}
      draft={createDraft()}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
    />,
  )
  expect(screen.getByLabelText('Message to Polaris')).toBeTruthy()
  expect((screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement).disabled).toBe(true)
})

test('Send becomes Stop while the reply is being produced', () => {
  render(
    <Conversation
      turns={[
        {
          key: 'pending',
          learner: 'What is a vertex?',
          reply: '',
          artifacts: [],
          streaming: true,
          failed: false,
        },
      ]}
      draft={createDraft('follow up')}
      sending
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
    />,
  )
  expect(screen.getByText('Thinking')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Stop' })).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Send' })).toBeNull()
})

test('a turn shows a whiteboard', async () => {
  const whiteboard: WhiteboardArtifact = { ...sampleWhiteboard, kind: 'whiteboard' }
  render(
    <Conversation
      turns={[
        {
          key: 'saved-0',
          learner: 'Explain fractions with a drawing.',
          reply: 'A fraction is one part of a whole.',
          artifacts: [whiteboard],
          streaming: false,
          failed: false,
        },
      ]}
      draft={createDraft()}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
    />,
  )
  expect(await screen.findByRole('region', { name: readableDescription(whiteboard) })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Open whiteboard' })).toBeTruthy()
  expect(screen.getByText('A fraction is one part of a whole.')).toBeTruthy()
})

test('a turn opens its whiteboard on its own', async () => {
  const whiteboard: WhiteboardArtifact = { ...sampleWhiteboard, kind: 'whiteboard' }
  const onOpenWhiteboard = vi.fn()
  render(
    <Conversation
      turns={[
        {
          key: 'saved-0',
          learner: 'Explain fractions with a drawing.',
          reply: 'A fraction is one part of a whole.',
          artifacts: [whiteboard],
          streaming: false,
          failed: false,
        },
      ]}
      draft={createDraft()}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={onOpenWhiteboard}
      onStart={noop}
    />,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Open whiteboard' }))
  expect(onOpenWhiteboard).toHaveBeenCalledWith(whiteboard.id)
})

test('Simpler sends that whiteboard without a typed message', async () => {
  const whiteboard: WhiteboardArtifact = { ...sampleWhiteboard, kind: 'whiteboard' }
  const onSimpler = vi.fn()
  render(
    <Conversation
      turns={[
        {
          key: 'saved-0',
          learner: 'Explain fractions with a drawing.',
          reply: 'A fraction is one part of a whole.',
          artifacts: [whiteboard],
          streaming: false,
          failed: false,
        },
      ]}
      draft={createDraft()}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onSimpler={onSimpler}
      onStart={noop}
    />,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Simpler' }))
  expect(onSimpler).toHaveBeenCalledWith(whiteboard.id)
})

test('a simpler whiteboard links to the original', async () => {
  const whiteboard: WhiteboardArtifact = {
    ...sampleWhiteboard,
    kind: 'whiteboard',
    id: 'wb-simple',
    version: 4,
    description: 'One box stands for the whole.',
    simplifies: 'wb-1',
  }
  render(
    <Conversation
      turns={[
        {
          key: 'saved-1',
          learner: 'Draw a simpler version of this whiteboard.',
          reply: 'Here is a simpler drawing.',
          artifacts: [whiteboard],
          streaming: false,
          failed: false,
        },
      ]}
      draft={createDraft()}
      sending={false}
      sendError={null}
      sessionOpen
      sessionId="session-1"
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onSimpler={noop}
      onStart={noop}
    />,
  )
  const link = await screen.findByRole('link', { name: 'Original whiteboard' })
  expect(link.getAttribute('href')).toBe('/whiteboard/session-1/wb-1')
})

const stepped: WhiteboardArtifact = {
  ...sampleWhiteboard,
  kind: 'whiteboard',
  comments: [
    { id: 'c-whole', author: 'agent', text: 'the whole', element_id: 'rect-1' },
    { id: 'c-part', author: 'agent', text: 'the part', element_id: 'rect-2' },
    { id: 'c-here', author: 'agent', text: 'over here', position: { x: 4, y: 8 } },
  ],
}

function renderStepped(turn: {
  reply: string
  streaming: boolean
  stopped?: boolean
}) {
  render(
    <Conversation
      turns={[
        {
          key: 'pending',
          learner: 'Explain fractions with a drawing.',
          reply: turn.reply,
          artifacts: [stepped],
          streaming: turn.streaming,
          stopped: turn.stopped,
          failed: false,
        },
      ]}
      draft={createDraft()}
      sending={turn.streaming}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
    />,
  )
}

test('steps follow the text', async () => {
  // Scenario: steps follow the text [WB-06]
  renderStepped({ reply: '', streaming: true })
  expect(screen.queryByRole('region', { name: readableDescription(stepped) })).toBeNull()

  cleanup()
  renderStepped({ reply: '[[step:ste', streaming: true })
  expect(screen.queryByRole('region', { name: readableDescription(stepped) })).toBeNull()
  expect(screen.queryByText(/\[\[step:/)).toBeNull()

  cleanup()
  const firstReply = '[[step:step-1]] The left box is the whole.'
  renderStepped({
    reply: firstReply,
    streaming: true,
  })
  const revealed = revealWhiteboard(stepped, firstReply, 'streaming')
  expect(
    await screen.findByRole('region', { name: readableDescription(revealed ?? stepped) }),
  ).toBeTruthy()
  expect(screen.getByText('The left box is the whole.')).toBeTruthy()
  expect(screen.getByText('the whole')).toBeTruthy()
  expect(screen.getByText('over here')).toBeTruthy()
  expect(screen.queryByText('the part')).toBeNull()
  expect(screen.queryByText(/\[\[step:/)).toBeNull()

  cleanup()
  renderStepped({
    reply: '[[step:step-1]] The left box is the whole. [[step:step-2]] The right box is one part.',
    streaming: true,
  })
  expect(await screen.findByText('the part')).toBeTruthy()
  expect(screen.getByText('The left box is the whole. The right box is one part.')).toBeTruthy()
})

test('a stopped turn keeps later steps hidden', async () => {
  renderStepped({
    reply: '[[step:step-1]] The left box is the whole.',
    streaming: false,
    stopped: true,
  })
  expect(await screen.findByText('the whole')).toBeTruthy()
  expect(screen.queryByText('the part')).toBeNull()
})

test('the composer shows pointed-at chips and can remove one', () => {
  const onRemovePoint = vi.fn()
  render(
    <Conversation
      turns={[]}
      draft={createDraft('What is this part?')}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
      pointing={{
        whiteboardId: 'wb-1',
        parts: [
          { id: 'text-1', label: 'half' },
          { id: 'rect-1', label: 'rectangle' },
        ],
      }}
      onRemovePoint={onRemovePoint}
    />,
  )

  expect(screen.getByText('half')).toBeTruthy()
  expect(screen.getByText('rectangle')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Remove half' }))
  expect(onRemovePoint).toHaveBeenCalledWith('text-1')
})

test('a sent turn shows the pointed-at chip', () => {
  render(
    <Conversation
      turns={[
        {
          key: 'saved-0',
          learner: 'What is this part?',
          reply: 'The left box is the whole.',
          artifacts: [],
          streaming: false,
          failed: false,
          pointing: {
            whiteboardId: 'wb-1',
            parts: [{ id: 'rect-1', label: 'rectangle' }],
          },
        },
      ]}
      draft={createDraft()}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
    />,
  )

  expect(screen.getByRole('list', { name: 'Pointed at' }).textContent).toContain('rectangle')
  expect(screen.queryByRole('button', { name: 'Remove rectangle' })).toBeNull()
})

test('a finished turn shows every step', async () => {
  renderStepped({
    reply: 'The reply ended without a marker.',
    streaming: false,
  })
  expect(await screen.findByText('the whole')).toBeTruthy()
  expect(screen.getByText('the part')).toBeTruthy()
  expect(screen.getByText('over here')).toBeTruthy()
})

test('a screen reader reads the drawing', async () => {
  // Scenario: a screen reader reads the drawing [WB-10]
  const description = 'Two boxes show one half of a whole.'
  const board: WhiteboardArtifact = {
    version: 4,
    id: 'wb-read',
    session_id: 'session-1',
    kind: 'whiteboard',
    description,
    comments: [],
    steps: [
      {
        id: 'step-1',
        reply_part: '[[step:step-1]]',
        elements: [sampleWhiteboard.steps[0].elements[0]],
      },
    ],
  }

  function show(reply: string, streaming: boolean) {
    render(
      <Conversation
        turns={[
          {
            key: 'pending',
            learner: 'Explain fractions with a drawing.',
            reply,
            artifacts: [board],
            streaming,
            failed: false,
          },
        ]}
        draft={createDraft()}
        sending={streaming}
        sendError={null}
        sessionOpen
        onDraftChange={noop}
        onSend={noop}
        onStop={noop}
        onCopy={noop}
        onTryAgain={noop}
        onOpenQuiz={noop}
        onOpenWhiteboard={noop}
        onStart={noop}
      />,
    )
  }

  show('', true)
  expect(screen.queryByRole('region', { name: description })).toBeNull()
  expect(screen.queryByText(description)).toBeNull()

  cleanup()
  show('[[step:step-1]] The left box is the whole.', true)
  const region = await screen.findByRole('region', { name: description })
  const caption = screen.getByText(description)
  expect(region.getAttribute('aria-labelledby')).toBe(caption.id)
  expect(caption.classList.contains('visually-hidden')).toBe(false)
})

test('the composer shows an attached picture of the drawing and can remove it', () => {
  const onRemovePicture = vi.fn()
  render(
    <Conversation
      turns={[]}
      draft={createDraft('Is my sketch right?')}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
      pictureAttached
      onRemovePicture={onRemovePicture}
    />,
  )

  const list = screen.getByRole('list', { name: 'Sent with your message' })
  expect(list.textContent).toContain('Picture of your drawing')
  fireEvent.click(screen.getByRole('button', { name: 'Remove picture of your drawing' }))
  expect(onRemovePicture).toHaveBeenCalledTimes(1)
})

test('the composer shows the animation step being asked about and can remove it (AN-17)', () => {
  const onRemoveAnimationStep = vi.fn()
  render(
    <Conversation
      turns={[]}
      draft={createDraft('Why the left half?')}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
      animationStep={{
        jobId: 'job-1',
        stepId: 'discard',
        stepNumber: 2,
        caption: '23 is bigger than 17, so the left half cannot hold it.',
      }}
      onRemoveAnimationStep={onRemoveAnimationStep}
    />,
  )

  expect(screen.getByRole('list', { name: 'Animation step' }).textContent).toContain(
    'Asking about step 2: 23 is bigger than 17, so the left half cannot hold it.',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Remove step 2' }))
  expect(onRemoveAnimationStep).toHaveBeenCalled()
})

test('a sent turn shows the animation step it asked about', () => {
  render(
    <Conversation
      turns={[
        {
          key: 'saved-0',
          learner: 'Why the left half?',
          reply: 'Every number there is smaller than 17.',
          artifacts: [],
          streaming: false,
          failed: false,
          animationStep: { jobId: 'job-1', stepId: 'discard' },
        },
      ]}
      draft={createDraft()}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
    />,
  )

  expect(screen.getByRole('list', { name: 'Animation step' }).textContent).toBe(
    'Asking about a step of an animation',
  )
  expect(screen.queryByRole('button', { name: /Remove/ })).toBeNull()
})

function savedTurn(reply: string, artifacts: WhiteboardArtifact[] = []) {
  return {
    key: 'saved-0',
    learner: 'Explain fractions with a drawing.',
    reply,
    artifacts,
    streaming: false,
    failed: false,
  }
}

function conversationWith(turns: ReturnType<typeof savedTurn>[], sending = false) {
  return (
    <Conversation
      turns={turns}
      draft={createDraft()}
      sending={sending}
      sendError={null}
      sessionOpen
      onDraftChange={noop}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
      sessionId="session-1"
    />
  )
}

test('a board in a turn has an editor only while it is near the screen', async () => {
  const observers: { report: (near: boolean) => void }[] = []
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
        observers.push({ report: (near) => callback([{ isIntersecting: near }]) })
      }
      observe() {}
      disconnect() {}
    },
  )
  const whiteboard: WhiteboardArtifact = { ...sampleWhiteboard, kind: 'whiteboard' }
  const { container } = render(conversationWith([savedTurn('A fraction is one part.', [whiteboard])]))
  const name = readableDescription(whiteboard)
  // Off screen: the board's description, and no editor.
  expect(screen.getByRole('region', { name })).toBeTruthy()
  expect(container.querySelector('.tl-container')).toBeNull()

  act(() => observers.at(-1)?.report(true))
  await waitFor(() => {
    expect(screen.getByRole('region', { name }).getAttribute('data-ready')).toBe('true')
  })

  act(() => observers.at(-1)?.report(false))
  expect(container.querySelector('.tl-container')).toBeNull()
  expect(screen.getByRole('region', { name })).toBeTruthy()
})

test('the view follows a reply only while the learner is at the bottom', () => {
  const { container, rerender } = render(conversationWith([savedTurn('One.')]))
  const scroller = container.querySelector('.conversation-scroll') as HTMLElement
  let top = 0
  Object.defineProperty(scroller, 'scrollHeight', { configurable: true, get: () => 1000 })
  Object.defineProperty(scroller, 'clientHeight', { configurable: true, get: () => 400 })
  Object.defineProperty(scroller, 'scrollTop', {
    configurable: true,
    get: () => top,
    set: (value: number) => {
      top = value
    },
  })
  function scrollTo(value: number) {
    top = value
    fireEvent.scroll(scroller)
  }

  // Reading an earlier turn: a longer reply does not pull the learner down.
  scrollTo(100)
  rerender(conversationWith([savedTurn('One. Two.')]))
  expect(top).toBe(100)

  // Back at the bottom, the view follows again.
  scrollTo(600)
  rerender(conversationWith([savedTurn('One. Two. Three.')]))
  expect(top).toBe(1000)

  // Sending goes back to the bottom from anywhere.
  scrollTo(100)
  rerender(conversationWith([savedTurn('One. Two. Three.')], true))
  expect(top).toBe(1000)
})

test('the composer keeps the typed text in the draft, and the app can clear and restore it', () => {
  const draft = createDraft()
  const typed: string[] = []
  render(
    <Conversation
      turns={[]}
      draft={draft}
      sending={false}
      sendError={null}
      sessionOpen
      onDraftChange={(value) => typed.push(value)}
      onSend={noop}
      onStop={noop}
      onCopy={noop}
      onTryAgain={noop}
      onOpenQuiz={noop}
      onOpenWhiteboard={noop}
      onStart={noop}
    />,
  )
  const box = screen.getByLabelText('Message to Polaris') as HTMLTextAreaElement
  const send = () => screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement

  // Typing shows in the box with no new props, so the app around it is not drawn again.
  fireEvent.change(box, { target: { value: 'What is a vertex?' } })
  expect(box.value).toBe('What is a vertex?')
  expect(draft.get()).toBe('What is a vertex?')
  expect(typed).toEqual(['What is a vertex?'])
  expect(send().disabled).toBe(false)

  // Sending clears it, and a failed send puts it back.
  act(() => draft.set(''))
  expect(box.value).toBe('')
  expect(send().disabled).toBe(true)
  act(() => draft.set('What is a vertex?'))
  expect(box.value).toBe('What is a vertex?')
})

test('web mode is a pressed toggle with a chip that names it (CH-23, CH-28)', () => {
  const onToggleWeb = vi.fn()
  const props = {
    turns: [],
    draft: createDraft(''),
    sending: false,
    sendError: null,
    sessionOpen: true,
    onDraftChange: noop,
    onSend: noop,
    onStop: noop,
    onCopy: noop,
    onTryAgain: noop,
    onOpenQuiz: noop,
    onOpenWhiteboard: noop,
    onStart: noop,
    onToggleWeb,
  }
  const { rerender } = render(<Conversation {...props} webMode={false} />)

  const toggle = screen.getByRole('button', { name: 'Web mode' })
  expect(toggle.getAttribute('aria-pressed')).toBe('false')
  expect(screen.queryByRole('list', { name: 'Web mode' })).toBeNull()
  fireEvent.click(toggle)
  expect(onToggleWeb).toHaveBeenCalledTimes(1)

  rerender(<Conversation {...props} webMode />)
  expect(screen.getByRole('button', { name: 'Web mode' }).getAttribute('aria-pressed')).toBe('true')
  expect(screen.getByRole('list', { name: 'Web mode' }).textContent).toContain('Polaris can search the web')
  fireEvent.click(screen.getByRole('button', { name: 'Turn off web mode' }))
  expect(onToggleWeb).toHaveBeenCalledTimes(2)
})
