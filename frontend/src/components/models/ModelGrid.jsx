import ModelCard from './ModelCard'
import EmptyState from '../ui/EmptyState'
import { Cpu } from 'lucide-react'

export default function ModelGrid({ models }) {
  if (models.length === 0) {
    return (
      <EmptyState
        icon={Cpu}
        heading="No models found"
        subtext="No models match the current filter"
      />
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {models.map((model) => (
        <ModelCard key={model.id} model={model} />
      ))}
    </div>
  )
}
