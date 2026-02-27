import { useEffect, useState } from 'react'
import Tabs from '../components/ui/Tabs'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useApp } from '../context/AppContext'
import { checkHealth } from '../api/health'
import { AVAILABLE_MODELS } from '../api/models'

function ConnectionTab() {
  const { backendUrl, setBackendUrl } = useApp()
  const [url, setUrl] = useState(backendUrl)
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState(null)

  const handleTest = async () => {
    setTesting(true)
    setResult(null)
    const res = await checkHealth(url)
    setResult(res)
    setTesting(false)
  }

  const handleSave = () => {
    setBackendUrl(url)
  }

  return (
    <Card className="max-w-xl p-6">
      <h3 className="text-sm font-semibold text-ink">Backend URL</h3>
      <p className="mt-1 text-xs text-ink-muted">
        The FastAPI backend server URL. Leave empty to use the Vite proxy (recommended for local dev).
      </p>

      <div className="mt-4 flex gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="http://localhost:8010 (leave empty for proxy)"
          className="flex-1 rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
        />
        <Button variant="secondary" onClick={handleTest} loading={testing}>
          Test
        </Button>
        <Button onClick={handleSave}>Save</Button>
      </div>

      {result && (
        <div
          className={`mt-4 rounded-lg p-4 ${
            result.healthy
              ? 'border border-emerald-200 bg-emerald-50'
              : 'border border-red-200 bg-red-50'
          }`}
        >
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                result.healthy ? 'bg-emerald-500' : 'bg-red-500'
              }`}
            />
            <span
              className={`text-sm font-medium ${
                result.healthy ? 'text-emerald-700' : 'text-red-700'
              }`}
            >
              {result.healthy ? 'Healthy' : 'Connection Failed'}
            </span>
          </div>
          {result.latency && (
            <p className="mt-1 text-xs text-ink-muted">Latency: {result.latency}ms</p>
          )}
          {result.error && <p className="mt-1 text-xs text-red-600">{result.error}</p>}
        </div>
      )}
    </Card>
  )
}

function AboutTab() {
  return (
    <Card className="max-w-xl p-6">
      <h3 className="text-sm font-semibold text-ink">UniSensoryAI</h3>
      <p className="mt-1 text-sm text-ink-muted">
        Multi-modal AI agent system for document perception and understanding.
      </p>

      <div className="mt-4 space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-ink-muted">Version</span>
          <span className="font-medium text-ink">0.1.0</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-ink-muted">Available Models</span>
          <span className="font-medium text-ink">{AVAILABLE_MODELS.length}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-ink-muted">Frontend</span>
          <span className="font-medium text-ink">React + Vite + Tailwind</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-ink-muted">Backend</span>
          <span className="font-medium text-ink">FastAPI + PyTorch</span>
        </div>
      </div>
    </Card>
  )
}

export default function Settings() {
  useEffect(() => {
    document.title = 'Settings — UniSensoryAI'
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold text-ink">Settings</h1>
      <p className="mt-1 text-sm text-ink-muted">Configure your UniSensoryAI instance</p>

      <Tabs
        className="mt-6"
        tabs={[
          { key: 'connection', label: 'Connection', content: <ConnectionTab /> },
          { key: 'about', label: 'About', content: <AboutTab /> },
        ]}
      />
    </div>
  )
}
