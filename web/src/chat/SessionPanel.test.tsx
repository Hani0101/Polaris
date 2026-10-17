import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { ApiError } from '../api.ts'
import type { SessionSummary } from '../api.ts'
import { SessionPanel } from './SessionPanel.tsx'

afterEach(() => {
  cleanup()
})

const unnamed: SessionSummary = { id: 'a', ended: false, name: '', preview: 'What is a fraction?' }
const named: SessionSummary = { id: 'b', ended: true, name: 'Fractions', preview: 'Older' }

function panel(onRename: (id: string, name: string) => Promise<void>, sessions = [unnamed, named]) {
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
