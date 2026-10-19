import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { AppearanceDialog } from './AppearanceDialog.tsx'
import { MODE_KEY, setMode } from './theme.ts'

beforeEach(() => {
  window.localStorage.clear()
  setMode('system')
})

afterEach(() => {
  cleanup()
})

test('Appearance offers System, Light, and Dark with one chosen [ST-02, ST-04]', () => {
  render(<AppearanceDialog open onClose={() => {}} />)

  expect(screen.getByRole('dialog', { name: 'Appearance' })).toBeTruthy()
  expect(screen.getByRole('group', { name: 'Colors' })).toBeTruthy()
  const radios = screen.getAllByRole('radio') as HTMLInputElement[]
  expect(radios.map((radio) => radio.value)).toEqual(['system', 'light', 'dark'])
  expect(radios.filter((radio) => radio.checked).map((radio) => radio.value)).toEqual(['system'])
  expect(screen.getByText('Follows your device')).toBeTruthy()
})

test('choosing a mode applies it and keeps it [ST-05]', () => {
  render(<AppearanceDialog open onClose={() => {}} />)

  fireEvent.click(screen.getByRole('radio', { name: /^Dark/ }))

  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(window.localStorage.getItem(MODE_KEY)).toBe('dark')
  expect((screen.getByRole('radio', { name: /^Dark/ }) as HTMLInputElement).checked).toBe(true)
})

test('the dialog has only a Close button, since the choice already applied [ST-01]', () => {
  const onClose = vi.fn()
  render(<AppearanceDialog open onClose={onClose} />)

  const buttons = screen.getAllByRole('button').map((button) => button.textContent)
  expect(buttons.filter((text) => text)).toEqual(['Close'])
  fireEvent.click(screen.getByText('Close'))

  expect(onClose).toHaveBeenCalled()
})
