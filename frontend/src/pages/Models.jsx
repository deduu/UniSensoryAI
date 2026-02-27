import { useEffect, useState } from 'react'
import ModelGrid from '../components/models/ModelGrid'
import { AVAILABLE_MODELS } from '../api/models'

const TYPE_TABS = [
  { key: 'all', label: 'All' },
  { key: 'local', label: 'Local' },
  { key: 'cloud', label: 'Cloud' },
]

export default function Models() {
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    document.title = 'Models — UniSensoryAI'
  }, [])

  const filtered =
    filter === 'all'
      ? AVAILABLE_MODELS
      : AVAILABLE_MODELS.filter((m) => m.type === filter)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Models</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Available vision-language models for document processing
        </p>
      </div>

      <div className="flex gap-1">
        {TYPE_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              filter === tab.key
                ? 'bg-brand text-white'
                : 'text-ink-muted hover:bg-surface-subtle'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <ModelGrid models={filtered} />
    </div>
  )
}
