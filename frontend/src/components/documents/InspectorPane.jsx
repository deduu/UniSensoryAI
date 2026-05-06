import { useState } from 'react'
import {
  X,
  Minus,
  Maximize2,
  Minimize2,
  Copy,
  Download,
  MessageSquare,
  Check,
  PanelRight,
  PanelBottom,
  Clock,
  Tag,
  Hash,
  Cpu,
  FileText,
  Layers,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const TABS = [
  { key: 'content', label: 'Content' },
  { key: 'metadata', label: 'Metadata' },
  { key: 'raw', label: 'Raw' },
]

function ContentTab({ doc }) {
  const [copied, setCopied] = useState(false)
  const content = doc.content_text || 'No content available'
  const lines = content.split('\n')

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-surface-border">
        <span className="text-xs text-ink-faint">
          {lines.length} lines · {content.length.toLocaleString()} chars
        </span>
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="flex-1 overflow-auto p-0">
        <div className="flex text-xs font-mono leading-6">
          {/* Line numbers */}
          <div className="sticky left-0 shrink-0 select-none border-r border-surface-border bg-surface-muted/50 px-3 text-right text-ink-faint">
            {lines.map((_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>
          {/* Content */}
          <pre className="flex-1 whitespace-pre-wrap break-words p-3 text-ink leading-6">
            {content}
          </pre>
        </div>
      </div>
    </div>
  )
}

function MetadataTab({ doc }) {
  const fields = [
    { icon: Hash, label: 'Document ID', value: doc.id || '—' },
    { icon: Hash, label: 'Job ID', value: doc.job_id || '—' },
    { icon: FileText, label: 'Filename', value: doc.filename || '—' },
    { icon: Tag, label: 'Status', value: doc.job_status || '—' },
    { icon: Cpu, label: 'Model', value: doc.model_id || '—' },
    { icon: Layers, label: 'Pages', value: doc.page_count || doc.pages || '—' },
    {
      icon: Clock,
      label: 'Created',
      value: doc.created_at ? new Date(doc.created_at).toLocaleString() : '—',
    },
    {
      icon: Clock,
      label: 'Updated',
      value: doc.updated_at ? new Date(doc.updated_at).toLocaleString() : '—',
    },
  ]

  return (
    <div className="p-4 space-y-1">
      {fields.map(({ icon: Icon, label, value }) => (
        <div
          key={label}
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-surface-subtle"
        >
          <Icon className="h-4 w-4 shrink-0 text-ink-faint" />
          <span className="w-24 shrink-0 text-xs font-medium uppercase tracking-wider text-ink-faint">
            {label}
          </span>
          <span className="text-sm text-ink truncate font-mono">{String(value)}</span>
        </div>
      ))}
    </div>
  )
}

function RawTab({ doc }) {
  const [copied, setCopied] = useState(false)
  const raw = JSON.stringify(doc, null, 2)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(raw)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-end px-4 py-2 border-b border-surface-border">
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy JSON'}
        </button>
      </div>
      <pre className="flex-1 overflow-auto p-4 font-mono text-xs text-ink-muted leading-6 whitespace-pre-wrap break-words">
        {raw}
      </pre>
    </div>
  )
}

export default function InspectorPane({
  doc,
  isOpen,
  isMinimized,
  isMaximized,
  dockPosition,
  paneWidth,
  paneHeight,
  onClose,
  onMinimize,
  onMaximize,
  onRestore,
  onDragStart,
  onToggleDock,
  isDragging,
}) {
  const [activeTab, setActiveTab] = useState('content')
  const navigate = useNavigate()

  if (!isOpen || !doc) return null

  const handleDownload = () => {
    const content = doc.content_text || ''
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${doc.filename || 'document'}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleOpenChat = () => {
    navigate('/chat', { state: { groundingDoc: doc } })
  }

  const isRight = dockPosition === 'right'

  // Compute pane style
  const paneStyle = {}
  if (isMaximized) {
    if (isRight) {
      paneStyle.width = '70%'
    } else {
      paneStyle.height = '70%'
    }
  } else if (!isMinimized) {
    if (isRight) {
      paneStyle.width = `${paneWidth}px`
    } else {
      paneStyle.height = `${paneHeight}px`
    }
  }

  // Minimized state: show a thin collapsed bar
  if (isMinimized) {
    return (
      <div
        className={`inspector-pane flex items-center border-surface-border ${
          isRight
            ? 'border-l w-10 flex-col py-4 gap-3'
            : 'border-t h-10 flex-row px-4 gap-3'
        }`}
      >
        <button
          onClick={onRestore}
          className="rounded-md p-1 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          title="Restore pane"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div
      className={`inspector-pane relative flex flex-col shrink-0 ${
        isRight
          ? 'border-l animate-slide-in-right'
          : 'border-t animate-slide-up-panel inspector-pane-bottom'
      }`}
      style={paneStyle}
    >
      {/* Drag Handle */}
      <div
        onMouseDown={onDragStart}
        className={`resize-handle ${isRight ? 'resize-handle-h' : 'resize-handle-v'} ${
          isDragging ? 'is-dragging' : ''
        }`}
      />

      {/* Header */}
      <div className="flex items-center justify-between border-b border-surface-border px-4 py-2.5 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 shrink-0 text-brand" />
          <h3 className="text-sm font-semibold text-ink truncate">
            {doc.filename || 'Untitled'}
          </h3>
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          {/* Minimize */}
          <button
            onClick={onMinimize}
            className="rounded-md p-1 text-ink-faint transition-colors hover:bg-surface-subtle hover:text-ink"
            title="Minimize"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          {/* Maximize / Restore */}
          <button
            onClick={isMaximized ? onRestore : onMaximize}
            className="rounded-md p-1 text-ink-faint transition-colors hover:bg-surface-subtle hover:text-ink"
            title={isMaximized ? 'Restore' : 'Maximize'}
          >
            {isMaximized ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </button>
          {/* Close */}
          <button
            onClick={onClose}
            className="rounded-md p-1 text-ink-faint transition-colors hover:bg-surface-subtle hover:text-ink"
            title="Close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-surface-border shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? 'border-b-2 border-brand text-brand'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'content' && <ContentTab doc={doc} />}
        {activeTab === 'metadata' && <MetadataTab doc={doc} />}
        {activeTab === 'raw' && <RawTab doc={doc} />}
      </div>

      {/* Action Bar */}
      <div className="flex items-center gap-2 border-t border-surface-border px-4 py-2.5 shrink-0">
        <button
          onClick={handleDownload}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        >
          <Download className="h-3.5 w-3.5" />
          Download
        </button>
        <button
          onClick={handleOpenChat}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand transition-colors hover:bg-brand/20"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Chat
        </button>
      </div>
    </div>
  )
}
