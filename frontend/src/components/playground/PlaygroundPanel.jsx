import { useState } from 'react'
import { Play } from 'lucide-react'
import DropZone from '../upload/DropZone'
import FilePreview from '../upload/FilePreview'
import Button from '../ui/Button'
import { AVAILABLE_MODELS } from '../../api/models'

export default function PlaygroundPanel({ onRun, loading }) {
  const [file, setFile] = useState(null)
  const [modelId, setModelId] = useState(AVAILABLE_MODELS[0].id)

  const handleFiles = (files) => {
    if (files.length > 0) setFile(files[0])
  }

  const handleRun = () => {
    if (file) onRun(file, modelId)
  }

  return (
    <div className="space-y-5">
      <div>
        <label className="mb-1.5 block text-sm font-medium text-ink">Model</label>
        <select
          value={modelId}
          onChange={(e) => setModelId(e.target.value)}
          className="w-full rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
        >
          {AVAILABLE_MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.providerLabel})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-ink">Document</label>
        {file ? (
          <FilePreview file={file} index={0} onRemove={() => setFile(null)} />
        ) : (
          <DropZone onFiles={handleFiles} className="py-8" />
        )}
      </div>

      <Button onClick={handleRun} disabled={!file} loading={loading} className="w-full">
        <Play className="h-4 w-4" />
        Run
      </Button>
    </div>
  )
}
