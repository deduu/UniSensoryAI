import { useState } from 'react'
import { ChevronDown, Brain, Zap, Thermometer, Cloud, HardDrive } from 'lucide-react'
import { AVAILABLE_MODELS } from '../../api/models'

export default function ChatToolbar({
  modelId,
  setModelId,
  thinkingEnabled,
  setThinkingEnabled,
  streamingEnabled,
  setStreamingEnabled,
  temperature,
  setTemperature,
  apiKeys = {},
}) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [tempDropdownOpen, setTempDropdownOpen] = useState(false)

  const selectedModel = AVAILABLE_MODELS.find((m) => m.id === modelId) || AVAILABLE_MODELS[0]

  const isModelReady = (model) => {
    if (model.type === 'local') return false
    if (model.provider === 'openai') return !!apiKeys.OPENAI_API_KEY
    if (model.provider === 'google') return !!apiKeys.GOOGLE_API_KEY
    return false
  }

  const tempPresets = [
    { label: 'Precise', value: 0.1, icon: '🎯' },
    { label: 'Balanced', value: 0.7, icon: '⚖️' },
    { label: 'Creative', value: 1.0, icon: '✨' },
  ]

  const currentPreset = tempPresets.find((p) => Math.abs(p.value - temperature) < 0.05)

  return (
    <div className="flex items-center gap-2 border-b border-surface-border/50 bg-surface/20 backdrop-blur-sm px-4 py-2.5 overflow-x-auto">
      {/* Model Selector */}
      <div className="relative">
        <button
          onClick={() => { setModelDropdownOpen(!modelDropdownOpen); setTempDropdownOpen(false) }}
          className="flex items-center gap-2 rounded-xl border border-surface-border bg-surface-muted/50 px-3 py-1.5 text-xs font-medium text-ink 
                     hover:border-brand/30 hover:bg-surface-subtle transition-all duration-200"
        >
          {selectedModel.type === 'cloud' ? (
            <Cloud className="h-3.5 w-3.5 text-cyan-400" />
          ) : (
            <HardDrive className="h-3.5 w-3.5 text-ink-muted" />
          )}
          <span className="max-w-[120px] truncate">{selectedModel.name}</span>
          <ChevronDown className="h-3 w-3 text-ink-muted" />
        </button>

        {modelDropdownOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setModelDropdownOpen(false)} />
            <div className="absolute top-full left-0 mt-1 z-50 w-80 rounded-xl border border-surface-border bg-surface-muted/95 backdrop-blur-xl shadow-modal animate-fade-in overflow-hidden">
              <div className="px-3 py-2 border-b border-surface-border/50">
                <span className="text-[11px] font-medium text-ink-faint uppercase tracking-wider">Select Model</span>
              </div>
              <div className="max-h-64 overflow-y-auto p-1.5">
                {AVAILABLE_MODELS.map((model) => {
                  const ready = isModelReady(model)
                  return (
                    <button
                      key={model.id}
                      onClick={() => {
                        if (ready) {
                          setModelId(model.id)
                          setModelDropdownOpen(false)
                        }
                      }}
                      disabled={!ready}
                      className={`w-full flex items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-all duration-150
                        ${model.id === modelId ? 'bg-brand/15 border border-brand/30' : 'hover:bg-surface-subtle border border-transparent'}
                        ${!ready ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                    >
                      <div className="shrink-0 mt-0.5">
                        {model.type === 'cloud' ? (
                          <Cloud className="h-4 w-4 text-cyan-400" />
                        ) : (
                          <HardDrive className="h-4 w-4 text-ink-faint" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-ink truncate">{model.name}</span>
                          {ready && (
                            <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-emerald-400" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] text-ink-faint">{model.providerLabel}</span>
                          <span className="text-[10px] text-ink-faint">·</span>
                          <span className="text-[10px] text-ink-faint">{model.params}</span>
                        </div>
                        {!ready && model.type === 'local' && (
                          <span className="text-[10px] text-amber-500/80 mt-0.5 block">Requires backend</span>
                        )}
                        {!ready && model.type === 'cloud' && (
                          <span className="text-[10px] text-amber-500/80 mt-0.5 block">API key not configured</span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Divider */}
      <div className="h-5 w-px bg-surface-border/50 shrink-0" />

      {/* Thinking Toggle */}
      <button
        onClick={() => setThinkingEnabled(!thinkingEnabled)}
        className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-all duration-200 border
          ${thinkingEnabled
            ? 'bg-purple-500/15 text-purple-400 border-purple-500/30 shadow-[0_0_8px_rgba(168,85,247,0.15)]'
            : 'bg-surface-muted/50 text-ink-muted border-surface-border hover:border-brand/30 hover:text-ink'
          }`}
        title="Toggle thinking mode — model shows reasoning steps"
      >
        <Brain className={`h-3.5 w-3.5 ${thinkingEnabled ? 'animate-pulse' : ''}`} />
        <span className="hidden sm:inline">Thinking</span>
      </button>

      {/* Stream Toggle */}
      <button
        onClick={() => setStreamingEnabled(!streamingEnabled)}
        className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-all duration-200 border
          ${streamingEnabled
            ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30 shadow-[0_0_8px_rgba(34,211,238,0.15)]'
            : 'bg-surface-muted/50 text-ink-muted border-surface-border hover:border-brand/30 hover:text-ink'
          }`}
        title="Toggle streaming responses"
      >
        <Zap className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Stream</span>
      </button>

      {/* Temperature */}
      <div className="relative">
        <button
          onClick={() => { setTempDropdownOpen(!tempDropdownOpen); setModelDropdownOpen(false) }}
          className="flex items-center gap-1.5 rounded-xl border border-surface-border bg-surface-muted/50 px-3 py-1.5 text-xs font-medium text-ink-muted
                     hover:border-brand/30 hover:text-ink transition-all duration-200"
          title="Temperature"
        >
          <Thermometer className="h-3.5 w-3.5" />
          <span>{currentPreset ? currentPreset.icon + ' ' + currentPreset.label : temperature.toFixed(1)}</span>
        </button>

        {tempDropdownOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setTempDropdownOpen(false)} />
            <div className="absolute top-full right-0 mt-1 z-50 w-56 rounded-xl border border-surface-border bg-surface-muted/95 backdrop-blur-xl shadow-modal animate-fade-in overflow-hidden">
              <div className="px-3 py-2 border-b border-surface-border/50">
                <span className="text-[11px] font-medium text-ink-faint uppercase tracking-wider">Temperature</span>
              </div>
              <div className="p-3 space-y-3">
                {tempPresets.map((preset) => (
                  <button
                    key={preset.label}
                    onClick={() => {
                      setTemperature(preset.value)
                      setTempDropdownOpen(false)
                    }}
                    className={`w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-all duration-150
                      ${Math.abs(temperature - preset.value) < 0.05 ? 'bg-brand/15 border border-brand/30' : 'hover:bg-surface-subtle border border-transparent'}`}
                  >
                    <span className="text-sm">{preset.icon}</span>
                    <div>
                      <span className="text-xs font-medium text-ink">{preset.label}</span>
                      <span className="text-[10px] text-ink-faint ml-2">{preset.value}</span>
                    </div>
                  </button>
                ))}
                <div className="pt-2 border-t border-surface-border/50">
                  <label className="text-[11px] text-ink-faint block mb-1.5">Custom: {temperature.toFixed(2)}</label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full accent-brand h-1"
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
