import { useState } from 'react'

export default function Tabs({ tabs, defaultTab, className = '' }) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.key)

  const currentTab = tabs.find((t) => t.key === active)

  return (
    <div className={className}>
      <div className="flex gap-1 border-b border-surface-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActive(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              active === tab.key
                ? 'border-b-2 border-brand text-brand'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-4">{currentTab?.content}</div>
    </div>
  )
}
