import { useId, useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

export type TabItem<Id extends string> = {
  id: Id
  label: string
}

type TabsProps<Id extends string> = {
  label: string
  tabs: TabItem<Id>[]
  selected: Id
  onSelect: (id: Id) => void
  children: ReactNode
}

/**
 * Underline tabs (DESIGN.md section 7, Tabs). ARIA tabs pattern with
 * automatic activation: arrow keys, Home, and End move and select.
 * Only the selected panel's content is rendered. Tabs never animate (8.3).
 */
export function Tabs<Id extends string>({
  label,
  tabs,
  selected,
  onSelect,
  children,
}: TabsProps<Id>) {
  const prefix = useId()
  const buttons = useRef(new Map<Id, HTMLButtonElement>())

  function move(event: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((tab) => tab.id === selected)
    let next = index
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length
    else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = tabs.length - 1
    else return
    event.preventDefault()
    const id = tabs[next].id
    onSelect(id)
    buttons.current.get(id)?.focus()
  }

  return (
    <div className="tabs">
      <div className="tabs-list" role="tablist" aria-label={label} onKeyDown={move}>
        {tabs.map((tab) => {
          const isSelected = tab.id === selected
          return (
            <button
              key={tab.id}
              ref={(node) => {
                if (node) buttons.current.set(tab.id, node)
                else buttons.current.delete(tab.id)
              }}
              type="button"
              role="tab"
              id={`${prefix}-tab-${tab.id}`}
              className="tabs-tab"
              aria-selected={isSelected}
              aria-controls={`${prefix}-panel-${tab.id}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => onSelect(tab.id)}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      {tabs.map((tab) => {
        const isSelected = tab.id === selected
        return (
          <div
            key={tab.id}
            role="tabpanel"
            id={`${prefix}-panel-${tab.id}`}
            className="tabs-panel"
            aria-labelledby={`${prefix}-tab-${tab.id}`}
            tabIndex={0}
            hidden={!isSelected}
          >
            {isSelected ? children : null}
          </div>
        )
      })}
    </div>
  )
}
