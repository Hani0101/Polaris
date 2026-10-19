import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { ProfileFact } from './api.ts'
import { ProfileDialog } from './ProfileDialog.tsx'

const { account, listFacts, addFact, editFact, removeFact } = vi.hoisted(() => ({
  account: { current: { status: 'signed-in', username: 'learner' } as { status: string } },
  listFacts: vi.fn<() => Promise<ProfileFact[]>>(),
  addFact: vi.fn<(text: string) => Promise<{ fact: ProfileFact; facts: ProfileFact[] }>>(),
  editFact:
    vi.fn<(id: string, text: string) => Promise<{ fact: ProfileFact; facts: ProfileFact[] }>>(),
  removeFact: vi.fn<(id: string) => Promise<{ facts: ProfileFact[] }>>(),
}))

vi.mock('./auth.ts', () => ({ useSignIn: () => account.current }))
vi.mock('./api.ts', () => ({ listFacts, addFact, editFact, removeFact, MAX_FACT_LENGTH: 300 }))

function fact(id: string, kind: ProfileFact['kind'], text: string): ProfileFact {
  return { id, kind, text, written_by: 'pass' }
}

const STRUGGLE = fact('f1', 'struggle', 'struggles with fractions')
const TAUGHT = fact('f2', 'taught', 'likes worked examples')

beforeEach(() => {
  account.current = { status: 'signed-in', username: 'learner' } as { status: string }
  listFacts.mockResolvedValue([TAUGHT, STRUGGLE])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('the facts are bullet points under the kind they belong to [PR-11]', async () => {
  render(<ProfileDialog open onClose={() => {}} onSignIn={() => {}} />)

  const taught = await screen.findByRole('region', { name: 'How you like to be taught' })
  expect(within(taught).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    'likes worked examples',
  ])
  const struggle = screen.getByRole('region', { name: 'Where you find it hard' })
  expect(within(struggle).getByText('struggles with fractions')).toBeTruthy()
  expect(screen.queryByRole('region', { name: 'Other things' })).toBeNull()
})

test('a signed-out learner is asked to sign in and nothing is fetched [PR-11, AU-12]', () => {
  account.current = { status: 'anonymous' }
  const onSignIn = vi.fn()
  render(<ProfileDialog open onClose={() => {}} onSignIn={onSignIn} />)

  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(onSignIn).toHaveBeenCalled()
  expect(listFacts).not.toHaveBeenCalled()
})

test('an empty profile says how it fills [PR-11]', async () => {
  listFacts.mockResolvedValue([])
  render(<ProfileDialog open onClose={() => {}} onSignIn={() => {}} />)

  expect(await screen.findByText('Nothing on your profile yet')).toBeTruthy()
  expect(screen.getByLabelText('Add something Polaris should know')).toBeTruthy()
})

test('changing a fact saves the new wording and returns focus to it [PR-11]', async () => {
  const changed = { ...STRUGGLE, id: 'f3', text: 'finds fractions hard', written_by: 'learner' as const }
  editFact.mockResolvedValue({ fact: changed, facts: [TAUGHT, changed] })
  render(<ProfileDialog open onClose={() => {}} onSignIn={() => {}} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Change “struggles with fractions”' }))
  const input = screen.getByLabelText('Change this')
  fireEvent.change(input, { target: { value: 'finds fractions hard' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save change' }))

  expect(await screen.findByText('finds fractions hard')).toBeTruthy()
  expect(editFact).toHaveBeenCalledWith('f1', 'finds fractions hard')
  expect(screen.queryByText('struggles with fractions')).toBeNull()
  await waitFor(() =>
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: 'Change “finds fractions hard”' }),
    ),
  )
  expect(screen.getByRole('status').textContent).toBe(
    'Saved. Polaris uses this from your next message.',
  )
})

test('Escape cancels a change without saving [PR-11]', async () => {
  render(<ProfileDialog open onClose={() => {}} onSignIn={() => {}} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Change “likes worked examples”' }))
  const input = screen.getByLabelText('Change this')
  fireEvent.change(input, { target: { value: 'something else' } })
  fireEvent.keyDown(input, { key: 'Escape' })

  expect(screen.getByText('likes worked examples')).toBeTruthy()
  expect(editFact).not.toHaveBeenCalled()
})

test('removing a fact asks first [PR-11]', async () => {
  removeFact.mockResolvedValue({ facts: [TAUGHT] })
  render(<ProfileDialog open onClose={() => {}} onSignIn={() => {}} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Remove “struggles with fractions”' }))
  const dialog = screen.getByRole('alertdialog', { name: 'Remove this from your profile?' })
  // The confirm opens over the Profile dialog and holds focus.
  await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))
  expect(removeFact).not.toHaveBeenCalled()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Remove from profile' }))

  await waitFor(() => expect(screen.queryByText('struggles with fractions')).toBeNull())
  expect(removeFact).toHaveBeenCalledWith('f1')
  await waitFor(() =>
    expect(document.activeElement).toBe(screen.getByLabelText('Add something Polaris should know')),
  )
})

test('adding a fact shows it, and a refused one shows why [PR-11]', async () => {
  const added = fact('f4', 'unsorted', 'learns from diagrams')
  addFact
    .mockRejectedValueOnce(new Error('Your profile already says this.'))
    .mockResolvedValueOnce({ fact: added, facts: [TAUGHT, STRUGGLE, added] })
  render(<ProfileDialog open onClose={() => {}} onSignIn={() => {}} />)

  const input = await screen.findByLabelText('Add something Polaris should know')
  fireEvent.click(screen.getByRole('button', { name: 'Add to profile' }))
  expect(screen.getByText('Type something to add.')).toBeTruthy()
  expect(addFact).not.toHaveBeenCalled()

  fireEvent.change(input, { target: { value: 'likes worked examples' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add to profile' }))
  expect(await screen.findByText('Your profile already says this.')).toBeTruthy()

  fireEvent.change(input, { target: { value: 'learns from diagrams' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add to profile' }))
  const other = await screen.findByRole('region', { name: 'Other things' })
  expect(within(other).getByText('learns from diagrams')).toBeTruthy()
  expect((input as HTMLInputElement).value).toBe('')
})

test('a profile that cannot load offers Try again [PR-11]', async () => {
  listFacts.mockRejectedValueOnce(new Error("Couldn't load your profile.")).mockResolvedValue([])
  render(<ProfileDialog open onClose={() => {}} onSignIn={() => {}} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('Nothing on your profile yet')).toBeTruthy()
  expect(listFacts).toHaveBeenCalledTimes(2)
})
