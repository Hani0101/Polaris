import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { Modal } from './Modal.tsx'

afterEach(() => {
  cleanup()
})

function Harness({ onMain = () => {} }: { onMain?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Delete session
      </button>
      <Modal
        open={open}
        variant="confirm"
        title="Delete this session?"
        mainLabel="Delete session"
        onMain={() => {
          onMain()
          setOpen(false)
        }}
        onCancel={() => setOpen(false)}
      >
        <p>This can't be undone.</p>
      </Modal>
    </>
  )
}

async function openDialog() {
  const opener = screen.getByRole('button', { name: 'Delete session' })
  opener.focus()
  fireEvent.click(opener)
  const dialog = await screen.findByRole('alertdialog', { name: 'Delete this session?' })
  return { opener, dialog }
}

test('focus moves into the dialog and Escape cancels back to the opener', async () => {
  const onMain = vi.fn()
  render(<Harness onMain={onMain} />)
  const { opener, dialog } = await openDialog()
  expect(dialog.getAttribute('aria-modal')).toBe('true')
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' }))

  fireEvent.keyDown(document.activeElement ?? dialog, { key: 'Escape' })
  await waitFor(() => {
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })
  expect(document.activeElement).toBe(opener)
  expect(onMain).not.toHaveBeenCalled()
})

test('focus is trapped inside the dialog', async () => {
  render(<Harness />)
  const { dialog } = await openDialog()
  const close = screen.getByRole('button', { name: 'Close' })
  const main = [...dialog.querySelectorAll('button')].at(-1)
  if (!main) throw new Error('No main button.')
  expect(main.textContent).toBe('Delete session')
  expect(main.classList.contains('destructive')).toBe(true)

  main.focus()
  fireEvent.keyDown(main, { key: 'Tab' })
  expect(document.activeElement).toBe(close)

  fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
  expect(document.activeElement).toBe(main)
})

test('the close button and the dim layer cancel, the main button confirms', async () => {
  const onMain = vi.fn()
  render(<Harness onMain={onMain} />)

  await openDialog()
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  await waitFor(() => {
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  await openDialog()
  const dim = document.querySelector('.modal-dim')
  if (!dim) throw new Error('No dim layer.')
  fireEvent.click(dim)
  await waitFor(() => {
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })
  expect(onMain).not.toHaveBeenCalled()

  const { dialog, opener } = await openDialog()
  const main = [...dialog.querySelectorAll('button')].at(-1)
  if (!main) throw new Error('No main button.')
  fireEvent.click(main)
  expect(onMain).toHaveBeenCalledTimes(1)
  await waitFor(() => {
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })
  expect(document.activeElement).toBe(opener)
})
