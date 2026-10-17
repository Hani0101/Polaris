import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { SettingsPage } from './SettingsPage.tsx'
import { MODE_KEY, setMode } from './theme.ts'

beforeEach(() => {
  window.localStorage.clear()
  setMode('system')
})

afterEach(() => {
  cleanup()
})

test('Appearance offers System, Light, and Dark with one chosen [ST-02, ST-04]', () => {
  render(<SettingsPage onBack={() => {}} />)

  const group = screen.getByRole('group', { name: 'Colors' })
  expect(group).toBeTruthy()
  const radios = screen.getAllByRole('radio') as HTMLInputElement[]
  expect(radios.map((radio) => radio.value)).toEqual(['system', 'light', 'dark'])
  expect(radios.filter((radio) => radio.checked).map((radio) => radio.value)).toEqual(['system'])
  expect(screen.getByText('Follows your device')).toBeTruthy()
})

test('choosing a mode applies it and keeps it [ST-05]', () => {
  render(<SettingsPage onBack={() => {}} />)

  fireEvent.click(screen.getByRole('radio', { name: /^Dark/ }))

  expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  expect(window.localStorage.getItem(MODE_KEY)).toBe('dark')
  expect((screen.getByRole('radio', { name: /^Dark/ }) as HTMLInputElement).checked).toBe(true)
})

test('Back returns to the conversation [ST-01]', () => {
  const onBack = vi.fn()
  render(<SettingsPage onBack={onBack} />)

  fireEvent.click(screen.getByRole('button', { name: /Back to the conversation/ }))

  expect(onBack).toHaveBeenCalled()
})
