import { useEffect, useState } from 'react'
import { MessageSquare, Send, Plus } from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'

export default function Chat() {
  const [message, setMessage] = useState('')
  const [toast, setToast] = useState(false)

  useEffect(() => {
    document.title = 'Chat — UniSensoryAI'
  }, [])

  const handleSend = () => {
    if (!message.trim()) return
    setToast(true)
    setMessage('')
    setTimeout(() => setToast(false), 3000)
  }

  return (
    <div className="flex h-[calc(100vh-12rem)] gap-6">
      {/* Conversation sidebar */}
      <Card className="w-72 shrink-0 flex flex-col">
        <div className="border-b border-surface-border p-4">
          <Button variant="secondary" className="w-full">
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <div className="rounded-lg bg-surface-subtle p-3">
            <p className="text-sm font-medium text-ink">New conversation</p>
            <p className="mt-0.5 text-xs text-ink-muted">Just now</p>
          </div>
        </div>
      </Card>

      {/* Chat area */}
      <Card className="flex flex-1 flex-col">
        {/* Messages */}
        <div className="flex flex-1 flex-col items-center justify-center p-8">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-light">
            <MessageSquare className="h-8 w-8 text-brand" />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-ink">Chat with your documents</h2>
          <p className="mt-1 max-w-sm text-center text-sm text-ink-muted">
            Ask questions about your processed documents using natural language.
            This feature is coming soon.
          </p>
        </div>

        {/* Input */}
        <div className="border-t border-surface-border p-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about your documents..."
              className="flex-1 rounded-lg border border-surface-border bg-white px-4 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
            />
            <Button onClick={handleSend}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Toast */}
        {toast && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 animate-fade-in rounded-lg bg-ink px-4 py-2 text-sm text-white shadow-lg">
            Coming soon — chat backend not yet available
          </div>
        )}
      </Card>
    </div>
  )
}
