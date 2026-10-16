import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { DropdownMenu, type MenuItem } from './Menu.tsx'

afterEach(() => {
  cleanup()
})

function items(onSelect: (id: string) => void): MenuItem[] {
  return [
    {
      id: 'delete',
      label: 'Delete session',
      icon: <span aria-hidden="true">x</span>,
      destructive: true,
      onSelect: () => onSelect('delete'),
    },
    { id: 'rename', label: 'Rename', onSelect: () => onSelect('rename') },
    { id: 'copy', label: 'Copy link', onSelect: () => onSelect('copy') },
  ]
}

async function openMenu() {
  const trigger = screen.getByRole('button', { name: 'Session actions' })
  trigger.focus()
  fireEvent.click(trigger)
  const menu = await screen.findByRole('menu', { name: 'Session actions' })
  return { trigger, menu }
}

test('destructive items come last, after a line', async () => {
  render(
    <DropdownMenu label="Session actions" items={items(() => {})}>
      More
    </DropdownMenu>,
  )
  const { trigger, menu } = await openMenu()
  expect(trigger.getAttribute('aria-expanded')).toBe('true')
  expect(trigger.getAttribute('aria-haspopup')).toBe('menu')
  const children = [...menu.children]
  expect(children.map((child) => child.getAttribute('role'))).toEqual([
    'menuitem',
    'menuitem',
    'separator',
    'menuitem',
  ])
  const last = children[3]
  expect(last.textContent).toBe('xDelete session')
  expect(last.classList.contains('is-destructive')).toBe(true)
})

test('arrow keys move between rows and Escape returns focus', async () => {
  render(
    <DropdownMenu label="Session actions" items={items(() => {})}>
      More
    </DropdownMenu>,
  )
  const { trigger, menu } = await openMenu()
  const rows = screen.getAllByRole('menuitem')
  await waitFor(() => {
    expect(document.activeElement).toBe(rows[0])
  })

  fireEvent.keyDown(menu, { key: 'ArrowDown' })
  expect(document.activeElement).toBe(rows[1])
  fireEvent.keyDown(menu, { key: 'ArrowDown' })
  expect(document.activeElement).toBe(rows[2])
  fireEvent.keyDown(menu, { key: 'ArrowDown' })
  expect(document.activeElement).toBe(rows[0])
  fireEvent.keyDown(menu, { key: 'ArrowUp' })
  expect(document.activeElement).toBe(rows[2])
  fireEvent.keyDown(menu, { key: 'Home' })
  expect(document.activeElement).toBe(rows[0])
  fireEvent.keyDown(menu, { key: 'End' })
  expect(document.activeElement).toBe(rows[2])

  fireEvent.keyDown(menu, { key: 'Escape' })
  expect(document.activeElement).toBe(trigger)
  expect(trigger.getAttribute('aria-expanded')).toBe('false')
  await waitFor(() => {
    expect(screen.queryByRole('menu')).toBeNull()
  })
})

test('choosing a row runs it, closes, and returns focus', async () => {
  const onSelect = vi.fn()
  render(
    <DropdownMenu label="Session actions" items={items(onSelect)}>
      More
    </DropdownMenu>,
  )
  const { trigger } = await openMenu()
  fireEvent.click(screen.getByRole('menuitem', { name: 'Rename' }))
  expect(onSelect).toHaveBeenCalledWith('rename')
  expect(document.activeElement).toBe(trigger)
  await waitFor(() => {
    expect(screen.queryByRole('menu')).toBeNull()
  })
})

test('a tap outside closes the menu without choosing', async () => {
  const onSelect = vi.fn()
  render(
    <DropdownMenu label="Session actions" items={items(onSelect)}>
      More
    </DropdownMenu>,
  )
  await openMenu()
  fireEvent.pointerDown(document.body)
  await waitFor(() => {
    expect(screen.queryByRole('menu')).toBeNull()
  })
  expect(onSelect).not.toHaveBeenCalled()
})
