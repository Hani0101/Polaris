import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { ApiError } from '../api.ts'
import type { SessionSummary } from '../api.ts'
import { SessionPanel } from './SessionPanel.tsx'

afterEach(() => {
  cleanup()
})

const unnamed: SessionSummary = { id: 'a', ended: false, name: '', title: '', preview: 'What is a fraction?' }
const named: SessionSummary = { id: 'b', ended: true, name: 'Fractions', title: '', preview: 'Older' }

function panel(
  onRename: (id: string, name: string) => Promise<void>,
  sessions = [unnamed, named],
  onDelete: (id: string) => Promise<void> = async () => {},
) {
  return render(
    <SessionPanel
      sessions={sessions}
      openId="a"
      loading={false}
      open
      onClose={() => {}}
      onStart={() => {}}
      onOpen={() => {}}
      onRename={onRename}
      onDelete={onDelete}
      onOpenSettings={() => {}}
    />,
  )
}

async function openRename(label: string) {
  fireEvent.click(screen.getByRole('button', { name: `Actions for ${label}` }))
  fireEvent.click(await screen.findByRole('menuitem', { name: 'Rename' }))
  return screen.findByRole('dialog', { name: 'Rename session' })
}

test('a session shows its name, else its first message', () => {
  panel(async () => {})

  expect(screen.getByText('Fractions')).toBeTruthy()
  expect(screen.getByText('What is a fraction?')).toBeTruthy()
})

test('rename starts from the current name and saves what was typed', async () => {
  const onRename = vi.fn(async () => {})
  panel(onRename)

  await openRename('Fractions')
  const input = screen.getByLabelText('Session name') as HTMLInputElement
  expect(input.value).toBe('Fractions')
  fireEvent.change(input, { target: { value: 'Ratios' } })
  fireEvent.click(screen.getByRole('button', { name: 'Rename' }))

  await waitFor(() => expect(onRename).toHaveBeenCalledWith('b', 'Ratios'))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

test('Enter saves and an unnamed session starts blank', async () => {
  const onRename = vi.fn(async () => {})
  panel(onRename)

  await openRename('What is a fraction?')
  const input = screen.getByLabelText('Session name') as HTMLInputElement
  expect(input.value).toBe('')
  fireEvent.change(input, { target: { value: 'Fractions' } })
  fireEvent.keyDown(input, { key: 'Enter' })

  await waitFor(() => expect(onRename).toHaveBeenCalledWith('a', 'Fractions'))
})

test('cancel changes nothing', async () => {
  const onRename = vi.fn(async () => {})
  panel(onRename)

  await openRename('Fractions')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(onRename).not.toHaveBeenCalled()
})

test('a failed save keeps the dialog open and says why', async () => {
  const onRename = vi.fn(async () => {
    throw new ApiError(422, 'A session name can be at most 80 characters.')
  })
  panel(onRename)

  await openRename('Fractions')
  fireEvent.click(screen.getByRole('button', { name: 'Rename' }))

  expect((await screen.findByRole('alert')).textContent).toContain('at most 80 characters')
  expect(screen.getByRole('dialog', { name: 'Rename session' })).toBeTruthy()
})

async function openDelete(label: string) {
  fireEvent.click(screen.getByRole('button', { name: `Actions for ${label}` }))
  fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete' }))
  return screen.findByRole('alertdialog', { name: 'Delete this session?' })
}

test('delete asks first, names the session, and says the profile keeps its facts', async () => {
  const onDelete = vi.fn(async () => {})
  panel(async () => {}, [unnamed, named], onDelete)

  const dialog = await openDelete('Fractions')

  expect(dialog.textContent).toContain('Fractions')
  expect(dialog.textContent).toContain('can’t be undone')
  expect(dialog.textContent).toContain('stays in your profile')
  expect(onDelete).not.toHaveBeenCalled()
})

test('confirming deletes that session', async () => {
  const onDelete = vi.fn(async () => {})
  panel(async () => {}, [unnamed, named], onDelete)

  await openDelete('Fractions')
  fireEvent.click(screen.getByRole('button', { name: 'Delete session' }))

  await waitFor(() => expect(onDelete).toHaveBeenCalledWith('b'))
  await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
})

test('cancelling a delete changes nothing', async () => {
  const onDelete = vi.fn(async () => {})
  panel(async () => {}, [unnamed, named], onDelete)

  await openDelete('Fractions')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

  await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
  expect(onDelete).not.toHaveBeenCalled()
})

test('a failed delete keeps the dialog open and says so', async () => {
  const onDelete = vi.fn(async () => {
    throw new Error('network')
  })
  panel(async () => {}, [unnamed, named], onDelete)

  await openDelete('Fractions')
  fireEvent.click(screen.getByRole('button', { name: 'Delete session' }))

  expect((await screen.findByRole('alert')).textContent).toContain("Couldn't delete the session")
  expect(screen.getByRole('alertdialog', { name: 'Delete this session?' })).toBeTruthy()
})
