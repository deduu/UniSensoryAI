import { useState } from 'react'
import { Copy, Download, Check } from 'lucide-react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

export default function ContentViewer({ doc, open, onClose }) {
  const [copied, setCopied] = useState(false)

  if (!doc) return null

  const content = doc.content_text || 'No content available'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${doc.filename || 'document'}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Modal open={open} onClose={onClose} title={doc.filename || 'Document Content'} wide>
      <div className="flex gap-2 mb-4">
        <Button variant="secondary" onClick={handleCopy}>
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
        <Button variant="secondary" onClick={handleDownload}>
          <Download className="h-4 w-4" />
          Download
        </Button>
      </div>
      <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border border-surface-border bg-surface-subtle p-4 font-mono text-sm leading-relaxed text-ink">
        {content}
      </pre>
    </Modal>
  )
}
